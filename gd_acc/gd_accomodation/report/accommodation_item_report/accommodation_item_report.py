# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

from gd_acc.gd_accomodation.item_balance import DETAIL_DOCTYPE, ENTRY_DOCTYPE

ENTRY_FIELDS = (
	"name",
	"posting_date",
	"employee",
	"employee_name",
	"allocation",
	"items_status",
	"location",
	"site",
	"room",
	"bed",
)

LINE_FIELDS = (
	"parent",
	"accommodation_item",
	"item_category",
	"quantity",
	"returned_quantity",
	"damaged_quantity",
	"lost_quantity",
	"outstanding_quantity",
	"last_return_date",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Assign Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": ENTRY_DOCTYPE,
			"width": 170,
		},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 130,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{
			"label": _("Allocation"),
			"fieldname": "allocation",
			"fieldtype": "Link",
			"options": "Accommodation Allocation",
			"width": 170,
		},
		{
			"label": _("Item"),
			"fieldname": "accommodation_item",
			"fieldtype": "Link",
			"options": "Accommodation Item",
			"width": 180,
		},
		{"label": _("Category"), "fieldname": "item_category", "fieldtype": "Data", "width": 120},
		{"label": _("Assigned"), "fieldname": "quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Returned"), "fieldname": "returned_quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Damaged"), "fieldname": "damaged_quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Lost"), "fieldname": "lost_quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Outstanding"), "fieldname": "outstanding_quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Last Return Date"), "fieldname": "last_return_date", "fieldtype": "Date", "width": 110},
		{"label": _("Status"), "fieldname": "items_status", "fieldtype": "Data", "width": 110},
		{
			"label": _("Location"),
			"fieldname": "location",
			"fieldtype": "Link",
			"options": "Accommodation Location",
			"width": 130,
		},
		{
			"label": _("Accommodation Site"),
			"fieldname": "site",
			"fieldtype": "Link",
			"options": "Accommodation Site",
			"width": 130,
		},
		{
			"label": _("Room"),
			"fieldname": "room",
			"fieldtype": "Link",
			"options": "Accommodation Room",
			"width": 130,
		},
		{
			"label": _("Bed"),
			"fieldname": "bed",
			"fieldtype": "Link",
			"options": "Accommodation Bed",
			"width": 130,
		},
	]


def get_data(filters):
	# get_list applies the viewer's read permission on the Item Entry.
	entries = frappe.get_list(
		ENTRY_DOCTYPE,
		filters=get_entry_filters(filters),
		fields=list(ENTRY_FIELDS),
		limit=0,
		order_by="posting_date desc, name desc",
	)
	if not entries:
		return []

	lines_by_entry = get_lines(filters, [entry.name for entry in entries])

	data = []
	for entry in entries:
		for line in lines_by_entry.get(entry.name, []):
			row = frappe._dict(entry)
			row.update({fieldname: line[fieldname] for fieldname in LINE_FIELDS if fieldname != "parent"})
			data.append(row)

	return data


def get_lines(filters, entry_names):
	line_filters = {"parent": ["in", entry_names], "parenttype": ENTRY_DOCTYPE, "parentfield": "items"}

	if filters.get("item_category"):
		line_filters["item_category"] = filters.item_category

	if filters.get("outstanding_only"):
		line_filters["outstanding_quantity"] = [">", 0]

	lines = frappe.get_all(
		DETAIL_DOCTYPE,
		filters=line_filters,
		fields=list(LINE_FIELDS),
		limit=0,
		order_by="idx asc",
	)

	lines_by_entry = {}
	for line in lines:
		lines_by_entry.setdefault(line.parent, []).append(line)

	return lines_by_entry


def get_entry_filters(filters):
	entry_filters = [["docstatus", "=", 1], ["purpose", "=", "Assign"]]

	for fieldname in ("location", "site", "employee", "allocation", "items_status"):
		if filters.get(fieldname):
			entry_filters.append([fieldname, "=", filters.get(fieldname)])

	if filters.get("from_date"):
		entry_filters.append(["posting_date", ">=", getdate(filters.from_date)])
	if filters.get("to_date"):
		entry_filters.append(["posting_date", "<=", getdate(filters.to_date)])

	return entry_filters
