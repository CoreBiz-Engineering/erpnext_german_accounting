// Copyright (c) 2016, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Summen und Salden (SuSa)"] = {
	"filters": [
		{
			"fieldname": "party",
			"label": __("Party"),
			"fieldtype": "Select",
			"options": ["Sachkonten", "Debitor", "Kreditor"],
			"default": "Sachkonten",
			"reqd": 1
		},
		{
			"fieldname": "year",
			"label": __("Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": "2020",
			"reqd": 1
		},
		{
			"fieldname": "month",
			"label": __("Month"),
			"fieldtype": "Select",
			"translatable": 1,
			"options": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
						"August", "September", "Oktober", "November", "Dezember"],
			"reqd": 1
		},

	]
};
