# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from gd_acc.gd_accomodation.accommodation_utils import resolve_hierarchy, update_bed_state

OPEN_STATUSES = ("Open", "In Progress")
CLOSED_STATUSES = ("Resolved", "Closed", "Cancelled")


class AccommodationMaintenance(Document):
	def validate(self):
		self.apply_hierarchy()
		self.validate_dates()
		self.validate_bed_is_free()

	def apply_hierarchy(self):
		resolved = resolve_hierarchy(
			location=self.location,
			site=self.site,
			floor=self.floor,
			room=self.room,
			bed=self.bed,
		)
		self.location = resolved["location"]
		self.site = resolved["site"]
		self.floor = resolved["floor"]
		self.room = resolved["room"]

	def validate_dates(self):
		if self.resolution_date and getdate(self.resolution_date) < getdate(self.reported_on):
			frappe.throw(_("Resolution Date cannot be before Reported On."), title=_("Invalid Dates"))

	def validate_bed_is_free(self):
		"""An occupied bed keeps its occupancy; maintenance never evicts an employee."""
		if not (self.set_bed_under_maintenance and self.bed and self.status in OPEN_STATUSES):
			return

		bed_status = frappe.db.get_value("Accommodation Bed", self.bed, "status")
		if bed_status == "Occupied":
			frappe.throw(
				_(
					"Bed {0} is occupied and cannot be put under maintenance. "
					"Transfer or release the employee first, or clear Set Bed Under Maintenance."
				).format(frappe.bold(self.bed)),
				title=_("Bed Occupied"),
			)

	def on_update(self):
		self.apply_bed_maintenance_state()

	def apply_bed_maintenance_state(self):
		if not self.bed:
			return

		bed_status = frappe.db.get_value("Accommodation Bed", self.bed, "status")

		if self.set_bed_under_maintenance and self.status in OPEN_STATUSES:
			if bed_status == "Available":
				update_bed_state(
					self.bed,
					status="Maintenance",
					reason="Maintenance",
					remarks=_("Under maintenance request {0}.").format(self.name),
				)
		elif self.status in CLOSED_STATUSES and bed_status == "Maintenance":
			update_bed_state(
				self.bed,
				status="Available",
				reason="Maintenance",
				remarks=_("Maintenance request {0} is {1}.").format(self.name, self.status),
			)
