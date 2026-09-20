# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import update_floor_occupancy


class AccommodationFloor(Document):
	def validate(self):
		self.location = frappe.db.get_value("Accommodation Site", self.site, "location")

	def on_update(self):
		update_floor_occupancy(self.name)

	def on_trash(self):
		rooms = frappe.db.count("Accommodation Room", {"floor": self.name})
		if rooms:
			frappe.throw(
				_("Cannot delete {0} because {1} room(s) belong to it.").format(
					frappe.bold(self.name), rooms
				),
				title=_("Floor In Use"),
			)
