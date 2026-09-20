// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.provide("gd_acc.accommodation");

/**
 * Enable / Disable button for accommodation master records.
 *
 * Status is read only on the form, so it moves only through this action.
 * Shared by Location, Site, Floor and Room.
 */
gd_acc.accommodation.add_status_buttons = function (frm) {
	if (frm.is_new()) {
		return;
	}

	const disabling = frm.doc.status === "Active";
	const label = disabling ? __("Disable") : __("Enable");
	const next_status = disabling ? "Inactive" : "Active";

	frm.add_custom_button(label, () => {
		frappe.confirm(
			disabling
				? __("Disable {0}? It stays in the system and keeps its history, but cannot be used for new allocations.", [
						frappe.utils.escape_html(frm.doc.name),
				  ])
				: __("Enable {0} again?", [frappe.utils.escape_html(frm.doc.name)]),
			() => {
				frappe.call({
					method: "gd_acc.gd_accomodation.api.set_master_status",
					args: { doctype: frm.doc.doctype, name: frm.doc.name, status: next_status },
					freeze: true,
					callback() {
						frm.reload_doc();
						frappe.show_alert({
							message: __("{0} is now {1}.", [frm.doc.name, __(next_status)]),
							indicator: disabling ? "orange" : "green",
						});
					},
				});
			}
		);
	});

	frm.page.set_indicator(__(frm.doc.status), disabling ? "green" : "gray");
};
