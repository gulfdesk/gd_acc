# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Roles and Employee customisations for the GD Accomodation module.

Kept idempotent so it can run from a patch on every migrate without
disturbing anything an administrator has changed afterwards.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ACCOMMODATION_ROLES = ("Accommodation Manager", "Accommodation User", "Maintenance User")

# The tab holds one HTML panel. Employee JS draws it from the allocations and entitlements.
EMPLOYEE_CUSTOM_FIELDS = {
	"Employee": [
		{
			"fieldname": "accommodation_tab",
			"fieldtype": "Tab Break",
			"label": "Accommodation",
			"insert_after": "old_parent",
		},
		{
			"fieldname": "accommodation_html",
			"fieldtype": "HTML",
			"label": "Accommodation",
			"insert_after": "accommodation_tab",
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

