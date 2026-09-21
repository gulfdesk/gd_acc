# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Pending Release: the step between an exit trigger and the actual release.

An employee exit, a relieving date or the end of a Company Accommodation
entitlement marks the current allocation Pending Release and notifies the
accommodation team once. The bed stays Occupied until a person releases the
allocation and records the returned items.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import formatdate, getdate, today

from gd_acc.gd_accomodation.accommodation_utils import CURRENT_STAY_STATUSES

ALLOCATION = "Accommodation Allocation"
PENDING_RELEASE = "Pending Release"

NOTIFY_ROLES = ("Accommodation Manager", "Accommodation User")
MANAGER_ROLES = ("Accommodation Manager", "System Manager")

# pending_release_reason -> release_reason proposed by the release dialog
PROPOSED_RELEASE_REASON = {
	"Employee Left": "Employee Exit",
	"Relieving Date Set": "Employee Exit",
	"Entitlement Ended": "Accommodation Status Change",
}


def handle_employee_update(doc, method=None):
	"""Employee on_update: an exit or a new relieving date starts the release."""
	before = doc.get_doc_before_save()
	if not before:
		return

	if doc.status == "Left" and before.status != "Left":
		mark_pending_release(doc.name, doc.relieving_date or today(), "Employee Left")
	elif doc.relieving_date and str(doc.relieving_date) != str(before.relieving_date or ""):
		mark_pending_release(doc.name, doc.relieving_date, "Relieving Date Set")


def handle_entitlement_update(entitlement):
	"""Entitlement on_update_after_submit: a new To Date ends the company stay."""
	if entitlement.entitlement_type != "Company Accommodation" or entitlement.status != "Active":
		return
	if not entitlement.to_date:
		return

	before = entitlement.get_doc_before_save()
	if before and str(before.to_date or "") == str(entitlement.to_date):
		return

	mark_pending_release(entitlement.employee, entitlement.to_date, "Entitlement Ended")


def mark_pending_release(employee, proposed_date, reason) -> str | None:
	"""Mark the employee's current allocation Pending Release. Return its name, or None."""
	row = frappe.db.get_value(
		ALLOCATION,
		{"employee": employee, "docstatus": 1, "status": ("in", CURRENT_STAY_STATUSES)},
		["name", "status", "start_date", "proposed_release_date"],
		as_dict=True,
		for_update=True,
	)
	if not row:
		return None

	proposed = max(getdate(proposed_date), getdate(row.start_date))

	if row.status == PENDING_RELEASE:
		# The team was told already. Only an earlier date moves the proposal.
		if not row.proposed_release_date or getdate(row.proposed_release_date) > proposed:
			frappe.db.set_value(ALLOCATION, row.name, "proposed_release_date", proposed)
		return row.name

	frappe.db.set_value(
		ALLOCATION,
		row.name,
		{
			"status": PENDING_RELEASE,
			"proposed_release_date": proposed,
			"pending_release_reason": reason,
		},
	)
	add_timeline_comment(
		row.name,
		_("Pending Release: {0}, proposed {1}.").format(_(reason), formatdate(proposed)),
	)
	notify_accommodation_team(row.name, employee, proposed, reason)
	return row.name


def notify_accommodation_team(allocation, employee, proposed, reason):
	"""Send one bell notification to each enabled Accommodation Manager and Accommodation User."""
	holders = frappe.get_all(
		"Has Role",
		filters={"role": ("in", NOTIFY_ROLES), "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	holders = [user for user in holders if user not in ("Administrator", "Guest")]
	if not holders:
		return

	# make_notification_logs looks the recipients up by email.
	emails = frappe.get_all(
		"User",
		filters={"name": ("in", holders), "enabled": 1, "user_type": "System User"},
		pluck="email",
	)
	emails = [email for email in emails if email]
	if not emails:
		return

	employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee
	make_notification_logs(
		frappe._dict(
			{
				"type": "Alert",
				"document_type": ALLOCATION,
				"document_name": allocation,
				"subject": _("Release accommodation of {0}: {1}, proposed {2}").format(
					employee_name, _(reason), formatdate(proposed)
				),
				"from_user": frappe.session.user,
			}
		),
		emails,
	)


@frappe.whitelist()
def keep_allocation_active(allocation):
	"""Return a Pending Release allocation to Active. The Accommodation Manager decides."""
	frappe.only_for(MANAGER_ROLES)

	status = frappe.db.get_value(ALLOCATION, allocation, "status", for_update=True)
	if status != PENDING_RELEASE:
		frappe.throw(
			_("Allocation {0} is {1}. Only a Pending Release allocation can be kept active.").format(
				frappe.bold(allocation), frappe.bold(_(status) if status else _("missing"))
			),
			title=_("Not Pending Release"),
		)

	frappe.db.set_value(
		ALLOCATION,
		allocation,
		{"status": "Active", "proposed_release_date": None, "pending_release_reason": None},
	)
	add_timeline_comment(allocation, _("Kept active by {0}.").format(frappe.session.user))
	return allocation


def add_timeline_comment(allocation, text):
	frappe.get_doc(ALLOCATION, allocation).add_comment("Info", text)
