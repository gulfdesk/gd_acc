# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import (
	log_bed_status_change,
	update_room_occupancy,
)


class AccommodationBed(Document):
	def validate(self):
		self.validate_room_capacity()
		self.validate_status_change()
		self.validate_room_change()

	def validate_room_capacity(self):
		capacity = frappe.db.get_value("Accommodation Room", self.room, "capacity")
		if not capacity:
			return

		existing = frappe.db.count("Accommodation Bed", {"room": self.room, "name": ("!=", self.name)})
		if existing + 1 > capacity:
			frappe.throw(
				_("Room {0} has a capacity of {1} bed(s).").format(frappe.bold(self.room), capacity),
				title=_("Room Full"),
			)

	def validate_status_change(self):
		"""Occupancy is owned by Accommodation Allocation, never set by hand."""
		before = self.get_doc_before_save()

		if self.is_new() or not before:
			if self.status == "Occupied":
				frappe.throw(
					_("A bed cannot be created as Occupied. Submit an Accommodation Allocation instead."),
					title=_("Not Allowed"),
				)
			return

		if before.status == self.status:
			return

		if self.status == "Occupied":
			frappe.throw(
				_("A bed is marked Occupied only by submitting an Accommodation Allocation."),
				title=_("Not Allowed"),
			)

		if before.status == "Occupied":
			frappe.throw(
				_("Bed {0} is occupied by {1}. Release allocation {2} before changing its status.").format(
					frappe.bold(self.name),
					frappe.bold(before.current_employee_name or before.current_employee),
					frappe.bold(before.current_allocation),
				),
				title=_("Bed Occupied"),
			)

	def validate_room_change(self):
		before = self.get_doc_before_save()
		if not before or before.room == self.room:
			return

		if before.status == "Occupied":
			frappe.throw(_("An occupied bed cannot be moved to another room."), title=_("Bed Occupied"))

	def on_update(self):
		before = self.get_doc_before_save()

		if before and before.status != self.status:
			log_bed_status_change(
				bed=self.name,
				previous_status=before.status,
				new_status=self.status,
				reason="Manual Update",
				remarks=self.remarks,
			)

		update_room_occupancy(self.room)
		if before and before.room != self.room:
			update_room_occupancy(before.room)

	def on_trash(self):
		if self.status == "Occupied":
			frappe.throw(
				_("Cannot delete an occupied bed. Release allocation {0} first.").format(
					frappe.bold(self.current_allocation)
				),
				title=_("Bed Occupied"),
			)

		allocations = frappe.db.count("Accommodation Allocation", {"bed": self.name, "docstatus": 1})
		if allocations:
			frappe.throw(
				_("Cannot delete {0} because it is referenced by {1} accommodation allocation(s).").format(
					frappe.bold(self.name), allocations
				),
				title=_("History Exists"),
			)

	def after_delete(self):
		update_room_occupancy(self.room)
