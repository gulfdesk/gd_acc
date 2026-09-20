# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Roles and Employee customisations for the GD Accomodation module.

Kept idempotent so it can run from a patch on every migrate without
disturbing anything an administrator has changed afterwards.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ACCOMMODATION_ROLES = ("Accommodation Manager", "Accommodation Officer", "Maintenance User")

EMPLOYEE_CUSTOM_FIELDS = {
	"Employee": [
		{
			"fieldname": "accommodation_tab",
			"fieldtype": "Tab Break",
			"label": "Accommodation",
			"insert_after": "old_parent",
		},
		{
			"fieldname": "accommodation_status",
			"fieldtype": "Select",
			"label": "Accommodation Status",
			"options": "Not Provided\nProvided\nAllowance",
			# Not Provided is the baseline every employee starts at, not a
			# decision someone made. Provided/Allowance only ever come from
			# a submitted Accommodation Entitlement.
			"default": "Not Provided",
			"in_standard_filter": 1,
			"read_only": 1,
			"description": (
				"Derived from the employee's active Accommodation Entitlement. "
				"Use Create Entitlement below to change it."
			),
			"insert_after": "accommodation_tab",
		},
		{
			"fieldname": "current_accommodation_entitlement",
			"fieldtype": "Link",
			"label": "Current Entitlement",
			"options": "Accommodation Entitlement",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "accommodation_status",
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
			"depends_on": 'eval:doc.accommodation_status == "Provided"',
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
			"fieldname": "accommodation_allowance_section",
			"fieldtype": "Section Break",
			"label": "Accommodation Allowance",
			"depends_on": 'eval:doc.accommodation_status == "Allowance"',
			"insert_after": "accommodation_expected_end_date",
		},
		{
			"fieldname": "accommodation_allowance_type",
			"read_only": 1,
			"fieldtype": "Select",
			"label": "Allowance Type",
			"options": "\nMonthly\nQuarterly\nAnnual\nOne Time",
			"insert_after": "accommodation_allowance_section",
		},
		{
			"fieldname": "accommodation_allowance_amount",
			"read_only": 1,
			"fieldtype": "Currency",
			"label": "Allowance Amount",
			"options": "accommodation_allowance_currency",
			"insert_after": "accommodation_allowance_type",
		},
		{
			"fieldname": "accommodation_allowance_currency",
			"read_only": 1,
			"fieldtype": "Link",
			"label": "Currency",
			"options": "Currency",
			"insert_after": "accommodation_allowance_amount",
		},
		{
			"fieldname": "accommodation_allowance_column",
			"fieldtype": "Column Break",
			"insert_after": "accommodation_allowance_currency",
		},
		{
			"fieldname": "accommodation_allowance_from_date",
			"read_only": 1,
			"fieldtype": "Date",
			"label": "Effective From",
			"insert_after": "accommodation_allowance_column",
		},
		{
			"fieldname": "accommodation_allowance_to_date",
			"read_only": 1,
			"fieldtype": "Date",
			"label": "Effective To",
			"insert_after": "accommodation_allowance_from_date",
		},
		{
			"fieldname": "accommodation_allowance_component",
			"read_only": 1,
			"fieldtype": "Link",
			"label": "Payroll Salary Component",
			"options": "Salary Component",
			"description": "Salary component used to pay this allowance, where payroll is configured.",
			"insert_after": "accommodation_allowance_to_date",
		},
		{
			"fieldname": "accommodation_history_section",
			"fieldtype": "Section Break",
			"label": "Accommodation History",
			"insert_after": "accommodation_allowance_component",
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
	backfill_default_accommodation_status()


def create_accommodation_roles():
	for role_name in ACCOMMODATION_ROLES:
		if frappe.db.exists("Role", role_name):
			continue

		role = frappe.new_doc("Role")
		role.update({"role_name": role_name, "desk_access": 1})
		role.flags.ignore_permissions = True
		role.insert()


def backfill_default_accommodation_status():
	"""Give every employee the Not Provided baseline until a real decision is made.

	Not Provided is the default state, not a decision someone made - it just
	means nobody has assigned company accommodation or an allowance yet.
	Runs on every migrate, so it is safe and self healing.
	"""
	frappe.db.sql(
		"""
		update `tabEmployee`
		set accommodation_status = 'Not Provided'
		where ifnull(accommodation_status, '') = ''
		"""
	)
