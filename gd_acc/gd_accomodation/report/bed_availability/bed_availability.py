# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Bed"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Accommodation Bed",
			"width": 220,
		},
		{
			"label": _("Bed Number"),
			"fieldname": "bed_number",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Room"),
			"fieldname": "room",
			"fieldtype": "Link",
			"options": "Accommodation Room",
			"width": 180,
		},
		{
			"label": _("Room Status"),
			"fieldname": "room_status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Room Type"),
			"fieldname": "room_type",
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
			"label": _("Accommodation Site"),
			"fieldname": "site",
			"fieldtype": "Link",
			"options": "Accommodation Site",
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
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Gender Restriction"),
			"fieldname": "gender_restriction",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Under Maintenance"),
			"fieldname": "under_maintenance",
			"fieldtype": "Check",
			"width": 90,
		},
		{
			"label": _("Hold Reason"),
			"fieldname": "hold_reason",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Bed Type"),
			"fieldname": "bed_type",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Current Employee"),
			"fieldname": "current_employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
	]


def get_data(filters):
	bed_filters = get_bed_filters(filters)
	if bed_filters is None:
		return []

	beds = frappe.get_all(
		"Accommodation Bed",
		filters=bed_filters,
		fields=[
			"name",
			"bed_number",
			"room",
			"floor",
			"site",
			"location",
			"status",
			"gender_restriction",
			"under_maintenance",
			"hold_reason",
			"bed_type",
			"current_employee",
		],
		order_by="location asc, site asc, floor asc, room asc, bed_number asc",
	)

	rooms = get_rooms([bed.room for bed in beds if bed.room])
	for bed in beds:
		room = rooms.get(bed.room) or {}
		bed.room_type = room.get("room_type")
		bed.room_status = room.get("occupancy_status")

	return beds


def get_bed_filters(filters):
	"""Bed filters for the selected scope, or None when nothing can match."""
	bed_filters = {}

	for fieldname in ("location", "site", "floor", "room"):
		if filters.get(fieldname):
			bed_filters[fieldname] = filters.get(fieldname)

	if filters.get("bed_status"):
		bed_filters["status"] = filters.bed_status

	for fieldname in ("bed_type", "gender_restriction"):
		if filters.get(fieldname):
			bed_filters[fieldname] = filters.get(fieldname)

	if filters.get("room_type"):
		rooms = get_rooms_of_type(filters)
		if not rooms:
			return None
		bed_filters["room"] = ["in", rooms]

	return bed_filters


def get_rooms_of_type(filters):
	room_filters = {"room_type": filters.room_type}
	for fieldname in ("location", "site", "floor"):
		if filters.get(fieldname):
			room_filters[fieldname] = filters.get(fieldname)
	if filters.get("room"):
		room_filters["name"] = filters.room

	return frappe.get_all("Accommodation Room", filters=room_filters, pluck="name")


def get_rooms(rooms):
	if not rooms:
		return {}

	return {
		room.name: room
		for room in frappe.get_all(
			"Accommodation Room",
			filters={"name": ["in", list(set(rooms))]},
			fields=["name", "room_type", "occupancy_status"],
		)
	}
