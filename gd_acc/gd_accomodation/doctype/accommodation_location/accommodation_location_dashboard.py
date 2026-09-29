# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	"""Connections tab: records at this location, with a count each.

	A transfer is counted at the location the employee moved to.
	"""
	return {
		"fieldname": "location",
		"non_standard_fieldnames": {"Accommodation Transfer": "to_location"},
		"transactions": [
			{
				"label": _("Structure"),
				"items": [
					"Accommodation Site",
					"Accommodation Floor",
					"Accommodation Room",
					"Accommodation Bed",
				],
			},
			{"label": _("Stays"), "items": ["Accommodation Allocation", "Accommodation Transfer"]},
			{
				"label": _("Operations"),
				"items": [
					"Accommodation Maintenance",
					"Accommodation Item Entry",
					"Accommodation Bulk Setup",
					"Bed Status History",
				],
			},
		],
	}
