# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from gd_acc.gd_accomodation.api import get_dashboard_data
from gd_acc.gd_accomodation.doctype.accommodation_allocation.test_accommodation_allocation import (
	make_allocation,
	make_employee,
	make_structure,
)


def make_request(structure, bed=None, set_bed_under_maintenance=1, **kwargs):
	return frappe.get_doc(
		{
			"doctype": "Accommodation Maintenance",
			"subject": "_Test AC not cooling",
			"issue_type": "Air Conditioning",
			"priority": "High",
			"status": "Open",
			"reported_by": "Administrator",
			"reported_on": today(),
			"location": structure.location.name,
			"site": structure.site.name,
			"bed": bed,
			"set_bed_under_maintenance": set_bed_under_maintenance,
			"description": "Test request",
			**kwargs,
		}
	).insert()


class TestAccommodationMaintenance(FrappeTestCase):
	def test_request_puts_its_bed_under_maintenance(self):
		structure = make_structure()
		make_request(structure, bed=structure.bed.name)

		self.assertEqual(
			frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Maintenance"
		)

	def test_resolving_frees_the_bed(self):
		structure = make_structure()
		request = make_request(structure, bed=structure.bed.name)

		request.status = "Resolved"
		request.resolution_date = today()
		request.resolution_details = "Fixed"
		request.save()

		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Available")

	def test_occupied_bed_cannot_be_put_under_maintenance(self):
		structure = make_structure()
		employee = make_employee()
		make_allocation(employee, structure)

		self.assertRaises(frappe.ValidationError, make_request, structure, bed=structure.bed.name)

	def test_bed_maintenance_count_is_not_the_request_count(self):
		"""A bed can be flagged by hand without a request, so the two differ.

		The dashboard reports them as separate figures rather than one
		number that looks wrong from either direction.
		"""
		structure = make_structure(beds_per_room=3)

		# One bed taken out of service directly on the bed record, no request.
		by_hand = frappe.get_doc("Accommodation Bed", structure.beds[1].name)
		by_hand.status = "Maintenance"
		by_hand.save()

		# One bed taken out of service through a request.
		make_request(structure, bed=structure.beds[0].name)

		kpi = get_dashboard_data(location=structure.location.name)["kpi"]

		self.assertEqual(kpi["maintenance"], 2, "beds sitting at Maintenance")
		self.assertEqual(kpi["open_maintenance_requests"], 1, "open maintenance requests")

	def test_request_without_touching_the_bed(self):
		structure = make_structure()
		make_request(structure, bed=structure.bed.name, set_bed_under_maintenance=0)

		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Available")

		kpi = get_dashboard_data(location=structure.location.name)["kpi"]
		self.assertEqual(kpi["maintenance"], 0)
		self.assertEqual(kpi["open_maintenance_requests"], 1)

	def test_dashboard_table_matches_the_request_count(self):
		structure = make_structure(beds_per_room=3)
		make_request(structure, bed=structure.beds[0].name)
		make_request(structure, bed=structure.beds[1].name)

		data = get_dashboard_data(location=structure.location.name)
		self.assertEqual(len(data["open_maintenance"]), data["kpi"]["open_maintenance_requests"])
		self.assertEqual(len(data["open_maintenance"]), 2)

	def test_permanent_room_maintenance_needs_an_empty_room(self):
		structure = make_structure()
		make_allocation(make_employee(), structure)

		self.assertRaises(
			frappe.ValidationError,
			make_request,
			structure,
			set_bed_under_maintenance=0,
			room=structure.room.name,
			maintenance_type="Permanent",
		)

	def test_temporary_room_maintenance_holds_no_bed(self):
		structure = make_structure()
		make_allocation(make_employee(), structure)

		request = make_request(
			structure, set_bed_under_maintenance=0, room=structure.room.name, maintenance_type="Temporary"
		)

		self.assertEqual(request.set_room_under_maintenance, 0)
		self.assertEqual(
			frappe.db.get_value("Accommodation Room", structure.room.name, "under_maintenance"), 0
		)

	def test_permanent_room_maintenance_holds_every_bed(self):
		structure = make_structure()

		make_request(
			structure, set_bed_under_maintenance=0, room=structure.room.name, maintenance_type="Permanent"
		)

		statuses = set(frappe.get_all("Accommodation Bed", {"room": structure.room.name}, pluck="status"))
		self.assertEqual(statuses, {"Maintenance"})

	def test_room_hold_cannot_move_to_a_bed(self):
		structure = make_structure()
		request = make_request(
			structure, set_bed_under_maintenance=0, room=structure.room.name, maintenance_type="Permanent"
		)

		request.bed = structure.bed.name
		request.set_bed_under_maintenance = 1
		self.assertRaises(frappe.ValidationError, request.save)

	def test_resolving_a_room_hold_frees_the_room_and_its_beds(self):
		structure = make_structure()
		request = make_request(
			structure, set_bed_under_maintenance=0, room=structure.room.name, maintenance_type="Permanent"
		)

		request.status = "Resolved"
		request.resolution_date = today()
		request.resolution_details = "Fixed"
		request.save()

		self.assertEqual(
			frappe.db.get_value("Accommodation Room", structure.room.name, "under_maintenance"), 0
		)
		statuses = set(frappe.get_all("Accommodation Bed", {"room": structure.room.name}, pluck="status"))
		self.assertEqual(statuses, {"Available"})

	def test_resolving_frees_a_hold_the_request_no_longer_points_at(self):
		# A room hold left behind when an older version let the request switch to a bed.
		structure = make_structure()
		request = make_request(
			structure, set_bed_under_maintenance=0, room=structure.room.name, maintenance_type="Permanent"
		)
		frappe.db.set_value(
			"Accommodation Maintenance",
			request.name,
			{"bed": structure.bed.name, "set_bed_under_maintenance": 1, "set_room_under_maintenance": 0},
		)

		request = frappe.get_doc("Accommodation Maintenance", request.name)
		request.status = "Resolved"
		request.resolution_date = today()
		request.resolution_details = "Fixed"
		request.save()

		statuses = set(frappe.get_all("Accommodation Bed", {"room": structure.room.name}, pluck="status"))
		self.assertEqual(statuses, {"Available"})
