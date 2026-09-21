// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

// A history table shows this many rows. More rows scroll.
const HISTORY_VISIBLE_ROWS = 5;

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		render_accommodation_tab(frm);
	},
});

function render_accommodation_tab(frm) {
	const panel = frm.get_field("accommodation_html");
	if (!panel) {
		return;
	}

	frappe.call({
		method: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.get_employee_entitlement_state",
		args: { employee: frm.doc.name },
		callback(response) {
			const state = response.message || {};
			panel.$wrapper.html(`${accommodation_styles()}${build_summary(state)}${build_history(state)}`);
			add_accommodation_buttons(frm, state);
		},
	});
}

/* ---------------------------------------------------------------- summary */

/** The current entitlement and place, as label and value pairs in two columns. */
function build_summary(state) {
	const entitlement = state.entitlement;
	const current_stay = state.active_allocation
		? (state.allocations || []).find((row) => row.name === state.active_allocation)
		: null;

	const rows = [];
	if (entitlement) {
		rows.push([__("Entitlement"), `${__(entitlement.entitlement_type)} ${stay_pill(entitlement)}`]);
		rows.push([__("Effective"), period(entitlement.from_date, entitlement.to_date)]);
	} else {
		rows.push([__("Entitlement"), current_stay ? __("No entitlement recorded") : __("Not Provided")]);
	}

	if (entitlement && entitlement.entitlement_type === "Allowance") {
		rows.push([
			__("Amount"),
			entitlement.allowance_amount
				? format_currency(entitlement.allowance_amount, entitlement.allowance_currency)
				: __("Amount not set"),
		]);
		rows.push([__("Salary Component"), escape(entitlement.allowance_component)]);
	}

	if (current_stay) {
		const place = state.place || {};
		rows.push([__("Location"), escape(place.location)]);
		rows.push([__("Site"), escape(place.site)]);
		rows.push([__("Floor"), escape(place.floor)]);
		rows.push([__("Room"), escape(place.room)]);
		rows.push([__("Bed"), escape(place.bed)]);
		rows.push([__("Since"), frappe.datetime.str_to_user(current_stay.start_date)]);
		if (current_stay.status === "Pending Release") {
			rows.push([
				__("Pending Release"),
				`${frappe.datetime.str_to_user(current_stay.proposed_release_date)} (${escape(
					__(current_stay.pending_release_reason || "")
				)})`,
			]);
		}
	}

	const cells = rows
		.map(
			([label, value]) => `
			<div class="col-sm-6">
				<div class="frappe-control">
					<div class="control-label">${label}</div>
					<div class="control-value like-disabled-input">${value || ""}</div>
				</div>
			</div>`
		)
		.join("");
	return `<div class="row">${cells}</div>`;
}

function stay_pill(entitlement) {
	if (entitlement.entitlement_type !== "Company Accommodation") {
		return "";
	}
	return gd_acc.accommodation.status_pill("Accommodation Entitlement", "stay_status", entitlement.stay_status);
}

/**
 * The actions sit in one Accommodation group in the form header. They depend on
 * whether the employee currently occupies a bed - not on whether an Entitlement
 * document happens to exist.
 */
function add_accommodation_buttons(frm, state) {
	const group = __("Accommodation");
	for (const label of [
		__("Create Entitlement"),
		__("Switch to Company Accommodation"),
		__("Release Accommodation"),
		__("Transfer"),
		__("View Allocation"),
	]) {
		frm.remove_custom_button(label, group);
	}

	const allocation = state.active_allocation;
	const entitlement = state.entitlement;

	if (allocation) {
		frm.add_custom_button(
			__("Release Accommodation"),
			() => {
				// The allocation form opens its release dialog, with the item returns, on arrival.
				frappe.flags.gd_acc_open_release = allocation;
				frappe.set_route("Form", "Accommodation Allocation", allocation);
			},
			group
		);
		frm.add_custom_button(
			__("Transfer"),
			() =>
				frappe.new_doc("Accommodation Transfer", {
					employee: frm.doc.name,
					current_allocation: allocation,
					transfer_date: frappe.datetime.get_today(),
				}),
			group
		);
		frm.add_custom_button(
			__("View Allocation"),
			() => frappe.set_route("Form", "Accommodation Allocation", allocation),
			group
		);
	} else if (entitlement && entitlement.entitlement_type === "Allowance") {
		frm.add_custom_button(
			__("Switch to Company Accommodation"),
			() => open_entitlement_dialog(frm, { prefill_type: "Company Accommodation" }),
			group
		);
	} else {
		frm.add_custom_button(__("Create Entitlement"), () => open_entitlement_dialog(frm), group);
	}
}

/**
 * One form, one Save button. Choosing Company Accommodation reveals the bed
 * assignment fields right here instead of sending the user to a second
 * screen; choosing Allowance reveals the payroll fields and auto-fills them.
 */
function open_entitlement_dialog(frm, options = {}) {
	const prefill_type = options.prefill_type || "Company Accommodation";
	const can_allocate = frappe.model.can_create("Accommodation Allocation");

	const maybe_fetch_allowance = () => {
		if (dialog.get_value("entitlement_type") !== "Allowance") {
			return;
		}
		frappe.call({
			method: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.fetch_allowance_details",
			args: {
				employee: frm.doc.name,
				on_date: dialog.get_value("from_date"),
				component: dialog.get_value("allowance_component") || null,
				salary_structure_assignment: dialog.get_value("salary_structure_assignment") || null,
			},
			callback(response) {
				const details = response.message || {};
				// set_value fires onchange, so only a changed value is set. Otherwise the fetch loops.
				const updates = {
					allowance_amount: details.amount || 0,
					allowance_currency: details.currency || null,
				};
				if (details.salary_structure_assignment && !dialog.get_value("salary_structure_assignment")) {
					updates.salary_structure_assignment = details.salary_structure_assignment;
				}
				dialog.set_values(updates);
				dialog.fields_dict.allowance_source.$wrapper.html(
					`<div class="text-muted small">${frappe.utils.escape_html(details.source || "")}</div>`
				);
			},
		});
	};

	// Only a user who may create an allocation houses the employee from this dialog.
	const allocation_note = {
		fieldname: "allocation_note",
		fieldtype: "HTML",
		options: `<div class="text-muted">${__("An Accommodation User allocates the bed.")}</div>`,
	};
	const allocation_fields = () => [
		{
			fieldname: "location",
			fieldtype: "Link",
			options: "Accommodation Location",
			label: __("Location"),
			get_query: () => ({ filters: { status: "Active", company: frm.doc.company } }),
			onchange: () => dialog.set_values({ site: null, floor: null, room: null, bed: null }),
		},
		{
			fieldname: "site",
			fieldtype: "Link",
			options: "Accommodation Site",
			label: __("Accommodation Site"),
			get_query: () => ({
				filters: {
					location: dialog.get_value("location"),
					status: "Active",
					gender_restriction: gender_restriction_filter(frm.doc.gender),
				},
			}),
			onchange: () => dialog.set_values({ floor: null, room: null, bed: null }),
		},
		{ fieldname: "accommodation_column", fieldtype: "Column Break" },
		{
			fieldname: "floor",
			fieldtype: "Link",
			options: "Accommodation Floor",
			label: __("Floor"),
			get_query: () => ({ filters: { site: dialog.get_value("site"), status: "Active" } }),
			onchange: () => dialog.set_values({ room: null, bed: null }),
		},
		{
			fieldname: "room",
			fieldtype: "Link",
			options: "Accommodation Room",
			label: __("Room"),
			get_query: () => ({
				filters: {
					floor: dialog.get_value("floor"),
					status: "Active",
					gender_restriction: gender_restriction_filter(frm.doc.gender),
				},
			}),
			onchange: () => dialog.set_value("bed", null),
		},
		{
			fieldname: "bed",
			fieldtype: "Link",
			options: "Accommodation Bed",
			label: __("Bed"),
			get_query: () => ({
				query: "gd_acc.gd_accomodation.doctype.accommodation_allocation.accommodation_allocation.get_allocatable_beds",
				filters: {
					room: dialog.get_value("room"),
					floor: dialog.get_value("floor"),
					site: dialog.get_value("site"),
					gender: frm.doc.gender || "",
				},
			}),
		},
		{
			fieldname: "expected_end_date",
			fieldtype: "Date",
			label: __("Expected End Date"),
			depends_on: 'eval:doc.entitlement_type=="Company Accommodation"',
		},
	];

	const dialog = new frappe.ui.Dialog({
		title: __("Create Entitlement"),
		size: "large",
		fields: [
			{
				fieldname: "entitlement_type",
				fieldtype: "Select",
				label: __("Entitlement"),
				options: ["Company Accommodation", "Allowance", "Not Provided"].join("\n"),
				default: prefill_type,
				reqd: 1,
				onchange: maybe_fetch_allowance,
			},
			{
				fieldname: "from_date",
				fieldtype: "Date",
				label: __("Effective From"),
				default: frappe.datetime.get_today(),
				reqd: 1,
				onchange: maybe_fetch_allowance,
			},
			{
				fieldname: "accommodation_section",
				fieldtype: "Section Break",
				label: __("Assign Accommodation"),
				depends_on: 'eval:doc.entitlement_type=="Company Accommodation"',
			},
			...(can_allocate ? allocation_fields() : [allocation_note]),
			{
				fieldname: "allowance_section",
				fieldtype: "Section Break",
				label: __("Accommodation Allowance"),
				depends_on: 'eval:doc.entitlement_type=="Allowance"',
			},
			{
				fieldname: "salary_structure_assignment",
				fieldtype: "Link",
				options: "Salary Structure Assignment",
				label: __("Salary Structure Assignment"),
				mandatory_depends_on: 'eval:doc.entitlement_type=="Allowance"',
				get_query: () => ({ filters: { employee: frm.doc.name, docstatus: 1 } }),
				onchange: () => {
					dialog.set_value("allowance_component", null);
					maybe_fetch_allowance();
				},
			},
			{
				fieldname: "allowance_component",
				fieldtype: "Link",
				options: "Salary Component",
				label: __("Salary Component"),
				mandatory_depends_on: 'eval:doc.entitlement_type=="Allowance"',
				get_query: () => ({
					query: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.get_assignment_components",
					filters: { salary_structure_assignment: dialog.get_value("salary_structure_assignment") },
				}),
				onchange: maybe_fetch_allowance,
			},
			{ fieldname: "allowance_column", fieldtype: "Column Break" },
			{
				fieldname: "allowance_amount",
				fieldtype: "Currency",
				label: __("Allowance Amount"),
				options: "allowance_currency",
				read_only: 1,
				description: __("From the latest submitted salary slip."),
			},
			{ fieldname: "allowance_currency", fieldtype: "Link", options: "Currency", hidden: 1 },
			{ fieldname: "allowance_source", fieldtype: "HTML" },
			{ fieldname: "remarks_section", fieldtype: "Section Break" },
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks"),
				depends_on: 'eval:doc.entitlement_type!="Allowance"',
			},
		],
		primary_action_label: __("Save"),
		primary_action(values) {
			dialog.disable_primary_action();
			frappe.call({
				method: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.create_entitlement",
				args: { employee: frm.doc.name, ...values },
				freeze: true,
				freeze_message: __("Saving..."),
				callback() {
					dialog.hide();
					frm.reload_doc();
					frappe.show_alert({ message: __("Entitlement saved."), indicator: "green" });
				},
				always() {
					dialog.enable_primary_action();
				},
			});
		},
	});

	dialog.show();

	if (prefill_type === "Allowance") {
		maybe_fetch_allowance();
	}
}

/* ---------------------------------------------------------------- history */

function build_history(state) {
	const entitlements = state.entitlements || [];
	const allocations = state.allocations || [];

	if (!entitlements.length && !allocations.length) {
		return `<div class="text-muted small acc-history">${__("No accommodation history yet.")}</div>`;
	}

	return `
		${entitlement_table(entitlements)}
		${allocation_table(allocations)}`;
}

function entitlement_table(rows) {
	return history_table(__("Entitlement History"), rows, [
		[__("Entitlement"), (row) => doc_link("accommodation-entitlement", row.name)],
		[__("Type"), (row) => escape(__(row.entitlement_type))],
		[__("Period"), (row) => period(row.from_date, row.to_date)],
		[
			__("Allowance"),
			(row) => (row.allowance_amount ? format_currency(row.allowance_amount, row.allowance_currency) : ""),
			"text-right",
		],
		[__("Status"), (row) => gd_acc.accommodation.status_pill("Accommodation Entitlement", "status", row.status)],
	]);
}

function allocation_table(rows) {
	return history_table(__("Accommodation History"), rows, [
		[__("Allocation"), (row) => doc_link("accommodation-allocation", row.name)],
		[__("Site"), (row) => escape((row.place || {}).site)],
		[__("Floor"), (row) => escape((row.place || {}).floor)],
		[__("Room"), (row) => escape((row.place || {}).room)],
		[__("Bed"), (row) => escape((row.place || {}).bed)],
		[__("Period"), (row) => period(row.start_date, row.release_date)],
		[__("Stay"), (row) => stay_length(row.start_date, row.release_date), "text-right"],
		[__("Status"), (row) => gd_acc.accommodation.status_pill("Accommodation Allocation", "status", row.status)],
	]);
}

/** Both history tables share this one layout. A column is [label, render, class]. */
function history_table(title, rows, columns) {
	if (!rows.length) {
		return "";
	}

	const head = columns.map(([label, , cls]) => `<th class="${cls || ""}">${label}</th>`).join("");
	const body = rows
		.map(
			(row) =>
				`<tr>${columns
					.map(([, render, cls]) => `<td class="${cls || ""}">${render(row) || ""}</td>`)
					.join("")}</tr>`
		)
		.join("");

	return `
		<div class="frappe-control acc-history">
			<div class="control-label">${title} (${rows.length})</div>
			<div class="acc-scroll">
				<table class="table table-bordered acc-table">
					<thead><tr>${head}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		</div>`;
}

function stay_length(start_date, release_date) {
	if (!start_date) {
		return "";
	}
	const end = release_date || frappe.datetime.get_today();
	const days = frappe.datetime.get_day_diff(end, start_date);
	return days >= 0 ? __("{0} days", [days]) : "";
}

/* ---------------------------------------------------------------- helpers */

function escape(value) {
	return frappe.utils.escape_html(value || "");
}

function doc_link(route, name) {
	return `<a href="/app/${route}/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`;
}

function period(from_date, to_date) {
	const start = from_date ? frappe.datetime.str_to_user(from_date) : "";
	const end = to_date ? frappe.datetime.str_to_user(to_date) : __("Present");
	return `${start} &rarr; ${end}`;
}

/**
 * Frappe classes carry the look. This only fixes the row height, so a table
 * shows HISTORY_VISIBLE_ROWS rows and a sticky header, then scrolls.
 */
function accommodation_styles() {
	return `
		<style>
			.acc-history { margin-top: var(--margin-md, 12px); }
			.acc-scroll {
				--acc-row: 32px;
				max-height: calc(var(--acc-row) * ${HISTORY_VISIBLE_ROWS + 1} + 2px);
				overflow: auto;
				border: 1px solid var(--table-border-color, var(--border-color));
				border-radius: var(--border-radius, 6px);
			}
			.acc-table { margin: 0; border: 0; border-collapse: separate; border-spacing: 0; }
			.acc-table th, .acc-table td {
				height: var(--acc-row);
				padding: 0 var(--padding-sm, 8px);
				border-width: 0 0 1px 0;
				white-space: nowrap;
				vertical-align: middle;
				font-size: var(--text-sm, 12px);
			}
			.acc-table tbody tr:last-child td { border-bottom: 0; }
			.acc-table thead th {
				position: sticky;
				top: 0;
				z-index: 1;
				background: var(--subtle-fg, var(--control-bg));
				color: var(--text-muted);
				font-weight: var(--weight-medium, 500);
			}
		</style>`;
}

// Places open to the employee's gender. An employee with no gender sees Any places only.
function gender_restriction_filter(gender) {
	return gender ? ["in", ["Any", gender]] : "Any";
}
