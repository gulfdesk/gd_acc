# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from gd_acc.gd_accomodation.accommodation_utils import resolve_hierarchy


class AccommodationAssetAssignment(Document):
	def validate(self):
		self.validate_items()
		self.apply_hierarchy()
		self.validate_dates()

	def validate_items(self):
		if not self.items:
			frappe.throw(_("Add at least one item under Items Issued."), title=_("Items Required"))

		seen = {}
		total = 0

		for row in self.items:
			quantity = cint(row.quantity)
			returned = cint(row.returned_quantity)

			if quantity < 1:
				frappe.throw(
					_("Row #{0}: Quantity must be at least 1.").format(row.idx),
					title=_("Invalid Quantity"),
				)

			if returned > quantity:
				frappe.throw(
					_("Row #{0}: Returned Qty ({1}) cannot be more than the Quantity issued ({2}).").format(
						row.idx, returned, quantity
					),
					title=_("Invalid Returned Quantity"),
				)

			if row.accommodation_item in seen:
				frappe.throw(
					_(
						"Row #{0}: {1} is already listed in row #{2}. "
						"Combine them into one row with a higher quantity."
					).format(row.idx, frappe.bold(row.accommodation_item), seen[row.accommodation_item]),
					title=_("Duplicate Item"),
				)

			seen[row.accommodation_item] = row.idx
			total += quantity

		self.total_items = total

	def apply_hierarchy(self):
		resolved = resolve_hierarchy(
			location=self.location,
			site=self.site,
			floor=self.floor,
			room=self.room,
			bed=self.bed,
		)
		self.location = resolved["location"]
		self.site = resolved["site"]
		self.floor = resolved["floor"]
		self.room = resolved["room"]

	def validate_dates(self):
		if self.return_date and getdate(self.return_date) < getdate(self.assignment_date):
			frappe.throw(_("Return Date cannot be before Assignment Date."), title=_("Invalid Dates"))

		if self.expected_return_date and getdate(self.expected_return_date) < getdate(self.assignment_date):
			frappe.throw(
				_("Expected Return Date cannot be before Assignment Date."), title=_("Invalid Dates")
			)
