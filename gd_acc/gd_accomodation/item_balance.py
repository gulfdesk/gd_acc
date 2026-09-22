# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Item balances of Accommodation Item Entry.

The submitted lines of Accommodation Item Entry are the ledger. An Assign line
issues a quantity. A Return line points to the Assign line it returns through
`against_entry` and `against_detail`. Only submitted lines (docstatus 1) count.

The balance fields on each Assign line, the Item Entry summary and the
allocation summary are a cache. `refresh_item_balances` is their only writer,
and it always rebuilds them from the submitted lines. Nothing in this module
commits: the request transaction commits or rolls back everything together.
"""

from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import getdate, today

ENTRY_DOCTYPE = "Accommodation Item Entry"
DETAIL_DOCTYPE = "Accommodation Item Entry Detail"
ALLOCATION_DOCTYPE = "Accommodation Allocation"

# return_type -> cache field on the Assign line
BALANCE_FIELDS = {
	"Returned": "returned_quantity",
	"Damaged": "damaged_quantity",
	"Lost": "lost_quantity",
}

CACHE_FIELDS = (*BALANCE_FIELDS.values(), "outstanding_quantity", "last_return_date")

MAX_QUANTITY = 100000


class ItemBalanceError(frappe.ValidationError):
	pass


def to_quantity(value, label, minimum=1):
	"""Return `value` as an int, or throw when it is not a whole number from `minimum` to MAX_QUANTITY.

	Never use cint() for a quantity: cint("1.5") is 1 and cint("abc") is 0.
	"""
	quantity = None

	if isinstance(value, bool):
		quantity = None
	elif isinstance(value, int):
		quantity = value
	elif isinstance(value, float | str):
		try:
			number = Decimal(value.strip() if isinstance(value, str) else repr(value))
		except (InvalidOperation, ValueError):
			number = None

		if number is not None and number.is_finite() and number == number.to_integral_value():
			quantity = int(number)

	if quantity is None or quantity < minimum or quantity > MAX_QUANTITY:
		frappe.throw(
			_("{0} must be a whole number from {1} to {2}.").format(label, minimum, MAX_QUANTITY),
			exc=ItemBalanceError,
			title=_("Invalid Quantity"),
		)

	return quantity


def lock_entries(assign_entries):
	"""Lock the allocations, then the Assign entries, in name order.

	The fixed order prevents a deadlock between two postings. The call is
	re-entrant: locks already held by this transaction are granted at once, and
	the rows returned always hold the current values.
	"""
	names = sorted({name for name in assign_entries or () if name})
	if not names:
		return {}

	allocations = sorted(
		{
			row.allocation
			for row in frappe.get_all(
				ENTRY_DOCTYPE, filters={"name": ["in", names]}, fields=["allocation"], limit=0
			)
			if row.allocation
		}
	)
	if allocations:
		frappe.db.sql(
			f"""SELECT name, docstatus FROM `tab{ALLOCATION_DOCTYPE}`
			WHERE name IN %(names)s ORDER BY name FOR UPDATE""",
			{"names": allocations},
		)

	rows = frappe.db.sql(
		f"""SELECT name, docstatus, purpose, posting_date, employee, allocation, location, site
		FROM `tab{ENTRY_DOCTYPE}` WHERE name IN %(names)s ORDER BY name FOR UPDATE""",
		{"names": names},
		as_dict=True,
	)
	locked = {row.name: row for row in rows}

	missing = [name for name in names if name not in locked]
	if missing:
		frappe.throw(
			_("{0} {1} not found.").format(_(ENTRY_DOCTYPE), ", ".join(missing)),
			exc=frappe.DoesNotExistError,
		)

	return locked


def get_assign_lines(assign_entries):
	"""Return the lines of these entries, read from the database, by line name."""
	names = sorted({name for name in assign_entries or () if name})
	if not names:
		return {}

	rows = frappe.db.sql(
		f"""SELECT name, parent, idx, accommodation_item, is_returnable, quantity
		FROM `tab{DETAIL_DOCTYPE}`
		WHERE parent IN %(names)s AND parenttype = %(parenttype)s AND parentfield = 'items'
		ORDER BY parent, idx""",
		{"names": names, "parenttype": ENTRY_DOCTYPE},
		as_dict=True,
	)
	return {row.name: row for row in rows}


def get_return_totals(assign_line_names):
	"""Sum the submitted Return lines per Assign line and return type."""
	names = sorted({name for name in assign_line_names or () if name})
	totals = {name: empty_totals() for name in names}
	if not names:
		return totals

	rows = frappe.db.sql(
		f"""SELECT d.against_detail, d.return_type, SUM(d.quantity) AS quantity,
			MAX(e.posting_date) AS last_date
		FROM `tab{DETAIL_DOCTYPE}` d
		JOIN `tab{ENTRY_DOCTYPE}` e ON e.name = d.parent
		WHERE d.against_detail IN %(names)s AND d.docstatus = 1 AND d.parenttype = %(parenttype)s
		GROUP BY d.against_detail, d.return_type""",
		{"names": names, "parenttype": ENTRY_DOCTYPE},
		as_dict=True,
	)

	for row in rows:
		line_totals = totals[row.against_detail]
		fieldname = BALANCE_FIELDS.get(row.return_type)
		if fieldname:
			line_totals[fieldname] += int(row.quantity or 0)
		else:
			# A submitted Return line without a known return type still moves stock.
			line_totals["unknown_quantity"] += int(row.quantity or 0)

		if row.last_date and (
			not line_totals["last_return_date"] or getdate(row.last_date) > line_totals["last_return_date"]
		):
			line_totals["last_return_date"] = getdate(row.last_date)

	return totals


def empty_totals():
	totals = {fieldname: 0 for fieldname in BALANCE_FIELDS.values()}
	totals["unknown_quantity"] = 0
	totals["last_return_date"] = None
	return totals


def get_balances(assign_entries):
	"""Return the balance of every line of these Assign entries, by line name."""
	return compute_balances(get_assign_lines(assign_entries))


def compute_balances(lines):
	totals = get_return_totals(lines.keys())
	balances = {}

	for name, line in lines.items():
		line_totals = totals[name]
		quantity = int(line.quantity or 0)
		moved = sum(line_totals[fieldname] for fieldname in BALANCE_FIELDS.values())
		moved += line_totals["unknown_quantity"]

		balances[name] = frappe._dict(
			parent=line.parent,
			idx=line.idx,
			accommodation_item=line.accommodation_item,
			is_returnable=int(line.is_returnable or 0),
			quantity=quantity,
			returned_quantity=line_totals["returned_quantity"],
			damaged_quantity=line_totals["damaged_quantity"],
			lost_quantity=line_totals["lost_quantity"],
			unknown_quantity=line_totals["unknown_quantity"],
			moved_quantity=moved,
			last_return_date=line_totals["last_return_date"],
			outstanding_quantity=quantity - moved if line.is_returnable else 0,
		)

	return balances


def validate_return(entry):
	"""Check a Return entry against the locked Assign lines. Runs in before_submit."""
	against = sorted({line.against_entry for line in entry.items if line.against_entry})
	missing_link = [line for line in entry.items if not line.against_entry or not line.against_detail]
	if missing_link:
		line = missing_link[0]
		frappe.throw(
			_("Row #{0} ({1}): pick the assigned line that this item returns.").format(
				line.idx, frappe.bold(line.accommodation_item)
			),
			exc=ItemBalanceError,
			title=_("Assigned Line Required"),
		)

	locked = lock_entries(against)
	lines = get_assign_lines(against)
	balances = compute_balances(lines)

	posting_date = getdate(entry.posting_date)
	if posting_date > getdate(today()):
		frappe.throw(
			_("A Return entry cannot have a future date."),
			exc=ItemBalanceError,
			title=_("Invalid Date"),
		)

	requested = {}
	for line in entry.items:
		label = _("Row #{0} ({1})").format(line.idx, frappe.bold(line.accommodation_item))
		source = locked.get(line.against_entry)

		if not source or source.docstatus != 1 or source.purpose != "Assign":
			frappe.throw(
				_("{0}: {1} is not a submitted Assign entry.").format(label, frappe.bold(line.against_entry)),
				exc=ItemBalanceError,
				title=_("Invalid Assign Entry"),
			)

		assign_line = lines.get(line.against_detail)
		if not assign_line or assign_line.parent != line.against_entry:
			frappe.throw(
				_("{0}: the assigned line is not a line of {1}.").format(
					label, frappe.bold(line.against_entry)
				),
				exc=ItemBalanceError,
				title=_("Invalid Assign Line"),
			)

		if assign_line.accommodation_item != line.accommodation_item:
			frappe.throw(
				_("{0}: the assigned line on {1} is for {2}, not for this item.").format(
					label, frappe.bold(line.against_entry), frappe.bold(assign_line.accommodation_item)
				),
				exc=ItemBalanceError,
				title=_("Item Mismatch"),
			)

		if not assign_line.is_returnable:
			frappe.throw(
				_("{0}: this item is not returnable.").format(label),
				exc=ItemBalanceError,
				title=_("Not Returnable"),
			)

		quantity = to_quantity(line.quantity, _("{0}: Qty").format(label), minimum=1)

		if (source.employee or "") != (entry.employee or ""):
			frappe.throw(
				_("{0}: {1} was assigned to {2}, not to {3}.").format(
					label,
					frappe.bold(line.against_entry),
					frappe.bold(source.employee or _("the site")),
					frappe.bold(entry.employee or _("the site")),
				),
				exc=ItemBalanceError,
				title=_("Holder Mismatch"),
			)

		if not entry.employee and source.site != entry.site:
			frappe.throw(
				_("{0}: {1} was assigned to site {2}, not to {3}.").format(
					label, frappe.bold(line.against_entry), frappe.bold(source.site), frappe.bold(entry.site)
				),
				exc=ItemBalanceError,
				title=_("Holder Mismatch"),
			)

		if posting_date < getdate(source.posting_date):
			frappe.throw(
				_("{0}: the return date cannot be before the assign date of {1} ({2}).").format(
					label, frappe.bold(line.against_entry), frappe.format(source.posting_date, "Date")
				),
				exc=ItemBalanceError,
				title=_("Invalid Date"),
			)

		requested.setdefault(line.against_detail, []).append((line, quantity))

	for against_detail, requested_lines in requested.items():
		balance = balances[against_detail]
		total = sum(quantity for _line, quantity in requested_lines)
		if total > balance.outstanding_quantity:
			line = requested_lines[0][0]
			frappe.throw(
				_("Row #{0} ({1}): {2} returned, but only {3} is outstanding on {4}.").format(
					line.idx,
					frappe.bold(line.accommodation_item),
					total,
					balance.outstanding_quantity,
					frappe.bold(line.against_entry),
				),
				exc=ItemBalanceError,
				title=_("Return Exceeds Outstanding"),
			)


def validate_assign_cancel(entry):
	"""Refuse to cancel an Assign entry while a submitted Return points to it."""
	lock_entries([entry.name])
	returns = has_active_returns(entry.name)
	if returns:
		frappe.throw(
			_("Items on {0} were already returned. Cancel those Return entries first: {1}.").format(
				frappe.bold(entry.name), ", ".join(returns[:5])
			),
			exc=ItemBalanceError,
			title=_("Returns Recorded"),
		)


def lock_for_return_cancel(entry):
	lock_entries(sorted({line.against_entry for line in entry.items if line.against_entry}))


def refresh_item_balances(assign_entries):
	"""Rebuild the cache of these Assign entries and of their allocations.

	Checks the invariant on every line first and writes nothing when one fails,
	so the whole transaction rolls back.
	"""
	names = sorted({name for name in assign_entries or () if name})
	if not names:
		return

	locked = lock_entries(names)
	balances = compute_balances(get_assign_lines(names))

	updates = []
	for name, balance in balances.items():
		source = locked[balance.parent]
		errors = get_invariant_errors(balance, source)
		if errors:
			frappe.throw(
				_("Item balance mismatch on row {0} ({1}) of {2}.").format(
					balance.idx, frappe.bold(balance.accommodation_item), frappe.bold(balance.parent)
				),
				exc=ItemBalanceError,
				title=_("Item Balance Error"),
			)
		updates.append((name, get_line_cache(balance, source)))

	for name, values in updates:
		frappe.db.set_value(DETAIL_DOCTYPE, name, values, update_modified=False)

	for name in names:
		entry_balances = [balance for balance in balances.values() if balance.parent == name]
		frappe.db.set_value(
			ENTRY_DOCTYPE, name, get_entry_summary(entry_balances, locked[name]), update_modified=False
		)

	for allocation in sorted({row.allocation for row in locked.values() if row.allocation}):
		refresh_allocation_summary(allocation)


def get_invariant_errors(balance, source):
	"""Return the invariant fields that fail for one Assign line."""
	errors = []
	parts = ("returned_quantity", "damaged_quantity", "lost_quantity")

	if source.purpose != "Assign":
		errors.append("purpose")

	if balance.unknown_quantity:
		errors.append("return_type")

	if balance.quantity < 0 or any(balance[part] < 0 for part in parts):
		errors.append("quantity")

	if not balance.is_returnable and balance.moved_quantity:
		errors.append("is_returnable")

	# outstanding_quantity is derived as quantity minus moved, so the sum always
	# balances. Only the sign is an independent check.
	if source.docstatus == 1 and balance.is_returnable:
		if balance.outstanding_quantity < 0:
			errors.append("outstanding_quantity")
	elif source.docstatus != 1 and balance.moved_quantity:
		errors.append("docstatus")

	return errors


def get_line_cache(balance, source):
	active = source.docstatus == 1
	return {
		"returned_quantity": balance.returned_quantity,
		"damaged_quantity": balance.damaged_quantity,
		"lost_quantity": balance.lost_quantity,
		"outstanding_quantity": balance.outstanding_quantity if active else 0,
		"last_return_date": balance.last_return_date,
	}


def get_entry_summary(entry_balances, source):
	active = source.docstatus == 1
	outstanding = sum(balance.outstanding_quantity for balance in entry_balances) if active else 0
	return {
		"total_items": sum(balance.quantity for balance in entry_balances),
		"outstanding_items": outstanding,
		"items_status": get_items_status(
			any(balance.is_returnable for balance in entry_balances), outstanding
		),
	}


def get_items_status(has_returnable, outstanding):
	if not has_returnable:
		return ""
	return "Outstanding" if outstanding > 0 else "Cleared"


def refresh_allocation_summary(allocation):
	"""Rebuild the item summary of one allocation from its submitted Assign entries."""
	frappe.db.set_value(
		ALLOCATION_DOCTYPE, allocation, get_allocation_summary(allocation), update_modified=False
	)


def get_allocation_summary(allocation):
	row = frappe.db.sql(
		f"""SELECT COALESCE(SUM(total_items), 0) AS total_items,
			COALESCE(SUM(outstanding_items), 0) AS outstanding_items,
			COALESCE(SUM(IFNULL(items_status, '') != ''), 0) AS returnable_entries
		FROM `tab{ENTRY_DOCTYPE}`
		WHERE allocation = %(allocation)s AND purpose = 'Assign' AND docstatus = 1""",
		{"allocation": allocation},
		as_dict=True,
	)[0]

	return {
		"total_items": int(row.total_items),
		"outstanding_items": int(row.outstanding_items),
		"items_status": get_items_status(int(row.returnable_entries) > 0, int(row.outstanding_items)),
	}


def has_active_returns(assign_entry):
	"""Return the names of submitted Return entries with a line against this Assign entry."""
	rows = frappe.db.sql(
		f"""SELECT DISTINCT r.parent
		FROM `tab{DETAIL_DOCTYPE}` r
		WHERE r.docstatus = 1 AND r.parenttype = %(parenttype)s
			AND r.against_detail IN (
				SELECT a.name FROM `tab{DETAIL_DOCTYPE}` a
				WHERE a.parent = %(assign_entry)s AND a.parenttype = %(parenttype)s
			)
		ORDER BY r.parent""",
		{"assign_entry": assign_entry, "parenttype": ENTRY_DOCTYPE},
	)
	return [row[0] for row in rows]


def get_outstanding_lines(employee=None, allocation=None, assign_entry=None, site=None):
	"""Return the submitted Assign lines with an outstanding quantity.

	`site` selects the items held by the site itself, that is Assign entries with
	no employee. The result reads the cache and is for display and prefill only:
	validate_return checks every quantity again under the lock.
	"""
	if not (employee or allocation or assign_entry or site):
		frappe.throw(_("Give an employee, an allocation, a site or an Assign entry."))

	conditions = ["e.docstatus = 1", "e.purpose = 'Assign'", "d.outstanding_quantity > 0"]
	values = {"parenttype": ENTRY_DOCTYPE}

	if employee:
		conditions.append("e.employee = %(employee)s")
		values["employee"] = employee
	elif site and not assign_entry and not allocation:
		conditions.append("IFNULL(e.employee, '') = ''")
		conditions.append("e.site = %(site)s")
		values["site"] = site

	if allocation:
		conditions.append("e.allocation = %(allocation)s")
		values["allocation"] = allocation

	if assign_entry:
		conditions.append("e.name = %(assign_entry)s")
		values["assign_entry"] = assign_entry

	return frappe.db.sql(
		f"""SELECT e.name AS against_entry, d.name AS against_detail, d.accommodation_item,
			d.outstanding_quantity, e.posting_date, e.allocation
		FROM `tab{DETAIL_DOCTYPE}` d
		JOIN `tab{ENTRY_DOCTYPE}` e ON e.name = d.parent
		WHERE d.parenttype = %(parenttype)s AND {" AND ".join(conditions)}
		ORDER BY e.posting_date, e.name, d.idx""",
		values,
		as_dict=True,
	)
