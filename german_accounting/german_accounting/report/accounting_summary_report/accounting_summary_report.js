// Copyright (c) 2022, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Accounting Summary Report"] = {
	"filters": [
		{
			"label": "Berichtstyp",
			"fieldname": "report_type",
			"fieldtype": "Select",
			"options": ["Monatsweise", "Monatspaare", "Quartal", "Kalenderjahr"],
			on_change: function () {
				frappe.query_report.get_filter("month").toggle(false);
				frappe.query_report.get_filter("pair").toggle(false);
				frappe.query_report.get_filter("quarter").toggle(false);
				switch (frappe.query_report.get_filter_value('report_type')) {
					case "Monatsweise":
						frappe.query_report.get_filter("month").toggle(true);
						break;
					case "Monatspaare":
						frappe.query_report.get_filter("pair").toggle(true);
						break;
					case "Quartal":
						frappe.query_report.get_filter("quarter").toggle(true);
						break;
				}
			}
		},
		{
			"label": "Ansicht",
			"fieldname": "view",
			"fieldtype": "Select",
			"options": ["Detailed", "Grouped"],
			on_change: function () {
				if (frappe.query_report.get_filter_value('report_type') &&
					(frappe.query_report.get_filter_value("month") ||
						frappe.query_report.get_filter_value("quarter"))) {
					frappe.query_report.refresh();
				}
			}
		},
		{
			"label": "Kalenderjahr",
			"fieldname": "year",
			"fieldtype": "Link",
			"options": "Fiscal Year",
			on_change: function () {}
		},
		{
			"label": __("Month"),
			"fieldname": "month",
			"fieldtype": "Select",
			"options": ["Jan.", "Feb.", "März", "April", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."],
			"hidden": 1
		},

		{
			"label": "Paare",
			"fieldname": "pair",
			"fieldtype": "Select",
			"options": ["Jan/Feb", "April/Mai", "Juli/Aug", "Okt/Nov"],
			"hidden": 1
		},
		{
			"label": "Quartal",
			"fieldname": "quarter",
			"fieldtype": "Select",
			"options": ["1. Quart.", "2. Quart.", "3. Quart.", "4. Quart."],
			"hidden": 1
		}
	]
};
