// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Allocation"] = {
	add_fields: ["status", "bed", "site"],
	get_indicator(doc) {
		const colors = {
			Draft: "red",
			Active: "green",
			Closed: "gray",
			Cancelled: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
