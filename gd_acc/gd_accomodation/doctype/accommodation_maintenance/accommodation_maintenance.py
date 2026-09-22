# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from gd_acc.gd_accomodation.accommodation_utils import (
	BED_STATUS_AVAILABLE,
	BED_STATUS_BLOCKED,
	BED_STATUS_MAINTENANCE,
	BED_STATUS_OCCUPIED,
	resolve_hierarchy,
	update_bed_state,
	update_room_occupancy,
)

OPEN_STATUSES = ("Open", "In Progress")
MANAGER_ROLES = ("Accommodation Manager", "System Manager")


class AccommodationMaintenance(Document):
	def validate(self):
		self.validate_cancel_right()
		self.apply_hierarchy()
		self.validate_dates()
		self.validate_hold_target()

	def validate_cancel_right(self):
		"""Only a manager sets the status to Cancelled, on a new record too."""
		if self.status != "Cancelled":
			return
		before = self.get_doc_before_save()
		if before and before.status == "Cancelled":
			return
		if not set(MANAGER_ROLES) & set(frappe.get_roles()):
			frappe.throw(
				_("Only an Accommodation Manager can cancel a maintenance request."),
				frappe.PermissionError,
				title=_("Not Permitted"),
			)

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

	def validate_hold_target(self):
		"""Maintenance may hold an occupied bed or room, never a Blocked one."""
		if self.bed:
			self.set_room_under_maintenance = 0

		if not self.is_holding():
			return

		if self.bed:
			if frappe.db.get_value("Accommodation Bed", self.bed, "status") == BED_STATUS_BLOCKED:
				frappe.throw(
					_("Bed {0} is Blocked. Clear the hold before maintenance starts.").format(
						frappe.bold(self.bed)
					),
					title=_("Bed Blocked"),
				)
		elif self.room and frappe.db.get_value("Accommodation Room", self.room, "is_blocked"):
			frappe.throw(
				_("Room {0} is Blocked. Clear the hold before maintenance starts.").format(frappe.bold(self.room)),
				title=_("Room Blocked"),
			)

	def is_holding(self):
		"""True while this record is open and holds a bed or a whole room."""
		if self.status not in OPEN_STATUSES:
			return False
		if self.bed:
			return bool(self.set_bed_under_maintenance)
		return bool(self.room and self.set_room_under_maintenance)

	def hold_was_set(self, fieldname):
		"""True when the flag was set before this save, so a cleared flag still releases the hold."""
		before = self.get_doc_before_save()
		return bool(before and before.get(fieldname))

	def on_update(self):
		self.apply_maintenance_state()

	def on_trash(self):
		if not self.is_holding():
			return
		if self.bed:
			release_bed_maintenance(self.bed, exclude=self.name)
		else:
			release_room_maintenance(self.room, exclude=self.name)

	def apply_maintenance_state(self):
		if self.bed:
			if self.set_bed_under_maintenance or self.hold_was_set("set_bed_under_maintenance"):
				self.apply_bed_hold()
		elif self.room and (
			self.set_room_under_maintenance or self.hold_was_set("set_room_under_maintenance")
		):
			self.apply_room_hold()

	def apply_bed_hold(self):
		if self.is_holding():
			hold_bed(self.bed, self.name)
		else:
			release_bed_maintenance(self.bed, exclude=self.name)

	def apply_room_hold(self):
		if not self.is_holding():
			release_room_maintenance(self.room, exclude=self.name)
			return

		frappe.db.set_value("Accommodation Room", self.room, "under_maintenance", 1, update_modified=False)
		beds = frappe.get_all(
			"Accommodation Bed",
			filters={"room": self.room, "status": ("in", (BED_STATUS_AVAILABLE, BED_STATUS_OCCUPIED))},
			pluck="name",
		)
		for bed in beds:
			hold_bed(bed, self.name)
		update_room_occupancy(self.room)


def hold_bed(bed, record):
	"""Put the bed under maintenance. An occupant stays; the bed only gets the flag."""
	row = frappe.db.get_value(
		"Accommodation Bed",
		bed,
		["status", "under_maintenance", "current_employee", "current_allocation", "occupied_since"],
		as_dict=True,
	)
	if not row or row.under_maintenance:
		return

	hold_reason = _("Maintenance {0}").format(record)
	if row.status == BED_STATUS_AVAILABLE:
		update_bed_state(
			bed,
			status=BED_STATUS_MAINTENANCE,
			under_maintenance=1,
			hold_reason=hold_reason,
			reason="Maintenance",
			remarks=_("Under maintenance request {0}.").format(record),
		)
	elif row.status == BED_STATUS_OCCUPIED:
		update_bed_state(
			bed,
			status=BED_STATUS_OCCUPIED,
			employee=row.current_employee,
			allocation=row.current_allocation,
			occupied_since=row.occupied_since,
			under_maintenance=1,
			hold_reason=hold_reason,
		)


def bed_still_held(bed, exclude):
	"""Return an open record other than exclude that holds the bed or its room, or None."""
	open_records = {"status": ("in", OPEN_STATUSES), "name": ("!=", exclude)}
	record = frappe.db.get_value(
		"Accommodation Maintenance",
		{**open_records, "bed": bed, "set_bed_under_maintenance": 1},
		"name",
	)
	if record:
		return record

	room = frappe.db.get_value("Accommodation Bed", bed, "room")
	return frappe.db.get_value(
		"Accommodation Maintenance",
		{**open_records, "room": room, "bed": ("is", "not set"), "set_room_under_maintenance": 1},
		"name",
	)


def release_bed_maintenance(bed, exclude):
	"""Release the bed unless another open record still holds it."""
	row = frappe.db.get_value(
		"Accommodation Bed",
		bed,
		["status", "under_maintenance", "current_employee", "current_allocation", "occupied_since"],
		as_dict=True,
	)
	if not row:
		return

	holder = bed_still_held(bed, exclude)
	if holder:
		# The bed stays held. Its reason names the record that still holds it.
		frappe.db.set_value(
			"Accommodation Bed", bed, "hold_reason", _("Maintenance {0}").format(holder), update_modified=False
		)
		return

	if row.status == BED_STATUS_MAINTENANCE:
		update_bed_state(
			bed,
			status=BED_STATUS_AVAILABLE,
			under_maintenance=0,
			hold_reason=None,
			reason="Maintenance",
			remarks=_("Maintenance request {0} released the bed.").format(exclude),
		)
	elif row.under_maintenance:
		update_bed_state(
			bed,
			status=row.status,
			employee=row.current_employee,
			allocation=row.current_allocation,
			occupied_since=row.occupied_since,
			under_maintenance=0,
			hold_reason=None,
		)


def release_room_maintenance(room, exclude):
	"""Release the room and its beds unless another open room-level record still holds the room."""
	if frappe.db.exists(
		"Accommodation Maintenance",
		{
			"room": room,
			"bed": ("is", "not set"),
			"set_room_under_maintenance": 1,
			"status": ("in", OPEN_STATUSES),
			"name": ("!=", exclude),
		},
	):
		return

	frappe.db.set_value("Accommodation Room", room, "under_maintenance", 0, update_modified=False)
	beds = frappe.get_all("Accommodation Bed", filters={"room": room, "under_maintenance": 1}, pluck="name")
	for bed in beds:
		release_bed_maintenance(bed, exclude)
	update_room_occupancy(room)
