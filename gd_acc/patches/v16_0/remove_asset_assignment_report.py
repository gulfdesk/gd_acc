# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Delete the report that Accommodation Item Report replaces."""
	if frappe.db.exists("Report", "Accommodation Asset Assignment Report"):
		frappe.delete_doc(
			"Report", "Accommodation Asset Assignment Report", force=True, ignore_missing=True
		)
