# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import (
	BED_STATUS_AVAILABLE,
	BED_STATUS_BLOCKED,
	count_current_stays,
	get_site_gender,
	update_bed_state,
	update_room_occupancy,
)


class AccommodationRoom(Document):
	def validate(self):
		self.gender_restriction = get_site_gender(self.site)
		self.validate_capacity()
		self.validate_hold()

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

	def validate_hold(self):
		"""A Blocked room is never occupied and never under maintenance at the same time."""
		if not self.is_blocked:
			self.hold_reason = None
			return
		if not self.has_value_changed("is_blocked"):
			return

		if self.under_maintenance:
			frappe.throw(
				_("Room {0} is under maintenance. Block it after the maintenance closes.").format(
					frappe.bold(self.name)
				),
				title=_("Room Under Maintenance"),
			)

		stays = count_current_stays(self.name)
		if stays:
			frappe.throw(
				_("Room {0} houses {1} employee(s). A Blocked room cannot be occupied.").format(
					frappe.bold(self.name), stays
				),
				title=_("Room Occupied"),
			)

	def on_update(self):
		if self.has_value_changed("is_blocked"):
			self.apply_room_block()
		update_room_occupancy(self.name)

	def apply_room_block(self):
		"""Block the free beds, or release the beds this room blocked. A bed blocked by itself keeps its hold."""
		if self.is_blocked:
			beds = frappe.get_all(
				"Accommodation Bed", filters={"room": self.name, "status": BED_STATUS_AVAILABLE}, pluck="name"
			)
			for bed in beds:
				update_bed_state(
					bed,
					status=BED_STATUS_BLOCKED,
					held_by_room=1,
					hold_reason=self.hold_reason,
					reason="Hold",
					remarks=_("Room {0} blocked.").format(self.name),
				)
			return

		beds = frappe.get_all(
			"Accommodation Bed",
			filters={"room": self.name, "status": BED_STATUS_BLOCKED, "held_by_room": 1},
			pluck="name",
		)
		for bed in beds:
			update_bed_state(
				bed,
				status=BED_STATUS_AVAILABLE,
				held_by_room=0,
				hold_reason=None,
				reason="Hold Released",
				remarks=_("Room {0} unblocked.").format(self.name),
			)

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
