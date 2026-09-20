# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Create entitlements for employees already living in company accommodation.

	Allocations existed before Accommodation Entitlement did. Without this the
	blanking rule in setup.py would wipe their status even though they are
	demonstrably housed, so each active allocation gets the entitlement it
	implies, dated from the day the stay began.
	"""
	if not frappe.db.exists("DocType", "Accommodation Entitlement"):
		return

	allocations = frappe.get_all(
		"Accommodation Allocation",
		filters={"status": "Active", "docstatus": 1},
		fields=["name", "employee", "start_date"],
		order_by="start_date asc",
	)

	for allocation in allocations:
		if frappe.db.exists(
			"Accommodation Entitlement",
			{"employee": allocation.employee, "status": "Active", "docstatus": 1},
		):
			continue

		entitlement = frappe.new_doc("Accommodation Entitlement")
		entitlement.update(
			{
				"employee": allocation.employee,
				"entitlement_type": "Company Accommodation",
				"from_date": allocation.start_date,
				"remarks": f"Created automatically from existing allocation {allocation.name}.",
			}
		)
		entitlement.flags.ignore_permissions = True
		entitlement.insert()
		entitlement.submit()
