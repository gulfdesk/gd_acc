# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, date_diff, getdate, today

ALLOCATION_FIELDS = (
	"name",
	"employee",
	"employee_name",
	"location",
	"site",
	"accommodation_type",
	"floor",
	"room",
	"bed",
	"start_date",
	"release_date",
	"proposed_release_date",
	"pending_release_reason",
	"status",
	"release_reason",
	"released_by_transfer",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Allocation"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Accommodation Allocation",
			"width": 170,
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
			"label": _("Type"),
			"fieldname": "accommodation_type",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Floor"),
			"fieldname": "floor",
			"fieldtype": "Link",
			"options": "Accommodation Floor",
			"width": 160,
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
			"label": _("Start Date"),
			"fieldname": "start_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Release Date"),
			"fieldname": "release_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Proposed Release Date"),
			"fieldname": "proposed_release_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Pending Release Reason"),
			"fieldname": "pending_release_reason",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Duration (Days)"),
			"fieldname": "duration_days",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Release Reason"),
			"fieldname": "release_reason",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Transfer"),
			"fieldname": "released_by_transfer",
			"fieldtype": "Link",
			"options": "Accommodation Transfer",
			"width": 160,
		},
	]


def get_data(filters):
	allocations = frappe.get_all(
		"Accommodation Allocation",
		filters=get_allocation_filters(filters),
		or_filters=get_or_filters(filters),
		fields=list(ALLOCATION_FIELDS),
		order_by="start_date desc, employee_name asc",
	)

	as_of_date = getdate(today())
	for allocation in allocations:
		allocation.duration_days = get_duration(allocation, as_of_date)

	return allocations


def get_allocation_filters(filters):
	"""Every allocation that is not cancelled, narrowed to the selected scope."""
	allocation_filters = [
		["docstatus", "<", 2],
		["status", "!=", "Cancelled"],
	]

	for fieldname in ("employee", "location", "site"):
		if filters.get(fieldname):
			allocation_filters.append([fieldname, "=", filters.get(fieldname)])

	if filters.get("allocation_status"):
		allocation_filters.append(["status", "=", filters.allocation_status])

	# An allocation overlaps the window when it started on or before the end of it.
	if filters.get("to_date"):
		allocation_filters.append(["start_date", "<=", getdate(filters.to_date)])

	return allocation_filters


def get_or_filters(filters):
	"""Keep allocations still running (no release date) or released inside the window."""
	if not filters.get("from_date"):
		return []

	return [
		["release_date", "is", "not set"],
		["release_date", ">=", getdate(filters.from_date)],
	]


def get_duration(allocation, as_of_date):
	if not allocation.start_date:
		return 0

	end_date = getdate(allocation.release_date) if allocation.release_date else as_of_date
	return cint(date_diff(end_date, getdate(allocation.start_date)))
