// Copyright (c) 2016, LIS and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["OP List"] = {

    "filters": [
        {
            "fieldname":"company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname":"party_type",
            "label": __("Party Type"),
            "fieldtype": "Select",
            "options": [__("Customer"), __("Supplier")],
            "default": "",
            on_change: function() {
                frappe.query_report.set_filter_value('party', "");
                frappe.query_report.set_filter_value('party_type_name', "");
            }
        },
		{
			"fieldname": "party_type_name",
			"label": __("Party Type Name"),
            "fieldtype": "Data",
			"hidden":1
		},
        {
            "fieldname":"party",
            "label": __("Party"),
            "fieldtype": "MultiSelectList",
            get_data: function(txt) {
                if (!frappe.query_report.filters) return;
                let party_type = frappe.query_report.get_filter_value('party_type');

                if (!party_type) return;
                if (party_type === "Customer" || party_type === "Kunde") {
                    party_type = "Customer";
                } else {
                    party_type = "Supplier";
                }
                return frappe.db.get_link_options(party_type, txt);
            },
            on_change: function() {
                var party_type = frappe.query_report.get_filter_value('party_type');
                if (party_type === "Customer" || party_type === "Kunde") {
                    party_type = "Customer";
                } else {
                    party_type = "Supplier";
                }
                var parties = frappe.query_report.get_filter_value('party');

                if(!party_type || parties.length === 0 || parties.length > 1) {
                    frappe.query_report.set_filter_value('party_name', "");
                    return;
                } else {
                    var party = parties[0];
                    var fieldname = erpnext.utils.get_party_name(party_type) || "name";
                    frappe.db.get_value(party_type, party, fieldname, function(value) {
                        frappe.query_report.set_filter_value('party_name', value[fieldname]);
                    });

                    if (party_type === "Customer" || party_type === "Supplier" || party_type === "Kunde" || party_type === "Lieferant") {
                        frappe.db.get_value(party_type, party, "tax_id", function(value) {
                            frappe.query_report.set_filter_value('tax_id', value["tax_id"]);
                        });
                    }
                }
            }
        },

        {
            "fieldname":"party_name",
            "label": __("Party Name"),
            "fieldtype": "Data",
            "hidden": 1
        },
        {
            "fieldname":"bank",
            "label": __("Bank"),
            "fieldtype": "Link",
            "options": 'Account',
            "get_query": function () {
                return {
                    "doctype": "Account",
                    "filters": {
                        "account_type": "Bank"
                    }
                }
            },
            on_change: function() {}
        },
        {
            "label": __("Buchungsbetrag"),
            "fieldname": "vlaue",
            "fieldtype": "Float",
            on_change: function() {}
        },
        {
            "label": __("Buchungsdatum"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            on_change: function() {}
        },
        {
            "label": __("Buchungstext"),
            "fieldname": "remark",
            "fieldtype": "Data",
            on_change: function() {}
        },
        {
            "label": __("Skonto"),
            "fieldname": "skonto",
            "fieldtype": "Check",
            on_change: function() {}
        },
        {
            "label": __("Verrechnen"),
            "fieldname": "allocate",
            "fieldtype": "Check",
            on_change: function() {}
        },
        {
            "label": __("Gewählte Summe"),
            "fieldname": "select_total",
            "fieldtype": "Currency",
            "default": 0,
            "read_only": 1,
            on_change: function() {}
        },
        {
            "label": __("Datei hochladen"),
            "fieldname": "attach",
            "fieldtype": "Attach",
            on_change: function () {
                $("div[data-fieldname='attach']").addClass('col-md-4').removeClass('col-md-2');
                if (frappe.query_report.get_filter_value('attach')) {
                    $("button[data-label='Create%20Payment']").hide();
                    $("button[data-label='Create%20Dunning']").hide();
                    $("button[data-label='Bankabgleich']").show();
                } else {
                    $("button[data-label='Bankabgleich']").hide();
                    $("button[data-label='Create%20Payment']").show();
                    $("button[data-label='Create%20Dunning']").show();
                }


            }
        },
    ],
    onload: function(report) {
        // not the peferct but fastest way
        //$('div[class="container page-body"]').width('95%')
        frappe.query_report.page.add_inner_button(__("Bankabgleich"), function() {
            var selected_rows = [];
            //collect all checked checkboxes
            $('.dt-scrollable').find(":input[type=checkbox]").each((idx, row) => {
                if(row.checked){
                    console.log("*** selected row id : " + (idx), frappe.query_report.data[idx].voucher_no);
                    var data = frappe.query_report.data[idx]
                    selected_rows.push({
                        "voucher_no": data.sales_invoice,
                        "posting_date": data.bank_posting_date,
                        "id": data.id,
                        "bank": frappe.query_report.get_filter_value('bank'),
                        "remark": frappe.query_report.get_filter_value('remark')
                    });
                }
            });
            console.log("xxx", selected_rows);
            frappe.call({
                method: "german_accounting.german_accounting.report.op_list.bank_file_reader.reconcile_bank",
                args: {
                    invoice_list: selected_rows
                },
                callback: function (r){
                    console.log("returned");
                }
            })
        }).hide();
        frappe.query_report.page.add_inner_button(__("Create Dunning"), function() {
            var selected_rows = [];
            //collect all checked checkboxesi
            $('.dt-scrollable').find(":input[type=checkbox]").each((idx, row) => {
                if(row.checked){
                    selected_rows.push(row.value);
                }
            });
            //send invoices to backend for creating dunning:
            frappe.call({
                method: "german_accounting.german_accounting.report.op_list.op_list.create_dunning",
                args: {
                    sales_invoices: selected_rows},
                callback: function() {
                    frappe.query_report.refresh()
                }
            });
        });
        frappe.query_report.page.add_inner_button(__("Create Payment"), function() {
            var selected_rows = [];
            //collect all checked checkboxes
            $('.dt-scrollable').find(":input[type=checkbox]").each((idx, row) => {
                if(row.checked){
                    selected_rows.push(frappe.query_report.data[idx].voucher_no);
                }
            });
            //send invoices to backend for creating payment:
            frappe.call({
                method: "german_accounting.german_accounting.report.op_list.op_list.create_payment",
                args: {
                    voucher_list: selected_rows,
                    party_type: frappe.query_report.get_filter_value('party_type'),
                    bank: frappe.query_report.get_filter_value('bank'),
                    value: frappe.query_report.get_filter_value('vlaue'),
                    posting_date: frappe.query_report.get_filter_value('posting_date'),
                    skonto: frappe.query_report.get_filter_value('skonto'),
                    remark: frappe.query_report.get_filter_value('remark'),
                    allocate: frappe.query_report.get_filter_value('allocate'),
                },
                callback: function() {
                    $('.dt-scrollable').find(":input[type=checkbox]").prop("checked", false);
                    $('div.dt-row--highlight').removeClass('dt-row--highlight');
                    $('span.dt-toast__message').remove();
                    frappe.query_report.set_filter_value("select_total", 0);
                }
            });
        });
    },
    get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true,
            events: {
                onCheckRow: function (data) {
                    console.log(frappe.query_report.get_filter_value("select_total"));
                    total_checked = 0
                    $('.dt-scrollable').find(":input[type=checkbox]").each((idx, row) => {
                        if(row.checked) {
                            total_checked += frappe.query_report.data[idx].outstanding_amount
                        }
                    });
                    $('span.dt-toast__message').remove();
                    frappe.query_report.set_filter_value("select_total", total_checked);
                },
            }
        });
    }
};

erpnext.dimension_filters.forEach((dimension) => {
    frappe.query_reports["Accounts Receivable"].filters.splice(9, 0 ,{
        "fieldname": dimension["fieldname"],
        "label": __(dimension["label"]),
        "fieldtype": "Link",
        "options": dimension["document_type"]
    });
});
