import frappe


def execute():
	"""Set Any on every site without a Gender Restriction, then copy each site's value down."""
	frappe.db.sql(
		"UPDATE `tabAccommodation Site` SET gender_restriction = 'Any' WHERE IFNULL(gender_restriction, '') = ''"
	)
	for doctype in ("Accommodation Floor", "Accommodation Room", "Accommodation Bed"):
		frappe.db.sql(
			f"""
			UPDATE `tab{doctype}` c
			JOIN `tabAccommodation Site` s ON s.name = c.site
			SET c.gender_restriction = s.gender_restriction
			"""
		)
