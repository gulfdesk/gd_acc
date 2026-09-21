// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Bed"] = {
	add_fields: ["status", "current_employee_name"],
	get_indicator(doc) {
		const colors = {
			Available: "green",
			Occupied: "blue",
			Reserved: "orange",
			Maintenance: "yellow",
			Blocked: "red",
			Inactive: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
