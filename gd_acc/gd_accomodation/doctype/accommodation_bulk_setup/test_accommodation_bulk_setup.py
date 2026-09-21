# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def make_site(suffix=None, enable_bed_allocation=1):
	suffix = suffix or frappe.generate_hash(length=6)

	location = frappe.get_doc(
		{
			"doctype": "Accommodation Location",
			"location_name": f"_Test Bulk Loc {suffix}",
			"status": "Active",
		}
	).insert()

	site = frappe.get_doc(
		{
			"doctype": "Accommodation Site",
			"site_name": f"_Test Bulk Site {suffix}",
			"location": location.name,
			"accommodation_type": "Camp",
			"enable_bed_allocation": enable_bed_allocation,
			"status": "Active",
		}
	).insert()

	return location, site


def make_bulk_setup(site, floors):
	setup = frappe.get_doc(
		{
			"doctype": "Accommodation Bulk Setup",
			"site": site.name,
			"generate_scope": "Floors, Rooms and Beds",
			"floors": floors,
		}
	)
	setup.insert()
	return setup


class TestAccommodationBulkSetup(FrappeTestCase):
	def test_generates_full_structure(self):
		_location, site = make_site()
		setup = make_bulk_setup(
			site,
			[
				{
					"floor_name": "01",
					"sequence": 1,
					"number_of_rooms": 3,
					"room_number_prefix": "1",
					"room_start_number": 1,
					"beds_per_room": 4,
					"bed_number_prefix": "B",
					"room_type": "Shared",
				},
				{
					"floor_name": "02",
					"sequence": 2,
					"number_of_rooms": 2,
					"room_number_prefix": "2",
					"room_start_number": 1,
					"beds_per_room": 2,
					"bed_number_prefix": "B",
					"room_type": "Shared",
				},
			],
		)

		created = setup.generate()

		self.assertEqual(created["floors"], 2)
		self.assertEqual(created["rooms"], 5)
		self.assertEqual(created["beds"], 16)

		setup.reload()
		self.assertEqual(setup.status, "Completed")
		self.assertEqual(setup.created_beds, 16)

		self.assertEqual(frappe.db.count("Accommodation Floor", {"site": site.name}), 2)
		self.assertEqual(frappe.db.count("Accommodation Room", {"site": site.name}), 5)
		self.assertEqual(frappe.db.count("Accommodation Bed", {"site": site.name}), 16)
		self.assertEqual(frappe.db.count("Accommodation Bed", {"site": site.name, "status": "Available"}), 16)

		room = frappe.db.get_value(
			"Accommodation Room",
			{"site": site.name, "room_number": "101"},
			["name", "total_beds", "available_beds"],
			as_dict=True,
		)
		self.assertIsNotNone(room)
		self.assertEqual(room.total_beds, 4)
		self.assertEqual(room.available_beds, 4)

		site.reload()
		self.assertEqual(site.total_beds, 16)
		self.assertEqual(site.total_rooms, 5)

	def test_duplicate_floor_in_table_is_rejected(self):
		_location, site = make_site()
		rows = [
			{"floor_name": "01", "number_of_rooms": 1, "beds_per_room": 2},
			{"floor_name": "01", "number_of_rooms": 1, "beds_per_room": 2},
		]
		self.assertRaises(frappe.ValidationError, make_bulk_setup, site, rows)

	def test_existing_floor_is_rejected_and_nothing_is_created(self):
		_location, site = make_site()
		make_bulk_setup(site, [{"floor_name": "01", "number_of_rooms": 2, "beds_per_room": 2}]).generate()

		beds_before = frappe.db.count("Accommodation Bed", {"site": site.name})

		self.assertRaises(
			frappe.ValidationError,
			make_bulk_setup,
			site,
			[
				{"floor_name": "02", "number_of_rooms": 1, "beds_per_room": 2},
				{"floor_name": "01", "number_of_rooms": 1, "beds_per_room": 2},
			],
		)

		self.assertEqual(frappe.db.count("Accommodation Bed", {"site": site.name}), beds_before)
		self.assertFalse(frappe.db.exists("Accommodation Floor", f"{site.name} - 02"))

	def test_bed_level_site_requires_beds_per_room(self):
		_location, site = make_site(enable_bed_allocation=1)
		self.assertRaises(
			frappe.ValidationError,
			make_bulk_setup,
			site,
			[{"floor_name": "01", "number_of_rooms": 2, "beds_per_room": 0}],
		)

	def test_bunk_setup_generates_two_beds_per_unit(self):
		_location, site = make_site()
		setup = make_bulk_setup(
			site,
			[
				{
					"floor_name": "01",
					"number_of_rooms": 2,
					"room_number_prefix": "1",
					"room_start_number": 1,
					"bed_configuration": "Bunk",
					"beds_per_room": 3,
					"bed_number_prefix": "B",
				}
			],
		)

		created = setup.generate()

		# 2 rooms x 3 bunk units x 2 levels
		self.assertEqual(created["rooms"], 2)
		self.assertEqual(created["beds"], 12)

		setup.reload()
		self.assertEqual(setup.floors[0].generated_beds_per_room, 6)

		self.assertEqual(
			frappe.db.count("Accommodation Bed", {"site": site.name, "bed_type": "Bunk Lower"}), 6
		)
		self.assertEqual(
			frappe.db.count("Accommodation Bed", {"site": site.name, "bed_type": "Bunk Upper"}), 6
		)

		room = f"{site.name} - 01 - 101"
		bed_numbers = frappe.get_all(
			"Accommodation Bed", filters={"room": room}, pluck="bed_number", order_by="bed_number asc"
		)
		self.assertEqual(bed_numbers, ["B01-L", "B01-U", "B02-L", "B02-U", "B03-L", "B03-U"])

		self.assertEqual(frappe.db.get_value("Accommodation Room", room, "capacity"), 6)

	def test_single_setup_marks_beds_as_single(self):
		_location, site = make_site()
		setup = make_bulk_setup(
			site,
			[
				{
					"floor_name": "01",
					"number_of_rooms": 2,
					"bed_configuration": "Single",
					"beds_per_room": 4,
				}
			],
		)

		created = setup.generate()

		self.assertEqual(created["beds"], 8)
		self.assertEqual(frappe.db.count("Accommodation Bed", {"site": site.name, "bed_type": "Single"}), 8)
		setup.reload()
		self.assertEqual(setup.floors[0].generated_beds_per_room, 4)

	def test_bunk_and_single_floors_in_one_run(self):
		_location, site = make_site()
		setup = make_bulk_setup(
			site,
			[
				{
					"floor_name": "01",
					"number_of_rooms": 2,
					"bed_configuration": "Single",
					"beds_per_room": 2,
				},
				{
					"floor_name": "02",
					"number_of_rooms": 2,
					"bed_configuration": "Bunk",
					"beds_per_room": 2,
				},
			],
		)

		created = setup.generate()

		# floor 01: 2 x 2 = 4 single, floor 02: 2 x 2 x 2 = 8 bunk
		self.assertEqual(created["beds"], 12)
		self.assertEqual(frappe.db.count("Accommodation Bed", {"site": site.name, "bed_type": "Single"}), 4)
		self.assertEqual(frappe.db.count("Accommodation Bed", {"floor": f"{site.name} - 02"}), 8)

	def test_villa_site_can_generate_rooms_without_beds(self):
		_location, site = make_site(enable_bed_allocation=0)
		setup = make_bulk_setup(site, [{"floor_name": "Ground", "number_of_rooms": 3, "beds_per_room": 0}])

		created = setup.generate()

		self.assertEqual(created["rooms"], 3)
		self.assertEqual(created["beds"], 0)
		self.assertEqual(frappe.db.count("Accommodation Bed", {"site": site.name}), 0)
