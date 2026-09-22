// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Bed"] = {
	add_fields: ["status", "current_employee_name"],
	get_indicator(doc) {
		const color = gd_acc.accommodation.status_color("Accommodation Bed", "status", doc.status);
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
