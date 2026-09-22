// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accommodation Transfer", {
	setup(frm) {
		frm.set_query("current_allocation", () => ({
			filters: {
				employee: frm.doc.employee,
				status: ["in", ["Active", "Pending Release"]],
				docstatus: 1,
			},
		}));

		// Only the employee's company can house the employee. The server checks it again on submit.
		frm.set_query("to_location", () => ({
			filters: { status: "Active", company: frm.doc.company },
		}));

		frm.set_query("to_site", () => ({
			filters: {
				location: frm.doc.to_location,
				status: "Active",
				gender_restriction: gender_restriction_filter(frm.doc.gender),
			},
		}));

		frm.set_query("to_floor", () => ({
			filters: { site: frm.doc.to_site, status: "Active" },
		}));

		frm.set_query("to_room", () => ({
			filters: {
				floor: frm.doc.to_floor,
				status: "Active",
				gender_restriction: gender_restriction_filter(frm.doc.gender),
			},
		}));

		// Custom query so the dropdown shows Single / Bunk Lower / Bunk Upper.
		frm.set_query("to_bed", () => ({
			query: "gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation.get_allocatable_beds",
			filters: {
				room: frm.doc.to_room,
				floor: frm.doc.to_floor,
				site: frm.doc.to_site,
				gender: frm.doc.gender || "",
			},
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.new_allocation) {
			frm.add_custom_button(__("View New Allocation"), () => {
				frappe.set_route("Form", "Accommodation Allocation", frm.doc.new_allocation);
			});
		}
	},

	employee(frm) {
		frm.set_value("current_allocation", null);
		if (!frm.doc.employee) {
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
				"name"
			)
			.then((response) => {
				const allocation = response.message && response.message.name;
				if (allocation) {
					frm.set_value("current_allocation", allocation);
				}
			});
	},

	to_location(frm) {
		frm.set_value({ to_site: null, to_floor: null, to_room: null, to_bed: null });
	},

	to_site(frm) {
		frm.set_value({ to_floor: null, to_room: null, to_bed: null });
	},

	to_floor(frm) {
		frm.set_value({ to_room: null, to_bed: null });
	},

	to_room(frm) {
		frm.set_value({ to_bed: null });
	},
});

// Places open to the employee's gender. An employee with no gender sees Any places only.
function gender_restriction_filter(gender) {
	return gender ? ["in", ["Any", gender]] : "Any";
}
