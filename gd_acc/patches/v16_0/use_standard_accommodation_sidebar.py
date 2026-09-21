# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.utils import get_app_level_directory_path

NAVIGATION = (
	("Workspace Sidebar", "workspace_sidebar", "Accommodation Management"),
	("Desktop Icon", "desktop_icon", "Accommodation Management"),
)


def execute():
	"""Replace the sidebar and desktop icon Desk generated with the standard ones gd_acc ships.

	Desk v16 generates a sidebar holding only the Home link. Migrate skips the
	shipped file when that generated record is newer, so import it by force. A
	record that is already standard is left alone.
	"""
	for doctype, folder, name in NAVIGATION:
		if frappe.db.get_value(doctype, name, "standard"):
			continue

		path = os.path.join(get_app_level_directory_path(folder, "gd_acc"), f"{frappe.scrub(name)}.json")
		import_file_by_path(path, force=True, ignore_version=True)
