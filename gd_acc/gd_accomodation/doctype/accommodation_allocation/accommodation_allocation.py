# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from gd_acc.gd_accomodation import item_balance
from gd_acc.gd_accomodation.accommodation_utils import (
	CURRENT_STAY_STATUSES,
	GENDER_ANY,
	HOLDER_FIELDS,
	get_active_allocation,
	occupy_bed,
	release_bed,
	refresh_stay_status,
	resolve_hierarchy,
	site_requires_bed,
	validate_placement,
)
from gd_acc.gd_accomodation.doctype.accommodation_item_entry.accommodation_item_entry import (
	create_item_entry,
)

RELEASE_REASONS = ("Transfer", "Employee Exit", "Accommodation Status Change", "Manual Release", "Other")


class AccommodationAllocation(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"

		self.validate_dates()
		self.apply_hierarchy()
		self.validate_bed_requirement()
		self.validate_items()

		if self.docstatus == 1:
			self.validate_employee_has_no_active_allocation()
			validate_placement(
				employee=self.employee_name or self.employee,
				employee_id=self.employee,
				company=self.company,
				location=self.location,
				site=self.site,
				floor=self.floor,
				room=self.room,
				bed=self.bed,
				start_date=self.start_date,
				end_date=self.expected_end_date,
				exclude=self.name,
			)

	def validate_dates(self):
		if self.expected_end_date and getdate(self.expected_end_date) < getdate(self.start_date):
			frappe.throw(_("Expected End Date cannot be before Start Date."), title=_("Invalid Dates"))

		if self.release_date and getdate(self.release_date) < getdate(self.start_date):
			frappe.throw(_("Release Date cannot be before Start Date."), title=_("Invalid Dates"))

	def apply_hierarchy(self):
		resolved = resolve_hierarchy(
			location=self.location,
			site=self.site,
			floor=self.floor,
			room=self.room,
			bed=self.bed,
		)
		self.location = resolved["location"]
		self.site = resolved["site"]
		self.floor = resolved["floor"]
		self.room = resolved["room"]

	def validate_bed_requirement(self):
		self.bed_required = 1 if site_requires_bed(self.site) else 0

		if self.bed_required and not self.bed:
			frappe.throw(
				_("Site {0} uses bed level allocation, so a Bed is required.").format(frappe.bold(self.site)),
				title=_("Bed Required"),
			)

	def validate_items(self):
		"""Check the Items table of a Draft and preview its summary.

		After submit, only item_balance.refresh_allocation_summary writes the summary.
		"""
		if self.docstatus != 0:
			return

		items = {
			row.name: row
			for row in frappe.get_all(
				"Accommodation Item",
				filters={"name": ["in", list({row.accommodation_item for row in self.items})]},
				fields=["name", "disabled", "is_returnable"],
				limit=0,
			)
		}
		seen = {}
		total = 0
		returnable_total = 0
		has_returnable = False

		for row in self.items:
			row.quantity = item_balance.to_quantity(row.quantity, _("Row #{0}: Qty").format(row.idx))
			item = items.get(row.accommodation_item)

			if not item:
				frappe.throw(
					_("Row #{0}: Item {1} does not exist.").format(row.idx, frappe.bold(row.accommodation_item)),
					title=_("Invalid Item"),
				)
			if item.disabled:
				frappe.throw(
					_("Row #{0}: Item {1} is disabled.").format(row.idx, frappe.bold(row.accommodation_item)),
					title=_("Disabled Item"),
				)
			if row.accommodation_item in seen:
				frappe.throw(
					_(
						"Row #{0}: {1} is already listed in row #{2}. "
						"Combine them into one row with a higher quantity."
					).format(row.idx, frappe.bold(row.accommodation_item), seen[row.accommodation_item]),
					title=_("Duplicate Item"),
				)

			seen[row.accommodation_item] = row.idx
			total += row.quantity
			if item.is_returnable:
				has_returnable = True
				returnable_total += row.quantity

		self.item_entry = None
		self.total_items = total
		self.outstanding_items = returnable_total
		self.items_status = item_balance.get_items_status(has_returnable, returnable_total)

	def validate_employee_has_no_active_allocation(self):
		existing = get_active_allocation(self.employee, exclude=self.name)
		if existing:
			frappe.throw(
				_(
					"{0} already has an active accommodation allocation {1}. "
					"Release it or use Accommodation Transfer to move the employee."
				).format(frappe.bold(self.employee_name or self.employee), frappe.bold(existing)),
				title=_("Active Allocation Exists"),
			)

	def on_submit(self):
		self.db_set("status", "Active")

		if self.bed:
			occupy_bed(
				self.bed,
				allocation=self.name,
				employee=self.employee,
				start_date=self.start_date,
				reason="Allocation",
			)

		if self.items:
			self.issue_items()

		refresh_stay_status(self.employee)

	def issue_items(self):
		"""Create and submit the Assign entry for the Items table, in this transaction."""
		name = create_item_entry(
			"Assign",
			lines=[
				{
					"accommodation_item": row.accommodation_item,
					"quantity": row.quantity,
					"condition": row.condition,
					"remarks": row.remarks,
				}
				for row in self.items
			],
			posting_date=self.start_date,
			employee=self.employee,
			allocation=self.name,
			holder={fieldname: self.get(fieldname) for fieldname in HOLDER_FIELDS},
			remarks=_("Issued with allocation {0}.").format(self.name),
			# The right to submit the allocation covers its Assign entry.
			ignore_permissions=True,
		)
		self.db_set("item_entry", name)
		self.update(
			frappe.db.get_value(
				self.doctype, self.name, ["total_items", "outstanding_items", "items_status"], as_dict=True
			)
		)

	def before_cancel(self):
		if self.released_by_transfer:
			frappe.throw(
				_("This allocation was closed by transfer {0}. Cancel that transfer instead.").format(
					frappe.bold(self.released_by_transfer)
				),
				title=_("Cancel Transfer First"),
			)

		if self.item_entry:
			returns = item_balance.has_active_returns(self.item_entry)
			if returns:
				frappe.throw(
					_(
						"Items issued with this allocation were already returned. "
						"Cancel those Return entries first: {0}."
					).format(", ".join(returns[:5])),
					title=_("Returns Recorded"),
				)

	def on_cancel(self):
		self.cancel_item_entry()

		if self.status in CURRENT_STAY_STATUSES and self.bed:
			release_bed(
				self.bed,
				allocation=self.name,
				employee=self.employee,
				reason="Release",
				remarks=_("Allocation cancelled."),
			)

		self.db_set({"status": "Cancelled", "release_date": None, "release_reason": None})

		refresh_stay_status(self.employee)

	def cancel_item_entry(self):
		"""Cancel the Assign entry that this allocation created."""
		if not self.item_entry:
			return

		entry = frappe.get_doc("Accommodation Item Entry", self.item_entry)
		if entry.docstatus != 1:
			return

		entry.flags.from_allocation = True
		entry.flags.ignore_permissions = True
		entry.cancel()

	def release(
		self,
		release_date=None,
		reason="Manual Release",
		transfer=None,
		remarks=None,
		item_returns=None,
		request_id=None,
	):
		"""Close this allocation and free the bed without touching history.

		The allocation row itself is kept exactly as it was apart from the
		closing fields, so the stay remains fully auditable. `item_returns`
		records the items handed back at release as one Return entry.
		"""
		# Lock the row, so a second concurrent release waits and then fails.
		info = frappe.db.get_value(
			self.doctype, self.name, ["docstatus", "status"], as_dict=True, for_update=True
		)
		if not info or info.docstatus != 1 or info.status not in CURRENT_STAY_STATUSES:
			frappe.throw(
				_("Only an active or pending release allocation can be released. {0} is {1}.").format(
					frappe.bold(self.name), frappe.bold(info.status if info else _("missing"))
				),
				title=_("Not Active"),
			)

		release_date = getdate(release_date or today())
		if release_date < getdate(self.start_date):
			frappe.throw(_("Release Date cannot be before Start Date."), title=_("Invalid Dates"))

		if reason not in RELEASE_REASONS:
			reason = "Other"

		self.db_set(
			{
				"status": "Closed",
				"release_date": release_date,
				"release_reason": reason,
				"released_by_transfer": transfer,
			}
		)

		if self.bed:
			release_bed(
				self.bed,
				allocation=self.name,
				employee=self.employee,
				reason="Transfer Out" if transfer else "Release",
				transfer=transfer,
				remarks=remarks,
			)

		refresh_stay_status(self.employee)

		if item_returns:
			self.return_items(item_returns, release_date, request_id=request_id, remarks=remarks)

		if not transfer:
			self.warn_outstanding_items()

	def return_items(self, item_returns, posting_date, request_id=None, remarks=None):
		lines = get_return_lines_from_dialog(item_returns)
		if not lines:
			return

		create_item_entry(
			"Return",
			lines,
			posting_date,
			employee=self.employee,
			allocation=self.name,
			request_id=request_id,
			remarks=remarks,
			holder={fieldname: self.get(fieldname) for fieldname in HOLDER_FIELDS},
		)

	def warn_outstanding_items(self):
		outstanding = sum(
			line.outstanding_quantity for line in item_balance.get_outstanding_lines(employee=self.employee)
		)
		if outstanding > 0:
			frappe.msgprint(
				_("{0} item(s) are still outstanding for {1}. Use Return Items when they come back.").format(
					outstanding, frappe.bold(self.employee_name or self.employee)
				),
				indicator="orange",
			)


def get_return_lines_from_dialog(item_returns):
	"""Turn release dialog rows into Return lines, one line per non-zero return type."""
	if not isinstance(item_returns, list):
		frappe.throw(_("Item returns must be a list."), title=_("Invalid Item Returns"))

	lines = []
	for position, row in enumerate(item_returns, start=1):
		if not isinstance(row, dict) or not row.get("against_entry") or not row.get("against_detail"):
			frappe.throw(
				_("Item return #{0} does not name the assigned line.").format(position),
				title=_("Invalid Item Returns"),
			)

		for return_type, fieldname in item_balance.BALANCE_FIELDS.items():
			label = _("Item return #{0} ({1}): {2}").format(
				position, row.get("accommodation_item"), frappe.unscrub(fieldname)
			)
			quantity = item_balance.to_quantity(row.get(fieldname) or 0, label, minimum=0)
			if quantity:
				lines.append(
					{
						"accommodation_item": row.get("accommodation_item"),
						"return_type": return_type,
						"quantity": quantity,
						"against_entry": row["against_entry"],
						"against_detail": row["against_detail"],
					}
				)

	return lines


@frappe.whitelist()
def release_allocation(
	allocation, release_date=None, reason="Manual Release", remarks=None, item_returns=None, request_id=None
):
	"""Release an allocation from the desk.

	Used both by the Accommodation Allocation form's own Release button and by
	the Employee tab's Release Accommodation action. The entitlement stays as it
	is; its Stay Status becomes Vacated. A repeated request with the same
	request_id does nothing.
	"""
	if request_id and frappe.db.exists("Accommodation Item Entry", {"request_id": request_id}):
		return allocation

	if isinstance(item_returns, str):
		item_returns = frappe.parse_json(item_returns)

	doc = frappe.get_doc("Accommodation Allocation", allocation)
	doc.check_permission("submit")
	doc.release(
		release_date=release_date,
		reason=reason,
		remarks=remarks,
		item_returns=item_returns,
		request_id=request_id,
	)
	return doc.name


@frappe.whitelist()
def get_release_lines(allocation):
	"""Return the employee's outstanding Assign lines, this allocation's lines first."""
	doc = frappe.get_doc("Accommodation Allocation", allocation)
	doc.check_permission("read")

	lines = item_balance.get_outstanding_lines(employee=doc.employee)
	return sorted(lines, key=lambda line: (line.allocation != doc.name, line.posting_date, line.against_entry))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_allocatable_beds(doctype, txt, searchfield, start, page_len, filters):
	"""Link query listing only free beds, with the bed type shown beside each.

	Lets whoever is assigning see at a glance whether they are giving out a
	single bed, a bunk lower or a bunk upper.
	"""
	frappe.has_permission("Accommodation Bed", "read", throw=True)

	conditions = {"status": "Available"}
	for key in ("room", "floor", "site", "location"):
		if filters and filters.get(key):
			conditions[key] = filters[key]

	# Old callers send no gender key and get no gender filter.
	if filters and "gender" in filters:
		gender = filters.get("gender")
		conditions["gender_restriction"] = ("in", (GENDER_ANY, gender)) if gender else GENDER_ANY

	if txt:
		conditions["name"] = ("like", f"%{txt}%")

	beds = frappe.get_all(
		"Accommodation Bed",
		filters=conditions,
		fields=["name", "bed_type"],
		limit_start=start,
		limit_page_length=page_len,
		order_by="name asc",
	)
	return [(bed.name, bed.bed_type or "") for bed in beds]
