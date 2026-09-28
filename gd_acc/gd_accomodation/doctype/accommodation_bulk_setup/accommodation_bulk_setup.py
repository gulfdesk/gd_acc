# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from gd_acc.gd_accomodation.accommodation_utils import site_requires_bed, update_room_occupancy
from gd_acc.gd_accomodation.doctype.accommodation_bed.accommodation_bed import BUNK_LEVELS

MAX_ROOMS_PER_RUN = 2000

MAX_BEDS_PER_RUN = 2000

SCOPE_BEDS_ONLY = "Beds Only"

BED_SETUP_BUNK = "Bunk"

BED_SETUP_MIXED = "Single + Bunk"


def bunks_and_singles(row, units):
	"""Bunk frames and single beds in one room. For a mixed setup, units counts the bunks."""
	if row.bed_configuration == BED_SETUP_BUNK:
		return units, 0
	if row.bed_configuration == BED_SETUP_MIXED:
		return units, cint(row.single_beds)
	return 0, units


def bunk_levels(row):
	"""The levels of each bunk on the row, bottom first. The same levels as a Bunk made on the Bed form."""
	levels = BUNK_LEVELS.get(cint(row.bunk_levels) or 2)
	if not levels:
		frappe.throw(_("Row {0}: Bunk Levels must be 2 or 3.").format(row.idx), title=_("Invalid Bed Setup"))
	return levels


def beds_in_room(row, units):
	"""A bunk frame holds one bed per level: Lower and Upper, or Lower, Middle and Upper."""
	bunks, singles = bunks_and_singles(row, units)
	return (bunks * len(bunk_levels(row)) if bunks else 0) + singles


def build_bed_plan(row, units_per_room, start=1):
	"""Bed numbers and types for one room.

	Single setups give B01, B02 … Bunk setups give each frame one bed per level,
	B01-L and B01-U, or B01-L, B01-M and B01-U for three levels, so the beds of
	one frame stay recognisable. A mixed setup numbers its bunks first, then its
	single beds: B01-L, B01-U, B02.
	"""
	prefix = (row.bed_number_prefix or "B").strip()
	bunks, singles = bunks_and_singles(row, units_per_room)
	beds = []
	number = start

	for _bunk in range(bunks):
		beds.extend(
			{"bed_number": f"{prefix}{number:02d}-{suffix}", "bed_type": bed_type}
			for suffix, bed_type in bunk_levels(row)
		)
		number += 1
	for _single in range(singles):
		beds.append({"bed_number": f"{prefix}{number:02d}", "bed_type": "Single"})
		number += 1

	return beds


def validate_mixed_setup(row, units):
	"""A mixed setup needs at least one bunk and one single bed; otherwise Single or Bunk fits."""
	if row.bed_configuration == BED_SETUP_MIXED and (units < 1 or cint(row.single_beds) < 1):
		frappe.throw(
			_(
				"Row {0}: Single + Bunk needs at least 1 bunk in Beds / Bunks and 1 bed in Single Beds."
			).format(row.idx),
			title=_("Invalid Bed Setup"),
		)


class AccommodationBulkSetup(Document):
	def validate(self):
		self.location = frappe.db.get_value("Accommodation Site", self.site, "location")

		if self.status == "Completed":
			frappe.throw(
				_("This bulk setup has already been generated. Create a new one to add more structure."),
				title=_("Already Generated"),
			)

		if self.beds_only():
			self.floors = []
			self.build_bed_only_plan()
		else:
			self.rooms = []
			self.build_plan()

	def beds_only(self):
		return self.generate_scope == SCOPE_BEDS_ONLY

	def build_plan(self):
		"""Resolve every floor, room and bed this run would create.

		Runs before anything is written so a duplicate or a bad configuration
		stops the run cleanly instead of leaving half a camp behind. A floor may
		appear on more than one row: each row adds its own rooms with its own bed
		setup, and the floor is created once.
		"""
		requires_bed = site_requires_bed(self.site)
		plan = []
		floors = {}
		total_rooms = 0

		for row in self.floors:
			floor_name = (row.floor_name or "").strip()
			if not floor_name:
				frappe.throw(_("Row {0}: Floor Name is required.").format(row.idx))

			floor = floors.get(floor_name)
			if floor is None:
				floor_docname = f"{self.site} - {floor_name}"
				if frappe.db.exists("Accommodation Floor", floor_docname):
					frappe.throw(
						_("Row {0}: Floor {1} already exists at this site.").format(row.idx, floor_name),
						title=_("Duplicate Floor"),
					)
				floor = {
					"floor_name": floor_name,
					"floor_docname": floor_docname,
					"sequence": cint(row.sequence),
					"rooms": [],
					"room_rows": {},
					"next_room_number": 1,
				}
				floors[floor_name] = floor
				plan.append(floor)

			number_of_rooms = cint(row.number_of_rooms)
			if number_of_rooms < 1:
				frappe.throw(_("Row {0}: Rooms must be at least 1.").format(row.idx))

			units_per_room = cint(row.beds_per_room)
			validate_mixed_setup(row, units_per_room)
			beds_per_room = beds_in_room(row, units_per_room)
			if requires_bed and beds_per_room < 1:
				frappe.throw(
					_(
						"Row {0}: Site {1} uses bed level allocation, so Beds / Bunks must be at least 1."
					).format(row.idx, self.site),
					title=_("Beds Required"),
				)
			row.generated_beds_per_room = beds_per_room

			total_rooms += number_of_rooms
			if total_rooms > MAX_ROOMS_PER_RUN:
				frappe.throw(
					_("A single bulk setup can generate at most {0} rooms.").format(MAX_ROOMS_PER_RUN),
					title=_("Too Large"),
				)

			# A repeated floor left at Room Start No 1 carries on after its previous row.
			start = cint(row.room_start_number) or 1
			if floor["rooms"] and start == 1:
				start = floor["next_room_number"]
			rooms = self.build_room_plan(row, floor["floor_docname"], number_of_rooms, units_per_room, start)
			for room in rooms:
				room["room_type"] = row.room_type or "Shared"
				room["capacity"] = cint(row.capacity) or beds_per_room
				earlier = floor["room_rows"].get(room["room_number"])
				if earlier:
					frappe.throw(
						_(
							"Row {0}: Room {1} on floor {2} is also made by row {3}. Change the Room Start No."
						).format(row.idx, room["room_number"], floor_name, earlier),
						title=_("Duplicate Room"),
					)
				floor["room_rows"][room["room_number"]] = row.idx
			floor["rooms"].extend(rooms)
			floor["next_room_number"] = start + number_of_rooms

		return plan

	def build_room_plan(self, row, floor_docname, number_of_rooms, units_per_room, start):
		prefix = (row.room_number_prefix or "").strip()
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

	def build_bed_only_plan(self):
		"""Resolve the beds a Beds Only run adds to rooms that already exist.

		A room may appear on more than one row, for example bunk beds on one row
		and single beds on another. Bed numbers must not clash with the room's
		beds or with another row, and the room total must fit its capacity.
		"""
		if not self.rooms:
			frappe.throw(_("Add at least one room to generate beds for."), title=_("No Rooms"))

		plan = []
		rooms = {}
		total_beds = 0

		for row in self.rooms:
			if not row.room:
				frappe.throw(_("Row {0}: Room is required.").format(row.idx))

			room = rooms.get(row.room)
			if room is None:
				room = self.get_bed_only_room(row)
				rooms[row.room] = room

			units = cint(row.beds_per_room)
			if units < 1:
				frappe.throw(_("Row {0}: Beds / Bunks must be at least 1.").format(row.idx))
			validate_mixed_setup(row, units)

			total_beds += beds_in_room(row, units)
			if total_beds > MAX_BEDS_PER_RUN:
				frappe.throw(
					_("A single bulk setup can generate at most {0} beds.").format(MAX_BEDS_PER_RUN),
					title=_("Too Large"),
				)

			row.bed_start_number = cint(row.bed_start_number) or 1
			beds = build_bed_plan(row, units, row.bed_start_number)
			row.generated_beds_per_room = len(beds)
			row.existing_beds = len(room.existing_numbers)

			for bed in beds:
				if bed["bed_number"] in room.existing_numbers:
					frappe.throw(
						_(
							"Row {0}: Bed {1} already exists in room {2}. Change the Start No. or the prefix."
						).format(row.idx, bed["bed_number"], frappe.bold(row.room)),
						title=_("Duplicate Bed"),
					)
				if bed["bed_number"] in room.planned_numbers:
					frappe.throw(
						_(
							"Row {0}: Bed {1} in room {2} is also made by row {3}. Change the Start No. or the prefix."
						).format(
							row.idx,
							bed["bed_number"],
							frappe.bold(row.room),
							room.planned_numbers[bed["bed_number"]],
						),
						title=_("Duplicate Bed"),
					)
				room.planned_numbers[bed["bed_number"]] = row.idx

			existing = len(room.existing_numbers)
			added = len(room.planned_numbers)
			if room.capacity and existing + added > room.capacity:
				frappe.throw(
					_(
						"Row {0}: Room {1} has a capacity of {2} bed(s). It has {3} and this run adds {4}."
					).format(row.idx, frappe.bold(row.room), room.capacity, existing, added),
					title=_("Room Full"),
				)

			plan.append({"room_docname": row.room, "beds": beds})

		return plan

	def get_bed_only_room(self, row):
		"""Check that the row's room is an active room of this site, and load its beds."""
		room = frappe.db.get_value(
			"Accommodation Room", row.room, ["site", "status", "capacity"], as_dict=True
		)
		if not room or room.site != self.site:
			frappe.throw(
				_("Row {0}: Room {1} does not belong to site {2}.").format(
					row.idx, frappe.bold(row.room), frappe.bold(self.site)
				),
				title=_("Wrong Site"),
			)
		if room.status != "Active":
			frappe.throw(
				_("Row {0}: Room {1} is Inactive.").format(row.idx, frappe.bold(row.room)),
				title=_("Room Inactive"),
			)

		room.capacity = cint(room.capacity)
		room.existing_numbers = set(
			frappe.get_all("Accommodation Bed", filters={"room": row.room}, pluck="bed_number")
		)
		room.planned_numbers = {}
		return room

	@frappe.whitelist()
	def get_rooms_without_beds(self):
		"""Active rooms of the site that have no bed yet, in floor and room order."""
		self.check_permission("read")
		if not self.site:
			return []

		return frappe.db.sql(
			"""
			SELECT r.name
			FROM `tabAccommodation Room` r
			JOIN `tabAccommodation Floor` f ON f.name = r.floor
			WHERE r.site = %s AND r.status = 'Active'
				AND NOT EXISTS (SELECT 1 FROM `tabAccommodation Bed` b WHERE b.room = r.name)
			ORDER BY f.sequence, f.name, LENGTH(r.room_number), r.room_number
			""",
			self.site,
			pluck=True,
		)

	@frappe.whitelist()
	def generate(self):
		"""Create the planned structure. Any failure rolls the whole run back."""
		self.check_permission("write")

		if self.status == "Completed":
			frappe.throw(_("This bulk setup has already been generated."), title=_("Already Generated"))

		created = {"floors": 0, "rooms": 0, "beds": 0}
		touched_rooms = []

		frappe.flags.skip_accommodation_rollup = True
		try:
			if self.beds_only():
				room_plans = self.build_bed_only_plan()
			else:
				room_plans = []
				for floor_plan in self.build_plan():
					self.create_floor(floor_plan)
					created["floors"] += 1

					for room_plan in floor_plan["rooms"]:
						self.create_room(room_plan, floor_plan)
						created["rooms"] += 1
						room_plans.append(room_plan)

			for room_plan in room_plans:
				touched_rooms.append(room_plan["room_docname"])
				for bed_plan in room_plan["beds"]:
					self.create_bed(bed_plan, room_plan)
					created["beds"] += 1
		finally:
			frappe.flags.skip_accommodation_rollup = False

		for room in dict.fromkeys(touched_rooms):
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

	# The create_* methods skip permission checks on purpose: generate() already checked
	# write on this Bulk Setup, and the roles with write here are the roles with create on
	# Accommodation Floor, Room and Bed.
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
				"room_type": room_plan["room_type"],
				"capacity": room_plan["capacity"],
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
