# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from gd_acc.gd_accomodation import item_balance
from gd_acc.gd_accomodation.accommodation_utils import HOLDER_FIELDS, resolve_hierarchy
from gd_acc.gd_accomodation.item_balance import ENTRY_DOCTYPE, to_quantity

RETURN_FIELDS = ("return_type", "against_entry", "against_detail")


class AccommodationItemEntry(Document):
	def validate(self):
		self.apply_allocation()
		self.apply_hierarchy()
		self.validate_quantities()

		if self.purpose == "Return":
			self.validate_return_lines()
		else:
			self.validate_assign_lines()

		self.clear_balance_cache()
		self.validate_dates()

		if self.purpose == "Return":
			self.validate_return_quantities()

	def apply_allocation(self):
		if not self.allocation:
			return

		allocation = frappe.db.get_value(
			"Accommodation Allocation",
			self.allocation,
			["docstatus", "employee", *HOLDER_FIELDS],
			as_dict=True,
		)
		if not allocation or allocation.docstatus != 1:
			frappe.throw(
				_("Allocation {0} is not submitted.").format(frappe.bold(self.allocation)),
				title=_("Invalid Allocation"),
			)

		if not self.employee:
			self.employee = allocation.employee
		elif self.employee != allocation.employee:
			frappe.throw(
				_("Allocation {0} belongs to {1}, not to {2}.").format(
					frappe.bold(self.allocation), frappe.bold(allocation.employee), frappe.bold(self.employee)
				),
				title=_("Employee Mismatch"),
			)

		if not self.location:
			for fieldname in HOLDER_FIELDS:
				self.set(fieldname, allocation.get(fieldname))

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

	def validate_quantities(self):
		for line in self.items:
			line.quantity = to_quantity(line.quantity, _("Row #{0}: Qty").format(line.idx))

	def validate_assign_lines(self):
		items = {
			row.name: row
			for row in frappe.get_all(
				"Accommodation Item",
				filters={"name": ["in", list({line.accommodation_item for line in self.items})]},
				fields=["name", "disabled"],
				limit=0,
			)
		}
		seen = {}

		for line in self.items:
			item = items.get(line.accommodation_item)
			if not item:
				frappe.throw(
					_("Row #{0}: Item {1} does not exist.").format(line.idx, frappe.bold(line.accommodation_item)),
					title=_("Invalid Item"),
				)
			if item.disabled:
				frappe.throw(
					_("Row #{0}: Item {1} is disabled.").format(line.idx, frappe.bold(line.accommodation_item)),
					title=_("Disabled Item"),
				)
			if line.accommodation_item in seen:
				frappe.throw(
					_(
						"Row #{0}: {1} is already listed in row #{2}. "
						"Combine them into one row with a higher quantity."
					).format(line.idx, frappe.bold(line.accommodation_item), seen[line.accommodation_item]),
					title=_("Duplicate Item"),
				)

			seen[line.accommodation_item] = line.idx
			for fieldname in RETURN_FIELDS:
				line.set(fieldname, None)

	def validate_return_lines(self):
		assign_lines = item_balance.get_assign_lines(
			{line.against_entry for line in self.items if line.against_entry}
		)
		seen = {}

		for line in self.items:
			if not (line.return_type and line.against_entry and line.against_detail):
				frappe.throw(
					_("Row #{0}: Return Type and the assigned line are required on a Return entry.").format(
						line.idx
					),
					title=_("Missing Values"),
				)

			assign_line = assign_lines.get(line.against_detail)
			if not assign_line or assign_line.parent != line.against_entry:
				frappe.throw(
					_("Row #{0}: the assigned line is not a line of {1}.").format(
						line.idx, frappe.bold(line.against_entry)
					),
					title=_("Invalid Assign Line"),
				)

			line.accommodation_item = assign_line.accommodation_item
			line.is_returnable = assign_line.is_returnable
			line.item_category = frappe.db.get_value(
				"Accommodation Item", assign_line.accommodation_item, "item_category"
			)
			line.condition = None

			key = (line.against_detail, line.return_type)
			if key in seen:
				frappe.throw(
					_("Row #{0}: {1} as {2} is already in row #{3}. Combine the two rows.").format(
						line.idx, frappe.bold(line.accommodation_item), _(line.return_type), seen[key]
					),
					title=_("Duplicate Line"),
				)
			seen[key] = line.idx

	def clear_balance_cache(self):
		for line in self.items:
			for fieldname in item_balance.CACHE_FIELDS:
				line.set(fieldname, None if fieldname == "last_return_date" else 0)

		self.total_items = sum(line.quantity for line in self.items)
		self.outstanding_items = 0
		self.items_status = ""

	def validate_dates(self):
		if self.purpose == "Return":
			self.expected_return_date = None
			return

		if self.expected_return_date and getdate(self.expected_return_date) < getdate(self.posting_date):
			frappe.throw(
				_("Expected Return Date cannot be before the Date."),
				title=_("Invalid Dates"),
			)

	def validate_return_quantities(self):
		"""Early check without a lock. before_submit checks again under the lock."""
		balances = item_balance.get_balances({line.against_entry for line in self.items})
		requested = {}
		for line in self.items:
			requested[line.against_detail] = requested.get(line.against_detail, 0) + line.quantity

		for line in self.items:
			balance = balances.get(line.against_detail)
			outstanding = balance.outstanding_quantity if balance else 0
			if requested[line.against_detail] > outstanding:
				frappe.throw(
					_("Row #{0} ({1}): {2} returned, but only {3} is outstanding on {4}.").format(
						line.idx,
						frappe.bold(line.accommodation_item),
						requested[line.against_detail],
						outstanding,
						frappe.bold(line.against_entry),
					),
					title=_("Return Exceeds Outstanding"),
				)

	def before_submit(self):
		if self.purpose == "Return":
			item_balance.validate_return(self)
		else:
			item_balance.lock_entries([self.name])

	def on_submit(self):
		item_balance.refresh_item_balances(self.get_balance_entries())

	def before_cancel(self):
		if self.purpose == "Return":
			item_balance.lock_for_return_cancel(self)
			return

		if self.allocation and not self.flags.from_allocation:
			allocation = frappe.db.get_value(
				"Accommodation Allocation", self.allocation, ["docstatus", "item_entry"], as_dict=True
			)
			if allocation and allocation.docstatus == 1 and allocation.item_entry == self.name:
				frappe.throw(
					_("This entry was created by {0}. Cancel the allocation instead.").format(
						frappe.bold(self.allocation)
					),
					title=_("Linked Allocation"),
				)

		item_balance.validate_assign_cancel(self)

	def on_cancel(self):
		item_balance.refresh_item_balances(self.get_balance_entries())

	def on_trash(self):
		if self.docstatus == 2:
			frappe.throw(_("Cancelled Item Entries are kept as history."), title=_("Not Allowed"))

	def get_balance_entries(self):
		if self.purpose == "Return":
			return sorted({line.against_entry for line in self.items if line.against_entry})
		return [self.name]


@frappe.whitelist()
def make_return(source_name):
	"""Return a new, unsaved Return entry for the outstanding lines of one Assign entry."""
	source = frappe.get_doc(ENTRY_DOCTYPE, source_name)
	source.check_permission("read")

	if source.docstatus != 1 or source.purpose != "Assign":
		frappe.throw(
			_("{0} is not a submitted Assign entry.").format(frappe.bold(source_name)),
			title=_("Invalid Assign Entry"),
		)

	return build_return_entry(source, item_balance.get_outstanding_lines(assign_entry=source.name))


@frappe.whitelist()
def make_return_for_allocation(source_name):
	"""Return a new, unsaved Return entry for the outstanding Assign lines of one allocation."""
	source = frappe.get_doc("Accommodation Allocation", source_name)
	source.check_permission("read")

	if source.docstatus != 1:
		frappe.throw(
			_("Allocation {0} is not submitted.").format(frappe.bold(source_name)),
			title=_("Invalid Allocation"),
		)

	return build_return_entry(source, item_balance.get_outstanding_lines(allocation=source.name))


def build_return_entry(source, lines):
	if not lines:
		frappe.throw(
			_("No items are outstanding on {0}.").format(frappe.bold(source.name)),
			title=_("Nothing Outstanding"),
		)

	entry = frappe.new_doc(ENTRY_DOCTYPE)
	entry.purpose = "Return"
	entry.posting_date = today()
	entry.employee = source.employee
	entry.employee_name = source.employee_name
	entry.allocation = source.name if source.doctype == "Accommodation Allocation" else source.allocation
	for fieldname in HOLDER_FIELDS:
		entry.set(fieldname, source.get(fieldname))

	for line in lines:
		entry.append("items", get_return_line(line))

	return entry


def get_return_line(line):
	return {
		"accommodation_item": line.accommodation_item,
		"return_type": "Returned",
		"quantity": line.outstanding_quantity,
		"against_entry": line.against_entry,
		"against_detail": line.against_detail,
	}


@frappe.whitelist()
def get_return_lines(employee=None, allocation=None, site=None):
	"""Return the outstanding Assign lines of a holder, shaped as Return lines."""
	frappe.has_permission(ENTRY_DOCTYPE, "read", throw=True)

	lines = item_balance.get_outstanding_lines(employee=employee, allocation=allocation, site=site)
	# outstanding_quantity is for the client check only. The saved line never keeps it.
	return [{**get_return_line(line), "outstanding_quantity": line.outstanding_quantity} for line in lines]


def create_item_entry(
	purpose,
	lines,
	posting_date,
	employee=None,
	allocation=None,
	request_id=None,
	remarks=None,
	ignore_permissions=False,
	holder=None,
):
	"""Insert and submit an Item Entry for server-side callers. Returns its name.

	A repeated call with the same request_id returns the first entry and does
	nothing else.
	"""
	if request_id:
		existing = frappe.db.get_value(
			ENTRY_DOCTYPE, {"request_id": request_id}, ["name", "docstatus"], as_dict=True
		)
		if existing and existing.docstatus == 2:
			# request_id is unique, so a new entry with the same id cannot be made.
			frappe.throw(
				_("This request was already used by cancelled entry {0}.").format(frappe.bold(existing.name)),
				title=_("Request Already Used"),
			)
		if existing:
			return existing.name

	entry = frappe.new_doc(ENTRY_DOCTYPE)
	entry.update(
		{
			"purpose": purpose,
			"posting_date": posting_date,
			"employee": employee,
			"allocation": allocation,
			"request_id": request_id,
			"remarks": remarks,
			**(holder or {}),
		}
	)
	for line in lines:
		entry.append("items", line)

	entry.flags.ignore_permissions = ignore_permissions
	entry.insert()
	entry.submit()
	return entry.name
