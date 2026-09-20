// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Location", {
	refresh(frm) {
		gd_acc.accommodation.add_status_buttons(frm);
	},
});
