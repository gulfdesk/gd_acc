# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today

MAINTENANCE_FIELDS = (
	"name",
	"subject",
	"issue_type",
	"priority",
	"status",
	"location",
	"site",
	"floor",
	"room",
	"bed",
	"reported_by",
	"reported_on",
	"assigned_to",
	"expected_completion_date",
	"resolution_date",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(data)


def get_columns():
	return [
		{
			"label": _("Request"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Accommodation Maintenance",
			"width": 170,
		},
		{
			"label": _("Subject"),
			"fieldname": "subject",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Issue Type"),
			"fieldname": "issue_type",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Priority"),
			"fieldname": "priority",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
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
			"label": _("Reported By"),
			"fieldname": "reported_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{
			"label": _("Reported On"),
			"fieldname": "reported_on",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Assigned To"),
			"fieldname": "assigned_to",
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{
			"label": _("Expected Completion"),
			"fieldname": "expected_completion_date",
			"fieldtype": "Date",
			"width": 150,
		},
		{
			"label": _("Resolution Date"),
			"fieldname": "resolution_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": _("Days Open"),
			"fieldname": "days_open",
			"fieldtype": "Int",
			"width": 100,
		},
	]


def get_data(filters):
	requests = frappe.get_all(
		"Accommodation Maintenance",
		filters=get_maintenance_filters(filters),
		fields=list(MAINTENANCE_FIELDS),
		order_by="reported_on desc, name desc",
	)

	as_of_date = getdate(today())
	for request in requests:
		request.days_open = get_days_open(request, as_of_date)

	return requests


def get_maintenance_filters(filters):
	maintenance_filters = []

	for fieldname in ("location", "site", "issue_type", "priority"):
		if filters.get(fieldname):
			maintenance_filters.append([fieldname, "=", filters.get(fieldname)])

	if filters.get("maintenance_status"):
		maintenance_filters.append(["status", "=", filters.maintenance_status])

	if filters.get("from_date"):
		maintenance_filters.append(["reported_on", ">=", getdate(filters.from_date)])
	if filters.get("to_date"):
		maintenance_filters.append(["reported_on", "<=", getdate(filters.to_date)])

	return maintenance_filters


def get_days_open(request, as_of_date):
	"""Days between reporting and resolution, or up to today while unresolved."""
	if not request.reported_on:
		return 0

	end_date = getdate(request.resolution_date) if request.resolution_date else as_of_date
	return cint(date_diff(end_date, getdate(request.reported_on)))


def get_report_summary(data):
	def count(status):
		return sum(1 for row in data if row.status == status)

	resolved = [row for row in data if row.resolution_date and row.reported_on]
	average_days = flt(sum(cint(row.days_open) for row in resolved) / len(resolved), 1) if resolved else 0.0

	return [
		{"value": count("Open"), "label": _("Open"), "datatype": "Int", "indicator": "Red"},
		{"value": count("In Progress"), "label": _("In Progress"), "datatype": "Int", "indicator": "Orange"},
		{"value": count("Resolved"), "label": _("Resolved"), "datatype": "Int", "indicator": "Green"},
		{
			"value": average_days,
			"label": _("Average Days to Resolve"),
			"datatype": "Float",
			"indicator": "Blue",
		},
	]
