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
			panel.$wrapper.html(
				`${accommodation_styles()}${build_stay(state)}${build_summary(state)}${build_history(state)}`
			);
			bind_panel_actions(frm, panel.$wrapper, state);
			add_accommodation_buttons(frm, state);
		},
	});
}

function current_stay(state) {
	return state.active_allocation
		? (state.allocations || []).find((row) => row.name === state.active_allocation)
		: null;
}

/** Entitled to company accommodation, but no bed today. */
function is_awaiting_bed(state) {
	const entitlement = state.entitlement;
	return Boolean(
		!current_stay(state) && entitlement && entitlement.entitlement_type === "Company Accommodation"
	);
}

/* ---------------------------------------------------------------- stay card */

/** The card at the top of the tab: the current stay, the wait for a bed, or the allowance. */
function build_stay(state) {
	const stay = current_stay(state);
	const entitlement = state.entitlement;

	if (stay) {
		return section(
			__("Current Stay"),
			__("Where the employee sleeps today"),
			allocated_card(state, stay)
		);
	}
	if (is_awaiting_bed(state)) {
		return section(__("Current Stay"), __("No bed allocated yet"), awaiting_card(state, entitlement));
	}
	if (entitlement && entitlement.entitlement_type === "Allowance") {
		return section(
			__("Accommodation Allowance"),
			__("Paid through payroll"),
			allowance_card(entitlement)
		);
	}
	return "";
}

function allocated_card(state, stay) {
	const place = state.place || {};
	const room = state.room || {};

	return stay_card({
		icon: "bed",
		title: join_parts(
			[
				place.site,
				place.floor,
				place.room && __("Room {0}", [place.room]),
				place.bed && __("Bed {0}", [place.bed]),
			],
			" &rsaquo; "
		),
		subtitle: join_parts([
			place.location,
			room.room_type && __("{0} room", [__(room.room_type)]),
			room.total_beds && __("{0} of {1} beds occupied", [room.occupied_beds || 0, room.total_beds]),
		]),
		pill: gd_acc.accommodation.status_pill("Accommodation Allocation", "status", stay.status),
		meta: since(stay.start_date),
		cells: [
			[__("Allocation"), doc_link("Accommodation Allocation", stay.name)],
			[__("Expected End Date"), user_date(stay.expected_end_date)],
			[__("Items Issued"), items_issued(stay)],
		],
		footer: stay.status === "Pending Release" ? pending_release_notice(stay) : "",
	});
}

function awaiting_card(state, entitlement) {
	const last = (state.allocations || [])[0];
	const place = (last && last.place) || {};
	const waiting_since =
		entitlement.stay_status === "Vacated" && last && last.release_date
			? last.release_date
			: entitlement.from_date;

	return (
		stay_card({
			icon: "bed",
			tone: "orange",
			title: escape(__("Company Accommodation")),
			subtitle: escape(__("Entitled from {0}", [user_date(entitlement.from_date)])),
			pill: gd_acc.accommodation.status_pill(
				"Accommodation Entitlement",
				"stay_status",
				entitlement.stay_status
			),
			meta: waiting_since
				? `${escape(__("Waiting since {0}", [user_date(waiting_since)]))} &middot; ${stay_length(
						waiting_since
				  )}`
				: "",
			cells: [
				[__("Entitlement"), doc_link("Accommodation Entitlement", entitlement.name)],
				[__("Effective From"), user_date(entitlement.from_date)],
				[
					__("Last Stay"),
					join_parts([place.site, place.room && __("Room {0}", [place.room])], " &rsaquo; "),
				],
				[__("Assign Bed"), escape(__("Accommodation > Create Entitlement"))],
			],
		})
	);
}

function allowance_card(entitlement) {
	const frequency = __(entitlement.allowance_frequency || "Monthly");
	const amount = entitlement.allowance_amount
		? format_currency(entitlement.allowance_amount, entitlement.allowance_currency)
		: "";

	return stay_card({
		icon: "wallet",
		title: amount ? `${amount} &middot; ${escape(frequency)}` : escape(frequency),
		subtitle: `${escape(__("Accommodation Allowance"))} &middot; ${period(
			entitlement.from_date,
			entitlement.to_date
		)}`,
		pill: gd_acc.accommodation.status_pill("Accommodation Entitlement", "status", entitlement.status),
		meta: since(entitlement.from_date),
		cells: [
			[__("Salary Component"), escape(entitlement.allowance_component)],
			[
				__("Salary Structure Assignment"),
				doc_link("Salary Structure Assignment", entitlement.salary_structure_assignment),
			],
			[__("Salary Structure"), doc_link("Salary Structure", entitlement.salary_structure)],
			[__("Entitlement"), doc_link("Accommodation Entitlement", entitlement.name)],
		],
		footer: frappe.model.can_create("Accommodation Entitlement")
			? action_bar(action_button("switch", __("Switch to Company Accommodation")))
			: "",
	});
}

/** The one card layout every state uses: a headline row, then a strip of cells across the card. */
function stay_card({ icon, tone, title, subtitle, pill, meta, cells, footer }) {
	const strip = cells
		.map(
			([label, value]) => `
			<div class="col-sm-${Math.floor(12 / cells.length)} acc-cell">
				<div class="control-label">${label}</div>
				<div class="acc-cell-value">${value || ""}</div>
			</div>`
		)
		.join("");

	return `
		<div class="acc-card">
			<div class="acc-card-head">
				<div class="acc-card-icon ${tone || ""}">${frappe.utils.icon(icon, "md")}</div>
				<div class="acc-card-body">
					<div class="acc-card-title">${title || ""}</div>
					<div class="text-muted small">${subtitle || ""}</div>
				</div>
				<div class="acc-card-side">
					${pill || ""}
					<div class="text-muted small">${meta || ""}</div>
				</div>
			</div>
			<div class="row no-gutters acc-strip">${strip}</div>
			${footer || ""}
		</div>`;
}

/** Items handed out for this stay, with the returnable ones still out. */
function items_issued(stay) {
	if (!stay.total_items) {
		return "";
	}
	if (!stay.outstanding_items) {
		return String(stay.total_items);
	}
	const color = gd_acc.accommodation.status_color(
		"Accommodation Item Entry",
		"items_status",
		"Outstanding"
	);
	return `${stay.total_items} <span class="indicator-pill ${color}">${escape(
		__("{0} Outstanding", [stay.outstanding_items])
	)}</span>`;
}

function pending_release_notice(stay) {
	const details = join_parts([
		stay.proposed_release_date && __("Release on {0}", [user_date(stay.proposed_release_date)]),
		stay.pending_release_reason && __(stay.pending_release_reason),
		stay.outstanding_items && __("{0} items outstanding", [stay.outstanding_items]),
	]);

	return `
		<div class="acc-notice">
			<div><strong>${escape(__("Pending Release"))}</strong> &middot; ${details}</div>
			${can_release() ? action_button("release", __("Release Accommodation")) : ""}
		</div>`;
}

function action_bar(buttons) {
	return `<div class="acc-actions">${buttons}</div>`;
}

function action_button(action, label, style = "btn-default") {
	return `<button type="button" class="btn btn-xs ${style}" data-acc-action="${action}">${escape(
		label
	)}</button>`;
}

/** Buttons inside the panel reuse the same actions as the Accommodation menu. */
function bind_panel_actions(frm, $wrapper, state) {
	$wrapper.off("click.gd_acc").on("click.gd_acc", "[data-acc-action]", (event) => {
		event.preventDefault();
		const action = $(event.currentTarget).attr("data-acc-action");

		if (action === "release") {
			open_release(state.active_allocation);
		} else if (action === "switch") {
			open_entitlement_dialog(frm, { prefill_type: "Company Accommodation" });
		}
	});
}

function open_release(allocation) {
	// The allocation form opens its release dialog, with the item returns, on arrival.
	frappe.flags.gd_acc_open_release = allocation;
	frappe.set_route("Form", "Accommodation Allocation", allocation);
}

/* ---------------------------------------------------------------- entitlement */

/** The current entitlement, as label and value pairs in two columns. */
function build_summary(state) {
	const entitlement = state.entitlement;

	const rows = [];
	if (entitlement) {
		rows.push([
			__("Entitlement"),
			`${escape(__(entitlement.entitlement_type))} ${gd_acc.accommodation.status_pill(
				"Accommodation Entitlement",
				"status",
				entitlement.status
			)}`,
		]);
		rows.push([__("Effective"), period(entitlement.from_date, entitlement.to_date)]);
		rows.push([__("Entitlement ID"), doc_link("Accommodation Entitlement", entitlement.name)]);
		rows.push([__("Remarks"), escape(entitlement.remarks)]);
	} else {
		rows.push([
			__("Entitlement"),
			current_stay(state) ? __("No entitlement recorded") : __("Not Provided"),
		]);
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
	return section(__("Entitlement"), "", `<div class="row">${cells}</div>`);
}

function section(title, subtitle, body) {
	return `
		<div class="acc-section">
			<div class="acc-section-head">
				<span class="acc-section-title">${escape(title)}</span>
				${subtitle ? `<span class="text-muted small">${escape(subtitle)}</span>` : ""}
			</div>
			${body}
		</div>`;
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
	const can_entitle = frappe.model.can_create("Accommodation Entitlement");

	// Each button needs the role that can finish its action, so an employee on self service sees none.
	if (allocation) {
		if (can_release()) {
			frm.add_custom_button(__("Release Accommodation"), () => open_release(allocation), group);
		}
		if (frappe.model.can_create("Accommodation Transfer")) {
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
		}
		if (frappe.model.can_read("Accommodation Allocation")) {
			frm.add_custom_button(
				__("View Allocation"),
				() => frappe.set_route("Form", "Accommodation Allocation", allocation),
				group
			);
		}
	} else if (!can_entitle) {
		return;
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

// The boot list works on any form; has_perm needs the Allocation meta, which the Employee form never loads.
function can_release() {
	return frappe.model.can_submit("Accommodation Allocation");
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
			description: frm.doc.gender
				? __("Only sites open to {0} employees are listed.", [__(frm.doc.gender)])
				: __("Only sites open to Any gender are listed. Set the employee's Gender to see more."),
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
			// Only floors with a free bed.
			get_query: () => ({
				filters: { site: dialog.get_value("site"), status: "Active", available_beds: [">", 0] },
			}),
			onchange: () => dialog.set_values({ room: null, bed: null }),
		},
		{
			fieldname: "room",
			fieldtype: "Link",
			options: "Accommodation Room",
			label: __("Room"),
			// Only rooms with a free bed. A Full, Blocked or Under Maintenance room is left out.
			get_query: () => ({
				filters: {
					floor: dialog.get_value("floor"),
					status: "Active",
					occupancy_status: "Available",
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
		{
			fieldname: "items_section",
			fieldtype: "Section Break",
			label: __("Items Issued"),
			description: __("Issued with the bed when you save."),
			depends_on: 'eval:doc.entitlement_type=="Company Accommodation"',
		},
		{
			fieldname: "items",
			fieldtype: "Table",
			label: __("Items"),
			in_place_edit: true,
			data: [],
			fields: [
				{
					fieldname: "accommodation_item",
					fieldtype: "Link",
					options: "Accommodation Item",
					label: __("Item"),
					in_list_view: 1,
					reqd: 1,
					get_query: () => ({ filters: { disabled: 0 } }),
				},
				{ fieldname: "quantity", fieldtype: "Int", label: __("Qty"), in_list_view: 1, reqd: 1, default: 1 },
				{
					fieldname: "condition",
					fieldtype: "Select",
					label: __("Condition"),
					options: ["New", "Good", "Fair", "Damaged"].join("\n"),
					default: "New",
					in_list_view: 1,
				},
			],
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
	// Self service shows the current entitlement only; its card and summary say it all.
	if (state.self_service) {
		return "";
	}

	const entitlements = state.entitlements || [];
	const allocations = state.allocations || [];
	const items = state.items || [];

	if (!entitlements.length && !allocations.length && !items.length) {
		return `<div class="text-muted small acc-history">${__("No accommodation history yet.")}</div>`;
	}

	return `
		${items_table(items)}
		${allocation_table(allocations)}
		${entitlement_table(entitlements)}`;
}

function items_table(rows) {
	return history_table(__("Items Issued"), rows, [
		[__("Item"), (row) => escape(row.accommodation_item)],
		[__("Category"), (row) => escape(__(row.item_category || ""))],
		[__("Qty"), (row) => escape(row.quantity), "text-right"],
		[__("Condition"), (row) => escape(__(row.condition || ""))],
		[__("Assigned On"), (row) => doc_link("Accommodation Item Entry", row.item_entry)],
	]);
}

function entitlement_table(rows) {
	return history_table(__("Entitlement History"), rows, [
		[__("Entitlement"), (row) => doc_link("Accommodation Entitlement", row.name)],
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
		[__("Allocation"), (row) => doc_link("Accommodation Allocation", row.name)],
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
	return frappe.utils.escape_html(value === 0 ? "0" : String(value || ""));
}

/** A link to the document, or its plain name when the viewer may not open it. */
function doc_link(doctype, name) {
	if (!name) {
		return "";
	}
	if (!frappe.model.can_read(doctype)) {
		return frappe.utils.escape_html(name);
	}
	return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(
		name
	)}">${frappe.utils.escape_html(name)}</a>`;
}

function user_date(value) {
	return value ? frappe.datetime.str_to_user(value) : "";
}

/** "Since 04-03-2026 · 208 days". */
function since(start_date) {
	if (!start_date) {
		return "";
	}
	return `${escape(__("Since {0}", [user_date(start_date)]))} &middot; ${stay_length(start_date)}`;
}

/** Escapes each non-empty part and joins them, for example "Dubai · Shared room". */
function join_parts(parts, separator = " &middot; ") {
	return parts
		.filter(Boolean)
		.map((part) => escape(part))
		.join(separator);
}

function period(from_date, to_date) {
	const start = from_date ? frappe.datetime.str_to_user(from_date) : "";
	const end = to_date ? frappe.datetime.str_to_user(to_date) : __("Present");
	return `${start} &rarr; ${end}`;
}

/**
 * Frappe classes carry the look. This fixes the row height, so a table shows
 * HISTORY_VISIBLE_ROWS rows and a sticky header, then scrolls, and lays out the
 * stay card with Frappe variables only.
 */
function accommodation_styles() {
	return `
		<style>
			.acc-section { margin-bottom: var(--margin-lg, 20px); }
			.acc-section-head {
				display: flex;
				align-items: baseline;
				gap: var(--margin-sm, 8px);
				margin-bottom: var(--margin-sm, 8px);
			}
			.acc-section-title { font-weight: var(--weight-semibold, 600); color: var(--heading-color); }
			.acc-card {
				background: var(--card-bg);
				border: 1px solid var(--border-color);
				border-radius: var(--border-radius-lg);
				overflow: hidden;
			}
			.acc-card-head {
				display: flex;
				align-items: center;
				gap: var(--padding-md, 12px);
				padding: var(--padding-md, 12px) var(--padding-lg, 16px);
			}
			.acc-card-icon {
				flex: none;
				display: flex;
				align-items: center;
				justify-content: center;
				width: 40px;
				height: 40px;
				border-radius: var(--border-radius-md, 8px);
				background: var(--bg-blue);
				color: var(--text-on-blue);
			}
			.acc-card-icon.orange { background: var(--bg-orange); color: var(--text-on-orange); }
			.acc-card-icon .icon { --icon-stroke: currentColor; stroke: currentColor; }
			.acc-card-body { flex: 1; min-width: 0; }
			.acc-card-title {
				font-size: var(--text-lg, 16px);
				font-weight: var(--weight-semibold, 600);
				color: var(--heading-color);
				white-space: nowrap;
				overflow: hidden;
				text-overflow: ellipsis;
			}
			.acc-card-side { flex: none; text-align: right; }
			.acc-card-side .text-muted { margin-top: 4px; }
			.acc-strip { border-top: 1px solid var(--border-color); }
			.acc-strip > .acc-cell { padding: var(--padding-sm, 8px) var(--padding-lg, 16px); border-left: 1px solid var(--border-color); }
			.acc-strip > .acc-cell:first-child { border-left: 0; }
			.acc-cell .control-label { margin-bottom: 2px; }
			.acc-cell-value { color: var(--text-color); min-height: 20px; overflow-wrap: anywhere; }
			.acc-notice, .acc-actions {
				display: flex;
				align-items: center;
				justify-content: space-between;
				gap: var(--padding-md, 12px);
				padding: var(--padding-sm, 8px) var(--padding-lg, 16px);
				border-top: 1px solid var(--border-color);
			}
			.acc-notice { background: var(--alert-bg-warning); color: var(--alert-text-warning); }
			.acc-actions { justify-content: flex-end; }
			@media (max-width: 767px) {
				.acc-card-head { flex-wrap: wrap; }
				.acc-card-side { flex-basis: 100%; text-align: left; }
				.acc-strip > .acc-cell { border-left: 0; border-top: 1px solid var(--border-color); }
				.acc-strip > .acc-cell:first-child { border-top: 0; }
				.acc-notice { flex-wrap: wrap; }
			}
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
