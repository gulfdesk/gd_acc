// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

const STAY_STATUS_COLORS = { "Awaiting Bed": "orange", Allocated: "green", Vacated: "gray" };

frappe.ui.form.on("Accommodation Entitlement", {
	refresh(frm) {
		render_allocation_panel(frm);

		if (frm.doc.docstatus === 1 && frm.doc.stay_status) {
			frm.dashboard.add_indicator(
				__("Stay Status: {0}", [__(frm.doc.stay_status)]),
				STAY_STATUS_COLORS[frm.doc.stay_status] || "gray"
			);
		}

		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("End or Extend"), () => show_end_or_extend_dialog(frm));

			if (
				frm.doc.entitlement_type === "Company Accommodation" &&
				frm.doc.stay_status !== "Allocated" &&
				frappe.model.can_create("Accommodation Allocation")
			) {
				frm.add_custom_button(
					__("Accommodation Allocation"),
					() => {
						frappe.new_doc("Accommodation Allocation", {
							employee: frm.doc.employee,
							start_date: frm.doc.from_date,
						});
					},
					__("Create")
				);
			}
			frm.page.set_inner_btn_group_as_primary(__("Create"));
		}
	},

	entitlement_type(frm) {
		if (frm.doc.entitlement_type === "Allowance") {
			fetch_allowance(frm);
		}
	},

	employee(frm) {
		if (frm.doc.entitlement_type === "Allowance") {
			fetch_allowance(frm);
		}
	},

	allowance_component(frm) {
		fetch_allowance(frm, true);
	},
});

/** HR ends or extends the entitlement by a change of its Effective To. */
function show_end_or_extend_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("End or Extend"),
		fields: [
			{
				fieldname: "to_date",
				fieldtype: "Date",
				label: __("Effective To"),
				default: frm.doc.to_date,
				description: __("Leave empty for an entitlement with no end date."),
			},
		],
		primary_action_label: __("Save"),
		primary_action(values) {
			frm.set_value("to_date", values.to_date || null);
			frm.save("Update").then(() => dialog.hide());
		},
	});
	dialog.show();
}

/** Pull the housing allowance straight from the employee's salary structure. */
function fetch_allowance(frm, force) {
	if (!frm.doc.employee || !frm.doc.from_date) {
		return;
	}

	frappe.call({
		method: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.fetch_allowance_details",
		args: {
			employee: frm.doc.employee,
			on_date: frm.doc.from_date,
			component: frm.doc.allowance_component || null,
		},
		callback(response) {
			const details = response.message || {};
			if (details.component && !frm.doc.allowance_component) {
				frm.set_value("allowance_component", details.component);
			}
			frm.set_value("salary_structure", details.salary_structure || null);
			frm.set_value("allowance_source", details.source || null);

			if (details.amount && (force || !frm.doc.allowance_amount)) {
				frm.set_value("allowance_amount", details.amount);
			}
			if (details.currency && !frm.doc.allowance_currency) {
				frm.set_value("allowance_currency", details.currency);
			}
		},
	});
}

function render_allocation_panel(frm) {
	const field = frm.get_field("allocation_html");
	if (!field || frm.is_new()) {
		return;
	}

	if (frm.doc.entitlement_type !== "Company Accommodation") {
		field.$wrapper.empty();
		return;
	}

	frappe.call({
		method: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.get_employee_entitlement_state",
		args: { employee: frm.doc.employee },
		callback(response) {
			const state = response.message || {};
			if (!state.active_allocation) {
				field.$wrapper.html(
					`<div class="text-muted">${__(
						"No bed allocated yet. Use Create &gt; Accommodation Allocation once this entitlement is submitted."
					)}</div>`
				);
				return;
			}

			const current = (state.allocations || []).find((row) => row.name === state.active_allocation);
			const place = current
				? [current.location, current.site, current.floor, current.room, current.bed]
						.filter(Boolean)
						.map((value) => frappe.utils.escape_html(value))
						.join(" &rsaquo; ")
				: "";

			field.$wrapper.html(`
				<div class="alert alert-info" role="alert">
					<b>${__("Currently allocated")}</b>: ${place}
					<a href="/app/accommodation-allocation/${encodeURIComponent(
						state.active_allocation
					)}">${frappe.utils.escape_html(state.active_allocation)}</a>
				</div>`);
		},
	});
}
