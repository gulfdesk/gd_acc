# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

GROUP_LEVELS = {
	"Location": {"fieldname": "location", "label": "Location", "options": "Accommodation Location"},
	"Site": {"fieldname": "site", "label": "Accommodation Site", "options": "Accommodation Site"},
	"Floor": {"fieldname": "floor", "label": "Floor", "options": "Accommodation Floor"},
	"Room": {"fieldname": "room", "label": "Room", "options": "Accommodation Room"},
}

STATUS_FIELDS = {
	"Available": "available",
	"Occupied": "occupied",
	"Reserved": "reserved",
	"Maintenance": "maintenance",
	"Blocked": "blocked",
	"Inactive": "inactive",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	level = GROUP_LEVELS.get(filters.get("group_by") or "Site", GROUP_LEVELS["Site"])
	data = get_data(filters, level)
	return get_columns(level), data, None, None, get_report_summary(data)


def get_columns(level):
	return [
		{
			"label": _(level["label"]),
			"fieldname": level["fieldname"],
			"fieldtype": "Link",
			"options": level["options"],
			"width": 240,
		},
		{
			"label": _("Total Beds"),
			"fieldname": "total_beds",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Occupied"),
			"fieldname": "occupied",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Available"),
			"fieldname": "available",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Reserved"),
			"fieldname": "reserved",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Maintenance"),
			"fieldname": "maintenance",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Blocked"),
			"fieldname": "blocked",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Inactive"),
			"fieldname": "inactive",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Occupancy %"),
			"fieldname": "occupancy_percent",
			"fieldtype": "Percent",
			"width": 120,
		},
	]


def get_data(filters, level):
	bed_filters = get_bed_filters(filters)
	if bed_filters is None:
		return []

	group_field = level["fieldname"]
	counts = frappe.get_all(
		"Accommodation Bed",
		filters=bed_filters,
		fields=[group_field, "status", {"COUNT": "name", "as": "bed_count"}],
		group_by=f"{group_field}, status",
	)

	grouped = {}
	for row in counts:
		key = row.get(group_field)
		summary = grouped.setdefault(key, new_group(group_field, key))
		bed_count = cint(row.bed_count)
		summary.total_beds += bed_count
		if row.status in STATUS_FIELDS:
			summary[STATUS_FIELDS[row.status]] += bed_count

	data = []
	for key in sorted(grouped, key=lambda value: (value is None, value or "")):
		summary = grouped[key]
		summary.occupancy_percent = get_percent(summary.occupied, summary.total_beds)
		data.append(summary)

	return data


def new_group(group_field, key):
	return frappe._dict(
		{
			group_field: key,
			"total_beds": 0,
			"occupied": 0,
			"available": 0,
			"reserved": 0,
			"maintenance": 0,
			"blocked": 0,
			"inactive": 0,
			"occupancy_percent": 0.0,
		}
	)


def get_bed_filters(filters):
	"""Bed filters for the selected scope, or None when nothing can match."""
	bed_filters = {}

	for fieldname in ("location", "site", "gender_restriction"):
		if filters.get(fieldname):
			bed_filters[fieldname] = filters.get(fieldname)

	if filters.get("accommodation_type"):
		sites = get_sites_of_type(filters)
		if not sites:
			return None
		bed_filters["site"] = ["in", sites]

	return bed_filters


def get_sites_of_type(filters):
	site_filters = {"accommodation_type": filters.accommodation_type}
	if filters.get("location"):
		site_filters["location"] = filters.location
	if filters.get("site"):
		site_filters["name"] = filters.site

	return frappe.get_all("Accommodation Site", filters=site_filters, pluck="name")


def get_percent(part, total):
	return flt(cint(part) * 100.0 / cint(total), 2) if cint(total) else 0.0


def get_report_summary(data):
	total_beds = sum(cint(row.total_beds) for row in data)
	occupied = sum(cint(row.occupied) for row in data)
	available = sum(cint(row.available) for row in data)
	blocked = sum(cint(row.blocked) for row in data)

	return [
		{"value": total_beds, "label": _("Total Beds"), "datatype": "Int", "indicator": "Blue"},
		{"value": occupied, "label": _("Occupied"), "datatype": "Int", "indicator": "Orange"},
		{"value": available, "label": _("Available"), "datatype": "Int", "indicator": "Green"},
		{"value": blocked, "label": _("Blocked"), "datatype": "Int", "indicator": "Red"},
		{
			"value": get_percent(occupied, total_beds),
			"label": _("Occupancy %"),
			"datatype": "Percent",
			"indicator": "Blue",
		},
	]
