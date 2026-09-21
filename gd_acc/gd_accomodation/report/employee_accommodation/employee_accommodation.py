# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint

from gd_acc.gd_accomodation.accommodation_utils import ENTITLEMENT_TO_EMPLOYEE_STATUS

EMPLOYEE_FIELDS = (
	"name",
	"employee_name",
	"company",
	"designation",
	"current_accommodation_entitlement",
	"current_accommodation_allocation",
	"current_accommodation_location",
	"current_accommodation_site",
	"current_accommodation_type",
	"current_accommodation_sub_type",
	"current_accommodation_floor",
	"current_accommodation_room",
	"current_accommodation_bed",
	"accommodation_start_date",
	"accommodation_expected_end_date",
)

ENTITLEMENT_FIELDS = (
	"name",
	"entitlement_type",
	"allowance_frequency",
	"allowance_amount",
	"allowance_currency",
	"stay_status",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(data)


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 130,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 140,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": 140,
		},
		{
			"label": _("Accommodation Status"),
			"fieldname": "accommodation_status",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Stay Status"),
			"fieldname": "stay_status",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Allocation Status"),
			"fieldname": "allocation_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Location"),
			"fieldname": "current_accommodation_location",
			"fieldtype": "Link",
			"options": "Accommodation Location",
			"width": 150,
		},
		{
			"label": _("Accommodation Site"),
			"fieldname": "current_accommodation_site",
			"fieldtype": "Link",
			"options": "Accommodation Site",
			"width": 180,
		},
		{
			"label": _("Type"),
			"fieldname": "current_accommodation_type",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Sub-Type"),
			"fieldname": "current_accommodation_sub_type",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Floor"),
			"fieldname": "current_accommodation_floor",
			"fieldtype": "Link",
			"options": "Accommodation Floor",
			"width": 160,
		},
		{
			"label": _("Room"),
			"fieldname": "current_accommodation_room",
			"fieldtype": "Link",
			"options": "Accommodation Room",
			"width": 160,
		},
		{
			"label": _("Bed"),
			"fieldname": "current_accommodation_bed",
			"fieldtype": "Link",
			"options": "Accommodation Bed",
			"width": 180,
		},
		{
			"label": _("Start Date"),
			"fieldname": "accommodation_start_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Expected End Date"),
			"fieldname": "accommodation_expected_end_date",
			"fieldtype": "Date",
			"width": 140,
		},
		{
			"label": _("Allowance Type"),
			"fieldname": "accommodation_allowance_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Allowance Amount"),
			"fieldname": "accommodation_allowance_amount",
			"fieldtype": "Currency",
			"options": "accommodation_allowance_currency",
			"width": 140,
		},
	]


def get_data(filters):
	data = frappe.get_all(
		"Employee",
		filters=get_employee_filters(filters),
		fields=list(EMPLOYEE_FIELDS),
		order_by="employee_name asc",
	)
	entitlements = get_entitlements(data)
	allocation_statuses = get_allocation_statuses(data)

	for row in data:
		entitlement = entitlements.get(row.current_accommodation_entitlement) or frappe._dict()
		row.accommodation_status = ENTITLEMENT_TO_EMPLOYEE_STATUS.get(
			entitlement.entitlement_type, "Not Provided"
		)
		row.stay_status = entitlement.stay_status
		row.allocation_status = allocation_statuses.get(row.current_accommodation_allocation)
		row.accommodation_allowance_type = entitlement.allowance_frequency
		row.accommodation_allowance_amount = entitlement.allowance_amount
		row.accommodation_allowance_currency = entitlement.allowance_currency

	if filters.get("accommodation_status"):
		data = [row for row in data if row.accommodation_status == filters.accommodation_status]
	if filters.get("stay_status"):
		data = [row for row in data if row.stay_status == filters.stay_status]

	return data


def get_entitlements(data):
	"""The current entitlement of each row, read in one query."""
	names = list(
		{row.current_accommodation_entitlement for row in data if row.current_accommodation_entitlement}
	)
	if not names:
		return {}

	return {
		row.name: row
		for row in frappe.get_all(
			"Accommodation Entitlement",
			filters={"name": ("in", names)},
			fields=list(ENTITLEMENT_FIELDS),
			limit=0,
		)
	}


def get_allocation_statuses(data):
	"""The status of each row's current allocation, read in one query."""
	names = list(
		{row.current_accommodation_allocation for row in data if row.current_accommodation_allocation}
	)
	if not names:
		return {}

	return dict(
		frappe.get_all(
			"Accommodation Allocation",
			filters={"name": ("in", names)},
			fields=["name", "status"],
			as_list=True,
			limit=0,
		)
	)


def get_employee_filters(filters):
	employee_filters = {}

	if filters.get("company"):
		employee_filters["company"] = filters.company
	if filters.get("employee"):
		employee_filters["name"] = filters.employee
	if filters.get("location"):
		employee_filters["current_accommodation_location"] = filters.location
	if filters.get("site"):
		employee_filters["current_accommodation_site"] = filters.site

	if not cint(filters.get("include_inactive_employees")):
		employee_filters["status"] = "Active"

	return employee_filters


def get_report_summary(data):
	def count(status):
		return sum(1 for row in data if row.accommodation_status == status)

	return [
		{"value": len(data), "label": _("Employees"), "datatype": "Int", "indicator": "Blue"},
		{"value": count("Provided"), "label": _("Provided"), "datatype": "Int", "indicator": "Green"},
		{"value": count("Allowance"), "label": _("Allowance"), "datatype": "Int", "indicator": "Orange"},
		{
			"value": count("Not Provided"),
			"label": _("Not Provided"),
			"datatype": "Int",
			"indicator": "Red",
		},
	]
