# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from gd_acc.gd_accomodation.accommodation_utils import (
	BED_STATUS_AVAILABLE,
	BED_STATUS_BLOCKED,
	BED_STATUS_MAINTENANCE,
	BED_STATUS_OCCUPIED,
	CURRENT_STAY_STATUSES,
	resolve_hierarchy,
	update_bed_state,
	update_room_occupancy,
)

OPEN_STATUSES = ("Open", "In Progress")
ROOM_PERMANENT = "Permanent"
# A finished request is locked; only a System Manager changes it, from the list's Actions > Edit.
LOCKED_STATUSES = ("Resolved", "Closed", "Cancelled")
RESOLVED_STATUSES = ("Resolved", "Closed")
# While a request holds its bed or room, the place and the hold stay as they are.
HOLD_FIELDS = ("location", "site", "floor", "room", "bed", "maintenance_type", "set_bed_under_maintenance")
MANAGER_ROLES = ("Accommodation Manager", "HR Manager", "System Manager")


class AccommodationMaintenance(Document):
	def validate(self):
		self.validate_not_locked()
		self.validate_hold_unchanged()
		self.validate_cancel_right()
		self.apply_hierarchy()
		self.validate_dates()
		self.validate_hold_target()

	def validate_not_locked(self):
		before = self.get_doc_before_save()
		if not before or before.status not in LOCKED_STATUSES:
			return
		if "System Manager" in frappe.get_roles():
			return
		frappe.throw(
			_(
				"Maintenance request {0} is {1} and can no longer be edited. A System Manager can "
				"change it from the list: select it, then Actions > Edit."
			).format(frappe.bold(self.name), _(before.status)),
			frappe.PermissionError,
			title=_("Request Locked"),
		)

	def validate_hold_unchanged(self):
		"""A request that holds a bed or room keeps its place: resolve or cancel it, then raise a new one."""
		before = self.get_doc_before_save()
		if not before or not holds(before):
			return
		changed = [field for field in HOLD_FIELDS if (self.get(field) or None) != (before.get(field) or None)]
		if not changed:
			return
		frappe.throw(
			_(
				"Maintenance request {0} holds {1}, so its place and hold cannot change. Resolve or "
				"cancel it to free the beds, then raise a new request."
			).format(frappe.bold(self.name), frappe.bold(before.bed or before.room)),
			title=_("Request Holds a Place"),
		)

	def validate_cancel_right(self):
		"""Only a manager sets the status to Cancelled, on a new record too."""
		if self.status != "Cancelled":
			return
		before = self.get_doc_before_save()
		if before and before.status == "Cancelled":
			return
		if not set(MANAGER_ROLES) & set(frappe.get_roles()):
			frappe.throw(
				_("Only an Accommodation Manager or HR Manager can cancel a maintenance request."),
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
		if self.status in RESOLVED_STATUSES and not (self.resolution_date and self.resolution_details):
			frappe.throw(
				_("A {0} request needs its Resolution Date and Resolution Details.").format(_(self.status)),
				title=_("Resolution Missing"),
			)
		if self.resolution_date and getdate(self.resolution_date) < getdate(self.reported_on):
			frappe.throw(_("Resolution Date cannot be before Reported On."), title=_("Invalid Dates"))
		if self.resolution_date and getdate(self.resolution_date) > getdate(today()):
			frappe.throw(_("Resolution Date cannot be in the future."), title=_("Invalid Dates"))

	def validate_hold_target(self):
		"""Maintenance holds only a free bed or an empty room, never a Blocked one.

		A room request holds the room only when its Room Maintenance Type is Permanent;
		a Temporary one leaves every bed in use.
		"""
		if self.bed:
			self.set_room_under_maintenance = 0
		else:
			self.set_room_under_maintenance = int(bool(self.room) and self.maintenance_type == ROOM_PERMANENT)

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
				_("Room {0} is Blocked. Clear the hold before maintenance starts.").format(
					frappe.bold(self.room)
				),
				title=_("Room Blocked"),
			)

		if self.hold_starts():
			self.validate_nobody_housed()

	def hold_starts(self):
		"""True when this save starts holding its bed or room, so an old hold stays editable."""
		before = self.get_doc_before_save()
		if not before or before.status not in OPEN_STATUSES:
			return True
		if before.bed != self.bed or before.room != self.room:
			return True
		if self.bed:
			return not before.set_bed_under_maintenance
		return not before.set_room_under_maintenance

	def validate_nobody_housed(self):
		"""A bed or room under maintenance must be empty: move or release its employees first."""
		filters = {"bed": self.bed} if self.bed else {"room": self.room}
		occupied = frappe.get_all(
			"Accommodation Allocation",
			filters={**filters, "docstatus": 1, "status": ("in", CURRENT_STAY_STATUSES)},
			fields=["name", "employee_name", "employee", "bed"],
			order_by="bed asc",
		)
		if not occupied:
			return

		if self.bed:
			stay = occupied[0]
			frappe.throw(
				_(
					"Bed {0} is allocated to {1} under {2}. Transfer the employee to another bed or "
					"release the allocation before putting this bed under maintenance."
				).format(
					frappe.bold(self.bed),
					frappe.bold(stay.employee_name or stay.employee),
					frappe.bold(stay.name),
				),
				title=_("Bed Occupied"),
			)

		stays = "<br>".join(
			_("{0}: {1} under {2}").format(
				frappe.bold(frappe.db.get_value("Accommodation Bed", stay.bed, "bed_number") or stay.bed),
				frappe.bold(stay.employee_name or stay.employee),
				stay.name,
			)
			for stay in occupied
		)
		frappe.throw(
			_(
				"Room {0} has {1} occupied bed(s). Transfer or release these allocations before putting "
				"the whole room under maintenance, or choose Temporary to keep the room in use:<br>{2}"
			).format(frappe.bold(self.room), len(occupied), stays),
			title=_("Room Occupied"),
		)

	def is_holding(self):
		"""True while this record is open and holds a bed or a whole room."""
		return holds(self)

	def on_update(self):
		self.apply_maintenance_state()

	def on_trash(self):
		self.release_holds()

	def apply_maintenance_state(self):
		if self.is_holding():
			if self.bed:
				hold_bed(self.bed, self.name)
			else:
				self.apply_room_hold()
			return

		before = self.get_doc_before_save()
		if before and holds(before):
			self.release_holds()

	def apply_room_hold(self):
		frappe.db.set_value("Accommodation Room", self.room, "under_maintenance", 1, update_modified=False)
		beds = frappe.get_all(
			"Accommodation Bed",
			filters={"room": self.room, "status": ("in", (BED_STATUS_AVAILABLE, BED_STATUS_OCCUPIED))},
			pluck="name",
		)
		for bed in beds:
			hold_bed(bed, self.name)
		update_room_occupancy(self.room)

	def release_holds(self):
		"""Free every bed and room this record holds, whatever its fields say now.

		The beds are found by the record named in their hold reason, so a hold is freed
		even when the record no longer points at it. Another open record keeps its own.
		"""
		beds = frappe.get_all(
			"Accommodation Bed",
			filters={"under_maintenance": 1, "hold_reason": ("like", f"%{self.name}")},
			fields=["name", "room"],
		)
		rooms = {bed.room for bed in beds} | ({self.room} if self.room else set())
		for room in rooms:
			if frappe.db.get_value("Accommodation Room", room, "under_maintenance"):
				release_room_maintenance(room, exclude=self.name)
		for bed in beds:
			release_bed_maintenance(bed.name, exclude=self.name)
		for room in rooms:
			update_room_occupancy(room)


def holds(record):
	"""True while the record is open and holds a bed or a whole room."""
	if record.status not in OPEN_STATUSES:
		return False
	if record.bed:
		return bool(record.set_bed_under_maintenance)
	return bool(record.room and record.set_room_under_maintenance)


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
			"Accommodation Bed",
			bed,
			"hold_reason",
			_("Maintenance {0}").format(holder),
			update_modified=False,
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
