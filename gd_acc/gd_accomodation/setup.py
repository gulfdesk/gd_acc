# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Roles and Employee customisations for the GD Accomodation module.

Kept idempotent so it can run from a patch on every migrate without
disturbing anything an administrator has changed afterwards.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ACCOMMODATION_ROLES = ("Accommodation Manager", "Accommodation User", "Maintenance User")

EMPLOYEE_CUSTOM_FIELDS = {
	"Employee": [
		{
			"fieldname": "accommodation_tab",
			"fieldtype": "Tab Break",
			"label": "Accommodation",
			"insert_after": "old_parent",
		},
		{
			"fieldname": "current_accommodation_entitlement",
			"fieldtype": "Link",
			"label": "Current Entitlement",
			"options": "Accommodation Entitlement",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "accommodation_tab",
		},
		{
			"fieldname": "accommodation_actions_html",
			"fieldtype": "HTML",
			"label": "Accommodation Actions",
			"insert_after": "current_accommodation_entitlement",
		},
		{
			"fieldname": "current_accommodation_section",
			"fieldtype": "Section Break",
			"label": "Current Accommodation",
			"depends_on": "eval:doc.current_accommodation_allocation",
			"insert_after": "accommodation_actions_html",
		},
		{
			"fieldname": "current_accommodation_allocation",
			"fieldtype": "Link",
			"label": "Current Allocation",
			"options": "Accommodation Allocation",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_section",
		},
		{
			"fieldname": "current_accommodation_location",
			"fieldtype": "Link",
			"label": "Location",
			"options": "Accommodation Location",
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
			"insert_after": "current_accommodation_allocation",
		},
		{
			"fieldname": "current_accommodation_site",
			"fieldtype": "Link",
			"label": "Accommodation Site",
			"options": "Accommodation Site",
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
			"insert_after": "current_accommodation_location",
		},
		{
			"fieldname": "current_accommodation_type",
			"fieldtype": "Data",
			"label": "Accommodation Type",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_site",
		},
		{
			"fieldname": "current_accommodation_sub_type",
			"fieldtype": "Data",
			"label": "Sub-Type",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_type",
		},
		{
			"fieldname": "current_accommodation_column",
			"fieldtype": "Column Break",
			"insert_after": "current_accommodation_sub_type",
		},
		{
			"fieldname": "current_accommodation_floor",
			"fieldtype": "Link",
			"label": "Floor",
			"options": "Accommodation Floor",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_column",
		},
		{
			"fieldname": "current_accommodation_room",
			"fieldtype": "Link",
			"label": "Room",
			"options": "Accommodation Room",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_floor",
		},
		{
			"fieldname": "current_accommodation_bed",
			"fieldtype": "Link",
			"label": "Bed",
			"options": "Accommodation Bed",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_room",
		},
		{
			"fieldname": "accommodation_start_date",
			"fieldtype": "Date",
			"label": "Allocation Start Date",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "current_accommodation_bed",
		},
		{
			"fieldname": "accommodation_expected_end_date",
			"fieldtype": "Date",
			"label": "Expected End Date",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "accommodation_start_date",
		},
		{
			"fieldname": "accommodation_history_section",
			"fieldtype": "Section Break",
			"label": "Accommodation History",
			"insert_after": "accommodation_expected_end_date",
		},
		{
			"fieldname": "accommodation_history_html",
			"fieldtype": "HTML",
			"label": "Accommodation History",
			"insert_after": "accommodation_history_section",
		},
	]
}


def setup_accommodation():
	create_accommodation_roles()
	create_custom_fields(EMPLOYEE_CUSTOM_FIELDS, ignore_validate=True, update=True)


def create_accommodation_roles():
	for role_name in ACCOMMODATION_ROLES:
		if frappe.db.exists("Role", role_name):
			continue

		role = frappe.new_doc("Role")
		role.update({"role_name": role_name, "desk_access": 1})
		role.flags.ignore_permissions = True
		role.insert()

