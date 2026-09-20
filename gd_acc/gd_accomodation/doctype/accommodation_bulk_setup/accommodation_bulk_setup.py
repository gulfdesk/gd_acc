# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from gd_acc.gd_accomodation.accommodation_utils import site_requires_bed, update_room_occupancy

MAX_ROOMS_PER_RUN = 2000

BUNK_LEVELS = (("L", "Bunk Lower"), ("U", "Bunk Upper"))


def beds_per_unit(bed_configuration):
	"""A bunk unit is one frame holding two beds; a single unit is one bed."""
	return len(BUNK_LEVELS) if bed_configuration == "Bunk" else 1


def build_bed_plan(row, units_per_room):
	"""Bed numbers and types for one room.

	Single setups give B01, B02 … Bunk setups pair each unit as B01-L and
	B01-U so the lower and upper of the same frame stay recognisable.
	"""
	prefix = (row.bed_number_prefix or "B").strip()

	if row.bed_configuration != "Bunk":
		return [
			{"bed_number": f"{prefix}{unit:02d}", "bed_type": "Single"}
			for unit in range(1, units_per_room + 1)
		]

	return [
		{"bed_number": f"{prefix}{unit:02d}-{suffix}", "bed_type": bed_type}
		for unit in range(1, units_per_room + 1)
		for suffix, bed_type in BUNK_LEVELS
	]


class AccommodationBulkSetup(Document):
	def validate(self):
		self.location = frappe.db.get_value("Accommodation Site", self.site, "location")

		if self.status == "Completed":
			frappe.throw(
				_("This bulk setup has already been generated. Create a new one to add more structure."),
				title=_("Already Generated"),
			)

		self.build_plan()

	def build_plan(self):
		"""Resolve every floor, room and bed this run would create.

		Runs before anything is written so a duplicate or a bad configuration
		stops the run cleanly instead of leaving half a camp behind.
		"""
		requires_bed = site_requires_bed(self.site)
		plan = []
		seen_floors = set()
		total_rooms = 0

		for row in self.floors:
			floor_name = (row.floor_name or "").strip()
			if not floor_name:
				frappe.throw(_("Row {0}: Floor Name is required.").format(row.idx))

			if floor_name in seen_floors:
				frappe.throw(
					_("Row {0}: Floor {1} is listed more than once.").format(row.idx, floor_name),
					title=_("Duplicate Floor"),
				)
			seen_floors.add(floor_name)

			floor_docname = f"{self.site} - {floor_name}"
			if frappe.db.exists("Accommodation Floor", floor_docname):
				frappe.throw(
					_("Row {0}: Floor {1} already exists at this site.").format(row.idx, floor_name),
					title=_("Duplicate Floor"),
				)

			number_of_rooms = cint(row.number_of_rooms)
			if number_of_rooms < 1:
				frappe.throw(_("Row {0}: Rooms must be at least 1.").format(row.idx))

			units_per_room = cint(row.beds_per_room)
			if requires_bed and units_per_room < 1:
				frappe.throw(
					_(
						"Row {0}: Site {1} uses bed level allocation, so Beds / Bunks must be at least 1."
					).format(row.idx, self.site),
					title=_("Beds Required"),
				)

			beds_per_room = units_per_room * beds_per_unit(row.bed_configuration)
			row.generated_beds_per_room = beds_per_room

			total_rooms += number_of_rooms
			if total_rooms > MAX_ROOMS_PER_RUN:
				frappe.throw(
					_("A single bulk setup can generate at most {0} rooms.").format(MAX_ROOMS_PER_RUN),
					title=_("Too Large"),
				)

			plan.append(
				{
					"floor_name": floor_name,
					"floor_docname": floor_docname,
					"sequence": cint(row.sequence),
					"room_type": row.room_type or "Shared",
					"capacity": cint(row.capacity) or beds_per_room,
					"rooms": self.build_room_plan(row, floor_docname, number_of_rooms, units_per_room),
				}
			)

		return plan

	def build_room_plan(self, row, floor_docname, number_of_rooms, units_per_room):
		prefix = (row.room_number_prefix or "").strip()
		start = cint(row.room_start_number) or 1
		rooms = []

		for offset in range(number_of_rooms):
			number = start + offset
			room_number = f"{prefix}{number:02d}" if prefix else str(number)
			room_docname = f"{floor_docname} - {room_number}"

			if frappe.db.exists("Accommodation Room", room_docname):
				frappe.throw(
					_("Row {0}: Room {1} already exists on this floor.").format(row.idx, room_number),
					title=_("Duplicate Room"),
				)

			rooms.append(
				{
					"room_number": room_number,
					"room_docname": room_docname,
					"beds": build_bed_plan(row, units_per_room),
				}
			)

		return rooms

	@frappe.whitelist()
	def generate(self):
		"""Create the planned structure. Any failure rolls the whole run back."""
		self.check_permission("write")

		if self.status == "Completed":
			frappe.throw(_("This bulk setup has already been generated."), title=_("Already Generated"))

		plan = self.build_plan()
		created = {"floors": 0, "rooms": 0, "beds": 0}
		touched_rooms = []

		frappe.flags.skip_accommodation_rollup = True
		try:
			for floor_plan in plan:
				self.create_floor(floor_plan)
				created["floors"] += 1

				for room_plan in floor_plan["rooms"]:
					self.create_room(room_plan, floor_plan)
					created["rooms"] += 1
					touched_rooms.append(room_plan["room_docname"])

					for bed_plan in room_plan["beds"]:
						self.create_bed(bed_plan, room_plan)
						created["beds"] += 1
		finally:
			frappe.flags.skip_accommodation_rollup = False

		for room in touched_rooms:
			update_room_occupancy(room)

		self.db_set(
			{
				"status": "Completed",
				"generated_on": now_datetime(),
				"created_floors": created["floors"],
				"created_rooms": created["rooms"],
				"created_beds": created["beds"],
				"generation_log": _("Created {0} floor(s), {1} room(s) and {2} bed(s) at {3}.").format(
					created["floors"], created["rooms"], created["beds"], self.site
				),
			}
		)

		return created

	def create_floor(self, floor_plan):
		floor = frappe.new_doc("Accommodation Floor")
		floor.update(
			{
				"floor_name": floor_plan["floor_name"],
				"site": self.site,
				"sequence": floor_plan["sequence"],
				"status": "Active",
			}
		)
		floor.flags.ignore_permissions = True
		floor.insert()
		return floor

	def create_room(self, room_plan, floor_plan):
		room = frappe.new_doc("Accommodation Room")
		room.update(
			{
				"room_number": room_plan["room_number"],
				"floor": floor_plan["floor_docname"],
				"room_type": floor_plan["room_type"],
				"capacity": floor_plan["capacity"],
				"status": "Active",
			}
		)
		room.flags.ignore_permissions = True
		room.insert()
		return room

	def create_bed(self, bed_plan, room_plan):
		bed = frappe.new_doc("Accommodation Bed")
		bed.update(
			{
				"bed_number": bed_plan["bed_number"],
				"bed_type": bed_plan["bed_type"],
				"room": room_plan["room_docname"],
				"status": "Available",
			}
		)
		bed.flags.ignore_permissions = True
		bed.insert()
		return bed
