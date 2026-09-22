// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Bulk Setup", {
	setup(frm) {
		frm.set_query("site", () => ({
			filters: { location: frm.doc.location, status: "Active" },
		}));
		frm.set_query("room", "rooms", () => ({
			filters: { site: frm.doc.site, status: "Active" },
		}));
	},

	refresh(frm) {
		if (frm.doc.status === "Completed") {
			return;
		}

		if (frm.doc.generate_scope === "Beds Only") {
			frm.add_custom_button(__("Get Rooms"), () => get_rooms_without_beds(frm));
		}

		if (!frm.is_new()) {
			frm.page.set_primary_action(__("Generate Structure"), () => confirm_generation(frm));
		}
	},

	location(frm) {
		frm.set_value("site", null);
	},

	site(frm) {
		frm.clear_table("rooms");
		frm.refresh_field("rooms");
	},

	generate_scope(frm) {
		frm.refresh();
	},
});

frappe.ui.form.on("Accommodation Bulk Setup Floor", {
	bed_configuration: show_generated_beds,
	beds_per_room: show_generated_beds,
});

frappe.ui.form.on("Accommodation Bulk Setup Room", {
	bed_configuration: show_generated_beds,
	beds_per_room: show_generated_beds,
});

function get_rooms_without_beds(frm) {
	if (!frm.doc.site) {
		frappe.msgprint(__("Select the Accommodation Site first."));
		return;
	}

	frm.call({ doc: frm.doc, method: "get_rooms_without_beds" }).then((response) => {
		const listed = new Set((frm.doc.rooms || []).map((row) => row.room));
		const rooms = (response.message || []).filter((room) => !listed.has(room));

		if (!rooms.length) {
			frappe.show_alert({ message: __("No more active rooms without beds at this site."), indicator: "orange" });
			return;
		}

		rooms.forEach((room) => frm.add_child("rooms", { room }));
		frm.refresh_field("rooms");
		frappe.show_alert({ message: __("Added {0} room(s).", [rooms.length]), indicator: "green" });
	});
}

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
	if (frm.doc.generate_scope === "Beds Only") {
		const beds = (frm.doc.rooms || []).reduce(
			(total, row) => total + (row.beds_per_room || 0) * beds_per_unit(row),
			0
		);
		frappe.confirm(
			__("Add {0} bed(s) to {1} existing room(s) under {2}?", [
				beds,
				new Set((frm.doc.rooms || []).map((row) => row.room)).size,
				frappe.utils.escape_html(frm.doc.site || ""),
			]),
			() => run_generation(frm)
		);
		return;
	}

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
		() => run_generation(frm)
	);
}

function run_generation(frm) {
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
