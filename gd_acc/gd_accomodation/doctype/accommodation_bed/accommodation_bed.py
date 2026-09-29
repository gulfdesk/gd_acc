# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from gd_acc.gd_accomodation.accommodation_utils import (
	BED_STATUS_AVAILABLE,
	BED_STATUS_BLOCKED,
	BED_STATUS_MAINTENANCE,
	get_site_gender,
	log_bed_status_change,
	update_room_occupancy,
)

BED_TYPE_SINGLE = "Single"
BED_TYPE_BUNK = "Bunk"

# Levels of a bunk, bottom first: the bed number suffix and the Bunk Level of each.
BUNK_LEVELS = {
	2: (("L", "Lower"), ("U", "Upper")),
	3: (("L", "Lower"), ("M", "Middle"), ("U", "Upper")),
}


def bed_type_label(bed_type, bunk_level=None):
	"""What a bed is, in one phrase: Single, or Bunk with its level, for example Bunk Lower."""
	if bed_type == BED_TYPE_BUNK and bunk_level:
		return f"{BED_TYPE_BUNK} {bunk_level}"
	return bed_type or BED_TYPE_SINGLE


class AccommodationBed(Document):
	def before_insert(self):
		self.plan_bunk()

	def plan_bunk(self):
		"""A new Bunk bed becomes its lowest level; after_insert creates the levels above it.

		A bed that already has its Bunk Level (one level made by Bulk Setup, or a row of an
		import) is a single level and is left as it is. Every level is checked here, before
		anything is written, so a clash or a full room never leaves half a bunk behind.
		"""
		if self.bed_type != BED_TYPE_BUNK or self.bunk_level:
			return

		levels = BUNK_LEVELS.get(cint(self.bunk_levels) or 2)
		if not levels:
			frappe.throw(_("Bunk Levels must be 2 or 3."), title=_("Invalid Bunk"))

		base = (self.bed_number or "").strip()
		plan = [(f"{base}-{suffix}", level) for suffix, level in levels]
		for bed_number, _level in plan:
			if frappe.db.exists("Accommodation Bed", {"room": self.room, "bed_number": bed_number}):
				frappe.throw(
					_("Bed {0} already exists in room {1}. Choose another Bed Number.").format(
						frappe.bold(bed_number), frappe.bold(self.room)
					),
					title=_("Duplicate Bed"),
				)

		capacity = cint(frappe.db.get_value("Accommodation Room", self.room, "capacity"))
		existing = frappe.db.count("Accommodation Bed", {"room": self.room})
		if capacity and existing + len(plan) > capacity:
			frappe.throw(
				_("Room {0} has a capacity of {1} bed(s). It has {2} and this bunk adds {3}.").format(
					frappe.bold(self.room), capacity, existing, len(plan)
				),
				title=_("Room Full"),
			)

		self.bed_number, self.bunk_level = plan[0]
		self.bunk_levels = str(len(plan))
		self.flags.bunk_levels_above = plan[1:]
		self.flags.bunk_status = self.status

	def after_insert(self):
		self.create_bunk_levels()

	def create_bunk_levels(self):
		above = self.flags.get("bunk_levels_above")
		if not above:
			return

		for bed_number, level in above:
			frappe.get_doc(
				{
					"doctype": self.doctype,
					"bed_number": bed_number,
					"bed_type": BED_TYPE_BUNK,
					"bunk_level": level,
					"bunk_levels": self.bunk_levels,
					"room": self.room,
					"status": self.flags.bunk_status,
					"remarks": self.remarks,
				}
			).insert()

		frappe.msgprint(
			_("Created bunk beds {0}.").format(
				", ".join([self.bed_number] + [number for number, _level in above])
			),
			alert=True,
			indicator="green",
		)

	def validate(self):
		self.validate_bed_type()
		self.gender_restriction = get_site_gender(self.site)
		self.validate_room_capacity()
		self.validate_status_change()
		self.validate_room_change()

	def validate_bed_type(self):
		"""A saved Single cannot turn into a Bunk: a bunk is created new, with its levels."""
		before = self.get_doc_before_save()
		if (
			before
			and self.bed_type == BED_TYPE_BUNK
			and before.bed_type != BED_TYPE_BUNK
			and not self.bunk_level
		):
			frappe.throw(
				_("A bunk is created as a new bed, which makes one bed for each level."),
				title=_("Invalid Bed Type"),
			)
		if self.bed_type != BED_TYPE_BUNK:
			self.bunk_level = None
		self.bed_type_label = bed_type_label(self.bed_type, self.bunk_level)

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
			if self.status == BED_STATUS_MAINTENANCE:
				throw_manual_maintenance()
			self.apply_room_hold()
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

		# update_bed_state writes with db_set, so a Maintenance record never reaches this check.
		if BED_STATUS_MAINTENANCE in (self.status, before.status):
			throw_manual_maintenance()

		if self.status == BED_STATUS_BLOCKED and self.under_maintenance:
			frappe.throw(
				_("Bed {0} is under maintenance. Block it after the maintenance closes.").format(
					frappe.bold(self.name)
				),
				title=_("Bed Under Maintenance"),
			)

		if before.status == BED_STATUS_BLOCKED:
			self.hold_reason = None
			self.held_by_room = 0

	def apply_room_hold(self):
		"""A new Available bed takes the hold of its room."""
		if self.status != BED_STATUS_AVAILABLE or not self.room:
			return

		room = frappe.db.get_value(
			"Accommodation Room", self.room, ["is_blocked", "hold_reason", "under_maintenance"], as_dict=True
		)
		if not room:
			return

		if room.is_blocked:
			self.status = BED_STATUS_BLOCKED
			self.held_by_room = 1
			self.hold_reason = room.hold_reason
		elif room.under_maintenance:
			record = frappe.db.get_value(
				"Accommodation Maintenance",
				{
					"room": self.room,
					"bed": ("is", "not set"),
					"set_room_under_maintenance": 1,
					"status": ("in", ("Open", "In Progress")),
				},
				"name",
			)
			self.status = BED_STATUS_MAINTENANCE
			self.under_maintenance = 1
			self.hold_reason = _("Maintenance {0}").format(record) if record else None

	def validate_room_change(self):
		before = self.get_doc_before_save()
		if not before or before.room == self.room:
			return

		if before.status == "Occupied":
			frappe.throw(_("An occupied bed cannot be moved to another room."), title=_("Bed Occupied"))

	def on_update(self):
		before = self.get_doc_before_save()

		if before and before.status != self.status:
			if self.status == BED_STATUS_BLOCKED:
				reason = "Hold"
			elif before.status == BED_STATUS_BLOCKED:
				reason = "Hold Released"
			else:
				reason = "Manual Update"

			log_bed_status_change(
				bed=self.name,
				previous_status=before.status,
				new_status=self.status,
				reason=reason,
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


def throw_manual_maintenance():
	frappe.throw(
		_("A bed shows Maintenance only through an Accommodation Maintenance record."),
		title=_("Not Allowed"),
	)
