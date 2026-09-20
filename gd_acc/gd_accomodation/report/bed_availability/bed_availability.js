// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Bed Availability"] = {
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
			fieldname: "floor",
			label: __("Floor"),
			fieldtype: "Link",
			options: "Accommodation Floor",
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
			fieldname: "room",
			label: __("Room"),
			fieldtype: "Link",
			options: "Accommodation Room",
			get_query: function () {
				const filters = {};
				const location = frappe.query_report.get_filter_value("location");
				const site = frappe.query_report.get_filter_value("site");
				const floor = frappe.query_report.get_filter_value("floor");
				if (location) {
					filters.location = location;
				}
				if (site) {
					filters.site = site;
				}
				if (floor) {
					filters.floor = floor;
				}
				return { filters: filters };
			},
		},
		{
			fieldname: "room_type",
			label: __("Room Type"),
			fieldtype: "Select",
			options: "\nShared\nPrivate\nStudio\nOther",
		},
		{
			fieldname: "bed_status",
			label: __("Bed Status"),
			fieldtype: "Select",
			options: "\nAvailable\nOccupied\nReserved\nMaintenance\nInactive",
			default: "Available",
		},
		{
			fieldname: "bed_type",
			label: __("Bed Type"),
			fieldtype: "Select",
			options: "\nSingle\nBunk Lower\nBunk Upper\nDouble\nOther",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status" && data && data.status) {
			const status_colors = {
				Available: "green",
				Occupied: "blue",
				Reserved: "orange",
				Maintenance: "red",
				Inactive: "gray",
			};
			value = `<span class="indicator-pill ${status_colors[data.status] || "gray"}">${__(data.status)}</span>`;
		}

		return value;
	},
};
