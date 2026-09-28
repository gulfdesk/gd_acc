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
		// Beds Only adds beds to existing rooms. Creating a room from here would skip the site filter.
		frm.fields_dict.rooms.grid.update_docfield_property("room", "only_select", 1);

		if (frm.doc.status === "Completed") {
			return;
		}
		show_beds_only_hint(frm);

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
		show_beds_only_hint(frm);
	},

	generate_scope(frm) {
		frm.refresh();
	},
});

frappe.ui.form.on("Accommodation Bulk Setup Floor", {
	bed_configuration: show_generated_beds,
	beds_per_room: show_generated_beds,
	single_beds: show_generated_beds,
	bunk_levels: show_generated_beds,
});

frappe.ui.form.on("Accommodation Bulk Setup Room", {
	bed_configuration: show_generated_beds,
	beds_per_room: show_generated_beds,
	single_beds: show_generated_beds,
	bunk_levels: show_generated_beds,
});

/** Beds Only needs rooms. A site without any is pointed to Floors, Rooms and Beds. */
function show_beds_only_hint(frm) {
	if (frm.doc.generate_scope !== "Beds Only" || !frm.doc.site) {
		frm.set_intro("");
		return;
	}
	frappe.db.count("Accommodation Room", { filters: { site: frm.doc.site } }).then((rooms) => {
		frm.set_intro(
			rooms
				? ""
				: __(
						"{0} has no rooms yet. Beds Only adds beds to existing rooms; choose Floors, Rooms and Beds to create the floors, rooms and beds.",
						[frappe.utils.escape_html(frm.doc.site)]
				  ),
			"orange"
		);
	});
}

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

// Beds in one room of the row. A bunk frame holds one bed per Bunk Level, 2 or 3;
// a Single + Bunk row adds its single beds after the bunks.
function beds_in_room(row) {
	const units = row.beds_per_room || 0;
	const levels = cint(row.bunk_levels) || 2;
	if (row.bed_configuration === "Bunk") {
		return units * levels;
	}
	if (row.bed_configuration === "Single + Bunk") {
		return units * levels + (row.single_beds || 0);
	}
	return units;
}

function show_generated_beds(frm, cdt, cdn) {
	frappe.model.set_value(cdt, cdn, "generated_beds_per_room", beds_in_room(locals[cdt][cdn]));
}

function confirm_generation(frm) {
	if (frm.doc.generate_scope === "Beds Only") {
		const beds = (frm.doc.rooms || []).reduce(
			(total, row) => total + beds_in_room(row),
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
			totals.beds += rooms * beds_in_room(row);
			return totals;
		},
		{ rooms: 0, beds: 0 }
	);

	frappe.confirm(
		__("Generate {0} floor(s), {1} room(s) and {2} bed(s) under {3}?", [
			// A floor repeated on several rows is created once.
			new Set((frm.doc.floors || []).map((row) => (row.floor_name || "").trim())).size,
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
