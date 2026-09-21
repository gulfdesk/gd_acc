// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.listview_settings["Accommodation Item Entry"] = {
	add_fields: ["purpose", "items_status", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
		if (doc.docstatus === 0) {
			return [__("Draft"), "gray", "docstatus,=,0"];
		}
		if (doc.purpose === "Return") {
			return [__("Return"), "blue", "purpose,=,Return|docstatus,=,1"];
		}
		if (doc.items_status === "Outstanding") {
			return [__("Outstanding"), "orange", "items_status,=,Outstanding|docstatus,=,1"];
		}
		if (doc.items_status === "Cleared") {
			return [__("Cleared"), "green", "items_status,=,Cleared|docstatus,=,1"];
		}
		return [__("Assigned"), "blue", "purpose,=,Assign|docstatus,=,1"];
	},
};
