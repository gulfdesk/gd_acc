// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

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

		this.location_field = this.page.add_field({
			fieldname: "location",
			fieldtype: "Link",
			label: __("Location"),
			options: "Accommodation Location",
			change: () => this.refresh(),
		});

		this.site_field = this.page.add_field({
			fieldname: "site",
			fieldtype: "Link",
			label: __("Accommodation Site"),
			options: "Accommodation Site",
			get_query: () => ({ filters: { location: this.location_field.get_value() } }),
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

	get scope() {
		const filters = {};
		const location = this.location_field.get_value();
		const site = this.site_field.get_value();
		if (location) {
			filters.location = location;
		}
		if (site) {
			filters.site = site;
		}
		return filters;
	}

	refresh() {
		frappe.call({
			method: "gd_acc.gd_accomodation.api.get_dashboard_data",
			args: {
				location: this.location_field.get_value() || null,
				site: this.site_field.get_value() || null,
			},
			callback: (response) => this.render(response.message || {}),
		});
	}

	render(data) {
		const kpi = data.kpi || {};
		const scope = this.scope;
		this.cards = [];

		// Site scope cannot be pushed onto a Location list, so it is dropped there.
		const location_scope = scope.location ? { name: scope.location } : {};
		const site_scope = scope.site ? { name: scope.site } : { ...scope };

		const structure = [
			this.card(__("Locations"), kpi.locations, null, "Accommodation Location", location_scope),
			this.card(__("Sites"), kpi.sites, null, "Accommodation Site", site_scope),
			this.card(__("Floors"), kpi.floors, null, "Accommodation Floor", scope),
			this.card(__("Rooms"), kpi.rooms, null, "Accommodation Room", scope),
			this.card(__("Beds"), kpi.beds, "blue", "Accommodation Bed", scope),
		];

		const beds = [
			this.card(__("Available"), kpi.available, "green", "Accommodation Bed", {
				...scope,
				status: "Available",
			}),
			this.card(__("Occupied"), kpi.occupied, "blue", "Accommodation Bed", {
				...scope,
				status: "Occupied",
			}),
			this.card(__("Reserved"), kpi.reserved, "orange", "Accommodation Bed", {
				...scope,
				status: "Reserved",
			}),
			this.card(__("Beds Under Maintenance"), kpi.maintenance, "red", "Accommodation Bed", {
				...scope,
				status: "Maintenance",
			}),
			this.card(__("Blocked"), kpi.blocked, "red", "Accommodation Bed", {
				...scope,
				status: "Blocked",
			}),
			this.card(__("Occupancy"), `${kpi.occupancy_percent || 0}%`, "purple"),
		];

		const people = [
			this.card(__("Provided"), kpi.employees_provided, "green", "Accommodation Entitlement", {
				status: "Active",
				entitlement_type: "Company Accommodation",
			}),
			this.card(__("Allowance"), kpi.employees_allowance, "blue", "Accommodation Entitlement", {
				status: "Active",
				entitlement_type: "Allowance",
			}),
			this.card(
				__("Not Provided"),
				kpi.employees_not_provided,
				"gray",
				"Employee Accommodation",
				{ accommodation_status: "Not Provided" },
				"query-report"
			),
			this.card(
				__("Open Maintenance Requests"),
				kpi.open_maintenance_requests,
				"orange",
				"Accommodation Maintenance",
				{ ...scope, status: ["in", ["Open", "In Progress"]] }
			),
			this.card(__("Pending Release"), kpi.pending_release, "orange", "Accommodation Allocation", {
				...scope,
				docstatus: 1,
				status: "Pending Release",
			}),
			this.card(
				__("Unhoused"),
				kpi.awaiting_bed,
				"orange",
				"Accommodation Entitlement",
				"Unhoused Employees",
				"Report"
			),
		];

		this.$container.html(`
			${this.styles()}

			<div class="section-title">${__("Structure")}</div>
			<div class="kpi-grid">${structure.join("")}</div>

			<div class="section-title">
				${__("Beds by Status")}
				<span class="section-hint">${__("Counts beds, not maintenance requests")}</span>
			</div>
			<div class="kpi-grid">${beds.join("")}</div>

			<div class="section-title">${__("Employees and Requests")}</div>
			<div class="kpi-grid">${people.join("")}</div>

			${this.occupancy_section(__("Occupancy by Location"), __("Location"), data.by_location)}
			${this.occupancy_section(__("Occupancy by Site Type"), __("Site Type"), data.by_site_type)}
			${this.occupancy_section(__("Occupancy by Site"), __("Site"), data.by_site)}
			${this.maintenance_section(data.open_maintenance || [])}
		`);
	}

	/** Build a KPI tile. Passing a doctype makes it open that filtered list. */
	card(label, value, color, doctype, filters, view = "List") {
		const index = this.cards.length;
		this.cards.push({ route: doctype ? { view, doctype, filters } : null });

		const clickable = doctype ? "is-clickable" : "";
		const accent = color ? `style="border-left-color: var(--${color}-500)"` : "";
		const hint = doctype ? `<span class="kpi-go">${frappe.utils.icon("right", "xs")}</span>` : "";

		return `
			<div class="kpi-card ${clickable}" ${accent} ${doctype ? `data-card-index="${index}"` : ""}>
				<div class="kpi-value">${frappe.utils.escape_html(String(value ?? 0))}</div>
				<div class="kpi-label">${label}${hint}</div>
			</div>`;
	}

	occupancy_section(title, column_label, rows) {
		rows = rows || [];
		if (!rows.length) {
			return `
				<div class="section-title">${title}</div>
				<div class="text-muted no-data">${__("No data yet.")}</div>`;
		}

		const body = rows
			.map(
				(row) => `
			<tr>
				<td>${frappe.utils.escape_html(row.name)}</td>
				<td class="text-right">${row.total}</td>
				<td class="text-right">${row.Occupied || 0}</td>
				<td class="text-right">${row.Available || 0}</td>
				<td class="text-right">${row.Maintenance || 0}</td>
				<td>
					<div class="occupancy-bar" title="${row.occupancy_percent || 0}%">
						<span style="width: ${Math.min(row.occupancy_percent || 0, 100)}%"></span>
					</div>
				</td>
				<td class="text-right">${row.occupancy_percent || 0}%</td>
			</tr>`
			)
			.join("");

		return `
			<div class="section-title">
				${title}
				<span class="section-hint">${__("{0} rows", [rows.length])}</span>
			</div>
			<div class="scroll-table">
				<table class="table table-bordered table-sm">
					<thead>
						<tr>
							<th>${column_label}</th>
							<th class="text-right">${__("Beds")}</th>
							<th class="text-right">${__("Occupied")}</th>
							<th class="text-right">${__("Available")}</th>
							<th class="text-right">${__("Maint.")}</th>
							<th style="width: 150px">${__("Occupancy")}</th>
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
				<div class="section-title">${__("Open Maintenance Requests")}</div>
				<div class="text-muted no-data">${__("No open maintenance requests.")}</div>`;
		}

		const priority_colors = { Urgent: "red", High: "orange", Medium: "blue", Low: "gray" };
		const status_colors = { Open: "orange", "In Progress": "blue" };

		const body = rows
			.map(
				(row) => `
			<tr>
				<td><a href="/app/accommodation-maintenance/${encodeURIComponent(
					row.name
				)}">${frappe.utils.escape_html(row.name)}</a></td>
				<td>${frappe.utils.escape_html(row.subject || "")}</td>
				<td>${frappe.utils.escape_html(row.issue_type || "")}</td>
				<td><span class="indicator-pill ${priority_colors[row.priority] || "gray"}">${frappe.utils.escape_html(
					row.priority || ""
				)}</span></td>
				<td>${frappe.utils.escape_html(row.site || "")}</td>
				<td>${frappe.utils.escape_html(row.room || row.bed || "")}</td>
				<td><span class="indicator-pill ${status_colors[row.status] || "gray"}">${frappe.utils.escape_html(
					row.status || ""
				)}</span></td>
				<td>${row.reported_on ? frappe.datetime.str_to_user(row.reported_on) : ""}</td>
			</tr>`
			)
			.join("");

		return `
			<div class="section-title">
				${__("Open Maintenance Requests")}
				<span class="section-hint">${__("{0} rows", [rows.length])}</span>
			</div>
			<div class="scroll-table">
				<table class="table table-bordered table-sm">
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

	styles() {
		return `
			<style>
				.accommodation-dashboard .kpi-grid {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
					gap: 12px;
					margin-bottom: 8px;
				}
				.accommodation-dashboard .kpi-card {
					background: var(--card-bg);
					border: 1px solid var(--border-color);
					border-left: 3px solid var(--gray-300);
					border-radius: var(--border-radius-md, 8px);
					padding: 12px 14px;
				}
				.accommodation-dashboard .kpi-card.is-clickable {
					cursor: pointer;
					transition: box-shadow 0.15s ease, transform 0.15s ease;
				}
				.accommodation-dashboard .kpi-card.is-clickable:hover {
					box-shadow: var(--shadow-base, 0 1px 8px rgba(0, 0, 0, 0.1));
					transform: translateY(-1px);
				}
				.accommodation-dashboard .kpi-value {
					font-size: 22px;
					font-weight: 600;
					line-height: 1.2;
					color: var(--text-color);
				}
				.accommodation-dashboard .kpi-label {
					font-size: var(--text-sm, 12px);
					color: var(--text-muted);
					margin-top: 4px;
					display: flex;
					align-items: center;
					gap: 4px;
				}
				.accommodation-dashboard .kpi-card.is-clickable:hover .kpi-go { opacity: 1; }
				.accommodation-dashboard .kpi-go { opacity: 0; transition: opacity 0.15s ease; }
				.accommodation-dashboard .section-title {
					font-size: var(--text-base, 14px);
					font-weight: 600;
					color: var(--text-color);
					margin: 22px 0 10px;
					display: flex;
					align-items: baseline;
					gap: 8px;
				}
				.accommodation-dashboard .section-hint {
					font-size: var(--text-sm, 12px);
					font-weight: normal;
					color: var(--text-muted);
				}
				.accommodation-dashboard .no-data { padding-bottom: 8px; }
				/* About five rows, then scroll. */
				.accommodation-dashboard .scroll-table {
					max-height: 232px;
					overflow-y: auto;
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius-md, 8px);
				}
				.accommodation-dashboard .scroll-table table { margin-bottom: 0; border: none; }
				.accommodation-dashboard .scroll-table thead th {
					position: sticky;
					top: 0;
					z-index: 1;
					background: var(--subtle-fg, var(--control-bg));
				}
				.accommodation-dashboard .occupancy-bar {
					background: var(--control-bg);
					border-radius: 4px;
					height: 8px;
					overflow: hidden;
					min-width: 80px;
				}
				.accommodation-dashboard .occupancy-bar > span {
					display: block;
					height: 100%;
					background: var(--blue-500);
				}
			</style>`;
	}
}
