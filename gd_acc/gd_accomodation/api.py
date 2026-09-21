# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Whitelisted endpoints for the Employee accommodation tab and the dashboard."""

import frappe
from frappe import _
from frappe.utils import flt

from gd_acc.gd_accomodation.accommodation_utils import (
	ENABLEABLE_MASTERS,
	count_active_allocations,
)

BED_STATUSES = ("Available", "Occupied", "Reserved", "Maintenance", "Blocked", "Inactive")


@frappe.whitelist()
def set_master_status(doctype, name, status):
	"""Enable or disable an accommodation master record.

	Status is system owned rather than a free field, so it moves only through
	this action and only when nobody is still housed under the record.
	"""
	if doctype not in ENABLEABLE_MASTERS:
		frappe.throw(_("{0} cannot be enabled or disabled.").format(doctype))

	if status not in ("Active", "Inactive"):
		frappe.throw(_("Status must be Active or Inactive."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")

	if doc.status == status:
		return status

	if status == "Inactive":
		occupants = count_active_allocations(doctype, name)
		if occupants:
			frappe.throw(
				_("{0} still houses {1} employee(s). Release or transfer them before disabling it.").format(
					frappe.bold(name), occupants
				),
				title=_("Still Occupied"),
			)

	doc.db_set("status", status)
	return status


@frappe.whitelist()
def get_employee_accommodation_history(employee):
	"""Every stay this employee has had, newest first. Read only, never trimmed."""
	if not frappe.has_permission("Employee", "read", doc=employee):
		frappe.throw(_("Not permitted to read this employee."), frappe.PermissionError)

	allocations = frappe.get_all(
		"Accommodation Allocation",
		filters={"employee": employee, "docstatus": ("!=", 2)},
		fields=[
			"name",
			"status",
			"start_date",
			"release_date",
			"expected_end_date",
			"location",
			"site",
			"accommodation_type",
			"sub_type",
			"floor",
			"room",
			"bed",
			"release_reason",
			"released_by_transfer",
		],
		order_by="start_date desc, creation desc",
	)

	transfers = frappe.get_all(
		"Accommodation Transfer",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "transfer_date", "from_site", "to_site", "from_bed", "to_bed", "reason"],
		order_by="transfer_date desc",
	)

	return {"allocations": allocations, "transfers": transfers}


@frappe.whitelist()
def get_dashboard_data(location=None, site=None):
	"""KPI totals and occupancy breakdowns for the Accommodation dashboard."""
	if not frappe.has_permission("Accommodation Allocation", "read"):
		frappe.throw(_("Not permitted to view accommodation data."), frappe.PermissionError)

	bed_filters = {}
	if location:
		bed_filters["location"] = location
	if site:
		bed_filters["site"] = site

	counts = {
		row.status: row.total
		for row in frappe.get_all(
			"Accommodation Bed",
			filters=bed_filters,
			fields=["status", {"COUNT": "name", "as": "total"}],
			group_by="status",
		)
	}

	total_beds = sum(counts.values())
	occupied = counts.get("Occupied", 0)

	structure_filters = dict(bed_filters)

	# Beds sitting at Maintenance and open maintenance requests are different
	# counts: a bed can be flagged by hand without a request, and a request
	# need not take its bed out of service. Both are reported separately.
	kpi = {
		"locations": frappe.db.count("Accommodation Location", {"name": location} if location else None),
		"sites": frappe.db.count("Accommodation Site", structure_filters_for_site(location, site)),
		"floors": frappe.db.count("Accommodation Floor", structure_filters),
		"rooms": frappe.db.count("Accommodation Room", structure_filters),
		"beds": total_beds,
		"available": counts.get("Available", 0),
		"occupied": occupied,
		"reserved": counts.get("Reserved", 0),
		"maintenance": counts.get("Maintenance", 0),
		"blocked": counts.get("Blocked", 0),
		"inactive": counts.get("Inactive", 0),
		"occupancy_percent": flt(occupied * 100.0 / total_beds, 2) if total_beds else 0,
		**count_employees_by_entitlement(),
		"open_maintenance_requests": frappe.db.count(
			"Accommodation Maintenance", get_maintenance_filters(location, site)
		),
		"pending_release": frappe.db.count(
			"Accommodation Allocation", {"docstatus": 1, "status": "Pending Release", **bed_filters}
		),
		# An entitlement has no location, so the location and site filters do not apply.
		"awaiting_bed": frappe.db.count(
			"Accommodation Entitlement",
			{
				"docstatus": 1,
				"status": "Active",
				"entitlement_type": "Company Accommodation",
				"stay_status": ("in", ("Awaiting Bed", "Vacated")),
			},
		),
	}

	return {
		"kpi": kpi,
		"by_location": get_occupancy_breakdown("location", bed_filters),
		"by_site": get_occupancy_breakdown("site", bed_filters),
		"by_site_type": get_site_type_breakdown(bed_filters),
		"open_maintenance": get_open_maintenance(location, site),
	}


def count_employees_by_entitlement():
	"""Active employees by the type of their current entitlement. No entitlement counts as Not Provided."""
	rows = frappe.db.sql(
		"""
		select e.entitlement_type, count(distinct e.employee) as total
		from `tabAccommodation Entitlement` e
		join `tabEmployee` emp on emp.name = e.employee
		where e.docstatus = 1 and e.status = 'Active' and emp.status = 'Active'
		group by e.entitlement_type
		""",
		as_dict=True,
	)
	counts = {row.entitlement_type: row.total for row in rows}
	provided = counts.get("Company Accommodation", 0)
	allowance = counts.get("Allowance", 0)

	return {
		"employees_provided": provided,
		"employees_allowance": allowance,
		"employees_not_provided": frappe.db.count("Employee", {"status": "Active"}) - provided - allowance,
	}


def structure_filters_for_site(location, site):
	filters = {}
	if location:
		filters["location"] = location
	if site:
		filters["name"] = site
	return filters


def get_occupancy_breakdown(group_field, bed_filters):
	rows = frappe.get_all(
		"Accommodation Bed",
		filters=bed_filters,
		fields=[group_field, "status", {"COUNT": "name", "as": "total"}],
		group_by=f"{group_field}, status",
	)

	grouped = {}
	for row in rows:
		key = row.get(group_field)
		if not key:
			continue

		entry = grouped.setdefault(key, {"name": key, "total": 0, **dict.fromkeys(BED_STATUSES, 0)})
		entry[row.status] = row.total
		entry["total"] += row.total

	for entry in grouped.values():
		entry["occupancy_percent"] = (
			flt(entry["Occupied"] * 100.0 / entry["total"], 2) if entry["total"] else 0
		)

	return sorted(grouped.values(), key=lambda entry: entry["name"])


def get_site_type_breakdown(bed_filters):
	sites = {
		row.name: row.accommodation_type
		for row in frappe.get_all("Accommodation Site", fields=["name", "accommodation_type"])
	}

	grouped = {}
	for entry in get_occupancy_breakdown("site", bed_filters):
		site_type = sites.get(entry["name"]) or _("Unspecified")
		bucket = grouped.setdefault(
			site_type, {"name": site_type, "total": 0, **dict.fromkeys(BED_STATUSES, 0)}
		)
		bucket["total"] += entry["total"]
		for status in BED_STATUSES:
			bucket[status] += entry.get(status, 0)

	for bucket in grouped.values():
		bucket["occupancy_percent"] = (
			flt(bucket["Occupied"] * 100.0 / bucket["total"], 2) if bucket["total"] else 0
		)

	return sorted(grouped.values(), key=lambda bucket: bucket["name"])


def get_maintenance_filters(location=None, site=None):
	filters = {"status": ("in", ("Open", "In Progress"))}
	if location:
		filters["location"] = location
	if site:
		filters["site"] = site
	return filters


def get_open_maintenance(location=None, site=None):
	requests = frappe.get_all(
		"Accommodation Maintenance",
		filters=get_maintenance_filters(location, site),
		fields=[
			"name",
			"subject",
			"issue_type",
			"priority",
			"status",
			"location",
			"site",
			"room",
			"bed",
			"reported_on",
		],
		order_by="reported_on asc",
	)

	priority_rank = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
	requests.sort(key=lambda row: priority_rank.get(row.priority, 4))
	return requests
