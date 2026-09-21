// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Allocation"] = {
	add_fields: ["status", "bed", "site", "proposed_release_date"],
	get_indicator(doc) {
		const color = gd_acc.accommodation.status_color("Accommodation Allocation", "status", doc.status);
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
