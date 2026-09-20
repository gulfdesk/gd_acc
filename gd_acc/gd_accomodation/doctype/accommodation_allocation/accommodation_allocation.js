// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Allocation", {
	setup(frm) {
		frm.set_query("site", () => ({
			filters: { location: frm.doc.location, status: "Active" },
		}));

		frm.set_query("floor", () => ({
			filters: { site: frm.doc.site, status: "Active" },
		}));

		frm.set_query("room", () => ({
			filters: { floor: frm.doc.floor, status: "Active" },
		}));

		// Custom query so the dropdown shows Single / Bunk Lower / Bunk Upper.
		frm.set_query("bed", () => ({
			query: "gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation.get_allocatable_beds",
			filters: { room: frm.doc.room, floor: frm.doc.floor, site: frm.doc.site },
		}));
	},

	refresh(frm) {
		toggle_bed_requirement(frm);

		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("Release Accommodation"), () => show_release_dialog(frm));
			frm.add_custom_button(
				__("Transfer"),
				() => {
					frappe.new_doc("Accommodation Transfer", {
						employee: frm.doc.employee,
						current_allocation: frm.doc.name,
						transfer_date: frappe.datetime.get_today(),
					});
				},
				__("Create")
			);
		}
	},

	location(frm) {
		frm.set_value({ site: null, floor: null, room: null, bed: null });
	},

	site(frm) {
		frm.set_value({ floor: null, room: null, bed: null });
		toggle_bed_requirement(frm);
	},

	floor(frm) {
		frm.set_value({ room: null, bed: null });
	},

	room(frm) {
		frm.set_value({ bed: null });
	},

	bed_required(frm) {
		toggle_bed_requirement(frm);
	},
});

function toggle_bed_requirement(frm) {
	frm.set_df_property("bed", "reqd", frm.doc.bed_required ? 1 : 0);
}

function show_release_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Release Accommodation"),
		fields: [
			{
				fieldname: "release_date",
				fieldtype: "Date",
				label: __("Release Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldname: "reason",
				fieldtype: "Select",
				label: __("Reason"),
				options: ["Manual Release", "Employee Exit", "Other"].join("\n"),
				default: "Manual Release",
				reqd: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Release"),
		primary_action(values) {
			frappe.call({
				method: "gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation.release_allocation",
				args: {
					allocation: frm.doc.name,
					release_date: values.release_date,
					reason: values.reason,
					remarks: values.remarks,
				},
				freeze: true,
				freeze_message: __("Releasing accommodation..."),
				callback() {
					dialog.hide();
					frm.reload_doc();
					frappe.show_alert({
						message: __("Accommodation released. The bed is available again."),
						indicator: "green",
					});
				},
			});
		},
	});

	dialog.show();
}
