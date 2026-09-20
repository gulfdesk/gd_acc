# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

ASSIGNMENT_DOCTYPE = "Accommodation Asset Assignment"

ASSIGNMENT_FIELDS = (
	"name",
	"employee",
	"employee_name",
	"location",
	"site",
	"room",
	"bed",
	"assignment_date",
	"return_date",
	"status",
)

ITEM_FIELDS = (
	"parent",
	"idx",
	"accommodation_item",
	"item_category",
	"quantity",
	"condition",
	"returned_quantity",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Assignment"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": ASSIGNMENT_DOCTYPE,
			"width": 180,
		},
		{
			"label": _("Employee"),
			"fieldname": "employee",
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
			"label": _("Item"),
			"fieldname": "accommodation_item",
			"fieldtype": "Link",
			"options": "Accommodation Item",
			"width": 180,
		},
		{
			"label": _("Category"),
			"fieldname": "item_category",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Quantity"),
			"fieldname": "quantity",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Condition"),
			"fieldname": "condition",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Returned Qty"),
			"fieldname": "returned_quantity",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Location"),
			"fieldname": "location",
			"fieldtype": "Link",
			"options": "Accommodation Location",
			"width": 150,
		},
		{
			"label": _("Accommodation Site"),
			"fieldname": "site",
			"fieldtype": "Link",
			"options": "Accommodation Site",
			"width": 180,
		},
		{
			"label": _("Room"),
			"fieldname": "room",
			"fieldtype": "Link",
			"options": "Accommodation Room",
			"width": 160,
		},
		{
			"label": _("Bed"),
			"fieldname": "bed",
			"fieldtype": "Link",
			"options": "Accommodation Bed",
			"width": 180,
		},
		{
			"label": _("Assignment Date"),
			"fieldname": "assignment_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": _("Return Date"),
			"fieldname": "return_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
	]


def get_data(filters):
	assignments = frappe.get_all(
		ASSIGNMENT_DOCTYPE,
		filters=get_assignment_filters(filters),
		fields=list(ASSIGNMENT_FIELDS),
		order_by="assignment_date desc, name desc",
	)

	if not assignments:
		return []

	rows_by_assignment = get_issued_items(filters, [assignment.name for assignment in assignments])

	data = []
	for assignment in assignments:
		for row in rows_by_assignment.get(assignment.name, []):
			data.append(
				frappe._dict(
					name=assignment.name,
					employee=assignment.employee,
					employee_name=assignment.employee_name,
					accommodation_item=row.accommodation_item,
					item_category=row.item_category,
					quantity=row.quantity,
					condition=row.condition,
					returned_quantity=row.returned_quantity,
					location=assignment.location,
					site=assignment.site,
					room=assignment.room,
					bed=assignment.bed,
					assignment_date=assignment.assignment_date,
					return_date=assignment.return_date,
					status=assignment.status,
				)
			)

	return data


def get_issued_items(filters, assignment_names):
	item_filters = {
		"parenttype": ASSIGNMENT_DOCTYPE,
		"parentfield": "items",
		"parent": ["in", assignment_names],
	}

	if filters.get("item_category"):
		item_filters["item_category"] = filters.item_category

	rows = frappe.get_all(
		"Accommodation Assigned Item",
		filters=item_filters,
		fields=list(ITEM_FIELDS),
		order_by="parent asc, idx asc",
	)

	rows_by_assignment = {}
	for row in rows:
		rows_by_assignment.setdefault(row.parent, []).append(row)

	return rows_by_assignment


def get_assignment_filters(filters):
	assignment_filters = []

	for fieldname in ("location", "site", "employee"):
		if filters.get(fieldname):
			assignment_filters.append([fieldname, "=", filters.get(fieldname)])

	if filters.get("assignment_status"):
		assignment_filters.append(["status", "=", filters.assignment_status])

	if filters.get("from_date"):
		assignment_filters.append(["assignment_date", ">=", getdate(filters.from_date)])
	if filters.get("to_date"):
		assignment_filters.append(["assignment_date", "<=", getdate(filters.to_date)])

	return assignment_filters
