// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Bed Status History Report"] = {
	filters: [
		{
			fieldname: "location",
			label: __("Location"),
			fieldtype: "Link",
			options: "Accommodation Location",
		},
		{
			fieldname: "site",
			label: __("Accommodation Site"),
			fieldtype: "Link",
			options: "Accommodation Site",
			get_query: function () {
				const filters = {};
				const location = frappe.query_report.get_filter_value("location");
				if (location) {
					filters.location = location;
				}
				return { filters: filters };
			},
		},
		{
			fieldname: "bed",
			label: __("Bed"),
			fieldtype: "Link",
			options: "Accommodation Bed",
			get_query: function () {
				const filters = {};
				const location = frappe.query_report.get_filter_value("location");
				const site = frappe.query_report.get_filter_value("site");
				if (location) {
					filters.location = location;
				}
				if (site) {
					filters.site = site;
				}
				return { filters: filters };
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "reason",
			label: __("Reason"),
			fieldtype: "Select",
			options: "\nAllocation\nRelease\nTransfer In\nTransfer Out\nManual Update\nMaintenance\nBulk Setup\nHold\nHold Released",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		const status_colors = {
			Available: "green",
			Occupied: "blue",
			Reserved: "orange",
			Maintenance: "red",
			Blocked: "red",
			Inactive: "gray",
		};

		if (column.fieldname === "new_status" && data && data.new_status) {
			value = `<span class="indicator-pill ${status_colors[data.new_status] || "gray"}">${__(
				data.new_status
			)}</span>`;
		}

		return value;
	},
};
