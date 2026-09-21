// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

const STAY_STATUS_COLORS = { "Awaiting Bed": "orange", Allocated: "green", Vacated: "gray" };
const ENTITLEMENT_COLORS = { "Company Accommodation": "green", Allowance: "blue", "Not Provided": "gray" };

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		render_accommodation_tab(frm);
	},
});

function render_accommodation_tab(frm) {
	const actions = frm.get_field("accommodation_actions_html");
	const history = frm.get_field("accommodation_history_html");
	if (!actions && !history) {
		return;
	}

	frappe.call({
		method: "gd_acc.gd_accomodation.doctype.accommodation_entitlement.accommodation_entitlement.get_employee_entitlement_state",
		args: { employee: frm.doc.name },
		callback(response) {
			const state = response.message || {};
			if (actions) {
				actions.$wrapper.html(build_actions(state));
				wire_actions(frm, actions.$wrapper, state);
			}
			if (history) {
				history.$wrapper.html(build_history(state));
			}
		},
	});
}

/* ---------------------------------------------------------------- actions */

/**
 * The summary shows the current entitlement and the current stay. The buttons
 * depend on whether the employee currently occupies a bed - not on whether an
 * Entitlement document happens to exist.
 */
function build_actions(state) {
	const has_bed = !!state.active_allocation;
	const entitlement = state.entitlement;
	const current_stay = has_bed
		? (state.allocations || []).find((row) => row.name === state.active_allocation)
		: null;

	const pending = current_stay && current_stay.status === "Pending Release";
	const stay_line = current_stay ? build_stay_line(current_stay) + pending_release_line(current_stay) : "";

	let summary;
	if (entitlement) {
		const color = pending ? "orange" : ENTITLEMENT_COLORS[entitlement.entitlement_type] || "gray";
		summary = `
			<div class="acc-banner ${color}">
				<div class="acc-banner-title">${__(entitlement.entitlement_type)} ${stay_pill(entitlement)}</div>
				<div class="acc-banner-sub">${period(entitlement.from_date, entitlement.to_date)}</div>
				${allowance_line(entitlement)}
				${stay_line}
			</div>`;
	} else if (has_bed) {
		summary = `
			<div class="acc-banner ${pending ? "orange" : "green"}">
				<div class="acc-banner-title">${__("Company Accommodation")}</div>
				${stay_line}
				<div class="acc-banner-sub">${__("No entitlement recorded")}</div>
			</div>`;
	} else {
		summary = `
			<div class="acc-banner gray">
				<div class="acc-banner-title">${__("Not Provided")}</div>
				<div class="acc-banner-sub">${__(
					"Neither company accommodation nor an accommodation allowance is provided."
				)}</div>
			</div>`;
	}

	let buttons;
	if (has_bed) {
		buttons = [
			`<button class="btn btn-primary btn-sm" data-action="release">${__("Release Accommodation")}</button>`,
			`<button class="btn btn-default btn-sm" data-action="transfer">${__("Transfer")}</button>`,
			`<button class="btn btn-default btn-sm" data-action="view">${__("View Allocation")}</button>`,
		];
	} else if (entitlement && entitlement.entitlement_type === "Allowance") {
		buttons = [
			`<button class="btn btn-primary btn-sm" data-action="entitlement" data-prefill="Company Accommodation">${__(
				"Switch to Company Accommodation"
			)}</button>`,
		];
	} else {
		buttons = [
			`<button class="btn btn-primary btn-sm" data-action="entitlement">${__("Create Entitlement")}</button>`,
		];
	}

	return `${accommodation_styles()}${summary}<div class="acc-actions">${buttons.join("")}</div>`;
}

function build_stay_line(stay) {
	const place = [stay.location, stay.site, stay.floor, stay.room, stay.bed]
		.filter(Boolean)
		.map((value) => frappe.utils.escape_html(value))
		.join(" <span class='acc-sep'>&rsaquo;</span> ");
	const since = __("Since {0}", [frappe.datetime.str_to_user(stay.start_date)]);
	return `<div class="acc-banner-sub">${place}${place ? " &middot; " : ""}${since}</div>`;
}

function pending_release_line(stay) {
	if (stay.status !== "Pending Release") {
		return "";
	}
	return `<div class="acc-banner-sub">${__("Pending Release on {0} ({1})", [
		frappe.datetime.str_to_user(stay.proposed_release_date),
		__(stay.pending_release_reason || ""),
	])}</div>`;
}

function stay_pill(entitlement) {
	if (entitlement.entitlement_type !== "Company Accommodation" || !entitlement.stay_status) {
		return "";
	}
	return `<span class="indicator-pill ${STAY_STATUS_COLORS[entitlement.stay_status] || "gray"}">${__(
		entitlement.stay_status
	)}</span>`;
}

function allowance_line(entitlement) {
	if (entitlement.entitlement_type !== "Allowance") {
		return "";
	}
	const parts = [
		entitlement.allowance_amount
			? format_currency(entitlement.allowance_amount, entitlement.allowance_currency)
			: __("Amount not set"),
		entitlement.allowance_frequency ? __(entitlement.allowance_frequency) : "",
		entitlement.allowance_component ? frappe.utils.escape_html(entitlement.allowance_component) : "",
	].filter(Boolean);
	return `<div class="acc-banner-sub">${parts.join(" &middot; ")}</div>`;
}

function wire_actions(frm, $wrapper, state) {
	$wrapper.find("[data-action]").on("click", function () {
		const action = $(this).attr("data-action");

		if (action === "entitlement") {
			open_entitlement_dialog(frm, { prefill_type: $(this).attr("data-prefill") });
		} else if (action === "transfer") {
			frappe.new_doc("Accommodation Transfer", {
				employee: frm.doc.name,
				current_allocation: state.active_allocation,
				transfer_date: frappe.datetime.get_today(),
			});
		} else if (action === "view") {
			frappe.set_route("Form", "Accommodation Allocation", state.active_allocation);
		} else if (action === "release") {
			// The allocation form opens its release dialog, with the item returns, on arrival.
			frappe.flags.gd_acc_open_release = state.active_allocation;
			frappe.set_route("Form", "Accommodation Allocation", state.active_allocation);
		}
	});
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
			},
			callback(response) {
				const details = response.message || {};
				if (details.component && !dialog.get_value("allowance_component")) {
					dialog.set_value("allowance_component", details.component);
				}
				if (details.amount) {
					dialog.set_value("allowance_amount", details.amount);
				}
				if (details.currency && !dialog.get_value("allowance_currency")) {
					dialog.set_value("allowance_currency", details.currency);
				}
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
				fieldname: "allowance_amount",
				fieldtype: "Currency",
				label: __("Allowance Amount"),
				options: "allowance_currency",
				description: __("Filled in from payroll automatically. Override only if it differs."),
			},
			{ fieldname: "allowance_currency", fieldtype: "Link", options: "Currency", label: __("Currency") },
			{ fieldname: "allowance_column", fieldtype: "Column Break" },
			{
				fieldname: "allowance_frequency",
				fieldtype: "Select",
				label: __("Frequency"),
				options: "Monthly\nQuarterly\nAnnual\nOne Time",
				default: "Monthly",
			},
			{
				fieldname: "allowance_component",
				fieldtype: "Link",
				options: "Salary Component",
				label: __("Salary Component"),
				onchange: maybe_fetch_allowance,
			},
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
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
		return `<div class="text-muted">${__("No accommodation history yet.")}</div>`;
	}

	return `
		${accommodation_styles()}
		${entitlement_table(entitlements)}
		${allocation_table(allocations)}`;
}

function entitlement_table(rows) {
	if (!rows.length) {
		return "";
	}

	const body = rows
		.map(
			(row) => `
		<tr>
			<td>${doc_link("accommodation-entitlement", row.name)}</td>
			<td>${frappe.utils.escape_html(row.entitlement_type || "")}</td>
			<td>${period(row.from_date, row.to_date)}</td>
			<td class="text-right">${
				row.allowance_amount
					? format_currency(row.allowance_amount, row.allowance_currency)
					: "&mdash;"
			}</td>
			<td>${pill(row.status)}</td>
		</tr>`
		)
		.join("");

	return `
		<div class="acc-history-title">${__("Entitlement History")}<span>${__("{0} rows", [
			rows.length,
		])}</span></div>
		<div class="acc-scroll">
			<table class="table table-bordered table-sm">
				<thead>
					<tr>
						<th style="width: 18%">${__("Entitlement")}</th>
						<th style="width: 22%">${__("Type")}</th>
						<th style="width: 26%">${__("Period")}</th>
						<th class="text-right" style="width: 18%">${__("Allowance")}</th>
						<th style="width: 16%">${__("Status")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</div>`;
}

/** Stays read as a journey down the page, so they are drawn as a timeline. */
function allocation_table(rows) {
	if (!rows.length) {
		return "";
	}

	const colors = {
		Active: "green",
		"Pending Release": "orange",
		Closed: "gray",
		Draft: "orange",
		Cancelled: "red",
	};

	const entries = rows
		.map((row) => {
			const color = colors[row.status] || "gray";
			const current = ["Active", "Pending Release"].includes(row.status);
			const place = [row.location, row.site, row.floor, row.room, row.bed]
				.filter(Boolean)
				.map((value) => frappe.utils.escape_html(value))
				.join(" <span class='acc-sep'>&rsaquo;</span> ");

			const days = stay_length(row.start_date, row.release_date);
			const meta = [
				row.bed_type ? `<span class="acc-tag">${frappe.utils.escape_html(row.bed_type)}</span>` : "",
				row.release_reason
					? `<span class="acc-tag">${frappe.utils.escape_html(row.release_reason)}</span>`
					: "",
				doc_link("accommodation-allocation", row.name),
			]
				.filter(Boolean)
				.join(" ");

			return `
			<div class="acc-step ${current ? "is-current" : ""}">
				<span class="acc-dot ${color}"></span>
				<div class="acc-step-body">
					<div class="acc-step-head">
						<span class="indicator-pill ${color}">${
							current ? __("Current") : frappe.utils.escape_html(row.status || "")
						}</span>
						<span class="acc-step-days">${days}</span>
					</div>
					<div class="acc-step-place">${place}</div>
					<div class="acc-step-meta">
						${period(row.start_date, row.release_date)} &middot; ${meta}
					</div>
				</div>
			</div>`;
		})
		.join("");

	return `
		<div class="acc-history-title">${__("Accommodation History")}<span>${__("{0} stays", [
			rows.length,
		])}</span></div>
		<div class="acc-scroll acc-timeline">${entries}</div>`;
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

function doc_link(route, name) {
	return `<a href="/app/${route}/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`;
}

function period(from_date, to_date) {
	const start = from_date ? frappe.datetime.str_to_user(from_date) : "";
	const end = to_date ? frappe.datetime.str_to_user(to_date) : __("Present");
	return `${start} &rarr; ${end}`;
}

function pill(status) {
	const colors = {
		Active: "green",
		"Pending Release": "orange",
		Closed: "gray",
		Draft: "orange",
		Cancelled: "red",
	};
	return `<span class="indicator-pill ${colors[status] || "gray"}">${frappe.utils.escape_html(
		status || ""
	)}</span>`;
}

function accommodation_styles() {
	if (accommodation_styles.done) {
		return "";
	}
	accommodation_styles.done = true;

	return `
		<style>
			.acc-banner {
				border-left: 3px solid var(--gray-400);
				background: var(--subtle-fg, var(--control-bg));
				border-radius: var(--border-radius-md, 8px);
				padding: 10px 14px;
				margin-bottom: 10px;
			}
			.acc-banner.green { border-left-color: var(--green-500); }
			.acc-banner.blue { border-left-color: var(--blue-500); }
			.acc-banner.gray { border-left-color: var(--gray-400); }
			.acc-banner.orange { border-left-color: var(--orange-500); }
			.acc-banner-title { font-weight: 600; color: var(--text-color); }
			.acc-banner-sub { font-size: var(--text-sm, 12px); color: var(--text-muted); margin-top: 2px; }
			.acc-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
			.acc-history-title {
				font-weight: 600;
				color: var(--text-color);
				margin: 16px 0 8px;
				display: flex;
				align-items: baseline;
				gap: 8px;
			}
			.acc-history-title span { font-weight: normal; font-size: var(--text-sm, 12px); color: var(--text-muted); }
			.acc-scroll {
				max-height: 232px;
				overflow-y: auto;
				border: 1px solid var(--border-color);
				border-radius: var(--border-radius-md, 8px);
			}
			.acc-scroll table { margin-bottom: 0; border: none; }
			.acc-scroll thead th { position: sticky; top: 0; z-index: 1; background: var(--subtle-fg, var(--control-bg)); }
			.acc-sep { color: var(--text-muted); }
			.acc-tag {
				font-size: 11px;
				padding: 1px 6px;
				border-radius: 8px;
				background: var(--control-bg);
				color: var(--text-muted);
			}
			.acc-timeline { padding: 4px 0 4px 6px; max-height: 330px; }
			.acc-step { display: flex; gap: 12px; padding: 10px 14px 10px 8px; position: relative; }
			.acc-step::before {
				content: "";
				position: absolute;
				left: 13px;
				top: 26px;
				bottom: -10px;
				width: 2px;
				background: var(--border-color);
			}
			.acc-step:last-child::before { display: none; }
			.acc-step.is-current { background: var(--alert-bg-green, var(--control-bg)); border-radius: 6px; }
			.acc-dot {
				width: 11px;
				height: 11px;
				border-radius: 50%;
				margin-top: 5px;
				flex: 0 0 auto;
				z-index: 1;
				box-shadow: 0 0 0 3px var(--card-bg, #fff);
			}
			.acc-dot.green { background: var(--green-500); }
			.acc-dot.gray { background: var(--gray-400); }
			.acc-dot.orange { background: var(--orange-500); }
			.acc-dot.red { background: var(--red-500); }
			.acc-step-body { flex: 1 1 auto; min-width: 0; }
			.acc-step-head { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
			.acc-step-days { font-size: var(--text-sm, 12px); color: var(--text-muted); }
			.acc-step-place { font-weight: 600; color: var(--text-color); word-break: break-word; }
			.acc-step-meta { font-size: var(--text-sm, 12px); color: var(--text-muted); margin-top: 2px; }
		</style>`;
}

// Places open to the employee's gender. An employee with no gender sees Any places only.
function gender_restriction_filter(gender) {
	return gender ? ["in", ["Any", gender]] : "Any";
}
