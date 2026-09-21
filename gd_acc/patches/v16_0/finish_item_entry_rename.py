# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Give every Item Entry carried over from Asset Assignment the Assign purpose.

	An old record stays a Draft. The officer reviews it and submits it.
	"""
	frappe.db.sql(
		"""UPDATE `tabAccommodation Item Entry`
		SET purpose = 'Assign' WHERE IFNULL(purpose, '') = ''"""
	)
