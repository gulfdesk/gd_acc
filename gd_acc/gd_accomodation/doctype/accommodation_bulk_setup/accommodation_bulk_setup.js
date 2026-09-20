// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Bulk Setup", {
	setup(frm) {
		frm.set_query("site", () => ({
			filters: { location: frm.doc.location, status: "Active" },
		}));
	},

	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "Completed") {
			return;
		}

		frm.page.set_primary_action(__("Generate Structure"), () => confirm_generation(frm));
	},

	location(frm) {
		frm.set_value("site", null);
	},
});

frappe.ui.form.on("Accommodation Bulk Setup Floor", {
	bed_configuration: show_generated_beds,
	beds_per_room: show_generated_beds,
});

// A bunk unit is one frame holding a lower and an upper bed.
function beds_per_unit(row) {
	return row.bed_configuration === "Bunk" ? 2 : 1;
}

function show_generated_beds(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(
		cdt,
		cdn,
		"generated_beds_per_room",
		(row.beds_per_room || 0) * beds_per_unit(row)
	);
}

function confirm_generation(frm) {
	const planned = (frm.doc.floors || []).reduce(
		(totals, row) => {
			const rooms = row.number_of_rooms || 0;
			totals.rooms += rooms;
			totals.beds += rooms * (row.beds_per_room || 0) * beds_per_unit(row);
			return totals;
		},
		{ rooms: 0, beds: 0 }
	);

	frappe.confirm(
		__("Generate {0} floor(s), {1} room(s) and {2} bed(s) under {3}?", [
			(frm.doc.floors || []).length,
			planned.rooms,
			planned.beds,
			frappe.utils.escape_html(frm.doc.site || ""),
		]),
		() => {
			frm.call({
				doc: frm.doc,
				method: "generate",
				freeze: true,
				freeze_message: __("Generating accommodation structure..."),
				callback(response) {
					const created = response.message || {};
					frm.reload_doc();
					frappe.msgprint({
						title: __("Structure Created"),
						indicator: "green",
						message: __("Created {0} floor(s), {1} room(s) and {2} bed(s).", [
							created.floors || 0,
							created.rooms || 0,
							created.beds || 0,
						]),
					});
				},
			});
		}
	);
}
