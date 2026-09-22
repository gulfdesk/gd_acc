// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

const ALLOCATION_METHOD =
	"gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation";

// Allocation statuses of an employee who still lives in the place.
const CURRENT = ["Active", "Pending Release"];

// pending_release_reason -> the release reason that the release dialog proposes.
const PROPOSED_RELEASE_REASON = {
	"Employee Left": "Employee Exit",
	"Relieving Date Set": "Employee Exit",
	"Entitlement Ended": "Accommodation Status Change",
};

frappe.ui.form.on("Accommodation Allocation", {
	setup(frm) {
		frm.set_query("accommodation_item", "items", () => ({ filters: { disabled: 0 } }));

		// Only the employee's company can house the employee. The server checks it again on submit.
		frm.set_query("location", () => ({
			filters: { status: "Active", company: frm.doc.company },
		}));

		frm.set_query("site", () => ({
			filters: {
				location: frm.doc.location,
				status: "Active",
				gender_restriction: gender_restriction_filter(frm.doc.gender),
			},
		}));

		frm.set_query("floor", () => ({
			filters: { site: frm.doc.site, status: "Active" },
		}));

		frm.set_query("room", () => ({
			filters: {
				floor: frm.doc.floor,
				status: "Active",
				gender_restriction: gender_restriction_filter(frm.doc.gender),
			},
		}));

		// Custom query so the dropdown shows Single / Bunk Lower / Bunk Upper.
		frm.set_query("bed", () => ({
			query: "gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation.get_allocatable_beds",
			filters: {
				room: frm.doc.room,
				floor: frm.doc.floor,
				site: frm.doc.site,
				gender: frm.doc.gender || "",
			},
		}));
	},

	refresh(frm) {
		toggle_bed_requirement(frm);

		if (frm.doc.docstatus === 1 && frm.doc.status === "Pending Release") {
			show_pending_release(frm);
		}

		if (frm.doc.docstatus === 1 && CURRENT.includes(frm.doc.status)) {
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

		if (frm.doc.docstatus === 1 && frm.doc.outstanding_items > 0) {
			frm.add_custom_button(__("Return Items"), () => {
				frappe.model.open_mapped_doc({
					method: "gd_acc.gd_accomodation.doctype.accommodation_item_entry.accommodation_item_entry.make_return_for_allocation",
					frm,
				});
			});
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Accommodation Item Entries"),
				() => {
					frappe.set_route("List", "Accommodation Item Entry", {
						allocation: frm.doc.name,
					});
				},
				__("View")
			);
		}

		// The Employee tab sets this flag to open the release dialog on arrival.
		if (frappe.flags.gd_acc_open_release === frm.doc.name) {
			frappe.flags.gd_acc_open_release = null;
			if (frm.doc.docstatus === 1 && CURRENT.includes(frm.doc.status)) {
				show_release_dialog(frm);
			}
		}
	},

	employee(frm) {
		// The new employee can be in another company, so the chosen place can be wrong.
		if (frm.doc.location) {
			frm.set_value("location", null);
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

function show_pending_release(frm) {
	// No field keeps the mark date. The last change of the row is the closest value.
	frm.set_intro(
		__("Pending Release since {0}: {1}. Proposed release date {2}.", [
			frappe.datetime.str_to_user(String(frm.doc.modified).split(" ")[0]),
			__(frm.doc.pending_release_reason || ""),
			frappe.datetime.str_to_user(frm.doc.proposed_release_date),
		]),
		"orange"
	);

	if (frappe.user.has_role("Accommodation Manager") || frappe.user.has_role("System Manager")) {
		frm.add_custom_button(__("Keep Active"), () => {
			frappe.confirm(
				__("Keep this allocation Active? The pending release is removed."),
				() => {
					frappe
						.call({
							method: "gd_acc.gd_accomodation.release_flow.keep_allocation_active",
							args: { allocation: frm.doc.name },
						})
						.then(() => frm.reload_doc());
				}
			);
		});
	}
}

function show_release_dialog(frm) {
	// One id per dialog, so a repeated click or a retried request records the return once.
	const request_id = frappe.utils.get_random(20);

	frappe
		.call({
			method: `${ALLOCATION_METHOD}.get_release_lines`,
			args: { allocation: frm.doc.name },
		})
		.then((response) => {
			build_release_dialog(frm, request_id, response.message || []).show();
		});
}

function build_release_dialog(frm, request_id, lines) {
	const fields = [
		{
			fieldname: "release_date",
			fieldtype: "Date",
			label: __("Release Date"),
			default: frm.doc.proposed_release_date || frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "reason",
			fieldtype: "Select",
			label: __("Reason"),
			options: ["Manual Release", "Employee Exit", "Accommodation Status Change", "Other"].join("\n"),
			default: PROPOSED_RELEASE_REASON[frm.doc.pending_release_reason] || "Manual Release",
			reqd: 1,
		},
		{
			fieldname: "remarks",
			fieldtype: "Small Text",
			label: __("Remarks"),
		},
	];

	if (lines.length) {
		fields.push(
			{
				fieldname: "items_section",
				fieldtype: "Section Break",
				label: __("Items Returned"),
				description: __(
					"Enter what comes back now. Anything left stays outstanding for a later Return entry."
				),
			},
			{
				fieldname: "item_returns",
				fieldtype: "Table",
				label: __("Items"),
				cannot_add_rows: true,
				cannot_delete_rows: true,
				in_place_edit: true,
				data: lines.map((line) => ({
					against_entry: line.against_entry,
					against_detail: line.against_detail,
					accommodation_item: line.accommodation_item,
					outstanding_quantity: line.outstanding_quantity,
					returned_quantity: line.outstanding_quantity,
					damaged_quantity: 0,
					lost_quantity: 0,
				})),
				fields: [
					{
						fieldname: "against_entry",
						fieldtype: "Link",
						options: "Accommodation Item Entry",
						label: __("Assigned On"),
						read_only: 1,
						in_list_view: 1,
						columns: 2,
					},
					{
						fieldname: "against_detail",
						fieldtype: "Data",
						label: __("Assign Line"),
						hidden: 1,
						read_only: 1,
					},
					{
						fieldname: "accommodation_item",
						fieldtype: "Link",
						options: "Accommodation Item",
						label: __("Item"),
						read_only: 1,
						in_list_view: 1,
						columns: 3,
					},
					{
						fieldname: "outstanding_quantity",
						fieldtype: "Int",
						label: __("Outstanding"),
						read_only: 1,
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "returned_quantity",
						fieldtype: "Int",
						label: __("Returned"),
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "damaged_quantity",
						fieldtype: "Int",
						label: __("Damaged"),
						in_list_view: 1,
						columns: 1,
					},
					{
						fieldname: "lost_quantity",
						fieldtype: "Int",
						label: __("Lost"),
						in_list_view: 1,
						columns: 1,
					},
				],
			}
		);
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Release Accommodation"),
		size: lines.length ? "large" : "small",
		fields,
		primary_action_label: __("Release"),
		primary_action(values) {
			const item_returns = get_item_returns(values.item_returns || []);

			dialog.get_primary_btn().prop("disabled", true);
			frappe
				.call({
					method: `${ALLOCATION_METHOD}.release_allocation`,
					args: {
						allocation: frm.doc.name,
						release_date: values.release_date,
						reason: values.reason,
						remarks: values.remarks,
						item_returns: item_returns.length ? item_returns : null,
						request_id,
					},
					freeze: true,
					freeze_message: __("Releasing accommodation..."),
				})
				.then(() => {
					dialog.hide();
					frm.reload_doc();
					frappe.show_alert({
						message: __("Accommodation released. The bed is available again."),
						indicator: "green",
					});
				})
				.finally(() => {
					dialog.get_primary_btn().prop("disabled", false);
				});
		},
	});

	return dialog;
}

function get_item_returns(rows) {
	const item_returns = [];

	rows.forEach((row) => {
		const quantities = ["returned_quantity", "damaged_quantity", "lost_quantity"].map(
			(fieldname) => row[fieldname] || 0
		);

		// The server checks again under a lock. This only catches a typing error early.
		if (quantities.some((quantity) => !Number.isInteger(Number(quantity)) || Number(quantity) < 0)) {
			frappe.throw(__("{0}: every quantity must be a whole number of 0 or more.", [row.accommodation_item]));
		}

		const total = quantities.reduce((sum, quantity) => sum + Number(quantity), 0);
		if (total > row.outstanding_quantity) {
			frappe.throw(
				__("{0}: {1} returned, but only {2} is outstanding.", [
					row.accommodation_item,
					total,
					row.outstanding_quantity,
				])
			);
		}

		if (total > 0) {
			item_returns.push({
				against_entry: row.against_entry,
				against_detail: row.against_detail,
				accommodation_item: row.accommodation_item,
				returned_quantity: Number(quantities[0]),
				damaged_quantity: Number(quantities[1]),
				lost_quantity: Number(quantities[2]),
			});
		}
	});

	return item_returns;
}

// Places open to the employee's gender. An employee with no gender sees Any places only.
function gender_restriction_filter(gender) {
	return gender ? ["in", ["Any", gender]] : "Any";
}
