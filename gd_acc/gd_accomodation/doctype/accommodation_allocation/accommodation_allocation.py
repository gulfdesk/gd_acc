# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from gd_acc.gd_accomodation.accommodation_utils import (
	ALLOCATABLE_BED_STATUSES,
	close_stale_entitlement,
	get_active_allocation,
	get_conflicting_allocation,
	occupy_bed,
	release_bed,
	resolve_hierarchy,
	site_requires_bed,
	sync_employee_accommodation,
)

RELEASE_REASONS = ("Transfer", "Employee Exit", "Accommodation Status Change", "Manual Release", "Other")


class AccommodationAllocation(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"

		self.validate_dates()
		self.apply_hierarchy()
		self.validate_bed_requirement()

		if self.docstatus == 1:
			self.validate_employee_has_no_active_allocation()
			self.validate_bed_is_allocatable()

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

	def validate_bed_is_allocatable(self):
		if not self.bed:
			return

		conflict = get_conflicting_allocation(
			self.bed, self.start_date, self.expected_end_date, exclude=self.name
		)
		if conflict:
			frappe.throw(
				_("Bed {0} is already allocated to {1} under {2} for an overlapping period.").format(
					frappe.bold(self.bed),
					frappe.bold(conflict.employee_name or conflict.employee),
					frappe.bold(conflict.name),
				),
				title=_("Double Booking"),
			)

		bed_status = frappe.db.get_value("Accommodation Bed", self.bed, "status")
		if bed_status not in ALLOCATABLE_BED_STATUSES:
			frappe.throw(
				_("Bed {0} is {1} and cannot be allocated. Only {2} beds can be allocated.").format(
					frappe.bold(self.bed), frappe.bold(bed_status), frappe.bold("Available")
				),
				title=_("Bed Not Available"),
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

		sync_employee_accommodation(self.employee, accommodation_status="Provided")

	def before_cancel(self):
		if self.released_by_transfer:
			frappe.throw(
				_("This allocation was closed by transfer {0}. Cancel that transfer instead.").format(
					frappe.bold(self.released_by_transfer)
				),
				title=_("Cancel Transfer First"),
			)

	def on_cancel(self):
		if self.status == "Active" and self.bed:
			release_bed(
				self.bed,
				allocation=self.name,
				employee=self.employee,
				reason="Release",
				remarks=_("Allocation cancelled."),
			)

		self.db_set({"status": "Cancelled", "release_date": None, "release_reason": None})

		remaining = get_active_allocation(self.employee)
		sync_employee_accommodation(self.employee, accommodation_status=None if remaining else "Not Provided")

	def release(
		self,
		release_date=None,
		reason="Manual Release",
		transfer=None,
		employee_status=None,
		remarks=None,
	):
		"""Close this allocation and free the bed without touching history.

		The allocation row itself is kept exactly as it was apart from the
		closing fields, so the stay remains fully auditable.
		"""
		if self.docstatus != 1 or self.status != "Active":
			frappe.throw(
				_("Only an active allocation can be released. {0} is {1}.").format(
					frappe.bold(self.name), frappe.bold(self.status)
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

		sync_employee_accommodation(self.employee, accommodation_status=employee_status)


@frappe.whitelist()
def release_allocation(allocation, release_date=None, reason="Manual Release", remarks=None):
	"""Release an allocation from the desk, marking the employee as Not Provided.

	Used both by the Accommodation Allocation form's own Release button and by
	the Employee tab's Release Accommodation action, so an entitlement created
	through either path is closed out the same way.
	"""
	doc = frappe.get_doc("Accommodation Allocation", allocation)
	doc.check_permission("submit")
	doc.release(
		release_date=release_date,
		reason=reason,
		employee_status="Not Provided",
		remarks=remarks,
	)
	close_stale_entitlement(doc.employee, doc.release_date, remarks=remarks)
	return doc.name


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
