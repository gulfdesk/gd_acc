import frappe


def execute():
	"""A room request that held its room is Permanent; every other request is Temporary."""
	frappe.db.sql(
		"""
		update `tabAccommodation Maintenance`
		set maintenance_type = if(ifnull(bed, '') = '' and set_room_under_maintenance = 1, 'Permanent', 'Temporary')
		"""
	)
