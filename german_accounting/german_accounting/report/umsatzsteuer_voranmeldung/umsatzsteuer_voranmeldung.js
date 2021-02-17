// Copyright (c) 2016, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Umsatzsteuer Voranmeldung"] = {
	"filters": [
        {
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company") || frappe.defaults.get_global_default("Company"),
			"reqd": 1
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"default": frappe.datetime.month_start(),
			"fieldtype": "Date",
			"reqd": 1
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"default": frappe.datetime.now_date(),
			"fieldtype": "Date",
			"reqd": 1
		},
		{
			"fieldname": "view",
			"lablel": __("View"),
			"fieldtype": "Select",
			"default": "Kontenansicht",
			"options": ["Kontenansicht", "Kurzansicht"],
			"reqd": 1
		}
	]
};
