// Copyright (c) 2016, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Betriebswirtschaftliche Auswertungen"] = {
	"filters": [
        {
			"fieldname": "from_date",
			"label": __("From Date"),
			"default": frappe.datetime.month_start(),
			"fieldtype": "Date",
			"reqd": 1,
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"default": frappe.datetime.now_date(),
			"fieldtype": "Date",
			"reqd": 1,
		},
		{
			"fieldname": "view",
			"lablel": __("View"),
			"fieldtype": "Select",
			"default": "Kontenansicht",
			"options": ["BWA Kurzbericht", "BWA Kontenansicht"],
			"reqd": 1,
		},
		{
			"fieldname": "comparison",
			"label": "Vorjahresvergleich",
			"fieldtype": "Check",
		}
	]
};
/*
frappe.query_report.get_filter_value('party');
frappe.set_df_property("compare_from_date", "hidden", 0);


var dt_filter= frappe.query_report.get_filter(“date”);
	if (frappe.user.has_role(“Role Name”)) {
		dt_filter.toggle(false);
	}
dt_filter.refresh();


* */
