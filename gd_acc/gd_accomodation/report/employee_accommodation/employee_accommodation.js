// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Accommodation"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "accommodation_status",
			label: __("Accommodation Status"),
			fieldtype: "Select",
			options: "\nProvided\nAllowance\nNot Provided",
		},
		{
			fieldname: "stay_status",
			label: __("Stay Status"),
			fieldtype: "Select",
			options: "\nAwaiting Bed\nAllocated\nVacated",
		},
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
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				const filters = {};
				const company = frappe.query_report.get_filter_value("company");
				if (company) {
					filters.company = company;
				}
				return { filters: filters };
			},
		},
		{
			fieldname: "include_inactive_employees",
			label: __("Include Inactive Employees"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "accommodation_status" && data && data.accommodation_status) {
			const status_colors = {
				Provided: "green",
				Allowance: "blue",
				"Not Provided": "gray",
			};
			value = `<span class="indicator-pill ${
				status_colors[data.accommodation_status] || "gray"
			}">${__(data.accommodation_status)}</span>`;
		}

		if (column.fieldname === "stay_status" && data && data.stay_status) {
			const stay_colors = {
				"Awaiting Bed": "orange",
				Allocated: "green",
				Vacated: "gray",
			};
			value = `<span class="indicator-pill ${stay_colors[data.stay_status] || "gray"}">${__(
				data.stay_status
			)}</span>`;
		}

		if (column.fieldname === "allocation_status" && data && data.allocation_status) {
			const allocation_colors = {
				Active: "green",
				"Pending Release": "orange",
				Closed: "blue",
			};
			value = `<span class="indicator-pill ${
				allocation_colors[data.allocation_status] || "gray"
			}">${__(data.allocation_status)}</span>`;
		}

		return value;
	},
};
