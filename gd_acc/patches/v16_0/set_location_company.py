import frappe


def execute():
	companies = frappe.get_all("Company", pluck="name", limit=2)
	if len(companies) != 1:
		return

	frappe.db.sql(
		"""UPDATE `tabAccommodation Location` SET company = %s WHERE IFNULL(company, '') = ''""",
		companies[0],
	)
