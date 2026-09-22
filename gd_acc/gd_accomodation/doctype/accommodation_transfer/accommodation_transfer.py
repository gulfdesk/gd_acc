# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from gd_acc.gd_accomodation.accommodation_utils import (
	CURRENT_STAY_STATUSES,
	resolve_hierarchy,
	site_requires_bed,
	validate_placement,
)


class AccommodationTransfer(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"

		self.validate_current_allocation()
		self.apply_hierarchy()
		self.validate_bed_requirement()
		self.validate_destination_differs()

		if self.docstatus == 1:
			self.validate_destination_is_free()

	def validate_current_allocation(self):
		allocation = frappe.db.get_value(
			"Accommodation Allocation",
			self.current_allocation,
			["employee", "status", "docstatus", "start_date"],
			as_dict=True,
		)
		if not allocation:
			frappe.throw(_("Current Allocation {0} not found.").format(self.current_allocation))

		if allocation.employee != self.employee:
			frappe.throw(
				_("Allocation {0} belongs to a different employee.").format(
					frappe.bold(self.current_allocation)
				),
				title=_("Wrong Allocation"),
			)

		if allocation.docstatus != 1 or allocation.status not in CURRENT_STAY_STATUSES:
			frappe.throw(
				_("Only an active or pending release allocation can be transferred. {0} is {1}.").format(
					frappe.bold(self.current_allocation), frappe.bold(allocation.status)
				),
				title=_("Not Active"),
			)

		if getdate(self.transfer_date) < getdate(allocation.start_date):
			frappe.throw(
				_("Transfer Date cannot be before the current allocation start date {0}.").format(
					frappe.bold(allocation.start_date)
				),
				title=_("Invalid Dates"),
			)

		if self.expected_end_date and getdate(self.expected_end_date) < getdate(self.transfer_date):
			frappe.throw(_("Expected End Date cannot be before Transfer Date."), title=_("Invalid Dates"))

	def apply_hierarchy(self):
		resolved = resolve_hierarchy(
			location=self.to_location,
			site=self.to_site,
			floor=self.to_floor,
			room=self.to_room,
			bed=self.to_bed,
		)
		self.to_location = resolved["location"]
		self.to_site = resolved["site"]
		self.to_floor = resolved["floor"]
		self.to_room = resolved["room"]

	def validate_bed_requirement(self):
		if site_requires_bed(self.to_site) and not self.to_bed:
			frappe.throw(
				_("Site {0} uses bed level allocation, so a destination Bed is required.").format(
					frappe.bold(self.to_site)
				),
				title=_("Bed Required"),
			)

	def validate_destination_differs(self):
		if self.to_bed and self.to_bed == self.from_bed:
			frappe.throw(
				_("The destination bed is the same as the current bed."), title=_("Nothing to Transfer")
			)

		if not self.to_bed and self.to_room and self.to_room == self.from_room:
			frappe.throw(
				_("The destination room is the same as the current room."), title=_("Nothing to Transfer")
			)

		if not self.to_bed and not self.to_room and self.to_site == self.from_site:
			frappe.throw(
				_("The destination site is the same as the current site."), title=_("Nothing to Transfer")
			)

	def validate_destination_is_free(self):
		validate_placement(
			employee=self.employee_name or self.employee,
			employee_id=self.employee,
			company=self.company,
			location=self.to_location,
			site=self.to_site,
			floor=self.to_floor,
			room=self.to_room,
			bed=self.to_bed,
			start_date=self.transfer_date,
			end_date=self.expected_end_date,
		)

	def on_submit(self):
		"""Close the old stay and open the new one in a single transaction.

		Any failure below rolls the whole request back, so the employee can
		never end up released from one bed without occupying the next.
		"""
		old_allocation = frappe.get_doc("Accommodation Allocation", self.current_allocation)
		old_allocation.release(
			release_date=self.transfer_date,
			reason="Transfer",
			transfer=self.name,
			remarks=_("Transferred via {0}.").format(self.name),
		)

		new_allocation = self.create_new_allocation()
		self.db_set({"new_allocation": new_allocation.name, "status": "Completed"})

		frappe.msgprint(
			_("Transferred to {0}. New allocation {1} created.").format(
				frappe.bold(self.to_bed or self.to_room or self.to_site),
				frappe.bold(new_allocation.name),
			),
			indicator="green",
			alert=True,
		)

	def create_new_allocation(self):
		allocation = frappe.new_doc("Accommodation Allocation")
		allocation.update(
			{
				"employee": self.employee,
				"location": self.to_location,
				"site": self.to_site,
				"floor": self.to_floor,
				"room": self.to_room,
				"bed": self.to_bed,
				"start_date": self.transfer_date,
				"expected_end_date": self.expected_end_date,
				"remarks": _("Created by transfer {0}.").format(self.name),
			}
		)
		allocation.flags.ignore_permissions = True
		allocation.insert()
		allocation.submit()
		return allocation

	def before_cancel(self):
		if self.status == "Completed":
			frappe.throw(
				_(
					"A completed transfer cannot be cancelled because it would rewrite "
					"accommodation history. Create a new Accommodation Transfer to move "
					"{0} back instead."
				).format(frappe.bold(self.employee_name or self.employee)),
				title=_("History Is Preserved"),
			)
