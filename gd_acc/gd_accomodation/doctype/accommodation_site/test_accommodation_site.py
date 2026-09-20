# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from gd_acc.gd_accomodation.api import set_master_status
from gd_acc.gd_accomodation.doctype.accommodation_allocation.test_accommodation_allocation import (
	make_employee,
	make_structure,
)
from gd_acc.gd_accomodation.doctype.accommodation_location.test_accommodation_location import (
	make_location,
)


def make_site(location=None, site_name=None, **kwargs):
	location = location or make_location()
	return frappe.get_doc(
		{
			"doctype": "Accommodation Site",
			"site_name": site_name or f"_Test Site {frappe.generate_hash(length=6)}",
			"location": location.name,
			"accommodation_type": "Camp",
			**kwargs,
		}
	).insert()


class TestAccommodationSite(FrappeTestCase):
	def test_code_is_generated_from_the_series(self):
		site = make_site()
		self.assertRegex(site.site_code, r"^SITE-\d{4,}$")

	def test_codes_increment_and_never_repeat(self):
		location = make_location()
		codes = [make_site(location).site_code for _ in range(3)]
		self.assertEqual(len(set(codes)), 3)

	def test_a_supplied_code_is_ignored(self):
		site = make_site(site_code="TYPED-BY-HAND")
		self.assertRegex(site.site_code, r"^SITE-\d{4,}$")

	def test_new_site_is_active_without_being_asked(self):
		self.assertEqual(make_site().status, "Active")

	def test_status_and_code_are_read_only_on_the_form(self):
		meta = frappe.get_meta("Accommodation Site")
		self.assertTrue(meta.get_field("status").read_only)
		self.assertTrue(meta.get_field("site_code").read_only)

	def test_occupied_master_cannot_be_disabled(self):
		structure = make_structure()
		employee = make_employee()

		allocation = frappe.get_doc(
			{
				"doctype": "Accommodation Allocation",
				"employee": employee.name,
				"location": structure.location.name,
				"site": structure.site.name,
				"bed": structure.bed.name,
				"start_date": today(),
			}
		)
		allocation.insert()
		allocation.submit()

		for doctype, name in (
			("Accommodation Site", structure.site.name),
			("Accommodation Location", structure.location.name),
			("Accommodation Floor", structure.floor.name),
			("Accommodation Room", structure.room.name),
		):
			self.assertRaises(frappe.ValidationError, set_master_status, doctype, name, "Inactive")

		allocation.release(reason="Employee Exit", employee_status="Not Provided")

		set_master_status("Accommodation Site", structure.site.name, "Inactive")
		self.assertEqual(frappe.db.get_value("Accommodation Site", structure.site.name, "status"), "Inactive")
