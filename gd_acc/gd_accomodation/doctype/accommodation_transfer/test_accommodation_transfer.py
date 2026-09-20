# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from gd_acc.gd_accomodation.doctype.accommodation_allocation.test_accommodation_allocation import (
	make_allocation,
	make_employee,
	make_structure,
)


def make_transfer(employee, allocation, destination, bed=None, submit=True, **kwargs):
	transfer = frappe.get_doc(
		{
			"doctype": "Accommodation Transfer",
			"employee": employee.name,
			"current_allocation": allocation.name,
			"transfer_date": today(),
			"to_location": destination.location.name,
			"to_site": destination.site.name,
			"to_floor": destination.floor.name,
			"to_room": destination.room.name,
			"to_bed": (bed or destination.bed).name if (bed or destination.bed) else None,
			"reason": "Test transfer",
			**kwargs,
		}
	)
	transfer.insert()
	if submit:
		transfer.submit()
	return transfer


class TestAccommodationTransfer(FrappeTestCase):
	def test_transfer_closes_old_and_opens_new_allocation(self):
		origin = make_structure()
		destination = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, origin)

		transfer = make_transfer(employee, allocation, destination)

		self.assertEqual(transfer.status, "Completed")
		self.assertTrue(transfer.new_allocation)

		allocation.reload()
		self.assertEqual(allocation.status, "Closed")
		self.assertEqual(str(allocation.release_date), today())
		self.assertEqual(allocation.release_reason, "Transfer")
		self.assertEqual(allocation.released_by_transfer, transfer.name)

		self.assertEqual(frappe.db.get_value("Accommodation Bed", origin.bed.name, "status"), "Available")
		self.assertEqual(frappe.db.get_value("Accommodation Bed", destination.bed.name, "status"), "Occupied")

		new_allocation = frappe.get_doc("Accommodation Allocation", transfer.new_allocation)
		self.assertEqual(new_allocation.status, "Active")
		self.assertEqual(new_allocation.employee, employee.name)
		self.assertEqual(new_allocation.bed, destination.bed.name)
		self.assertEqual(str(new_allocation.start_date), today())

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Provided")
		self.assertEqual(employee.current_accommodation_allocation, new_allocation.name)
		self.assertEqual(employee.current_accommodation_bed, destination.bed.name)

	def test_transfer_preserves_both_stays(self):
		origin = make_structure()
		destination = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, origin, start_date="2026-01-01")

		make_transfer(employee, allocation, destination)

		history = frappe.get_all(
			"Accommodation Allocation",
			filters={"employee": employee.name, "docstatus": 1},
			fields=["name", "status", "bed", "start_date"],
		)
		self.assertEqual(len(history), 2)
		self.assertEqual({row.status for row in history}, {"Closed", "Active"})

		bed_history = frappe.get_all(
			"Bed Status History",
			filters={"bed": origin.bed.name},
			fields=["new_status", "reason"],
		)
		self.assertIn("Transfer Out", [row.reason for row in bed_history])

	def test_transfer_to_occupied_bed_is_rejected(self):
		origin = make_structure()
		destination = make_structure()
		employee = make_employee()
		other_employee = make_employee()

		allocation = make_allocation(employee, origin)
		make_allocation(other_employee, destination)

		transfer = frappe.get_doc(
			{
				"doctype": "Accommodation Transfer",
				"employee": employee.name,
				"current_allocation": allocation.name,
				"transfer_date": today(),
				"to_location": destination.location.name,
				"to_site": destination.site.name,
				"to_floor": destination.floor.name,
				"to_room": destination.room.name,
				"to_bed": destination.bed.name,
			}
		)
		transfer.insert()
		self.assertRaises(frappe.ValidationError, transfer.submit)

	def test_transfer_to_same_bed_is_rejected(self):
		origin = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, origin)

		transfer = frappe.get_doc(
			{
				"doctype": "Accommodation Transfer",
				"employee": employee.name,
				"current_allocation": allocation.name,
				"transfer_date": today(),
				"to_location": origin.location.name,
				"to_site": origin.site.name,
				"to_floor": origin.floor.name,
				"to_room": origin.room.name,
				"to_bed": origin.bed.name,
			}
		)
		self.assertRaises(frappe.ValidationError, transfer.insert)

	def test_completed_transfer_cannot_be_cancelled(self):
		origin = make_structure()
		destination = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, origin)

		transfer = make_transfer(employee, allocation, destination)
		self.assertRaises(frappe.ValidationError, transfer.cancel)

	def test_transfer_requires_an_active_allocation(self):
		origin = make_structure()
		destination = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, origin)
		allocation.release(reason="Employee Exit", employee_status="Not Provided")

		transfer = frappe.get_doc(
			{
				"doctype": "Accommodation Transfer",
				"employee": employee.name,
				"current_allocation": allocation.name,
				"transfer_date": today(),
				"to_location": destination.location.name,
				"to_site": destination.site.name,
				"to_floor": destination.floor.name,
				"to_room": destination.room.name,
				"to_bed": destination.bed.name,
			}
		)
		self.assertRaises(frappe.ValidationError, transfer.insert)
