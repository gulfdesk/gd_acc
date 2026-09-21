# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import count_active_allocations, generate_master_code

# The places below a location that keep a copy of its Company.
COMPANY_COPY_DOCTYPES = (
	"Accommodation Site",
	"Accommodation Floor",
	"Accommodation Room",
	"Accommodation Bed",
)


class AccommodationLocation(Document):
	def before_insert(self):
		self.status = "Active"
		self.location_code = generate_master_code(self.doctype)

	def validate(self):
		if self.latitude and not -90 <= self.latitude <= 90:
			frappe.throw(_("Latitude must be between -90 and 90."))

		if self.longitude and not -180 <= self.longitude <= 180:
			frappe.throw(_("Longitude must be between -180 and 180."))

		self.validate_company_change()

	def validate_company_change(self):
		"""The company cannot change while an employee still lives at the location."""
		if self.is_new() or not self.has_value_changed("company"):
			return

		stays = count_active_allocations(self.doctype, self.name)
		if stays:
			frappe.throw(
				_("{0} employee(s) live at {1}. Release them before you change the company.").format(
					stays, frappe.bold(self.name)
				),
				title=_("Location Occupied"),
			)

	def on_update(self):
		if self.has_value_changed("company"):
			for doctype in COMPANY_COPY_DOCTYPES:
				frappe.db.sql(
					f"UPDATE `tab{doctype}` SET company = %s WHERE location = %s",
					(self.company, self.name),
				)

	def on_trash(self):
		sites = frappe.db.count("Accommodation Site", {"location": self.name})
		if sites:
			frappe.throw(
				_("Cannot delete {0} because {1} accommodation site(s) belong to it.").format(
					frappe.bold(self.name), sites
				),
				title=_("Location In Use"),
			)
