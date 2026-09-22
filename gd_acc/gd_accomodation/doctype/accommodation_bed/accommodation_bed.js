// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Bed", {
	refresh(frm) {
		if (frm.doc.status !== "Occupied" || !frm.doc.current_allocation) {
			return;
		}

		frappe.db
			.get_value("Accommodation Allocation", frm.doc.current_allocation, [
				"status",
				"proposed_release_date",
			])
			.then((response) => {
				const allocation = response.message || {};
				if (allocation.status === "Pending Release") {
					frm.set_intro(
						__("Pending Release: proposed release date {0}.", [
							frappe.datetime.str_to_user(allocation.proposed_release_date),
						]),
						"orange"
					);
				}
			});
	},
});
