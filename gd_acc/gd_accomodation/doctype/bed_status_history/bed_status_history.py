# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BedStatusHistory(Document):
	"""Append-only audit trail of bed status changes."""

	def before_save(self):
		if not self.is_new():
			frappe.throw(
				_("Bed Status History entries are an audit trail and cannot be edited."),
				title=_("Read Only"),
			)
