# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Shared accommodation logic.

Bed state, occupancy roll-ups and the employee's current accommodation are all
derived from Accommodation Allocation, which is the single source of truth.
Nothing in this module deletes or rewrites historical allocation records.
"""

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, now_datetime

# Master codes are system generated, read only, and never reused.
# Maps each master to its code field and naming series.
MASTER_CODE_SERIES = {
	"Accommodation Location": ("location_code", "LOC-.####"),
	"Accommodation Site": ("site_code", "SITE-.####"),
}

# Masters that can be enabled and disabled, and the Allocation field that
# tells us whether anybody still lives under them.
ENABLEABLE_MASTERS = {
	"Accommodation Location": "location",
	"Accommodation Site": "site",
	"Accommodation Floor": "floor",
	"Accommodation Room": "room",
}

# Accommodation Entitlement drives the employee's accommodation status.
ENTITLEMENT_TO_EMPLOYEE_STATUS = {
	"Company Accommodation": "Provided",
	"Allowance": "Allowance",
	"Not Provided": "Not Provided",
}

BED_STATUS_AVAILABLE = "Available"
BED_STATUS_OCCUPIED = "Occupied"

ALLOCATABLE_BED_STATUSES = (BED_STATUS_AVAILABLE,)

EMPLOYEE_CURRENT_FIELDS = (
	"current_accommodation_allocation",
	"current_accommodation_location",
	"current_accommodation_site",
	"current_accommodation_type",
	"current_accommodation_sub_type",
	"current_accommodation_floor",
	"current_accommodation_room",
	"current_accommodation_bed",
	"accommodation_start_date",
	"accommodation_expected_end_date",
)


def generate_master_code(doctype):
	"""Next code in this master's series, for example LOC-0001."""
	return make_autoname(MASTER_CODE_SERIES[doctype][1])


def count_active_allocations(doctype, name):
	"""How many employees are still housed under this master record."""
	scope_field = ENABLEABLE_MASTERS.get(doctype)
	if not scope_field:
		return 0

	return frappe.db.count(
		"Accommodation Allocation", {scope_field: name, "status": "Active", "docstatus": 1}
	)


def resolve_hierarchy(location=None, site=None, floor=None, room=None, bed=None):
	"""Fill in and verify the Location → Site → Floor → Room → Bed chain.

	Walks upward from the deepest level supplied so a caller may pass only a bed
	and still get a consistent set of parents back. Any value the caller did
	supply must match the real parent, otherwise this throws.
	"""
	if bed:
		bed_room = frappe.db.get_value("Accommodation Bed", bed, "room")
		if room and room != bed_room:
			frappe.throw(
				_("Bed {0} belongs to room {1}, not to {2}.").format(bed, bed_room, room),
				title=_("Inconsistent Hierarchy"),
			)
		room = bed_room

	if room:
		room_floor = frappe.db.get_value("Accommodation Room", room, "floor")
		if floor and floor != room_floor:
			frappe.throw(
				_("Room {0} belongs to floor {1}, not to {2}.").format(room, room_floor, floor),
				title=_("Inconsistent Hierarchy"),
			)
		floor = room_floor

	if floor:
		floor_site = frappe.db.get_value("Accommodation Floor", floor, "site")
		if site and site != floor_site:
			frappe.throw(
				_("Floor {0} belongs to site {1}, not to {2}.").format(floor, floor_site, site),
				title=_("Inconsistent Hierarchy"),
			)
		site = floor_site

	if site:
		site_location = frappe.db.get_value("Accommodation Site", site, "location")
		if location and location != site_location:
			frappe.throw(
				_("Site {0} belongs to location {1}, not to {2}.").format(site, site_location, location),
				title=_("Inconsistent Hierarchy"),
			)
		location = site_location

	return {"location": location, "site": site, "floor": floor, "room": room, "bed": bed}


def site_requires_bed(site):
	return bool(frappe.db.get_value("Accommodation Site", site, "enable_bed_allocation"))


def get_active_allocation(employee, exclude=None):
	"""Return the name of the employee's active allocation, if any."""
	filters = {"employee": employee, "status": "Active", "docstatus": 1}
	if exclude:
		filters["name"] = ("!=", exclude)

	return frappe.db.get_value("Accommodation Allocation", filters, "name")


def get_active_entitlement(employee, exclude=None):
	"""Return the name of the employee's active entitlement, if any."""
	filters = {"employee": employee, "status": "Active", "docstatus": 1}
	if exclude:
		filters["name"] = ("!=", exclude)

	return frappe.db.get_value("Accommodation Entitlement", filters, "name")


def close_stale_entitlement(employee, release_date, remarks=None):
	"""Keep the entitlement record honest after a release outside the Entitlement flow.

	Releasing a bed straight from the Allocation form (or the Employee tab's
	Release action, which calls the same whitelisted function) does not by
	itself touch Accommodation Entitlement. Without this, an old "Company
	Accommodation" entitlement would stay Active even though the employee no
	longer occupies a bed, which would misrepresent their real status. A fresh
	"Not Provided" entitlement records the change and closes the old one.
	"""
	active = get_active_entitlement(employee)
	if not active:
		return None

	entitlement_type = frappe.db.get_value("Accommodation Entitlement", active, "entitlement_type")
	if entitlement_type == "Not Provided":
		return None

	entitlement = frappe.new_doc("Accommodation Entitlement")
	entitlement.update(
		{
			"employee": employee,
			"entitlement_type": "Not Provided",
			"from_date": release_date,
			"remarks": remarks or _("Closed automatically because the accommodation was released."),
		}
	)
	entitlement.flags.ignore_permissions = True
	entitlement.insert()
	entitlement.submit()
	return entitlement.name


def get_conflicting_allocation(bed, start_date, end_date=None, exclude=None):
	"""Return an allocation that would overlap the given date range on this bed.

	An allocation that is still Active is treated as open ended because the bed
	is physically occupied until it is released. Closed allocations end on their
	release date, so historical stays may sit back to back without conflicting.
	"""
	if not bed:
		return None

	start_date = getdate(start_date)
	end_date = getdate(end_date) if end_date else None

	filters = {"bed": bed, "docstatus": 1, "status": ("in", ("Active", "Closed"))}
	if exclude:
		filters["name"] = ("!=", exclude)

	existing = frappe.get_all(
		"Accommodation Allocation",
		filters=filters,
		fields=["name", "employee", "employee_name", "start_date", "release_date", "status"],
	)

	for row in existing:
		other_start = getdate(row.start_date)
		other_end = getdate(row.release_date) if row.status == "Closed" and row.release_date else None

		starts_before_other_ends = other_end is None or start_date <= other_end
		other_starts_before_end = end_date is None or other_start <= end_date

		if starts_before_other_ends and other_starts_before_end:
			return row

	return None


def occupy_bed(bed, allocation, employee, start_date, reason="Allocation", transfer=None):
	update_bed_state(
		bed,
		status=BED_STATUS_OCCUPIED,
		employee=employee,
		allocation=allocation,
		occupied_since=start_date,
		reason=reason,
		transfer=transfer,
	)


def release_bed(bed, allocation=None, employee=None, reason="Release", transfer=None, remarks=None):
	update_bed_state(
		bed,
		status=BED_STATUS_AVAILABLE,
		employee=None,
		allocation=None,
		occupied_since=None,
		reason=reason,
		transfer=transfer,
		remarks=remarks,
		history_employee=employee,
		history_allocation=allocation,
	)


def update_bed_state(
	bed,
	*,
	status,
	employee=None,
	allocation=None,
	occupied_since=None,
	reason=None,
	transfer=None,
	remarks=None,
	history_employee=None,
	history_allocation=None,
):
	"""Write the bed's derived state and record the change in Bed Status History."""
	if not bed:
		return

	bed_doc = frappe.get_doc("Accommodation Bed", bed)
	previous_status = bed_doc.status
	previous_employee = bed_doc.current_employee

	bed_doc.db_set(
		{
			"status": status,
			"current_employee": employee,
			"current_employee_name": frappe.db.get_value("Employee", employee, "employee_name")
			if employee
			else None,
			"current_allocation": allocation,
			"occupied_since": occupied_since,
		},
		update_modified=True,
	)

	if previous_status != status or previous_employee != employee:
		log_bed_status_change(
			bed=bed,
			previous_status=previous_status,
			new_status=status,
			reason=reason,
			employee=history_employee or employee,
			allocation=history_allocation or allocation,
			transfer=transfer,
			remarks=remarks,
		)

	update_room_occupancy(bed_doc.room)


def log_bed_status_change(
	*,
	bed,
	previous_status,
	new_status,
	reason=None,
	employee=None,
	allocation=None,
	transfer=None,
	remarks=None,
):
	entry = frappe.new_doc("Bed Status History")
	entry.update(
		{
			"bed": bed,
			"previous_status": previous_status,
			"new_status": new_status,
			"change_datetime": now_datetime(),
			"reason": reason,
			"employee": employee,
			"allocation": allocation,
			"transfer": transfer,
			"changed_by": frappe.session.user,
			"remarks": remarks,
		}
	)
	entry.insert(ignore_permissions=True)
	return entry.name


def _bed_status_counts(fieldname, value):
	if not value:
		return {}

	rows = frappe.get_all(
		"Accommodation Bed",
		filters={fieldname: value},
		fields=["status", {"COUNT": "name", "as": "total"}],
		group_by="status",
	)
	return {row.status: row.total for row in rows}


def _rollup_suspended():
	"""Bulk setup suspends roll-ups and recalculates once at the end."""
	return bool(frappe.flags.get("skip_accommodation_rollup"))


def update_room_occupancy(room):
	if not room or _rollup_suspended():
		return

	counts = _bed_status_counts("room", room)
	total = sum(counts.values())
	occupied = counts.get(BED_STATUS_OCCUPIED, 0)
	available = counts.get(BED_STATUS_AVAILABLE, 0)

	frappe.db.set_value(
		"Accommodation Room",
		room,
		{
			"total_beds": total,
			"occupied_beds": occupied,
			"available_beds": available,
			"occupancy_percent": flt(occupied * 100.0 / total, 2) if total else 0,
		},
		update_modified=False,
	)

	floor = frappe.db.get_value("Accommodation Room", room, "floor")
	update_floor_occupancy(floor)


def update_floor_occupancy(floor):
	if not floor or _rollup_suspended():
		return

	counts = _bed_status_counts("floor", floor)
	frappe.db.set_value(
		"Accommodation Floor",
		floor,
		{
			"total_rooms": frappe.db.count("Accommodation Room", {"floor": floor}),
			"total_beds": sum(counts.values()),
			"occupied_beds": counts.get(BED_STATUS_OCCUPIED, 0),
			"available_beds": counts.get(BED_STATUS_AVAILABLE, 0),
		},
		update_modified=False,
	)

	site = frappe.db.get_value("Accommodation Floor", floor, "site")
	update_site_occupancy(site)


def update_site_occupancy(site):
	if not site or _rollup_suspended():
		return

	counts = _bed_status_counts("site", site)
	frappe.db.set_value(
		"Accommodation Site",
		site,
		{
			"total_floors": frappe.db.count("Accommodation Floor", {"site": site}),
			"total_rooms": frappe.db.count("Accommodation Room", {"site": site}),
			"total_beds": sum(counts.values()),
			"occupied_beds": counts.get(BED_STATUS_OCCUPIED, 0),
		},
		update_modified=False,
	)

	location = frappe.db.get_value("Accommodation Site", site, "location")
	update_location_occupancy(location)


def update_location_occupancy(location):
	if not location or _rollup_suspended():
		return

	counts = _bed_status_counts("location", location)
	frappe.db.set_value(
		"Accommodation Location",
		location,
		{
			"total_sites": frappe.db.count("Accommodation Site", {"location": location}),
			"total_rooms": frappe.db.count("Accommodation Room", {"location": location}),
			"total_beds": sum(counts.values()),
			"occupied_beds": counts.get(BED_STATUS_OCCUPIED, 0),
		},
		update_modified=False,
	)


def sync_employee_accommodation(employee, accommodation_status=None, entitlement=None):
	"""Rewrite the employee's current accommodation fields from the active allocation.

	These Employee fields are a projection of the allocation, never an
	independent record, so they are always rebuilt rather than patched.
	"""
	if not employee or not frappe.db.exists("Employee", employee):
		return

	allocation = get_active_allocation(employee)
	values = dict.fromkeys(EMPLOYEE_CURRENT_FIELDS)

	if allocation:
		row = frappe.db.get_value(
			"Accommodation Allocation",
			allocation,
			[
				"location",
				"site",
				"accommodation_type",
				"sub_type",
				"floor",
				"room",
				"bed",
				"start_date",
				"expected_end_date",
			],
			as_dict=True,
		)
		values.update(
			{
				"current_accommodation_allocation": allocation,
				"current_accommodation_location": row.location,
				"current_accommodation_site": row.site,
				"current_accommodation_type": row.accommodation_type,
				"current_accommodation_sub_type": row.sub_type,
				"current_accommodation_floor": row.floor,
				"current_accommodation_room": row.room,
				"current_accommodation_bed": row.bed,
				"accommodation_start_date": row.start_date,
				"accommodation_expected_end_date": row.expected_end_date,
			}
		)

	if accommodation_status:
		values["accommodation_status"] = accommodation_status

	# Passed explicitly when an entitlement drives the change, otherwise the
	# employee's current entitlement is simply re-derived.
	values["current_accommodation_entitlement"] = entitlement or get_active_entitlement(employee)

	frappe.db.set_value("Employee", employee, values, update_modified=False)
