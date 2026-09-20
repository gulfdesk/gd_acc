// Copyright (c) 2026, Rahmed-dev and contributors
// For license information, please see license.txt

frappe.query_reports["Accommodation Occupancy"] = {
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
			fieldname: "accommodation_type",
			label: __("Accommodation Type"),
			fieldtype: "Select",
			options: "\nCamp\nBuilding\nOther",
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Location\nSite\nFloor\nRoom",
			default: "Site",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "occupancy_percent" && data) {
			const percent = flt(data.occupancy_percent);
			let color = "green";
			if (percent >= 100) {
				color = "red";
			} else if (percent >= 85) {
				color = "orange";
			}
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}

		return value;
	},
};
