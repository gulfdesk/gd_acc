// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Asset Assignment", {
	setup(frm) {
		frm.set_query("accommodation_item", "items", () => ({ filters: { disabled: 0 } }));
		frm.set_query("site", () => ({ filters: { location: frm.doc.location } }));
		frm.set_query("floor", () => ({ filters: { site: frm.doc.site } }));
		frm.set_query("room", () => ({ filters: { floor: frm.doc.floor } }));
		frm.set_query("bed", () => ({ filters: { room: frm.doc.room } }));
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.assignment_date) {
			frm.set_value("assignment_date", frappe.datetime.get_today());
		}
	},

	employee(frm) {
		if (!frm.doc.employee || frm.doc.location) {
			return;
		}

		frappe.db
			.get_value("Employee", frm.doc.employee, [
				"current_accommodation_location",
				"current_accommodation_site",
				"current_accommodation_floor",
				"current_accommodation_room",
				"current_accommodation_bed",
			])
			.then((response) => {
				const current = response.message || {};
				if (!current.current_accommodation_location) {
					return;
				}

				frm.set_value({
					location: current.current_accommodation_location,
					site: current.current_accommodation_site,
					floor: current.current_accommodation_floor,
					room: current.current_accommodation_room,
					bed: current.current_accommodation_bed,
				});
			});
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
});
