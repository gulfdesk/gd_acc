# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe

OLD_ROLE = "Accommodation Officer"
NEW_ROLE = "Accommodation User"


def execute():
	"""Rename the Officer role. Frappe moves every Link to the role with it."""
	if not frappe.db.exists("Role", OLD_ROLE):
		return

	merge = bool(frappe.db.exists("Role", NEW_ROLE))
	frappe.rename_doc("Role", OLD_ROLE, NEW_ROLE, force=True, merge=merge)
	remove_duplicate_role_rows()


def remove_duplicate_role_rows():
	# A user who held both roles before a merge now has two Has Role rows.
	frappe.db.sql(
		"""
		DELETE hr FROM `tabHas Role` hr
		JOIN `tabHas Role` keep
			ON keep.parent = hr.parent AND keep.parenttype = hr.parenttype
			AND keep.role = hr.role AND keep.name < hr.name
		WHERE hr.role = %s
		""",
		NEW_ROLE,
	)
