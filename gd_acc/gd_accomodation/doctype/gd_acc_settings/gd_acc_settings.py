# Copyright (c) 2026, Gulf Desks and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class GDAccSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		accommodation_allowance_component: DF.Link | None
	# end: auto-generated types
	pass
