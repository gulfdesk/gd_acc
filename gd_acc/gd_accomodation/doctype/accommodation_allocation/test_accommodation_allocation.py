# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


def get_test_company():
	company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("A Company is required to run accommodation tests.")
	return company


def make_structure(
	suffix=None,
	accommodation_type="Camp",
	sub_type=None,
	enable_bed_allocation=1,
	rooms=1,
	beds_per_room=2,
):
	"""Create an isolated Location → Site → Floor → Room → Bed tree for one test."""
	suffix = suffix or frappe.generate_hash(length=6)

	location = frappe.get_doc(
		{
			"doctype": "Accommodation Location",
			"location_name": f"_Test Loc {suffix}",
			"location_code": f"TL{suffix}",
			"status": "Active",
		}
	).insert()

	site = frappe.get_doc(
		{
			"doctype": "Accommodation Site",
			"site_name": f"_Test Site {suffix}",
			"site_code": f"TS{suffix}",
			"location": location.name,
			"accommodation_type": accommodation_type,
			"sub_type": sub_type,
			"enable_bed_allocation": enable_bed_allocation,
			"status": "Active",
		}
	).insert()

	floor = frappe.get_doc(
		{
			"doctype": "Accommodation Floor",
			"floor_name": "01",
			"site": site.name,
			"sequence": 1,
			"status": "Active",
		}
	).insert()

	created_rooms = []
	created_beds = []
	for room_index in range(1, rooms + 1):
		room = frappe.get_doc(
			{
				"doctype": "Accommodation Room",
				"room_number": f"10{room_index}",
				"floor": floor.name,
				"room_type": "Shared",
				"status": "Active",
			}
		).insert()
		created_rooms.append(room)

		for bed_index in range(1, beds_per_room + 1):
			created_beds.append(
				frappe.get_doc(
					{
						"doctype": "Accommodation Bed",
						"bed_number": f"B0{bed_index}",
						"room": room.name,
						"status": "Available",
					}
				).insert()
			)

	return frappe._dict(
		location=location,
		site=site,
		floor=floor,
		room=created_rooms[0],
		rooms=created_rooms,
		bed=created_beds[0] if created_beds else None,
		beds=created_beds,
	)


def fill_site_specific_mandatory_fields(doc):
	"""Satisfy mandatory Employee customisations that these tests do not care about.

	Sites customise Employee differently, so anything still empty and required is
	given a valid placeholder rather than being hard coded into every test.
	"""
	for df in frappe.get_meta(doc.doctype).fields:
		if not df.reqd or doc.get(df.fieldname):
			continue

		if df.fieldtype == "Select":
			options = [option for option in (df.options or "").split("\n") if option.strip()]
			if options:
				doc.set(df.fieldname, options[0])
		elif df.fieldtype == "Link" and df.options:
			value = frappe.db.get_value(df.options, {}, "name")
			if value:
				doc.set(df.fieldname, value)
		elif df.fieldtype in ("Date", "Datetime"):
			doc.set(df.fieldname, today())
		elif df.fieldtype in ("Data", "Small Text", "Text", "Text Editor"):
			doc.set(df.fieldname, "_Test")
		elif df.fieldtype in ("Int", "Float", "Currency"):
			doc.set(df.fieldname, 1)


def make_employee(label=None):
	label = label or frappe.generate_hash(length=6)
	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			# The site's default AKBM series counter trails its real records, so
			# tests take the untouched standard series instead.
			"naming_series": "HR-EMP-",
			"first_name": f"_Test Acc {label}",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"company": get_test_company(),
			"status": "Active",
		}
	)
	fill_site_specific_mandatory_fields(employee)
	return employee.insert()


def make_allocation(employee, structure, bed=None, start_date=None, submit=True, **kwargs):
	allocation = frappe.get_doc(
		{
			"doctype": "Accommodation Allocation",
			"employee": employee.name,
			"location": structure.location.name,
			"site": structure.site.name,
			"floor": structure.floor.name,
			"room": structure.room.name,
			"bed": (bed or structure.bed).name if (bed or structure.bed) else None,
			"start_date": start_date or today(),
			**kwargs,
		}
	)
	allocation.insert()
	if submit:
		allocation.submit()
	return allocation


class TestAccommodationAllocation(FrappeTestCase):
	def test_allocation_occupies_bed_and_updates_employee(self):
		structure = make_structure()
		employee = make_employee()

		allocation = make_allocation(employee, structure)

		self.assertEqual(allocation.status, "Active")
		bed = frappe.get_doc("Accommodation Bed", structure.bed.name)
		self.assertEqual(bed.status, "Occupied")
		self.assertEqual(bed.current_employee, employee.name)
		self.assertEqual(bed.current_allocation, allocation.name)

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Provided")
		self.assertEqual(employee.current_accommodation_allocation, allocation.name)
		self.assertEqual(employee.current_accommodation_bed, structure.bed.name)
		self.assertEqual(employee.current_accommodation_site, structure.site.name)

		room = frappe.get_doc("Accommodation Room", structure.room.name)
		self.assertEqual(room.occupied_beds, 1)
		self.assertEqual(room.available_beds, 1)

		self.assertTrue(
			frappe.db.exists(
				"Bed Status History",
				{"bed": structure.bed.name, "new_status": "Occupied", "allocation": allocation.name},
			)
		)

	def test_release_frees_bed_and_preserves_history(self):
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure, start_date="2026-01-01")

		allocation.release(release_date="2026-03-31", reason="Manual Release", employee_status="Not Provided")

		allocation.reload()
		self.assertEqual(allocation.status, "Closed")
		self.assertEqual(str(allocation.release_date), "2026-03-31")
		self.assertEqual(str(allocation.start_date), "2026-01-01")
		self.assertEqual(allocation.bed, structure.bed.name)

		bed = frappe.get_doc("Accommodation Bed", structure.bed.name)
		self.assertEqual(bed.status, "Available")
		self.assertIsNone(bed.current_employee)

		room = frappe.get_doc("Accommodation Room", structure.room.name)
		self.assertEqual(room.occupied_beds, 0)
		self.assertEqual(room.available_beds, 2)

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")
		self.assertIsNone(employee.current_accommodation_allocation)

	def test_released_bed_is_reusable_and_both_histories_survive(self):
		structure = make_structure()
		employee_a = make_employee()
		employee_b = make_employee()

		first = make_allocation(employee_a, structure, start_date="2026-01-01")
		first.release(release_date="2026-03-31", reason="Manual Release", employee_status="Not Provided")

		second = make_allocation(employee_b, structure, start_date="2026-04-01")

		self.assertEqual(second.status, "Active")
		self.assertEqual(
			frappe.db.get_value("Accommodation Bed", structure.bed.name, "current_employee"),
			employee_b.name,
		)

		self.assertTrue(frappe.db.exists("Accommodation Allocation", first.name))
		self.assertEqual(frappe.db.get_value("Accommodation Allocation", first.name, "status"), "Closed")
		self.assertEqual(
			frappe.db.get_value("Accommodation Allocation", first.name, "employee"), employee_a.name
		)

	def test_overlapping_historical_allocation_is_rejected(self):
		structure = make_structure()
		employee_a = make_employee()
		employee_b = make_employee()

		first = make_allocation(employee_a, structure, start_date="2026-01-01")
		first.release(release_date="2026-03-31", reason="Manual Release", employee_status="Not Provided")

		overlapping = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee_b.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": structure.room.name,
				"bed": structure.bed.name,
				"start_date": "2026-02-01",
			}
		)
		overlapping.insert()
		self.assertRaises(frappe.ValidationError, overlapping.submit)

	def test_active_bed_cannot_be_double_booked(self):
		structure = make_structure()
		employee_a = make_employee()
		employee_b = make_employee()

		make_allocation(employee_a, structure)

		second = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee_b.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": structure.room.name,
				"bed": structure.bed.name,
				"start_date": today(),
			}
		)
		second.insert()
		self.assertRaises(frappe.ValidationError, second.submit)

	def test_bed_under_maintenance_cannot_be_allocated(self):
		structure = make_structure()
		employee = make_employee()

		bed = frappe.get_doc("Accommodation Bed", structure.bed.name)
		bed.status = "Maintenance"
		bed.save()

		allocation = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": structure.room.name,
				"bed": structure.bed.name,
				"start_date": today(),
			}
		)
		allocation.insert()
		self.assertRaises(frappe.ValidationError, allocation.submit)

	def test_employee_cannot_hold_two_active_allocations(self):
		structure = make_structure()
		employee = make_employee()
		make_allocation(employee, structure)

		second = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": structure.room.name,
				"bed": structure.beds[1].name,
				"start_date": today(),
			}
		)
		second.insert()
		self.assertRaises(frappe.ValidationError, second.submit)

	def test_hierarchy_mismatch_is_rejected(self):
		structure = make_structure()
		other = make_structure()
		employee = make_employee()

		allocation = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": other.room.name,
				"start_date": today(),
			}
		)
		self.assertRaises(frappe.ValidationError, allocation.insert)

	def test_bed_is_required_for_bed_level_site(self):
		structure = make_structure()
		employee = make_employee()

		allocation = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": structure.room.name,
				"start_date": today(),
			}
		)
		self.assertRaises(frappe.ValidationError, allocation.insert)

	def test_bed_is_optional_for_villa(self):
		structure = make_structure(
			accommodation_type="Other", sub_type="Villa", enable_bed_allocation=0, beds_per_room=0
		)
		employee = make_employee()

		allocation = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"floor": structure.floor.name,
				"room": structure.room.name,
				"start_date": today(),
			}
		)
		allocation.insert()
		allocation.submit()

		self.assertEqual(allocation.status, "Active")
		self.assertIsNone(allocation.bed)

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Provided")
		self.assertEqual(employee.current_accommodation_site, structure.site.name)

	def test_status_change_to_not_provided_releases_allocation(self):
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure)

		employee.reload()
		employee.accommodation_status = "Not Provided"
		employee.save()

		allocation.reload()
		self.assertEqual(allocation.status, "Closed")
		self.assertEqual(str(allocation.release_date), today())
		self.assertEqual(allocation.release_reason, "Accommodation Status Change")

		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Available")

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")
		self.assertIsNone(employee.current_accommodation_allocation)

	def test_status_change_to_allowance_releases_allocation(self):
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure)

		employee.reload()
		employee.accommodation_status = "Allowance"
		employee.accommodation_allowance_type = "Monthly"
		employee.accommodation_allowance_amount = 1500
		employee.save()

		allocation.reload()
		self.assertEqual(allocation.status, "Closed")
		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Available")

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Allowance")
		self.assertIsNone(employee.current_accommodation_bed)
		self.assertEqual(employee.accommodation_allowance_amount, 1500)
		self.assertEqual(str(employee.accommodation_allowance_from_date), today())

	def test_no_employee_stays_allocated_while_not_provided(self):
		structure = make_structure()
		employee = make_employee()
		make_allocation(employee, structure)

		for status in ("Allowance", "Not Provided"):
			employee.reload()
			employee.accommodation_status = status
			employee.save()

			self.assertFalse(
				frappe.db.exists(
					"Accommodation Allocation",
					{"employee": employee.name, "status": "Active", "docstatus": 1},
				),
				f"An active allocation survived the change to {status}.",
			)

	def test_masters_stay_active_after_release(self):
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure)
		allocation.release(reason="Employee Exit", employee_status="Not Provided")

		self.assertEqual(frappe.db.get_value("Accommodation Room", structure.room.name, "status"), "Active")
		self.assertEqual(frappe.db.get_value("Accommodation Floor", structure.floor.name, "status"), "Active")
		self.assertEqual(frappe.db.get_value("Accommodation Site", structure.site.name, "status"), "Active")
		self.assertEqual(
			frappe.db.get_value("Accommodation Location", structure.location.name, "status"), "Active"
		)

	def test_bed_cannot_be_marked_occupied_by_hand(self):
		structure = make_structure()
		bed = frappe.get_doc("Accommodation Bed", structure.bed.name)
		bed.status = "Occupied"
		self.assertRaises(frappe.ValidationError, bed.save)

	def test_occupied_bed_status_cannot_be_changed_by_hand(self):
		structure = make_structure()
		employee = make_employee()
		make_allocation(employee, structure)

		bed = frappe.get_doc("Accommodation Bed", structure.bed.name)
		bed.status = "Maintenance"
		self.assertRaises(frappe.ValidationError, bed.save)

	def test_cancelling_allocation_frees_the_bed(self):
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure)

		allocation.cancel()

		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Available")
		allocation.reload()
		self.assertEqual(allocation.status, "Cancelled")

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")

	def test_allocation_shows_the_bed_type(self):
		structure = make_structure()
		employee = make_employee()

		bunk = frappe.get_doc("Accommodation Bed", structure.beds[1].name)
		bunk.bed_type = "Bunk Upper"
		bunk.save()

		allocation = make_allocation(employee, structure, bed=bunk)

		self.assertEqual(allocation.bed_type, "Bunk Upper")

	def test_allocatable_bed_query_lists_free_beds_with_their_type(self):
		from gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation import (
			get_allocatable_beds,
		)

		structure = make_structure()
		employee = make_employee()

		lower = frappe.get_doc("Accommodation Bed", structure.beds[0].name)
		lower.bed_type = "Bunk Lower"
		lower.save()

		results = get_allocatable_beds("Accommodation Bed", "", "name", 0, 20, {"room": structure.room.name})
		self.assertIn((lower.name, "Bunk Lower"), results)

		make_allocation(employee, structure, bed=lower)

		results = get_allocatable_beds("Accommodation Bed", "", "name", 0, 20, {"room": structure.room.name})
		self.assertNotIn(lower.name, [row[0] for row in results])

	def test_release_date_before_start_date_is_rejected(self):
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure, start_date=today())

		self.assertRaises(
			frappe.ValidationError,
			allocation.release,
			release_date=add_days(today(), -5),
		)
