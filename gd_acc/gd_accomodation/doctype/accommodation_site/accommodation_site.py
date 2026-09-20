# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import generate_master_code


class AccommodationSite(Document):
	def before_insert(self):
		self.status = "Active"
		self.site_code = generate_master_code(self.doctype)

	def validate(self):
		if self.accommodation_type != "Other":
			self.sub_type = None

		self.validate_bed_allocation_change()

	def validate_bed_allocation_change(self):
		"""Bed level allocation cannot be switched off while beds are occupied."""
		if self.is_new() or self.enable_bed_allocation:
			return

		before = self.get_doc_before_save()
		if not before or not before.enable_bed_allocation:
			return

		occupied = frappe.db.count("Accommodation Bed", {"site": self.name, "status": "Occupied"})
		if occupied:
			frappe.throw(
				_("Cannot switch off bed level allocation while {0} bed(s) are occupied at {1}.").format(
					occupied, frappe.bold(self.name)
				),
				title=_("Beds Occupied"),
			)

	def on_trash(self):
		floors = frappe.db.count("Accommodation Floor", {"site": self.name})
		if floors:
			frappe.throw(
				_("Cannot delete {0} because {1} floor(s) belong to it.").format(
					frappe.bold(self.name), floors
				),
				title=_("Site In Use"),
			)
