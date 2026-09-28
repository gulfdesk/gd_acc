// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

// Bed statuses in the order the charts and table show them.
const BED_STATUS_ORDER = ["Occupied", "Available", "Reserved", "Maintenance", "Blocked", "Inactive"];

const CHART_HEIGHT = 260;

// Frappe Charts redraws when its box resizes, for example when the page scrollbar
// appears. During an animation its chart is swapped out, and that redraw then fails.
const CHART_MOTION = { animate: 0, disableEntryAnimation: 1 };

/** "1 site" or "3 sites". */
function count_label(count, one, many) {
	return count === 1 ? one : many.replace("{0}", count || 0);
}

frappe.pages["accommodation-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Accommodation Dashboard"),
		single_column: true,
	});

	const dashboard = new AccommodationDashboard(page);
	dashboard.refresh();
};

class AccommodationDashboard {
	constructor(page) {
		this.page = page;
		this.cards = [];
		this.charts = [];
		this.request = 0;

		this.location_field = this.page.add_field({
			fieldname: "location",
			fieldtype: "Link",
			label: __("Location"),
			options: "Accommodation Location",
			change: () => this.refresh(),
		});

		this.page.set_secondary_action(__("Refresh"), () => this.refresh());

		this.$container = $('<div class="accommodation-dashboard"></div>').appendTo(this.page.main);

		this.$container.on("click", "[data-card-index]", (event) => {
			const card = this.cards[$(event.currentTarget).attr("data-card-index")];
			if (card && card.route && card.route.view === "Report") {
				// A Report Builder report opens by name and keeps its own saved filters.
				frappe.set_route("List", card.route.doctype, "Report", card.route.filters);
			} else if (card && card.route) {
				frappe.set_route(card.route.view, card.route.doctype, card.route.filters || {});
			}
		});
	}

	get location() {
		return this.location_field.get_value() || null;
	}

	get scope() {
		return this.location ? { location: this.location } : {};
	}

	refresh() {
		// Only the latest request renders, so a quick filter change never draws twice.
		const request = ++this.request;
		frappe.call({
			method: "gd_acc.gd_accomodation.api.get_dashboard_data",
			args: { location: this.location },
			callback: (response) => request === this.request && this.render(response.message || {}),
		});
	}

	render(data) {
		const kpi = data.kpi || {};
		const scope = this.scope;
		const by_site = data.by_site || [];
		this.cards = [];
		this.charts.forEach((chart) => chart.destroy && chart.destroy());
		this.charts = [];

		const headline = [
			this.card({
				title: __("Total Beds"),
				value: kpi.beds,
				note: [
					count_label(kpi.locations, __("1 location"), __("{0} locations")),
					count_label(kpi.sites, __("1 site"), __("{0} sites")),
					count_label(kpi.rooms, __("1 room"), __("{0} rooms")),
				].join(" · "),
				doctype: "Accommodation Bed",
				filters: scope,
			}),
			this.card({
				title: __("Occupancy"),
				value: `${flt(kpi.occupancy_percent || 0, 1)}%`,
				note: __("{0} of {1} beds occupied", [kpi.occupied || 0, kpi.beds || 0]),
				status: "Occupied",
				doctype: "Accommodation Bed",
				filters: { ...scope, status: "Occupied" },
			}),
			this.card({
				title: __("Available Beds"),
				value: kpi.available,
				note: __("Ready to allocate"),
				status: "Available",
				doctype: "Accommodation Bed",
				filters: { ...scope, status: "Available" },
			}),
			this.card({
				title: __("Out of Service"),
				value: (kpi.maintenance || 0) + (kpi.blocked || 0),
				note: __("{0} under maintenance · {1} blocked", [kpi.maintenance || 0, kpi.blocked || 0]),
				status: "Maintenance",
				doctype: "Accommodation Bed",
				filters: { ...scope, status: ["in", ["Maintenance", "Blocked"]] },
			}),
		];

		const people = [
			this.card({
				title: __("Housed"),
				value: kpi.housed,
				note: __("Sleeping in a bed today"),
				color: gd_acc.accommodation.status_color("Accommodation Entitlement", "stay_status", "Allocated"),
				doctype: "Accommodation Allocation",
				filters: { ...scope, docstatus: 1, status: ["in", ["Active", "Pending Release"]] },
			}),
			this.card({
				title: __("Unhoused"),
				value: kpi.awaiting_bed,
				note: __("Entitled, waiting for a bed"),
				color: gd_acc.accommodation.status_color("Accommodation Entitlement", "stay_status", "Awaiting Bed"),
				doctype: "Accommodation Entitlement",
				filters: "Unhoused Employees",
				view: "Report",
			}),
			this.card({
				title: __("Pending Release"),
				value: kpi.pending_release,
				note: __("Leaving soon"),
				color: gd_acc.accommodation.status_color("Accommodation Allocation", "status", "Pending Release"),
				doctype: "Accommodation Allocation",
				filters: { ...scope, docstatus: 1, status: "Pending Release" },
			}),
			this.card({
				title: __("Company Accommodation"),
				value: kpi.employees_provided,
				note: __("Entitled employees"),
				color: gd_acc.accommodation.status_color("Employee", "accommodation_status", "Provided"),
				doctype: "Accommodation Entitlement",
				filters: { status: "Active", entitlement_type: "Company Accommodation" },
			}),
			this.card({
				title: __("Allowance"),
				value: kpi.employees_allowance,
				note: __("Paid through payroll"),
				color: gd_acc.accommodation.status_color("Employee", "accommodation_status", "Allowance"),
				doctype: "Accommodation Entitlement",
				filters: { status: "Active", entitlement_type: "Allowance" },
			}),
			this.card({
				title: __("Not Provided"),
				value: kpi.employees_not_provided,
				note: __("No accommodation"),
				color: gd_acc.accommodation.status_color("Employee", "accommodation_status", "Not Provided"),
				doctype: "Employee Accommodation",
				filters: { accommodation_status: "Not Provided" },
				view: "query-report",
			}),
		];

		this.$container.html(`
			${this.styles()}

			<div class="acc-grid acc-grid-4">${headline.join("")}</div>

			<div class="acc-grid acc-grid-charts">
				${this.chart_box("acc-status-chart", __("Beds by Status"), __("Every bed, by its current status"))}
				${this.chart_box("acc-site-chart", __("Occupancy by Site"), __("Beds per site, by status"))}
			</div>

			${this.section_title(__("Employees"), this.location ? __("All locations") : "")}
			<div class="acc-grid acc-grid-6">${people.join("")}</div>

			${this.site_table(by_site)}
			${this.maintenance_section(data.open_maintenance || [])}
		`);

		this.render_status_chart(kpi);
		this.render_site_chart(by_site);
	}

	/** A Frappe number card. With a doctype it opens that filtered list. */
	card({ title, value, note, status, color, doctype, filters, view = "List" }) {
		const index = this.cards.length;
		this.cards.push({ route: doctype ? { view, doctype, filters } : null });

		const dot_color = color || (status ? gd_acc.accommodation.status_color("Accommodation Bed", "status", status) : "");
		const dot = dot_color ? `<span class="acc-dot" style="background: var(--${dot_color}-500)"></span>` : "";

		return `
			<div class="widget number-widget-box acc-card ${doctype ? "is-clickable" : ""}"
				${doctype ? `data-card-index="${index}"` : ""}>
				<div class="widget-head">
					<div class="widget-label">
						<div class="widget-title">${dot}${frappe.utils.escape_html(title)}</div>
					</div>
				</div>
				<div class="widget-body">
					<div class="widget-content">
						<div class="number">${frappe.utils.escape_html(String(value ?? 0))}</div>
						<div class="acc-card-note text-muted">${frappe.utils.escape_html(note || "")}</div>
					</div>
				</div>
			</div>`;
	}

	chart_box(id, title, subtitle) {
		return `
			<div class="widget dashboard-widget-box acc-chart-box">
				<div class="widget-head">
					<div class="widget-label">
						<div class="widget-title">${frappe.utils.escape_html(title)}</div>
						<div class="widget-subtitle">${frappe.utils.escape_html(subtitle)}</div>
					</div>
				</div>
				<div class="widget-body"><div class="${id}"></div></div>
			</div>`;
	}

	/** Chart colours come from the one status map, read as Frappe CSS variables. */
	chart_color(status) {
		const name = gd_acc.accommodation.status_color("Accommodation Bed", "status", status);
		const value = getComputedStyle(document.documentElement).getPropertyValue(`--${name}-500`).trim();
		return value || name;
	}

	render_status_chart(kpi) {
		const counts = {
			Occupied: kpi.occupied,
			Available: kpi.available,
			Reserved: kpi.reserved,
			Maintenance: kpi.maintenance,
			Blocked: kpi.blocked,
			Inactive: kpi.inactive,
		};
		const statuses = BED_STATUS_ORDER.filter((status) => counts[status]);
		const $target = this.$container.find(".acc-status-chart");

		if (!statuses.length) {
			$target.html(`<div class="text-muted acc-empty">${__("No beds yet.")}</div>`);
			return;
		}

		this.charts.push(new frappe.Chart($target[0], {
			type: "donut",
			height: CHART_HEIGHT,
			...CHART_MOTION,
			data: {
				labels: statuses.map((status) => __(status)),
				datasets: [{ values: statuses.map((status) => counts[status]) }],
			},
			colors: statuses.map((status) => this.chart_color(status)),
		}));
	}

	render_site_chart(rows) {
		const $target = this.$container.find(".acc-site-chart");
		if (!rows.length) {
			$target.html(`<div class="text-muted acc-empty">${__("No sites yet.")}</div>`);
			return;
		}

		const statuses = BED_STATUS_ORDER.filter((status) => rows.some((row) => row[status]));
		this.charts.push(new frappe.Chart($target[0], {
			type: "bar",
			height: CHART_HEIGHT,
			...CHART_MOTION,
			data: {
				labels: rows.map((row) => row.label),
				datasets: statuses.map((status) => ({
					name: __(status),
					values: rows.map((row) => row[status] || 0),
				})),
			},
			colors: statuses.map((status) => this.chart_color(status)),
			barOptions: { stacked: 1, spaceRatio: 0.6 },
			axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
		}));
	}

	section_title(title, hint) {
		return `
			<div class="acc-section-title">
				${frappe.utils.escape_html(title)}
				${hint ? `<span class="acc-section-hint">${frappe.utils.escape_html(hint)}</span>` : ""}
			</div>`;
	}

	/** One row per site. Every bed status has a column, so each row adds up to Beds. */
	site_table(rows) {
		if (!rows.length) {
			return "";
		}

		const statuses = BED_STATUS_ORDER.filter(
			(status) => ["Occupied", "Available", "Maintenance", "Blocked"].includes(status) || rows.some((row) => row[status])
		);
		const head = statuses.map((status) => `<th class="text-right">${__(status)}</th>`).join("");
		const body = rows
			.map(
				(row) => `
			<tr>
				<td><a href="/app/accommodation-site/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(
					row.label
				)}</a></td>
				<td class="text-right">${row.total}</td>
				${statuses.map((status) => `<td class="text-right">${row[status] || 0}</td>`).join("")}
				<td>
					<div class="acc-bar" title="${row.occupancy_percent || 0}%">
						<span style="width: ${Math.min(row.occupancy_percent || 0, 100)}%"></span>
					</div>
				</td>
				<td class="text-right">${flt(row.occupancy_percent || 0, 1)}%</td>
			</tr>`
			)
			.join("");

		return `
			${this.section_title(__("Occupancy by Site"), count_label(rows.length, __("1 site"), __("{0} sites")))}
			<div class="acc-scroll">
				<table class="table table-bordered acc-table">
					<thead>
						<tr>
							<th>${__("Site")}</th>
							<th class="text-right">${__("Beds")}</th>
							${head}
							<th class="acc-bar-col">${__("Occupancy")}</th>
							<th class="text-right">%</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>`;
	}

	maintenance_section(rows) {
		if (!rows.length) {
			return `
				${this.section_title(__("Open Maintenance Requests"))}
				<div class="text-muted acc-empty">${__("No open maintenance requests.")}</div>`;
		}

		const body = rows
			.map(
				(row) => `
			<tr>
				<td><a href="/app/accommodation-maintenance/${encodeURIComponent(
					row.name
				)}">${frappe.utils.escape_html(row.name)}</a></td>
				<td>${frappe.utils.escape_html(row.subject || "")}</td>
				<td>${frappe.utils.escape_html(row.issue_type || "")}</td>
				<td>${gd_acc.accommodation.status_pill("Accommodation Maintenance", "priority", row.priority)}</td>
				<td>${frappe.utils.escape_html(row.site || "")}</td>
				<td>${frappe.utils.escape_html(row.room || row.bed || "")}</td>
				<td>${gd_acc.accommodation.status_pill("Accommodation Maintenance", "status", row.status)}</td>
				<td>${row.reported_on ? frappe.datetime.str_to_user(row.reported_on) : ""}</td>
			</tr>`
			)
			.join("");

		return `
			${this.section_title(
				__("Open Maintenance Requests"),
				count_label(rows.length, __("1 request"), __("{0} requests"))
			)}
			<div class="acc-scroll">
				<table class="table table-bordered acc-table">
					<thead>
						<tr>
							<th>${__("Request")}</th>
							<th>${__("Subject")}</th>
							<th>${__("Issue Type")}</th>
							<th>${__("Priority")}</th>
							<th>${__("Site")}</th>
							<th>${__("Room / Bed")}</th>
							<th>${__("Status")}</th>
							<th>${__("Reported On")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>`;
	}

	/** Frappe's widget classes carry the card look. This only lays them out. */
	styles() {
		return `
			<style>
				.accommodation-dashboard { padding-bottom: var(--padding-xl, 24px); }
				.accommodation-dashboard .acc-grid {
					display: grid;
					gap: var(--margin-md, 12px);
					margin-top: var(--margin-md, 12px);
				}
				.accommodation-dashboard .acc-grid-4 { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
				.accommodation-dashboard .acc-grid-6 { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
				.accommodation-dashboard .acc-grid-charts { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
				.accommodation-dashboard .acc-card { margin: 0; cursor: default; }
				.accommodation-dashboard .acc-card.is-clickable { cursor: pointer; }
				.accommodation-dashboard .acc-card.is-clickable:hover { border-color: var(--gray-400); }
				.accommodation-dashboard .acc-card .widget-title { display: flex; align-items: center; gap: 6px; }
				.accommodation-dashboard .acc-dot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
				.accommodation-dashboard .acc-card .widget-content { padding-top: var(--padding-sm, 8px); }
				.accommodation-dashboard .acc-card-note { font-size: var(--text-sm, 12px); margin-top: 2px; }
				.accommodation-dashboard .acc-chart-box { margin: 0; }
				.accommodation-dashboard .acc-status-chart,
				.accommodation-dashboard .acc-site-chart { height: ${CHART_HEIGHT}px; }
				.accommodation-dashboard .acc-empty { padding: var(--padding-md, 12px) 0; }
				.accommodation-dashboard .acc-section-title {
					display: flex;
					align-items: baseline;
					gap: var(--margin-sm, 8px);
					margin: var(--margin-xl, 24px) 0 0;
					font-weight: var(--weight-semibold, 600);
					color: var(--heading-color);
				}
				.accommodation-dashboard .acc-section-title + .acc-scroll,
				.accommodation-dashboard .acc-section-title + .acc-empty { margin-top: var(--margin-sm, 8px); }
				.accommodation-dashboard .acc-section-hint {
					font-size: var(--text-sm, 12px);
					font-weight: normal;
					color: var(--text-muted);
				}
				/* Five rows, a sticky header, then scroll. */
				.accommodation-dashboard .acc-scroll {
					max-height: 214px;
					overflow: auto;
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius-md, 8px);
				}
				.accommodation-dashboard .acc-table { margin: 0; border: 0; }
				.accommodation-dashboard .acc-table th,
				.accommodation-dashboard .acc-table td {
					white-space: nowrap;
					vertical-align: middle;
					font-size: var(--text-sm, 12px);
					padding: 6px var(--padding-sm, 8px);
				}
				.accommodation-dashboard .acc-table thead th {
					position: sticky;
					top: 0;
					z-index: 1;
					background: var(--subtle-fg, var(--control-bg));
					color: var(--text-muted);
					font-weight: var(--weight-medium, 500);
				}
				.accommodation-dashboard .acc-bar-col { width: 160px; }
				.accommodation-dashboard .acc-bar {
					background: var(--control-bg);
					border-radius: 4px;
					height: 6px;
					overflow: hidden;
				}
				.accommodation-dashboard .acc-bar > span {
					display: block;
					height: 100%;
					background: var(--${gd_acc.accommodation.status_color("Accommodation Bed", "status", "Occupied")}-500);
				}
			</style>`;
	}
}
