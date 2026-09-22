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

		if (column.fieldname === "accommodation_status" && data) {
			value = gd_acc.accommodation.status_pill("Employee", "accommodation_status", data.accommodation_status);
		}

		if (column.fieldname === "stay_status" && data) {
			value = gd_acc.accommodation.status_pill("Accommodation Entitlement", "stay_status", data.stay_status);
		}

		if (column.fieldname === "allocation_status" && data) {
			value = gd_acc.accommodation.status_pill("Accommodation Allocation", "status", data.allocation_status);
		}

		return value;
	},
};
