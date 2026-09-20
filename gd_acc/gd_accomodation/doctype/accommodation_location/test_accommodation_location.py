# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from gd_acc.gd_accomodation.api import set_master_status


def make_location(location_name=None, **kwargs):
	return frappe.get_doc(
		{
			"doctype": "Accommodation Location",
			"location_name": location_name or f"_Test Loc {frappe.generate_hash(length=6)}",
			**kwargs,
		}
	).insert()


class TestAccommodationLocation(FrappeTestCase):
	def test_code_is_generated_from_the_series(self):
		location = make_location()
		self.assertRegex(location.location_code, r"^LOC-\d{4,}$")

	def test_codes_increment_and_never_repeat(self):
		codes = [make_location().location_code for _ in range(3)]

		self.assertEqual(len(set(codes)), 3)
		numbers = [int(re.sub(r"^LOC-", "", code)) for code in codes]
		self.assertEqual(numbers, sorted(numbers))
		self.assertEqual(numbers[1] - numbers[0], 1)

	def test_a_supplied_code_is_ignored(self):
		"""The field is system owned, so anything sent in is replaced."""
		location = make_location(location_code="TYPED-BY-HAND")
		self.assertRegex(location.location_code, r"^LOC-\d{4,}$")

	def test_new_location_is_active_without_being_asked(self):
		location = make_location()
		self.assertEqual(location.status, "Active")

	def test_status_is_read_only_on_the_form(self):
		meta = frappe.get_meta("Accommodation Location")
		self.assertTrue(meta.get_field("status").read_only)
		self.assertTrue(meta.get_field("location_code").read_only)

	def test_disable_and_enable_through_the_action(self):
		location = make_location()

		set_master_status("Accommodation Location", location.name, "Inactive")
		self.assertEqual(frappe.db.get_value("Accommodation Location", location.name, "status"), "Inactive")

		set_master_status("Accommodation Location", location.name, "Active")
		self.assertEqual(frappe.db.get_value("Accommodation Location", location.name, "status"), "Active")

	def test_an_invalid_status_is_rejected(self):
		location = make_location()
		self.assertRaises(
			frappe.ValidationError, set_master_status, "Accommodation Location", location.name, "Archived"
		)

	def test_a_doctype_without_a_status_cannot_be_toggled(self):
		self.assertRaises(
			frappe.ValidationError, set_master_status, "Accommodation Allocation", "any", "Inactive"
		)
