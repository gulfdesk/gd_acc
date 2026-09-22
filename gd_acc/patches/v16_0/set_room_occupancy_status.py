import frappe

from gd_acc.gd_accomodation.accommodation_utils import update_room_occupancy


def execute():
	"""Run the room roll-up once so every room gets its Occupancy Status."""
	for room in frappe.get_all("Accommodation Room", pluck="name"):
		update_room_occupancy(room)
