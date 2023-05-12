// Copyright (c) 2022, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Profit Account Check"] = {
	"filters": [
        {
			"fieldname": "from_date",
			"label": __("From Date"),
			// "default": frappe.datetime.month_start(),
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			// "default": frappe.datetime.now_date(),
			"fieldtype": "Date",
		}
	],
	onload: function () {
		frappe.query_report.page.add_inner_button(__("Submit"), function() {
            var selected_rows = [];
            //collect all checked checkboxes

            frappe.query_report.datatable.rowmanager.checkMap.forEach((checked, index) => {
                var name = frappe.query_report.data[index].invoice
                if(checked && name && !selected_rows.includes(name)) {
                    selected_rows.push(name);

                }
            });
            if (selected_rows.length >= 1) {
                frappe.call({
                    method: "german_accounting.german_accounting.report.profit_account_check.profit_account_check.submit_invoice",
                    args: {
                          "invoice_list": selected_rows
                    },
                    callback: function (r) {
                        location.reload()
                        frappe.query_report.refresh();
                        $('.dt-scrollable').find(":input[type=checkbox]").prop("checked", false);
                        $('div.dt-row--highlight').removeClass('dt-row--highlight');
                        $('span.dt-toast__message').remove();
                    }
                })
            }
		})
	},
	get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true,
            events: {
                onCheckRow: function (data) {
                    var selected_rows3 = []
                    frappe.query_report.datatable.rowmanager.checkMap.forEach((checked, index) => {
                        if(checked) {
                            selected_rows3.push(index)
                        }
                    });
                }
            }
        });
    }
};
