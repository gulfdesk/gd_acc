# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import generate_master_code


class AccommodationLocation(Document):
	def before_insert(self):
		self.status = "Active"
		self.location_code = generate_master_code(self.doctype)

	def validate(self):
		if self.latitude and not -90 <= self.latitude <= 90:
			frappe.throw(_("Latitude must be between -90 and 90."))

		if self.longitude and not -180 <= self.longitude <= 180:
			frappe.throw(_("Longitude must be between -180 and 180."))

	def on_trash(self):
		sites = frappe.db.count("Accommodation Site", {"location": self.name})
		if sites:
			frappe.throw(
				_("Cannot delete {0} because {1} accommodation site(s) belong to it.").format(
					frappe.bold(self.name), sites
				),
				title=_("Location In Use"),
			)
