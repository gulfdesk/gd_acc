import frappe

MODULE = "GD Accomodation"


def execute():
	"""Delete the site Sidebar that hides the standard GD Accomodation Sidebar.

	Frappe v16.50 turns the old site sidebar "Accommodation Management" into a site Sidebar row
	for this module, and a site row wins over the Sidebar that gd_acc ships.
	"""
	if not frappe.db.exists("DocType", "Sidebar"):
		return

	if not frappe.db.exists("Sidebar", {"module": MODULE, "standard": 1}):
		return

	for name in frappe.get_all("Sidebar", filters={"module": MODULE, "standard": 0}, pluck="name"):
		frappe.delete_doc("Sidebar", name, ignore_permissions=True)
