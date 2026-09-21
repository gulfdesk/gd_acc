// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

const ITEM_ENTRY_METHOD =
	"gd_acc.gd_accomodation.doctype.accommodation_item_entry.accommodation_item_entry";

frappe.ui.form.on("Accommodation Item Entry", {
	setup(frm) {
		frm.set_query("accommodation_item", "items", () => ({ filters: { disabled: 0 } }));
		frm.set_query("site", () => ({ filters: { location: frm.doc.location } }));
		frm.set_query("floor", () => ({ filters: { site: frm.doc.site } }));
		frm.set_query("room", () => ({ filters: { floor: frm.doc.floor } }));
		frm.set_query("bed", () => ({ filters: { room: frm.doc.room } }));
		frm.set_query("allocation", () => {
			const filters = { docstatus: 1 };
			if (frm.doc.employee) {
				filters.employee = frm.doc.employee;
			}
			return { filters };
		});
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.posting_date) {
			frm.set_value("posting_date", frappe.datetime.get_today());
		}
	},

	refresh(frm) {
		toggle_return_grid(frm);

		if (frm.doc.docstatus !== 1 || frm.doc.purpose !== "Assign") {
			return;
		}

		if (frm.doc.outstanding_items > 0) {
			frm.add_custom_button(__("Return Items"), () => {
				frappe.model.open_mapped_doc({
					method: `${ITEM_ENTRY_METHOD}.make_return`,
					frm,
				});
			});
		}

		frm.add_custom_button(
			__("View Returns"),
			() => {
				frappe.set_route("List", "Accommodation Item Entry", {
					purpose: "Return",
					"Accommodation Item Entry Detail.against_entry": frm.doc.name,
				});
			},
			__("View")
		);
	},

	purpose(frm) {
		toggle_return_grid(frm);
	},

	validate(frm) {
		if (frm.doc.purpose !== "Return" || !frm.outstanding_by_line) {
			return;
		}

		// The server checks again under a lock. This only catches a typing error early.
		const requested = {};
		(frm.doc.items || []).forEach((line) => {
			requested[line.against_detail] = (requested[line.against_detail] || 0) + cint(line.quantity);
		});

		(frm.doc.items || []).forEach((line) => {
			const outstanding = frm.outstanding_by_line[line.against_detail];
			if (outstanding !== undefined && requested[line.against_detail] > outstanding) {
				frappe.throw(
					__("Row #{0} ({1}): {2} returned, but only {3} is outstanding.", [
						line.idx,
						line.accommodation_item,
						requested[line.against_detail],
						outstanding,
					])
				);
			}
		});
	},

	get_outstanding_items(frm) {
		if (!frm.doc.employee && !frm.doc.allocation && !frm.doc.site) {
			frappe.msgprint(__("Set the Employee, the Allocation or the Accommodation Site first."));
			return;
		}

		frappe
			.call({
				method: `${ITEM_ENTRY_METHOD}.get_return_lines`,
				args: {
					employee: frm.doc.employee,
					allocation: frm.doc.allocation,
					site: frm.doc.site,
				},
				freeze: true,
			})
			.then((response) => {
				const lines = response.message || [];
				frm.outstanding_by_line = {};
				frm.clear_table("items");

				lines.forEach((line) => {
					frm.outstanding_by_line[line.against_detail] = line.outstanding_quantity;
					const row = frm.add_child("items");
					Object.assign(row, {
						accommodation_item: line.accommodation_item,
						return_type: line.return_type,
						quantity: line.quantity,
						against_entry: line.against_entry,
						against_detail: line.against_detail,
					});
				});

				frm.refresh_field("items");
				if (!lines.length) {
					frappe.msgprint(__("No items are outstanding for this holder."));
				}
			});
	},

	allocation(frm) {
		if (!frm.doc.allocation) {
			return;
		}

		frappe.db
			.get_value("Accommodation Allocation", frm.doc.allocation, [
				"employee",
				"location",
				"site",
				"floor",
				"room",
				"bed",
			])
			.then((response) => {
				const allocation = response.message || {};
				set_holder(frm, {
					employee: allocation.employee,
					location: allocation.location,
					site: allocation.site,
					floor: allocation.floor,
					room: allocation.room,
					bed: allocation.bed,
				});
			});
	},

	employee(frm) {
		if (frm.filling_holder || !frm.doc.employee || frm.doc.location) {
			return;
		}

		frappe.db
			.get_value(
				"Accommodation Allocation",
				{
					employee: frm.doc.employee,
					docstatus: 1,
					status: ["in", ["Active", "Pending Release"]],
				},
				["location", "site", "floor", "room", "bed"]
			)
			.then((response) => {
				const current = response.message || {};
				if (!current.location) {
					return;
				}

				set_holder(frm, {
					location: current.location,
					site: current.site,
					floor: current.floor,
					room: current.room,
					bed: current.bed,
				});
			});
	},

	location(frm) {
		if (frm.filling_holder) {
			return;
		}
		frm.set_value({ site: null, floor: null, room: null, bed: null });
	},

	site(frm) {
		if (frm.filling_holder) {
			return;
		}
		frm.set_value({ floor: null, room: null, bed: null });
	},

	floor(frm) {
		if (frm.filling_holder) {
			return;
		}
		frm.set_value({ room: null, bed: null });
	},

	room(frm) {
		if (frm.filling_holder) {
			return;
		}
		frm.set_value({ bed: null });
	},
});

function toggle_return_grid(frm) {
	const grid = frm.get_field("items").grid;
	const is_return = frm.doc.purpose === "Return";
	grid.cannot_add_rows = is_return;
	frm.refresh_field("items");
}

function set_holder(frm, values) {
	// The cascade handlers clear the lower levels. Skip them while a full holder is set.
	frm.filling_holder = true;
	return frm.set_value(values).finally(() => {
		frm.filling_holder = false;
	});
}
