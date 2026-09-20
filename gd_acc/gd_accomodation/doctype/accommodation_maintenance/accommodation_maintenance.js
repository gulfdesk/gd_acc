// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Maintenance", {
	setup(frm) {
		frm.set_query("site", () => ({ filters: { location: frm.doc.location } }));
		frm.set_query("floor", () => ({ filters: { site: frm.doc.site } }));
		frm.set_query("room", () => ({ filters: { floor: frm.doc.floor } }));
		frm.set_query("bed", () => ({ filters: { room: frm.doc.room } }));
	},

	onload(frm) {
		if (frm.is_new()) {
			frm.set_value("reported_by", frappe.session.user);
			frm.set_value("reported_on", frappe.datetime.get_today());
		}
	},

	location(frm) {
		frm.set_value({ site: null, floor: null, room: null, bed: null });
	},

	site(frm) {
		frm.set_value({ floor: null, room: null, bed: null });
	},

	floor(frm) {
		frm.set_value({ room: null, bed: null });
	},

	room(frm) {
		frm.set_value({ bed: null });
	},

	status(frm) {
		if (["Resolved", "Closed"].includes(frm.doc.status) && !frm.doc.resolution_date) {
			frm.set_value("resolution_date", frappe.datetime.get_today());
		}
	},
});
