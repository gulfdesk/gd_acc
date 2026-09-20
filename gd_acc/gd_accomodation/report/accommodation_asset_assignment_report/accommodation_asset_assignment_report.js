// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Accommodation Asset Assignment Report"] = {
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
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "item_category",
			label: __("Item Category"),
			fieldtype: "Select",
			options: "\nFurniture\nBedding\nElectrical\nKitchen\nSafety\nCleaning\nOther",
		},
		{
			fieldname: "assignment_status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nAssigned\nReturned\nDamaged\nLost\nCancelled",
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

		if (column.fieldname === "status" && data && data.status) {
			const status_colors = {
				Assigned: "blue",
				Returned: "green",
				Damaged: "orange",
				Lost: "red",
				Cancelled: "gray",
			};
			value = `<span class="indicator-pill ${status_colors[data.status] || "gray"}">${__(data.status)}</span>`;
		}

		return value;
	},
};
