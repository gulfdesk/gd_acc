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

# The label that the report and the dashboard show for each entitlement type.
ENTITLEMENT_TO_EMPLOYEE_STATUS = {
	"Company Accommodation": "Provided",
	"Allowance": "Allowance",
	"Not Provided": "Not Provided",
}

# The place fields that an allocation and an Item Entry share, top level first.
HOLDER_FIELDS = ("location", "site", "floor", "room", "bed")

BED_STATUS_AVAILABLE = "Available"
BED_STATUS_OCCUPIED = "Occupied"
BED_STATUS_BLOCKED = "Blocked"
BED_STATUS_MAINTENANCE = "Maintenance"

ALLOCATABLE_BED_STATUSES = (BED_STATUS_AVAILABLE,)

GENDER_ANY = "Any"

# Allocation statuses of an employee who still lives in the place.
CURRENT_STAY_STATUSES = ("Active", "Pending Release")

# The places above a bed, top level first, with the label a message shows.
HIERARCHY_LEVELS = (
	("Accommodation Location", "location", "Location"),
	("Accommodation Site", "site", "Site"),
	("Accommodation Floor", "floor", "Floor"),
	("Accommodation Room", "room", "Room"),
)

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
		"Accommodation Allocation",
		{scope_field: name, "status": ("in", CURRENT_STAY_STATUSES), "docstatus": 1},
	)


def count_current_stays(room):
	"""How many employees live in this room now (Active or Pending Release)."""
	return frappe.db.count(
		"Accommodation Allocation",
		{"room": room, "docstatus": 1, "status": ("in", CURRENT_STAY_STATUSES)},
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


def get_site_gender(site):
	"""Return the Gender Restriction of a site. A missing site or value means Any."""
	return (site and frappe.db.get_value("Accommodation Site", site, "gender_restriction")) or GENDER_ANY


def site_requires_bed(site):
	return bool(frappe.db.get_value("Accommodation Site", site, "enable_bed_allocation"))


def get_active_allocation(employee, exclude=None):
	"""Return the name of the employee's current allocation (Active or Pending Release), if any."""
	filters = {"employee": employee, "status": ("in", CURRENT_STAY_STATUSES), "docstatus": 1}
	if exclude:
		filters["name"] = ("!=", exclude)

	return frappe.db.get_value("Accommodation Allocation", filters, "name")


def get_active_entitlement(employee, exclude=None):
	"""Return the name of the employee's active entitlement, if any."""
	filters = {"employee": employee, "status": "Active", "docstatus": 1}
	if exclude:
		filters["name"] = ("!=", exclude)

	return frappe.db.get_value("Accommodation Entitlement", filters, "name", order_by="from_date desc")


def refresh_stay_status(employee):
	"""Set the Stay Status of the current Company Accommodation entitlement from the allocations."""
	entitlement = frappe.db.get_value(
		"Accommodation Entitlement",
		{
			"employee": employee,
			"docstatus": 1,
			"status": "Active",
			"entitlement_type": "Company Accommodation",
		},
		["name", "from_date"],
		as_dict=True,
		order_by="from_date desc",
	)
	if not entitlement:
		return

	if get_active_allocation(employee):
		status = "Allocated"
	elif frappe.db.exists(
		"Accommodation Allocation",
		{
			"employee": employee,
			"docstatus": 1,
			"status": "Closed",
			"release_date": (">=", entitlement.from_date),
		},
	):
		status = "Vacated"
	else:
		status = "Awaiting Bed"

	frappe.db.set_value(
		"Accommodation Entitlement", entitlement.name, "stay_status", status, update_modified=False
	)


def get_conflicting_allocation(bed, start_date, end_date=None, exclude=None):
	"""Return an allocation that would overlap the given date range on this bed.

	An allocation that is still Active or Pending Release is treated as open ended because the bed
	is physically occupied until it is released. Closed allocations end on their
	release date, so historical stays may sit back to back without conflicting.
	"""
	if not bed:
		return None

	start_date = getdate(start_date)
	end_date = getdate(end_date) if end_date else None

	filters = {"bed": bed, "docstatus": 1, "status": ("in", (*CURRENT_STAY_STATUSES, "Closed"))}
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


def validate_placement(
	*,
	employee,
	employee_id,
	company,
	location,
	site,
	floor=None,
	room=None,
	bed=None,
	start_date,
	end_date=None,
	exclude=None,
):
	"""Run every check a new stay must pass. Call it inside the submit transaction.

	The bed row is locked first, so every later read sees the committed state and
	a second submit for the same bed waits until this transaction ends.
	`employee` is the name that the messages show. `employee_id` is the Employee
	record name.
	"""
	places = {"location": location, "site": site, "floor": floor, "room": room}
	bed_row = lock_bed(bed)
	check_hierarchy_active(places)
	check_company(company, location, employee)
	check_gender(employee_id, employee, site)
	check_holds(room)
	check_bed(bed, bed_row, start_date, end_date, exclude)


def lock_bed(bed):
	"""Lock the bed row with SELECT ... FOR UPDATE. Returns its status and room, or None."""
	if not bed:
		return None
	return frappe.db.get_value("Accommodation Bed", bed, ["status", "room"], as_dict=True, for_update=True)


def check_hierarchy_active(places):
	for doctype, fieldname, label in HIERARCHY_LEVELS:
		name = places.get(fieldname)
		if not name:
			continue
		if frappe.db.get_value(doctype, name, "status") == "Inactive":
			frappe.throw(
				_("{0} {1} is Inactive. Enable it or choose another {0}.").format(_(label), frappe.bold(name)),
				title=_("Inactive {0}").format(_(label)),
			)


def check_company(company, location, employee):
	location_company = frappe.db.get_value("Accommodation Location", location, "company")
	if not location_company:
		frappe.throw(
			_("Set the Company on Location {0} before you house anyone there.").format(frappe.bold(location)),
			title=_("Company Missing"),
		)

	if company != location_company:
		frappe.throw(
			_("Location {0} belongs to {1}. {2} belongs to {3}.").format(
				frappe.bold(location),
				frappe.bold(location_company),
				frappe.bold(employee),
				frappe.bold(company or _("no company")),
			),
			title=_("Company Mismatch"),
		)


def check_gender(employee_id, employee, site):
	restriction = get_site_gender(site)
	if restriction == GENDER_ANY:
		return

	gender = frappe.db.get_value("Employee", employee_id, "gender")
	if not gender:
		frappe.throw(
			_("Set the Gender of {0}. Site {1} is for {2} employees only.").format(
				frappe.bold(employee), frappe.bold(site), _(restriction)
			),
			title=_("Gender Restriction"),
		)

	if gender != restriction:
		frappe.throw(
			_("Site {0} is for {1} employees only. {2} is {3}.").format(
				frappe.bold(site), _(restriction), frappe.bold(employee), _(gender)
			),
			title=_("Gender Restriction"),
		)


def check_holds(room):
	"""Refuse a room that is Blocked or under maintenance. A held bed fails check_bed."""
	if not room:
		return

	hold = frappe.db.get_value(
		"Accommodation Room", room, ["is_blocked", "hold_reason", "under_maintenance"], as_dict=True
	)
	if not hold:
		return

	if hold.is_blocked:
		frappe.throw(
			_("Room {0} is Blocked: {1}.").format(frappe.bold(room), hold.hold_reason or _("no reason")),
			title=_("Room On Hold"),
		)

	if hold.under_maintenance:
		frappe.throw(_("Room {0} is under maintenance.").format(frappe.bold(room)), title=_("Room On Hold"))


def check_bed(bed, bed_row, start_date, end_date=None, exclude=None):
	"""Refuse a bed that overlaps another stay or is not Available. bed_row is read under the lock."""
	if not bed:
		return

	conflict = get_conflicting_allocation(bed, start_date, end_date, exclude=exclude)
	if conflict:
		frappe.throw(
			_("Bed {0} is already allocated to {1} under {2} for an overlapping period.").format(
				frappe.bold(bed),
				frappe.bold(conflict.employee_name or conflict.employee),
				frappe.bold(conflict.name),
			),
			title=_("Double Booking"),
		)

	bed_status = bed_row.status if bed_row else None
	if bed_status not in ALLOCATABLE_BED_STATUSES:
		frappe.throw(
			_("Bed {0} is {1} and cannot be allocated. Only {2} beds can be allocated.").format(
				frappe.bold(bed), frappe.bold(bed_status), frappe.bold(_(BED_STATUS_AVAILABLE))
			),
			title=_("Bed Not Available"),
		)


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
	"""Free the bed. A bed that a Maintenance record holds becomes Maintenance, not Available."""
	under_maintenance = bed and frappe.db.get_value("Accommodation Bed", bed, "under_maintenance")
	update_bed_state(
		bed,
		status=BED_STATUS_MAINTENANCE if under_maintenance else BED_STATUS_AVAILABLE,
		employee=None,
		allocation=None,
		occupied_since=None,
		reason=reason,
		transfer=transfer,
		remarks=remarks,
		history_employee=employee,
		history_allocation=allocation,
	)


# Marks a hold keyword of update_bed_state that the caller did not pass, so None can clear it.
_KEEP = object()


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
	held_by_room=_KEEP,
	under_maintenance=_KEEP,
	hold_reason=_KEEP,
):
	"""Write the bed's derived state and record the change in Bed Status History.

	The hold keywords are written only when passed. The history gets a row only when
	the status or the employee changes.
	"""
	if not bed:
		return

	bed_doc = frappe.get_doc("Accommodation Bed", bed)
	previous_status = bed_doc.status
	previous_employee = bed_doc.current_employee

	values = {
		"status": status,
		"current_employee": employee,
		"current_employee_name": frappe.db.get_value("Employee", employee, "employee_name")
		if employee
		else None,
		"current_allocation": allocation,
		"occupied_since": occupied_since,
	}
	holds = {"held_by_room": held_by_room, "under_maintenance": under_maintenance, "hold_reason": hold_reason}
	values.update({fieldname: value for fieldname, value in holds.items() if value is not _KEEP})

	bed_doc.db_set(values, update_modified=True)

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
	hold = frappe.db.get_value(
		"Accommodation Room", room, ["floor", "is_blocked", "under_maintenance"], as_dict=True
	)
	if not hold:
		return

	frappe.db.set_value(
		"Accommodation Room",
		room,
		{
			"total_beds": total,
			"occupied_beds": occupied,
			"available_beds": available,
			"occupancy_percent": flt(occupied * 100.0 / total, 2) if total else 0,
			"occupancy_status": get_room_occupancy_status(
				hold.is_blocked, hold.under_maintenance, total, available
			),
		},
		update_modified=False,
	)

	update_floor_occupancy(hold.floor)


def get_room_occupancy_status(is_blocked, under_maintenance, total, available):
	"""A hold wins over the bed counts. A room with no beds has no status."""
	if is_blocked:
		return "Blocked"
	if under_maintenance:
		return "Under Maintenance"
	if not total:
		return ""
	return "Available" if available else "Full"


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


def sync_employee_accommodation(employee, entitlement=None):
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

	# Passed explicitly when an entitlement drives the change, otherwise the
	# employee's current entitlement is simply re-derived.
	values["current_accommodation_entitlement"] = entitlement or get_active_entitlement(employee)

	frappe.db.set_value("Employee", employee, values, update_modified=False)
	refresh_stay_status(employee)
