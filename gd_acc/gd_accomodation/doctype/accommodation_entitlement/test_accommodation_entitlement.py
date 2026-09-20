# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from gd_acc.gd_accomodation.api import get_dashboard_data
from gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation import (
	release_allocation,
)
from gd_acc.gd_accomodation.doctype.accommodation_allocation.test_accommodation_allocation import (
	make_allocation,
	make_employee,
	make_structure,
)
from gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement import (
	create_entitlement,
	get_employee_entitlement_state,
)


def make_entitlement(employee, entitlement_type="Company Accommodation", submit=True, **kwargs):
	doc = frappe.get_doc(
		{
			"doctype": "Accommodation Entitlement",
			"employee": employee.name,
			"entitlement_type": entitlement_type,
			"from_date": kwargs.pop("from_date", today()),
			**kwargs,
		}
	)
	doc.insert()
	if submit:
		doc.submit()
	return doc


class TestAccommodationEntitlement(FrappeTestCase):
	def test_new_employee_defaults_to_not_provided(self):
		"""Not Provided is the baseline every employee starts at, no entitlement needed."""
		employee = make_employee()

		self.assertEqual(employee.accommodation_status, "Not Provided")
		self.assertFalse(employee.current_accommodation_entitlement)

		state = get_employee_entitlement_state(employee.name)
		self.assertIsNone(state["entitlement"])
		self.assertIsNone(state["active_allocation"])

	def test_employee_status_buckets_cover_every_employee(self):
		make_employee()
		kpi = get_dashboard_data()["kpi"]

		covered = kpi["employees_provided"] + kpi["employees_allowance"] + kpi["employees_not_provided"]
		self.assertEqual(covered, frappe.db.count("Employee"))

	def test_company_accommodation_marks_employee_provided(self):
		employee = make_employee()
		entitlement = make_entitlement(employee)

		self.assertEqual(entitlement.status, "Active")
		employee.reload()
		self.assertEqual(employee.accommodation_status, "Provided")
		self.assertEqual(employee.current_accommodation_entitlement, entitlement.name)

	def test_not_provided_marks_employee_not_provided(self):
		employee = make_employee()
		make_entitlement(employee, "Not Provided")

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")

	def test_allowance_marks_employee_allowance(self):
		employee = make_employee()
		entitlement = make_entitlement(employee, "Allowance", allowance_amount=1500)

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Allowance")
		self.assertEqual(entitlement.allowance_amount, 1500)

	def test_new_entitlement_closes_the_previous_one(self):
		employee = make_employee()
		first = make_entitlement(employee, "Not Provided", from_date=add_days(today(), -30))
		second = make_entitlement(employee, "Allowance", allowance_amount=1000)

		first.reload()
		self.assertEqual(first.status, "Closed")
		self.assertEqual(str(first.to_date), second.from_date)
		self.assertEqual(second.previous_entitlement, first.name)

	def test_release_date_is_required_when_leaving_company_accommodation(self):
		structure = make_structure()
		employee = make_employee()
		make_entitlement(employee)
		make_allocation(employee, structure)

		moving_off = frappe.get_doc(
			{
				"doctype": "Accommodation Entitlement",
				"employee": employee.name,
				"entitlement_type": "Allowance",
				"from_date": today(),
			}
		)
		self.assertRaises(frappe.ValidationError, moving_off.insert)

	def test_release_date_closes_the_allocation_and_frees_the_bed(self):
		structure = make_structure()
		employee = make_employee()
		make_entitlement(employee, from_date=add_days(today(), -60))
		allocation = make_allocation(employee, structure, start_date=add_days(today(), -60))

		release_on = add_days(today(), -1)
		make_entitlement(
			employee,
			"Allowance",
			allowance_amount=2000,
			release_date=release_on,
			release_reason="Employee Exit",
		)

		allocation.reload()
		self.assertEqual(allocation.status, "Closed")
		self.assertEqual(str(allocation.release_date), release_on)

		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Available")

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Allowance")
		self.assertIsNone(employee.current_accommodation_allocation)

	def test_release_date_cannot_precede_the_allocation(self):
		structure = make_structure()
		employee = make_employee()
		make_entitlement(employee)
		make_allocation(employee, structure, start_date=today())

		moving_off = frappe.get_doc(
			{
				"doctype": "Accommodation Entitlement",
				"employee": employee.name,
				"entitlement_type": "Not Provided",
				"from_date": today(),
				"release_date": add_days(today(), -10),
			}
		)
		self.assertRaises(frappe.ValidationError, moving_off.insert)

	def test_staying_on_company_accommodation_keeps_the_bed(self):
		structure = make_structure()
		employee = make_employee()
		make_entitlement(employee, from_date=add_days(today(), -30))
		allocation = make_allocation(employee, structure, start_date=add_days(today(), -30))

		renewed = make_entitlement(employee, "Company Accommodation")

		self.assertIsNone(renewed.previous_allocation)
		allocation.reload()
		self.assertEqual(allocation.status, "Active")
		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Occupied")

	def test_history_is_preserved_across_several_entitlements(self):
		structure = make_structure()
		employee = make_employee()

		make_entitlement(employee, "Not Provided", from_date=add_days(today(), -90))
		make_entitlement(employee, "Company Accommodation", from_date=add_days(today(), -60))
		make_allocation(employee, structure, start_date=add_days(today(), -60))
		make_entitlement(employee, "Allowance", allowance_amount=1200, release_date=add_days(today(), -10))

		state = get_employee_entitlement_state(employee.name)

		self.assertEqual(len(state["entitlements"]), 3)
		self.assertEqual(state["entitlement"]["entitlement_type"], "Allowance")
		self.assertEqual(len(state["allocations"]), 1)
		self.assertEqual(state["allocations"][0]["status"], "Closed")
		self.assertIsNone(state["active_allocation"])

		statuses = [row["status"] for row in state["entitlements"]]
		self.assertEqual(statuses.count("Active"), 1)
		self.assertEqual(statuses.count("Closed"), 2)

	def test_a_replaced_entitlement_cannot_be_cancelled(self):
		employee = make_employee()
		first = make_entitlement(employee, "Not Provided", from_date=add_days(today(), -5))
		make_entitlement(employee, "Allowance", allowance_amount=500)

		first.reload()
		self.assertRaises(frappe.ValidationError, first.cancel)

	def test_cancelling_restores_the_previous_entitlement(self):
		employee = make_employee()
		first = make_entitlement(employee, "Not Provided", from_date=add_days(today(), -5))
		second = make_entitlement(employee, "Allowance", allowance_amount=500)

		second.reload()
		second.cancel()

		first.reload()
		self.assertEqual(first.status, "Active")
		self.assertIsNone(first.to_date)

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")


class TestCreateEntitlement(FrappeTestCase):
	"""The single-save flow used by the Employee tab's Create Entitlement dialog."""

	def test_company_accommodation_creates_allocation_and_entitlement_together(self):
		structure = make_structure()
		employee = make_employee()

		result = create_entitlement(
			employee=employee.name,
			entitlement_type="Company Accommodation",
			from_date=today(),
			location=structure.location.name,
			site=structure.site.name,
			floor=structure.floor.name,
			room=structure.room.name,
			bed=structure.bed.name,
		)

		self.assertTrue(result["entitlement"])
		self.assertTrue(result["allocation"])

		employee.reload()
		self.assertEqual(employee.accommodation_status, "Provided")
		self.assertEqual(employee.current_accommodation_allocation, result["allocation"])
		self.assertEqual(employee.current_accommodation_entitlement, result["entitlement"])
		self.assertEqual(frappe.db.get_value("Accommodation Bed", structure.bed.name, "status"), "Occupied")

	def test_company_accommodation_without_a_free_bed_creates_nothing(self):
		structure = make_structure()
		other_employee = make_employee()
		employee = make_employee()

		make_allocation(other_employee, structure)

		self.assertRaises(
			frappe.ValidationError,
			create_entitlement,
			employee=employee.name,
			entitlement_type="Company Accommodation",
			from_date=today(),
			location=structure.location.name,
			site=structure.site.name,
			bed=structure.bed.name,
		)

		self.assertFalse(frappe.db.exists("Accommodation Entitlement", {"employee": employee.name}))
		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")

	def test_allowance_via_create_entitlement(self):
		employee = make_employee()

		result = create_entitlement(
			employee=employee.name,
			entitlement_type="Allowance",
			from_date=today(),
			allowance_amount=1800,
		)

		self.assertIsNone(result["allocation"])
		employee.reload()
		self.assertEqual(employee.accommodation_status, "Allowance")
		self.assertEqual(
			frappe.db.get_value("Accommodation Entitlement", result["entitlement"], "allowance_amount"),
			1800,
		)

	def test_switching_from_allowance_to_company_accommodation(self):
		structure = make_structure()
		employee = make_employee()

		first = create_entitlement(
			employee=employee.name, entitlement_type="Allowance", from_date=today(), allowance_amount=500
		)

		second = create_entitlement(
			employee=employee.name,
			entitlement_type="Company Accommodation",
			from_date=today(),
			location=structure.location.name,
			site=structure.site.name,
			bed=structure.bed.name,
		)

		self.assertEqual(
			frappe.db.get_value("Accommodation Entitlement", first["entitlement"], "status"), "Closed"
		)
		employee.reload()
		self.assertEqual(employee.accommodation_status, "Provided")
		self.assertEqual(employee.current_accommodation_entitlement, second["entitlement"])


class TestReleaseClosesStaleEntitlement(FrappeTestCase):
	"""Releasing directly (Allocation form or the Employee tab) must not leave
	an old Company Accommodation entitlement looking Active."""

	def test_release_closes_the_active_entitlement(self):
		structure = make_structure()
		employee = make_employee()

		created = create_entitlement(
			employee=employee.name,
			entitlement_type="Company Accommodation",
			from_date=today(),
			location=structure.location.name,
			site=structure.site.name,
			bed=structure.bed.name,
		)

		release_allocation(created["allocation"], release_date=today(), reason="Employee Exit")

		self.assertEqual(
			frappe.db.get_value("Accommodation Entitlement", created["entitlement"], "status"), "Closed"
		)
		employee.reload()
		self.assertEqual(employee.accommodation_status, "Not Provided")
		self.assertTrue(employee.current_accommodation_entitlement)
		self.assertNotEqual(employee.current_accommodation_entitlement, created["entitlement"])

		new_entitlement = frappe.get_doc(
			"Accommodation Entitlement", employee.current_accommodation_entitlement
		)
		self.assertEqual(new_entitlement.entitlement_type, "Not Provided")

	def test_release_of_allocation_created_directly_needs_no_entitlement(self):
		"""An allocation made straight from the Accommodation module, with no
		entitlement behind it, must still release cleanly."""
		structure = make_structure()
		employee = make_employee()
		allocation = make_allocation(employee, structure)

		self.assertFalse(employee.current_accommodation_entitlement)

		release_allocation(allocation.name, release_date=today(), reason="Manual Release")

		self.assertFalse(
			frappe.db.exists("Accommodation Entitlement", {"employee": employee.name}),
			"No entitlement should be invented where none existed before.",
		)
		self.assertEqual(
			frappe.db.get_value("Employee", employee.name, "accommodation_status"), "Not Provided"
		)
