// Copyright (c) 2016, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Umsatzliste"] = {
	"filters": [
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
	]
};
