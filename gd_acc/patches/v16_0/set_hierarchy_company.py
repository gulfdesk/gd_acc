import frappe


def execute():
	"""Copy each location's company down to its sites, floors, rooms and beds that have none."""
	for doctype in ("Accommodation Site", "Accommodation Floor", "Accommodation Room", "Accommodation Bed"):
		frappe.db.sql(
			f"""
			UPDATE `tab{doctype}` c
			JOIN `tabAccommodation Location` l ON l.name = c.location
			SET c.company = l.company
			WHERE IFNULL(c.company, '') = ''
			"""
		)
