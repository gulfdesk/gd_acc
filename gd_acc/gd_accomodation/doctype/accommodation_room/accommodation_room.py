# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import update_room_occupancy


class AccommodationRoom(Document):
	def validate(self):
		self.validate_capacity()

	def validate_capacity(self):
		if not self.capacity or self.is_new():
			return

		beds = frappe.db.count("Accommodation Bed", {"room": self.name})
		if beds > self.capacity:
			frappe.throw(
				_("Capacity {0} is lower than the {1} bed(s) already in this room.").format(
					self.capacity, beds
				),
				title=_("Capacity Too Low"),
			)

	def on_update(self):
		update_room_occupancy(self.name)

	def on_trash(self):
		beds = frappe.db.count("Accommodation Bed", {"room": self.name})
		if beds:
			frappe.throw(
				_("Cannot delete {0} because {1} bed(s) belong to it.").format(frappe.bold(self.name), beds),
				title=_("Room In Use"),
			)

		allocations = frappe.db.count("Accommodation Allocation", {"room": self.name, "docstatus": 1})
		if allocations:
			frappe.throw(
				_("Cannot delete {0} because it is referenced by {1} accommodation allocation(s).").format(
					frappe.bold(self.name), allocations
				),
				title=_("History Exists"),
			)
