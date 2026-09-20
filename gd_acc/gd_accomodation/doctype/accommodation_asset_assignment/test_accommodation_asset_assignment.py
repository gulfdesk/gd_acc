# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from gd_acc.gd_accomodation.doctype.accommodation_allocation.test_accommodation_allocation import (
	make_employee,
	make_structure,
)


def make_item(category="Furniture", **kwargs):
	"""Create a catalogue item with a unique name so parallel runs never clash."""
	return frappe.get_doc(
		{
			"doctype": "Accommodation Item",
			"item_name": f"_Test Item {frappe.generate_hash(length=8)}",
			"item_category": category,
			**kwargs,
		}
	).insert()


def build_assignment(structure, employee, items, **kwargs):
	return frappe.get_doc(
		{
			"doctype": "Accommodation Asset Assignment",
			"status": "Assigned",
			"assignment_date": today(),
			"employee": employee.name,
			"location": structure.location.name,
			"site": structure.site.name,
			"floor": structure.floor.name,
			"room": structure.room.name,
			"bed": structure.bed.name,
			"items": items,
			**kwargs,
		}
	)


class TestAccommodationAssetAssignment(FrappeTestCase):
	def test_one_document_issues_several_items(self):
		structure = make_structure()
		employee = make_employee()
		cupboard = make_item()
		mattress = make_item(category="Bedding")
		kettle = make_item(category="Kitchen")

		assignment = build_assignment(
			structure,
			employee,
			[
				{"accommodation_item": cupboard.name, "quantity": 1},
				{"accommodation_item": mattress.name, "quantity": 2, "condition": "Good"},
				{"accommodation_item": kettle.name, "quantity": 1, "returned_quantity": 1},
			],
		)
		assignment.insert()

		self.assertEqual(len(assignment.items), 3)
		self.assertEqual(assignment.total_items, 4)
		self.assertEqual(assignment.items[1].item_category, "Bedding")
		self.assertEqual(assignment.items[0].condition, "New")

	def test_assignment_without_items_is_rejected(self):
		structure = make_structure()
		employee = make_employee()

		assignment = build_assignment(structure, employee, [])
		self.assertRaises(frappe.ValidationError, assignment.insert)

	def test_the_same_item_twice_is_rejected(self):
		structure = make_structure()
		employee = make_employee()
		blanket = make_item(category="Bedding")

		assignment = build_assignment(
			structure,
			employee,
			[
				{"accommodation_item": blanket.name, "quantity": 1},
				{"accommodation_item": blanket.name, "quantity": 2},
			],
		)
		self.assertRaises(frappe.ValidationError, assignment.insert)

	def test_returning_more_than_was_issued_is_rejected(self):
		structure = make_structure()
		employee = make_employee()
		helmet = make_item(category="Safety")

		assignment = build_assignment(
			structure,
			employee,
			[{"accommodation_item": helmet.name, "quantity": 2, "returned_quantity": 3}],
		)
		self.assertRaises(frappe.ValidationError, assignment.insert)

	def test_quantity_below_one_is_rejected(self):
		structure = make_structure()
		employee = make_employee()
		bucket = make_item(category="Cleaning")

		assignment = build_assignment(
			structure, employee, [{"accommodation_item": bucket.name, "quantity": 0}]
		)
		self.assertRaises(frappe.ValidationError, assignment.insert)
