# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe

RENAMES = (
	# The child goes first, so the parent's Table field points to an existing DocType.
	("Accommodation Assigned Item", "Accommodation Item Entry Detail"),
	("Accommodation Asset Assignment", "Accommodation Item Entry"),
)


def execute():
	"""Rename Asset Assignment and its child table before the model sync.

	rename_doc renames the tables and the DocType records and updates the Link
	options. The app files already carry the new names.
	"""
	for old, new in RENAMES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)
