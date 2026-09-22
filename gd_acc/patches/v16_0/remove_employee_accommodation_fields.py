import frappe

# The Employee custom fields that the single Accommodation HTML panel replaces.
REMOVED = (
	"current_accommodation_entitlement",
	"accommodation_actions_html",
	"current_accommodation_section",
	"current_accommodation_allocation",
	"current_accommodation_location",
	"current_accommodation_site",
	"current_accommodation_sub_type",
	"current_accommodation_column",
	"current_accommodation_floor",
	"current_accommodation_room",
	"current_accommodation_bed",
	"accommodation_start_date",
	"accommodation_expected_end_date",
	"accommodation_history_section",
	"accommodation_history_html",
)

# ERPNext has its own current_accommodation_type (Rented or Owned). The removed custom field
# wrote a site type into that core column, so only those values are cleared.
CORE_FIELD = "current_accommodation_type"
SITE_TYPES = ("Camp", "Building", "Other")


def execute():
	"""Delete the removed Employee fields. The columns stay in tabEmployee. Nothing reads them."""
	for fieldname in REMOVED:
		frappe.delete_doc("Custom Field", f"Employee-{fieldname}", ignore_missing=True, force=True)

	frappe.db.delete("Property Setter", {"doc_type": "Employee", "field_name": ("in", REMOVED)})

	# A direct delete. Custom Field on_trash would also delete the core field's property setters.
	frappe.db.delete("Custom Field", {"dt": "Employee", "fieldname": CORE_FIELD})
	frappe.db.sql(
		f"UPDATE `tabEmployee` SET `{CORE_FIELD}` = NULL WHERE `{CORE_FIELD}` IN %(types)s",
		{"types": SITE_TYPES},
	)

	frappe.clear_cache(doctype="Employee")
