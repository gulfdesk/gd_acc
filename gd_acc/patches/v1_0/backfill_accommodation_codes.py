# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.naming import NamingSeries, make_autoname
from frappe.utils import cint

from gd_acc.gd_accomodation.accommodation_utils import MASTER_CODE_SERIES


def execute():
	"""Give series codes to accommodation masters saved before codes were generated.

	Codes that already follow the series are left untouched, so re-running this
	never renumbers a record that is already correct.
	"""
	for doctype, (fieldname, series) in MASTER_CODE_SERIES.items():
		if frappe.db.exists("DocType", doctype):
			backfill(doctype, fieldname, series)


def backfill(doctype, fieldname, series):
	prefix = series.split(".")[0]
	pattern = re.compile(rf"^{re.escape(prefix)}\d+$")

	highest = 0
	pending = []

	for row in frappe.get_all(doctype, fields=["name", fieldname], order_by="creation asc"):
		code = row.get(fieldname)
		if code and pattern.match(code):
			highest = max(highest, cint(code[len(prefix) :]))
		else:
			pending.append(row.name)

	# Always reserve first: codes may already exist even when none are pending,
	# and a counter left behind them would hand out a duplicate on the next save.
	reserve_series(series, highest)

	if not pending:
		return

	for name in pending:
		frappe.db.set_value(doctype, name, fieldname, make_autoname(series), update_modified=False)


def reserve_series(series, highest):
	"""Move the counter past codes that already exist so nothing collides."""
	if not highest:
		return

	naming_series = NamingSeries(series)
	if naming_series.get_current_value() < highest:
		naming_series.update_counter(highest)
