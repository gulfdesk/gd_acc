// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Accommodation Maintenance Report"] = {
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
			fieldname: "maintenance_status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nIn Progress\nResolved\nClosed\nCancelled",
		},
		{
			fieldname: "issue_type",
			label: __("Issue Type"),
			fieldtype: "Select",
			options:
				"\nElectrical\nPlumbing\nAir Conditioning\nFurniture\nCleaning\nStructural\nPest Control\nOther",
		},
		{
			fieldname: "priority",
			label: __("Priority"),
			fieldtype: "Select",
			options: "\nLow\nMedium\nHigh\nUrgent",
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
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status" && data) {
			value = gd_acc.accommodation.status_pill("Accommodation Maintenance", "status", data.status);
		}

		if (column.fieldname === "priority" && data) {
			value = gd_acc.accommodation.status_pill("Accommodation Maintenance", "priority", data.priority);
		}

		return value;
	},
};
