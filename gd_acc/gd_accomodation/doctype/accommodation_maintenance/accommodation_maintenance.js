// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

const LOCKED_STATUSES = ["Resolved", "Closed", "Cancelled"];
const OPEN_STATUSES = ["Open", "In Progress"];
const HOLD_FIELDS = ["location", "site", "floor", "room", "bed", "maintenance_type", "set_bed_under_maintenance"];

// The saved request holds its bed or room, so the place and the hold cannot change.
function holds(doc) {
	if (!OPEN_STATUSES.includes(doc.status)) {
		return false;
	}
	return doc.bed ? Boolean(doc.set_bed_under_maintenance) : Boolean(doc.room && doc.set_room_under_maintenance);
}

frappe.ui.form.on("Accommodation Maintenance", {
	setup(frm) {
		frm.set_query("site", () => ({ filters: { location: frm.doc.location } }));
		frm.set_query("floor", () => ({ filters: { site: frm.doc.site } }));
		frm.set_query("room", () => ({ filters: { floor: frm.doc.floor } }));
		frm.set_query("bed", () => ({ filters: { room: frm.doc.room } }));
	},

	refresh(frm) {
		// A finished request is read only here, for every role. A System Manager changes it
		// from the list: select it, then Actions > Edit.
		if (!frm.is_new() && LOCKED_STATUSES.includes(frm.doc.status)) {
			frm.disable_form();
			frm.set_intro(
				__("This request is {0} and locked. A System Manager can change it from the list: select it, then Actions > Edit.", [
					__(frm.doc.status),
				]),
				"blue"
			);
			return;
		}

		// Remember the saved request, so Resolved picked from the list can be put back cleanly.
		frm.__saved_status = frm.doc.status;
		frm.__saved_snapshot = snapshot(frm.doc);
		if (!frm.is_new() && OPEN_STATUSES.includes(frm.doc.status)) {
			frm.add_custom_button(__("Resolve"), () => open_resolve_dialog(frm)).addClass("btn-primary");
		}

		const holding = !frm.is_new() && holds(frm.doc);
		HOLD_FIELDS.forEach((field) => frm.set_df_property(field, "read_only", holding ? 1 : 0));
		frm.set_intro(
			holding
				? __("This request holds {0}. Set Status to Resolved or Cancelled to free it; for another place, raise a new request.", [
						frappe.utils.escape_html(frm.doc.bed || frm.doc.room),
				  ])
				: ""
		);
	},

	onload(frm) {
		if (frm.is_new()) {
			frm.set_value("reported_by", frappe.session.user);
			frm.set_value("reported_on", frappe.datetime.get_today());
		}
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

	status(frm) {
		// A saved request is resolved through the dialog, so the date and details are always recorded.
		if (frm.doc.status === "Resolved" && !frm.is_new() && !frm.__resolving) {
			restore_status(frm);
			open_resolve_dialog(frm);
		}
	},
});

// Put back the saved status. When nothing else was edited, the form is clean again.
function restore_status(frm) {
	frm.doc.status = frm.__saved_status || "Open";
	frm.refresh_field("status");
	if (snapshot(frm.doc) === frm.__saved_snapshot) {
		frm.doc.__unsaved = 0;
		frm.refresh_header();
	}
}

function snapshot(doc) {
	return JSON.stringify(Object.keys(doc).filter((key) => !key.startsWith("__")).sort().map((key) => [key, doc[key]]));
}

function open_resolve_dialog(frm) {
	const today = frappe.datetime.get_today();
	const dialog = new frappe.ui.Dialog({
		title: __("Resolve {0}", [frm.doc.name]),
		fields: [
			{
				fieldname: "resolution_date",
				fieldtype: "Date",
				label: __("Resolution Date"),
				default: frm.doc.resolution_date || today,
				reqd: 1,
				description: __("Reported on {0}.", [frappe.datetime.str_to_user(frm.doc.reported_on)]),
			},
			{
				fieldname: "resolution_details",
				fieldtype: "Small Text",
				label: __("Resolution Details"),
				default: frm.doc.resolution_details,
				reqd: 1,
				description: __("What was done, for example the part replaced or the contractor's note."),
			},
		],
		primary_action_label: __("Resolve"),
		primary_action(values) {
			if (values.resolution_date < frm.doc.reported_on) {
				frappe.msgprint(__("Resolution Date cannot be before Reported On."));
				return;
			}
			if (values.resolution_date > today) {
				frappe.msgprint(__("Resolution Date cannot be in the future."));
				return;
			}

			frm.__resolving = true;
			frm.set_value({
				status: "Resolved",
				resolution_date: values.resolution_date,
				resolution_details: values.resolution_details,
			})
				.then(() => frm.save())
				.then(() => {
					dialog.hide();
					frappe.show_alert({ message: __("{0} resolved.", [frm.doc.name]), indicator: "green" });
				})
				.catch(() => restore_status(frm))
				.finally(() => {
					frm.__resolving = false;
				});
		},
	});
	dialog.show();
}
