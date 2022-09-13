// Copyright (c) 2022, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Profit Account Check"] = {
	"filters": [

	],
	onload: function () {
		frappe.query_report.page.add_inner_button(__("Submit"), function() {
            var selected_rows = [];
            //collect all checked checkboxes
            $('.dt-scrollable').find(":input[type=checkbox]").each((idx, row) => {
                if(row.checked && !selected_rows.includes(frappe.query_report.data[idx/2].invoice)){
                    console.log(idx/2);
                    console.log(frappe.query_report.data[idx/2].invoice);
                    selected_rows.push(frappe.query_report.data[idx/2].invoice);
                }
            });
            console.log(selected_rows);
            if (selected_rows.length >= 1) {
                frappe.call({
                    method: "german_accounting.german_accounting.report.profit_account_check.profit_account_check.submit_invoice",
                    args: {
                          "invoice_list": selected_rows
                    },
                    callback: function (r) {
                        location.reload()
                        /*frappe.query_report.refresh();
                        $('.dt-scrollable').find(":input[type=checkbox]").prop("checked", false);
                        $('div.dt-row--highlight').removeClass('dt-row--highlight');
                        $('span.dt-toast__message').remove();
                        console.log("after refresh");*/
                    }
                })
            }
		})
	},
	get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true,
            /*events: {
                onCheckRow: function (data) {
                    $('span.dt-toast__message').remove();
                }
            }*/
        });
    }
};
