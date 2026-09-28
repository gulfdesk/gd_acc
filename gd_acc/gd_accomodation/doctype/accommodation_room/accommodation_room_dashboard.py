# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	"""Connections tab: records at this room, with a count each.

	A transfer is counted at the room the employee moved to.
	"""
	return {
		"fieldname": "room",
		"non_standard_fieldnames": {"Accommodation Transfer": "to_room"},
		"transactions": [
			{"label": _("Structure"), "items": ["Accommodation Bed"]},
			{"label": _("Stays"), "items": ["Accommodation Allocation", "Accommodation Transfer"]},
			{
				"label": _("Operations"),
				"items": ["Accommodation Maintenance", "Accommodation Item Entry", "Bed Status History"],
			},
		],
	}
