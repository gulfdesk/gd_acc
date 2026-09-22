# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

"""Checks and repairs the item balance cache that item_balance.py writes.

`verify_item_balances` only reads. `repost_item_balances` rebuilds one cache
through `item_balance.refresh_item_balances`, the only writer of the cache.
"""

import frappe
from frappe import _
from frappe.utils import getdate

from gd_acc.gd_accomodation.item_balance import (
	ALLOCATION_DOCTYPE,
	CACHE_FIELDS,
	DETAIL_DOCTYPE,
	ENTRY_DOCTYPE,
	ItemBalanceError,
	compute_balances,
	get_allocation_summary,
	get_assign_lines,
	get_entry_summary,
	get_invariant_errors,
	get_line_cache,
	lock_entries,
	refresh_item_balances,
)

VERIFY_BATCH_SIZE = 500


@frappe.whitelist()
def verify_item_balances(assign_entry=None):
	"""Compare every cached quantity with the submitted lines. Read only.

	Returns one row per difference. An empty list means every cache is correct.
	"""
	frappe.only_for(("Accommodation Manager", "System Manager"))

	if assign_entry:
		batches = [[assign_entry]]
	else:
		names = frappe.get_all(
			ENTRY_DOCTYPE,
			filters={"purpose": "Assign", "docstatus": ["in", [1, 2]]},
			pluck="name",
			order_by="name asc",
			limit=0,
		)
		batches = [names[start : start + VERIFY_BATCH_SIZE] for start in range(0, len(names), VERIFY_BATCH_SIZE)]

	differences = []
	allocations = set()
	for batch in batches:
		differences.extend(verify_entries(batch, allocations))

	for allocation in sorted(allocations):
		cached = frappe.db.get_value(
			ALLOCATION_DOCTYPE, allocation, ["total_items", "outstanding_items", "items_status"], as_dict=True
		)
		if not cached:
			continue
		for fieldname, actual in get_allocation_summary(allocation).items():
			add_difference(differences, ALLOCATION_DOCTYPE, allocation, None, None, fieldname, cached[fieldname], actual)

	return differences


def verify_entries(names, allocations):
	differences = []
	entries = {
		row.name: row
		for row in frappe.get_all(
			ENTRY_DOCTYPE,
			filters={"name": ["in", names]},
			fields=["name", "docstatus", "purpose", "allocation", "total_items", "outstanding_items", "items_status"],
			limit=0,
		)
	}
	lines = get_assign_lines(entries.keys())
	balances = compute_balances(lines)
	cached_lines = {}
	if lines:
		cached_lines = {
			row.name: row
			for row in frappe.get_all(
				DETAIL_DOCTYPE, filters={"name": ["in", list(lines)]}, fields=["name", *CACHE_FIELDS], limit=0
			)
		}

	for name, balance in balances.items():
		source = entries[balance.parent]
		for field in get_invariant_errors(balance, source):
			add_difference(
				differences, ENTRY_DOCTYPE, balance.parent, balance.idx, balance.accommodation_item,
				f"invariant:{field}", None, None, force=True,
			)

		cached = cached_lines.get(name) or {}
		for fieldname, actual in get_line_cache(balance, source).items():
			add_difference(
				differences, ENTRY_DOCTYPE, balance.parent, balance.idx, balance.accommodation_item,
				fieldname, cached.get(fieldname), actual,
			)

	for name, source in entries.items():
		if source.allocation and source.purpose == "Assign":
			allocations.add(source.allocation)
		entry_balances = [balance for balance in balances.values() if balance.parent == name]
		for fieldname, actual in get_entry_summary(entry_balances, source).items():
			add_difference(differences, ENTRY_DOCTYPE, name, None, None, fieldname, source.get(fieldname), actual)

	return differences


def add_difference(differences, doctype, name, row, item, field, cache, actual, force=False):
	if not force:
		if field == "last_return_date":
			cache = getdate(cache) if cache else None
		elif field == "items_status":
			cache = cache or ""
		else:
			cache = int(cache or 0)
		if cache == actual:
			return

	differences.append(
		{"doctype": doctype, "name": name, "row": row, "item": item, "field": field, "cache": cache, "actual": actual}
	)


@frappe.whitelist()
def repost_item_balances(assign_entry):
	"""Rebuild the cache of one Assign entry from its submitted lines. It never changes a line."""
	frappe.only_for("System Manager")

	purpose = frappe.db.get_value(ENTRY_DOCTYPE, assign_entry, "purpose")
	if purpose != "Assign":
		frappe.throw(_("{0} is not an Assign entry.").format(frappe.bold(assign_entry)), exc=ItemBalanceError)

	lock_entries([assign_entry])
	refresh_item_balances([assign_entry])
