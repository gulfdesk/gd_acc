// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Entitlement"] = {
	add_fields: ["status", "stay_status", "entitlement_type"],

	get_indicator(doc) {
		const stay_colors = { "Awaiting Bed": "orange", Allocated: "green", Vacated: "gray" };

		if (doc.status === "Active" && doc.stay_status) {
			return [__(doc.stay_status), stay_colors[doc.stay_status] || "gray", `stay_status,=,${doc.stay_status}`];
		}

		const colors = { Draft: "red", Active: "green", Closed: "gray", Cancelled: "red" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
