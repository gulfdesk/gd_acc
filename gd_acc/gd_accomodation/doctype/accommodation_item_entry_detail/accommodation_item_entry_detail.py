# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AccommodationItemEntryDetail(Document):
	pass


def on_doctype_update():
	# Indexed from the child's own hook: this table does not exist yet when the parent syncs on a fresh install.
	frappe.db.add_index("Accommodation Item Entry Detail", ["against_detail", "docstatus"])
