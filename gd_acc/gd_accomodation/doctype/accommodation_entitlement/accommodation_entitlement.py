# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from gd_acc.gd_accomodation.accommodation_utils import (
	get_active_allocation,
	refresh_stay_status,
)
from gd_acc.gd_accomodation.release_flow import handle_entitlement_update

ENTITLEMENT_DOCTYPE = "Accommodation Entitlement"
COMPANY_ACCOMMODATION = "Company Accommodation"


class AccommodationEntitlement(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"

		self.validate_to_date()
		self.validate_no_open_entitlement()
		self.validate_not_housed()
		self.set_previous_entitlement()
		self.apply_allowance()

	def validate_to_date(self):
		if self.to_date and getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("Effective To cannot be before Effective From."), title=_("Invalid Dates"))

	def get_other_active_entitlements(self):
		return frappe.get_all(
			ENTITLEMENT_DOCTYPE,
			filters={
				"employee": self.employee,
				"docstatus": 1,
				"status": "Active",
				"name": ("!=", self.name),
			},
			fields=["name", "entitlement_type", "from_date", "to_date"],
			order_by="from_date desc",
		)

	def validate_no_open_entitlement(self):
		"""Refuse the entitlement while another one is open on its From Date."""
		from_date = getdate(self.from_date)
		for row in self.get_other_active_entitlements():
			if row.to_date and getdate(row.to_date) < from_date:
				continue

			until = (
				_("until {0}").format(frappe.format(row.to_date, {"fieldtype": "Date"}))
				if row.to_date
				else _("with no end date")
			)
			frappe.throw(
				_(
					"{0} already holds entitlement {1} ({2}) from {3} {4}. "
					"Set its Effective To before {5} first."
				).format(
					frappe.bold(self.employee_name or self.employee),
					frappe.bold(row.name),
					_(row.entitlement_type),
					frappe.format(row.from_date, {"fieldtype": "Date"}),
					until,
					frappe.format(self.from_date, {"fieldtype": "Date"}),
				),
				title=_("Open Entitlement"),
			)

	def validate_not_housed(self):
		if self.entitlement_type == COMPANY_ACCOMMODATION:
			return

		allocation = get_active_allocation(self.employee)
		if allocation:
			frappe.throw(
				_(
					"{0} is housed under allocation {1}. End the Company Accommodation entitlement "
					"and release the stay first."
				).format(frappe.bold(self.employee_name or self.employee), frappe.bold(allocation)),
				title=_("Employee Housed"),
			)

	def set_previous_entitlement(self):
		"""The latest Active entitlement that ends before this one starts."""
		from_date = getdate(self.from_date)
		self.previous_entitlement = next(
			(
				row.name
				for row in self.get_other_active_entitlements()
				if row.to_date and getdate(row.to_date) < from_date
			),
			None,
		)

	def apply_allowance(self):
		if self.entitlement_type != "Allowance":
			self.allowance_component = None
			self.allowance_amount = 0
			self.salary_structure_assignment = None
			self.salary_structure = None
			self.allowance_source = None
			return

		payroll = get_payroll_allowance(
			self.employee, self.from_date, self.allowance_component, self.salary_structure_assignment
		)
		self.salary_structure_assignment = payroll.get("salary_structure_assignment")
		self.salary_structure = payroll.get("salary_structure")
		self.allowance_source = payroll.get("source")

		if not flt(self.allowance_amount):
			self.allowance_amount = flt(payroll.get("amount"))

		if not self.allowance_currency:
			self.allowance_currency = payroll.get("currency") or frappe.db.get_value(
				"Company", self.company, "default_currency"
			)

	def on_submit(self):
		self.close_superseded()
		self.db_set(
			{
				"status": "Active",
				"stay_status": "Awaiting Bed" if self.entitlement_type == COMPANY_ACCOMMODATION else None,
			}
		)
		refresh_stay_status(self.employee)

	def close_superseded(self):
		"""Close each older Active entitlement that ends before this one starts. Its To Date stays."""
		from_date = getdate(self.from_date)
		for row in self.get_other_active_entitlements():
			if row.to_date and getdate(row.to_date) < from_date:
				frappe.db.set_value(ENTITLEMENT_DOCTYPE, row.name, "status", "Closed")

	def before_update_after_submit(self):
		self.validate_to_date()
		self.validate_no_later_overlap()

	def validate_no_later_overlap(self):
		"""A later Active entitlement must still start after this one ends."""
		later = frappe.get_all(
			ENTITLEMENT_DOCTYPE,
			filters={
				"employee": self.employee,
				"docstatus": 1,
				"status": "Active",
				"name": ("!=", self.name),
				"from_date": (">", self.from_date),
			},
			fields=["name", "from_date"],
			order_by="from_date asc",
			limit=1,
		)
		if not later:
			return

		later = later[0]
		if not self.to_date or getdate(later.from_date) <= getdate(self.to_date):
			frappe.throw(
				_("Entitlement {0} starts on {1}. This one must end before it.").format(
					frappe.bold(later.name), frappe.format(later.from_date, {"fieldtype": "Date"})
				),
				title=_("Overlap"),
			)

	def on_update_after_submit(self):
		refresh_stay_status(self.employee)
		handle_entitlement_update(self)

	def before_cancel(self):
		if self.status == "Closed":
			frappe.throw(
				_(
					"This entitlement has already been replaced by a newer one, so cancelling it "
					"would rewrite history. Create a new entitlement instead."
				),
				title=_("Already Replaced"),
			)

		if self.previous_allocation:
			frappe.throw(
				_(
					"This entitlement released allocation {0}. Cancelling it will not put the employee "
					"back in that bed. Create a new Company Accommodation entitlement and allocate a bed."
				).format(frappe.bold(self.previous_allocation)),
				title=_("Cannot Undo A Release"),
			)

	def on_cancel(self):
		self.db_set("status", "Cancelled")

		if (
			self.previous_entitlement
			and frappe.db.get_value(ENTITLEMENT_DOCTYPE, self.previous_entitlement, "status") == "Closed"
		):
			frappe.db.set_value(ENTITLEMENT_DOCTYPE, self.previous_entitlement, "status", "Active")

		refresh_stay_status(self.employee)


def get_payroll_allowance(employee, on_date, component, assignment=None):
	"""Read the accommodation allowance from the employee's payroll.

	The assignment names the salary structure that HR picks the component from.
	The amount comes from the latest submitted salary slip of the employee.
	"""
	result = {
		"amount": 0,
		"salary_structure_assignment": None,
		"salary_structure": None,
		"currency": None,
		"source": None,
	}

	assignment = get_salary_structure_assignment(employee, on_date, assignment)
	if not assignment:
		result["source"] = _("No submitted Salary Structure Assignment found for this employee.")
		return result

	result["salary_structure_assignment"] = assignment.name
	result["salary_structure"] = assignment.salary_structure
	result["currency"] = assignment.currency

	if not component:
		result["source"] = _("Select the salary component that pays the accommodation allowance.")
		return result

	slip = frappe.get_all(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "start_date", "end_date", "currency"],
		order_by="end_date desc, creation desc",
		limit=1,
	)
	if not slip:
		result["source"] = _("No submitted Salary Slip found for this employee.")
		return result

	slip = slip[0]
	result["currency"] = slip.currency or result["currency"]

	amounts = frappe.get_all(
		"Salary Detail",
		filters={
			"parent": slip.name,
			"parenttype": "Salary Slip",
			"parentfield": "earnings",
			"salary_component": component,
		},
		pluck="amount",
	)
	if not amounts:
		result["source"] = _("{0} is not an earning on salary slip {1}.").format(component, slip.name)
		return result

	result["amount"] = sum(flt(amount) for amount in amounts)
	result["source"] = _("{0} on salary slip {1}, {2} to {3}.").format(
		component,
		slip.name,
		frappe.format(slip.start_date, "Date"),
		frappe.format(slip.end_date, "Date"),
	)
	return result


def get_salary_structure_assignment(employee, on_date, assignment=None):
	"""The chosen assignment, or the latest submitted one on or before the date."""
	filters = {"employee": employee, "docstatus": 1}
	if assignment:
		filters["name"] = assignment
	else:
		filters["from_date"] = ("<=", getdate(on_date))

	rows = frappe.get_all(
		"Salary Structure Assignment",
		filters=filters,
		fields=["name", "salary_structure", "currency"],
		order_by="from_date desc",
		limit=1,
	)
	return rows[0] if rows else None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_assignment_components(doctype, txt, searchfield, start, page_len, filters):
	"""Earning components of the salary structure behind the chosen assignment."""
	assignment = (filters or {}).get("salary_structure_assignment")
	if not assignment:
		return []

	salary_structure = frappe.db.get_value("Salary Structure Assignment", assignment, "salary_structure")
	if not salary_structure:
		return []

	return frappe.get_all(
		"Salary Detail",
		filters={
			"parent": salary_structure,
			"parenttype": "Salary Structure",
			"parentfield": "earnings",
			"salary_component": ("like", f"%{txt}%"),
		},
		fields=["salary_component"],
		distinct=True,
		order_by="salary_component",
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
def create_entitlement(
	employee,
	entitlement_type,
	from_date,
	location=None,
	site=None,
	floor=None,
	room=None,
	bed=None,
	expected_end_date=None,
	allowance_amount=None,
	allowance_component=None,
	allowance_currency=None,
	allowance_frequency=None,
	salary_structure_assignment=None,
	remarks=None,
):
	"""Single-save creation used by the Employee accommodation tab.

	For Company Accommodation with a site, this also houses the employee: the
	Accommodation Allocation is submitted first and the Entitlement second, in
	one transaction. If the bed is not available, nothing is created. Without a
	site, only the entitlement is created and it waits for a bed.
	"""
	if not frappe.has_permission("Accommodation Entitlement", "create"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	new_allocation = None
	if entitlement_type == COMPANY_ACCOMMODATION and site:
		if not frappe.has_permission("Accommodation Allocation", "create"):
			frappe.throw(
				_(
					"You can create the entitlement, but not the allocation. Leave the accommodation "
					"fields empty; an Accommodation User allocates the bed."
				),
				title=_("Not Permitted"),
			)

		allocation = frappe.new_doc("Accommodation Allocation")
		allocation.update(
			{
				"employee": employee,
				"location": location,
				"site": site,
				"floor": floor,
				"room": room,
				"bed": bed,
				"start_date": from_date,
				"expected_end_date": expected_end_date,
			}
		)
		allocation.insert()
		allocation.submit()
		new_allocation = allocation.name

	entitlement = frappe.new_doc("Accommodation Entitlement")
	entitlement.update(
		{
			"employee": employee,
			"entitlement_type": entitlement_type,
			"from_date": from_date,
			"allowance_amount": allowance_amount,
			"allowance_component": allowance_component,
			"allowance_currency": allowance_currency,
			"allowance_frequency": allowance_frequency or "Monthly",
			"salary_structure_assignment": salary_structure_assignment,
			"remarks": remarks,
		}
	)
	entitlement.insert()
	entitlement.submit()

	return {"entitlement": entitlement.name, "allocation": new_allocation}


@frappe.whitelist()
def fetch_allowance_details(employee, on_date, component=None, salary_structure_assignment=None):
	"""Called from the form so the user can pull payroll figures on demand."""
	if not frappe.has_permission("Accommodation Entitlement", "read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	return get_payroll_allowance(employee, on_date, component, salary_structure_assignment)


@frappe.whitelist()
def get_employee_entitlement_state(employee):
	"""Everything the Employee accommodation tab needs, in one call."""
	if not frappe.has_permission("Employee", "read", doc=employee):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	entitlements = frappe.get_all(
		"Accommodation Entitlement",
		filters={"employee": employee, "docstatus": ("!=", 2)},
		fields=[
			"name",
			"entitlement_type",
			"status",
			"from_date",
			"to_date",
			"allowance_amount",
			"allowance_currency",
			"allowance_frequency",
			"allowance_component",
			"stay_status",
			"release_date",
		],
		order_by="from_date desc, creation desc",
	)

	allocations = frappe.get_all(
		"Accommodation Allocation",
		filters={"employee": employee, "docstatus": ("!=", 2)},
		fields=[
			"name",
			"status",
			"start_date",
			"expected_end_date",
			"release_date",
			"location",
			"site",
			"floor",
			"room",
			"bed",
			"bed_type",
			"release_reason",
			"proposed_release_date",
			"pending_release_reason",
		],
		order_by="start_date desc, creation desc",
	)

	active = next((row for row in entitlements if row.status == "Active"), None)
	active_allocation = get_active_allocation(employee)
	set_place_labels(allocations)

	return {
		"entitlement": active,
		"entitlements": entitlements,
		"allocations": allocations,
		"active_allocation": active_allocation,
		"place": next((row.place for row in allocations if row.name == active_allocation), {}),
	}


# Allocation field, the DocType it links to, and that DocType's short name field.
PLACE_LABEL_FIELDS = (
	("site", "Accommodation Site", "site_name"),
	("floor", "Accommodation Floor", "floor_name"),
	("room", "Accommodation Room", "room_number"),
	("bed", "Accommodation Bed", "bed_number"),
)


def set_place_labels(allocations):
	"""Give each allocation a place dict of short names, for example Floor 1 in place of A - Site 1 - Floor 1."""
	labels = {}
	for fieldname, doctype, label_field in PLACE_LABEL_FIELDS:
		names = list({row.get(fieldname) for row in allocations if row.get(fieldname)})
		labels[fieldname] = (
			dict(
				frappe.get_all(
					doctype, filters={"name": ("in", names)}, fields=["name", label_field], as_list=True
				)
			)
			if names
			else {}
		)

	for row in allocations:
		row.place = {"location": row.location}
		for fieldname, _doctype, _label_field in PLACE_LABEL_FIELDS:
			value = row.get(fieldname)
			row.place[fieldname] = value and (labels[fieldname].get(value) or value)
