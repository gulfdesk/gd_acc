# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from gd_acc.gd_accomodation.accommodation_utils import (
	ENTITLEMENT_TO_EMPLOYEE_STATUS,
	get_active_allocation,
	get_active_entitlement,
	sync_employee_accommodation,
)


class AccommodationEntitlement(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"

		self.set_replaced_records()
		self.validate_dates()
		self.apply_allowance()

	def set_replaced_records(self):
		"""Work out what this entitlement supersedes.

		An allocation only needs releasing when the employee is moving off
		company accommodation; staying on it keeps the current room.
		"""
		self.previous_entitlement = get_active_entitlement(self.employee, exclude=self.name)

		active_allocation = get_active_allocation(self.employee)
		if active_allocation and self.entitlement_type != "Company Accommodation":
			self.previous_allocation = active_allocation
		else:
			self.previous_allocation = None
			self.release_date = None

	def validate_dates(self):
		if not self.previous_allocation:
			return

		if not self.release_date:
			frappe.throw(
				_(
					"{0} is currently housed under allocation {1}. "
					"Enter the Release Date so the stay is closed correctly and kept in history."
				).format(
					frappe.bold(self.employee_name or self.employee), frappe.bold(self.previous_allocation)
				),
				title=_("Release Date Required"),
			)

		start_date = frappe.db.get_value("Accommodation Allocation", self.previous_allocation, "start_date")
		if getdate(self.release_date) < getdate(start_date):
			frappe.throw(
				_("Release Date cannot be before the allocation started on {0}.").format(
					frappe.bold(start_date)
				),
				title=_("Invalid Dates"),
			)

	def apply_allowance(self):
		if self.entitlement_type != "Allowance":
			self.allowance_component = None
			self.allowance_amount = 0
			self.salary_structure = None
			self.allowance_source = None
			return

		if not self.allowance_component:
			self.allowance_component = frappe.db.get_single_value(
				"GD Acc Settings", "accommodation_allowance_component"
			)

		payroll = get_payroll_allowance(self.employee, self.from_date, self.allowance_component)
		self.salary_structure = payroll.get("salary_structure")
		self.allowance_source = payroll.get("source")

		if not flt(self.allowance_amount):
			self.allowance_amount = flt(payroll.get("amount"))

		if not self.allowance_currency:
			self.allowance_currency = payroll.get("currency") or frappe.db.get_value(
				"Company", self.company, "default_currency"
			)

	def on_submit(self):
		self.close_previous_entitlement()
		self.release_previous_allocation()

		self.db_set("status", "Active")
		sync_employee_accommodation(
			self.employee,
			accommodation_status=ENTITLEMENT_TO_EMPLOYEE_STATUS[self.entitlement_type],
			entitlement=self.name,
		)

	def close_previous_entitlement(self):
		if not self.previous_entitlement:
			return

		previous = frappe.get_doc("Accommodation Entitlement", self.previous_entitlement)
		previous.db_set({"status": "Closed", "to_date": self.from_date})

	def release_previous_allocation(self):
		if not self.previous_allocation:
			return

		allocation = frappe.get_doc("Accommodation Allocation", self.previous_allocation)
		allocation.release(
			release_date=self.release_date,
			reason=self.release_reason or "Accommodation Status Change",
			remarks=_("Entitlement changed to {0} by {1}.").format(self.entitlement_type, self.name),
		)

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

		restored = None
		if self.previous_entitlement:
			previous = frappe.get_doc("Accommodation Entitlement", self.previous_entitlement)
			previous.db_set({"status": "Active", "to_date": None})
			restored = previous

		status = ENTITLEMENT_TO_EMPLOYEE_STATUS[restored.entitlement_type] if restored else "Not Provided"
		sync_employee_accommodation(
			self.employee,
			accommodation_status=status,
			entitlement=restored.name if restored else None,
		)


def get_payroll_allowance(employee, on_date, component):
	"""Read the accommodation allowance from the employee's salary structure."""
	result = {"amount": 0, "salary_structure": None, "currency": None, "source": None}

	if not component:
		result["source"] = _("No accommodation allowance component is set in GD Acc Settings.")
		return result

	assignment = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee, "docstatus": 1, "from_date": ("<=", getdate(on_date))},
		fields=["name", "salary_structure", "from_date", "currency"],
		order_by="from_date desc",
		limit=1,
	)
	if not assignment:
		result["source"] = _("No submitted Salary Structure Assignment found for this employee.")
		return result

	assignment = assignment[0]
	result["salary_structure"] = assignment.salary_structure
	result["currency"] = assignment.currency

	rows = frappe.get_all(
		"Salary Detail",
		filters={
			"parent": assignment.salary_structure,
			"parenttype": "Salary Structure",
			"parentfield": "earnings",
			"salary_component": component,
		},
		fields=["amount", "amount_based_on_formula", "formula"],
	)
	if not rows:
		result["source"] = _("{0} is not an earning in salary structure {1}.").format(
			component, assignment.salary_structure
		)
		return result

	row = rows[0]
	result["amount"] = flt(row.amount)

	if row.amount_based_on_formula and not flt(row.amount):
		result["source"] = _(
			"{0} in {1} is calculated by the formula '{2}'. Enter the amount manually."
		).format(component, assignment.salary_structure, row.formula)
	else:
		result["source"] = _("{0} in salary structure {1}, effective {2}.").format(
			component, assignment.salary_structure, assignment.from_date
		)

	return result


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
	remarks=None,
):
	"""Single-save creation used by the Employee accommodation tab.

	Company Accommodation also needs a bed, so this creates the Accommodation
	Allocation first and the Entitlement second: if the bed turns out to be
	unavailable the whole action fails before any entitlement is created, and
	the caller only ever has to fill in and submit one form.
	"""
	if not frappe.has_permission("Accommodation Entitlement", "create"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	new_allocation = None
	if entitlement_type == "Company Accommodation":
		if not frappe.has_permission("Accommodation Allocation", "create"):
			frappe.throw(_("Not permitted."), frappe.PermissionError)

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
			"remarks": remarks,
		}
	)
	entitlement.insert()
	entitlement.submit()

	return {"entitlement": entitlement.name, "allocation": new_allocation}


@frappe.whitelist()
def fetch_allowance_details(employee, on_date, component=None):
	"""Called from the form so the user can pull payroll figures on demand."""
	if not frappe.has_permission("Accommodation Entitlement", "read"):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	component = component or frappe.db.get_single_value(
		"GD Acc Settings", "accommodation_allowance_component"
	)
	details = get_payroll_allowance(employee, on_date, component)
	details["component"] = component
	return details


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
			"release_date",
			"location",
			"site",
			"floor",
			"room",
			"bed",
			"bed_type",
			"release_reason",
		],
		order_by="start_date desc, creation desc",
	)

	active = next((row for row in entitlements if row.status == "Active"), None)

	return {
		"entitlement": active,
		"entitlements": entitlements,
		"allocations": allocations,
		"active_allocation": get_active_allocation(employee),
	}
