# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint

EMPLOYEE_FIELDS = (
	"name",
	"employee_name",
	"company",
	"designation",
	"accommodation_status",
	"current_accommodation_location",
	"current_accommodation_site",
	"current_accommodation_type",
	"current_accommodation_sub_type",
	"current_accommodation_floor",
	"current_accommodation_room",
	"current_accommodation_bed",
	"accommodation_start_date",
	"accommodation_expected_end_date",
	"accommodation_allowance_type",
	"accommodation_allowance_amount",
	"accommodation_allowance_currency",
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
	return frappe.get_all(
		"Employee",
		filters=get_employee_filters(filters),
		fields=list(EMPLOYEE_FIELDS),
		order_by="employee_name asc",
	)


def get_employee_filters(filters):
	employee_filters = {}

	if filters.get("company"):
		employee_filters["company"] = filters.company
	if filters.get("employee"):
		employee_filters["name"] = filters.employee
	if filters.get("accommodation_status"):
		employee_filters["accommodation_status"] = filters.accommodation_status
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
