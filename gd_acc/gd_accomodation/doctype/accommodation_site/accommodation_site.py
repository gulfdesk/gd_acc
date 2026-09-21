# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from gd_acc.gd_accomodation.accommodation_utils import (
	CURRENT_STAY_STATUSES,
	GENDER_ANY,
	generate_master_code,
)

# The places below a site that keep a copy of its Gender Restriction and Company.
GENDER_COPY_DOCTYPES = ("Accommodation Floor", "Accommodation Room", "Accommodation Bed")


class AccommodationSite(Document):
	def before_insert(self):
		self.status = "Active"
		self.site_code = generate_master_code(self.doctype)

	def validate(self):
		if self.accommodation_type != "Other":
			self.sub_type = None

		self.validate_bed_allocation_change()
		self.validate_gender_change()

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

	def validate_gender_change(self):
		"""A site cannot be restricted while an employee of another gender lives there."""
		if self.is_new() or self.gender_restriction == GENDER_ANY:
			return
		if not self.has_value_changed("gender_restriction"):
			return

		others = frappe.db.sql(
			"""
			SELECT COUNT(*)
			FROM `tabAccommodation Allocation` a
			JOIN `tabEmployee` e ON e.name = a.employee
			WHERE a.site = %s AND a.docstatus = 1 AND a.status IN %s
				AND IFNULL(e.gender, '') != %s
			""",
			(self.name, CURRENT_STAY_STATUSES, self.gender_restriction),
		)[0][0]
		if others:
			frappe.throw(
				_("{0} employee(s) who are not {1} live at {2}. Move them before you restrict the site.").format(
					others, _(self.gender_restriction), frappe.bold(self.name)
				),
				title=_("Gender Restriction"),
			)

	def on_update(self):
		for fieldname in ("gender_restriction", "company"):
			if not self.has_value_changed(fieldname):
				continue
			for doctype in GENDER_COPY_DOCTYPES:
				frappe.db.sql(
					f"UPDATE `tab{doctype}` SET `{fieldname}` = %s WHERE site = %s",
					(self.get(fieldname), self.name),
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
