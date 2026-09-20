# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

HISTORY_FIELDS = (
	"change_datetime",
	"bed",
	"room",
	"floor",
	"site",
	"previous_status",
	"new_status",
	"reason",
	"employee",
	"employee_name",
	"allocation",
	"transfer",
	"changed_by",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Changed On"),
			"fieldname": "change_datetime",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": _("Bed"),
			"fieldname": "bed",
			"fieldtype": "Link",
			"options": "Accommodation Bed",
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
			"label": _("Floor"),
			"fieldname": "floor",
			"fieldtype": "Link",
			"options": "Accommodation Floor",
			"width": 160,
		},
		{
			"label": _("Accommodation Site"),
			"fieldname": "site",
			"fieldtype": "Link",
			"options": "Accommodation Site",
			"width": 180,
		},
		{
			"label": _("Previous Status"),
			"fieldname": "previous_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("New Status"),
			"fieldname": "new_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Reason"),
			"fieldname": "reason",
			"fieldtype": "Data",
			"width": 130,
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
			"label": _("Allocation"),
			"fieldname": "allocation",
			"fieldtype": "Link",
			"options": "Accommodation Allocation",
			"width": 170,
		},
		{
			"label": _("Transfer"),
			"fieldname": "transfer",
			"fieldtype": "Link",
			"options": "Accommodation Transfer",
			"width": 160,
		},
		{
			"label": _("Changed By"),
			"fieldname": "changed_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
	]


def get_data(filters):
	return frappe.get_all(
		"Bed Status History",
		filters=get_history_filters(filters),
		fields=list(HISTORY_FIELDS),
		order_by="change_datetime desc, creation desc",
	)


def get_history_filters(filters):
	history_filters = []

	for fieldname in ("bed", "location", "site", "reason"):
		if filters.get(fieldname):
			history_filters.append([fieldname, "=", filters.get(fieldname)])

	if filters.get("from_date"):
		history_filters.append(["change_datetime", ">=", f"{getdate(filters.from_date)} 00:00:00"])
	if filters.get("to_date"):
		history_filters.append(["change_datetime", "<=", f"{getdate(filters.to_date)} 23:59:59"])

	return history_filters
