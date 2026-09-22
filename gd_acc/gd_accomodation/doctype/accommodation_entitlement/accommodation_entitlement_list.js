// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Entitlement"] = {
	add_fields: ["status", "stay_status", "entitlement_type"],

	get_indicator(doc) {
		if (doc.status === "Active" && doc.stay_status) {
			const color = gd_acc.accommodation.status_color("Accommodation Entitlement", "stay_status", doc.stay_status);
			return [__(doc.stay_status), color, `stay_status,=,${doc.stay_status}`];
		}

		const color = gd_acc.accommodation.status_color("Accommodation Entitlement", "status", doc.status);
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
};
