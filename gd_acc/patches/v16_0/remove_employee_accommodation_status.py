import frappe

from gd_acc.gd_accomodation.accommodation_utils import refresh_stay_status

# The Employee custom fields that the Accommodation Entitlement replaces.
REMOVED = (
	"accommodation_status",
	"accommodation_allowance_section",
	"accommodation_allowance_type",
	"accommodation_allowance_amount",
	"accommodation_allowance_currency",
	"accommodation_allowance_column",
	"accommodation_allowance_from_date",
	"accommodation_allowance_to_date",
	"accommodation_allowance_component",
)


def execute():
	"""Delete the removed Employee fields and fill the Stay Status of current entitlements.

	The columns stay in tabEmployee with their old values. Nothing reads them.
	"""
	for fieldname in REMOVED:
		frappe.delete_doc("Custom Field", f"Employee-{fieldname}", ignore_missing=True, force=True)

	frappe.db.delete("Property Setter", {"doc_type": "Employee", "field_name": ("in", REMOVED)})
	frappe.clear_cache(doctype="Employee")

	for employee in frappe.get_all(
		"Accommodation Entitlement",
		filters={"docstatus": 1, "status": "Active", "entitlement_type": "Company Accommodation"},
		pluck="employee",
		distinct=True,
	):
		refresh_stay_status(employee)
