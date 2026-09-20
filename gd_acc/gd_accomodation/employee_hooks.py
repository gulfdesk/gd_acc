# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Keeps Employee.accommodation_status consistent with physical allocations.

An employee must never sit in an active bed allocation while marked Allowance
or Not Provided, so moving away from Provided releases the allocation instead
of leaving the two records disagreeing.
"""

import frappe
from frappe import _
from frappe.utils import today

from gd_acc.gd_accomodation.accommodation_utils import (
	EMPLOYEE_CURRENT_FIELDS,
	get_active_allocation,
)

RELEASING_STATUSES = ("Not Provided", "Allowance")


def validate_accommodation_status(doc, method=None):
	doc.flags.release_accommodation = False

	if doc.is_new():
		return

	before = doc.get_doc_before_save()
	if not before:
		return

	previous = before.get("accommodation_status") or "Not Provided"
	current = doc.get("accommodation_status") or "Not Provided"
	if previous == current:
		return

	if current in RELEASING_STATUSES and get_active_allocation(doc.name):
		doc.flags.release_accommodation = True

	if current == "Allowance" and not doc.get("accommodation_allowance_from_date"):
		doc.accommodation_allowance_from_date = today()

	if previous == "Allowance" and current == "Not Provided":
		if not doc.get("accommodation_allowance_to_date"):
			doc.accommodation_allowance_to_date = today()

	if current == "Provided" and not get_active_allocation(doc.name):
		frappe.msgprint(
			_("Create an Accommodation Allocation for {0} to record where the employee lives.").format(
				frappe.bold(doc.employee_name or doc.name)
			),
			title=_("Allocation Required"),
			indicator="orange",
		)


def handle_accommodation_status_change(doc, method=None):
	if not doc.flags.get("release_accommodation"):
		return

	allocation_name = get_active_allocation(doc.name)
	if not allocation_name:
		return

	allocation = frappe.get_doc("Accommodation Allocation", allocation_name)
	allocation.release(
		release_date=today(),
		reason="Accommodation Status Change",
		remarks=_("Accommodation status changed to {0}.").format(doc.accommodation_status),
	)

	for fieldname in EMPLOYEE_CURRENT_FIELDS:
		doc.set(fieldname, None)

	frappe.msgprint(
		_("Allocation {0} was closed and bed {1} released because the status changed to {2}.").format(
			frappe.bold(allocation.name),
			frappe.bold(allocation.bed or allocation.room or allocation.site),
			frappe.bold(doc.accommodation_status),
		),
		title=_("Accommodation Released"),
		indicator="blue",
	)
