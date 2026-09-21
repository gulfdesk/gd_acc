// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Accommodation Item Report"] = {
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
			fieldname: "allocation",
			label: __("Allocation"),
			fieldtype: "Link",
			options: "Accommodation Allocation",
		},
		{
			fieldname: "item_category",
			label: __("Item Category"),
			fieldtype: "Select",
			options: "\nFurniture\nBedding\nElectrical\nKitchen\nSafety\nCleaning\nOther",
		},
		{
			fieldname: "items_status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOutstanding\nCleared",
		},
		{
			fieldname: "outstanding_only",
			label: __("Outstanding Only"),
			fieldtype: "Check",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) {
			return value;
		}

		if (column.fieldname === "items_status" && data.items_status) {
			const status_colors = { Outstanding: "orange", Cleared: "green" };
			value = `<span class="indicator-pill ${status_colors[data.items_status] || "gray"}">${__(
				data.items_status
			)}</span>`;
		}

		if (column.fieldname === "outstanding_quantity" && data.outstanding_quantity > 0) {
			value = `<span style="color: var(--orange-600)">${value}</span>`;
		}

		return value;
	},
};
