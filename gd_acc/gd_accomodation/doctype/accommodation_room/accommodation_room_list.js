// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Room"] = {
	add_fields: ["status", "occupancy_status"],
	get_indicator(doc) {
		if (doc.status === "Inactive") {
			return [__("Inactive"), "gray", "status,=,Inactive"];
		}
		if (!doc.occupancy_status) {
			return [__("No Beds"), "gray", "total_beds,=,0"];
		}
		const colors = {
			Available: "green",
			Full: "blue",
			Blocked: "red",
			"Under Maintenance": "orange",
		};
		return [
			__(doc.occupancy_status),
			colors[doc.occupancy_status] || "gray",
			`occupancy_status,=,${doc.occupancy_status}`,
		];
	},
};
