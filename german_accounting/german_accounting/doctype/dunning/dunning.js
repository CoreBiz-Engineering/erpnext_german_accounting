// Copyright (c) 2019, Alyf and contributors
// For license information, please see license.txt
// extension LIS AG

frappe.ui.form.on('Dunning', {
    setup: function (frm) {
        frm.set_query('sales_invoice', () => {
            return {
                "filters": {
                    "docstatus": 1,
                    "company": frm.doc.company,
                    "outstanding_amount": [">", 0],
                    "status": "Overdue"
                },
           };
        });
        frm.set_query('customer_address', function(doc) {
			if(!doc.company) {
				frappe.throw(__('Please set Customer'));
			}
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Customer',
					link_name: doc.customer
				}
			};
		});
        frm.set_query('company_address', function(doc) {
			if(!doc.company) {
				frappe.throw(__('Please set Customer'));
			}
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Company',
					link_name: doc.company
				}
			};
		});
    },
    refresh: function (frm) {
        frm.set_df_property("company", "read_only", frm.doc.__islocal ? 0 : 1);
        frm.toggle_display("naming_series", false);
        if (frm.is_new()) {
            frm.trigger("calculate_overdue_days");
            frm.set_value("posting_date", frappe.datetime.nowdate());
        };
        frm.set_query("sales_invoice", "dunning_items", function () {
            return {
                filters: {"customer": frm.doc.customer, "status": "Overdue"}
            }
        });
    },
    company: function(frm) {
        if (frm.doc.company == 'SC ESO Electronic S.R.L') {
            frm.set_value('naming_series', 'PR-RO-.YY.-.#####');
        }
        else {
            frm.set_value('naming_series', 'PR-DE-.YY.-.#####');
        }
        frappe.call({
            //get_address
            method: "german_accounting.german_accounting.doctype.dunning.dunning.get_address",
            args: {
                name:frm.doc.company,
                party: "Company"
            },
            callback: function (r) {
                frm.set_value("company_address", r.message);
            }
        });
    },
    customer: function(frm) {
        if (frm.doc.customer){
             frappe.call({
                //get_address
                method: "german_accounting.german_accounting.doctype.dunning.dunning.get_address",
                args: {
                    name:frm.doc.customer,
                    party: "Customer"
                },
                callback: function (r) {
                    frm.set_value("customer_address", r.message);
                }
            });
        } else {
            frm.set_value("customer_address", "");
        }
    },

    customer_address: function(frm) {
        if (frm.doc.customer_address) {
            frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {address_dict: frm.doc.customer_address},
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("address_display", r.message);
                    }
                }
            });
        } else {
            frm.set_value("address_display", "");
        }
    },

    dunning_type: function(frm) {
        if (frm.doc.dunning_type) {
            frappe.call({
                method: "german_accounting.german_accounting.doctype.dunning.dunning.get_dunning_text",
                args: {
                    name: frm.doc.dunning_type,
                    doc: frm.doc
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("text_body", r.message);
                    }
                }
            });
        } else {
            frm.set_value("text_body", "");
        }
    },

    language: function(frm) {
        frm.trigger("get_text_block");
    },
    get_text_block: function (frm) {
        if(frm.doc.dunning_type && frm.doc.language) {
            frappe.call({
              method: "german_accounting.german_accounting.doctype.dunning.dunning.get_text_block",
              args: {
                  dunning_type: frm.doc.dunning_type,
                  language: frm.doc.language,
                  doc: frm.doc
              },
              callback: function(r) {
                  if (r.message) {
                      frm.set_value("top_text_block", r.message.top_text_block);
                      frm.set_value("bottom_text_block", r.message.bottom_text_block);
                  }
                  else {
                      frm.set_value("top_text_block", '');
                      frm.set_value("bottom_text_block", '');
                  }
              }
            });
        }
    },
    /*due_date: function (frm) {
        frm.trigger("calculate_overdue_days");
    },
    posting_date: function (frm) {
        frm.trigger("calculate_overdue_days");
    },*/
    test: function (frm) {
        frm.set_value("top_text_block", frm.doc.posting_date)
    },
    interest_rate: function (frm) {
        frm.trigger("calculate_interest");
    },
    outstanding_amount: function (frm) {
        frm.trigger("calculate_sum");
    },
    interest_amount: function (frm) {
        frm.trigger("calculate_sum");
    },
    dunning_fee: function (frm) {
        frm.trigger("calculate_sum");
    },
    calculate_overdue_days: function (frm) {
        if (frm.doc.posting_date && frm.doc.due_date) {
            const posting_date = frm.get_field("posting_date").get_value();
            const due_date = frm.get_field("due_date").get_value();

            const overdue_days = moment(posting_date).diff(due_date, "days");
            frm.set_value("overdue_days", overdue_days);
        }
    },
    calculate_sum: function (frm) {
        const outstanding_amount = frm.get_field("outstanding_amount").get_value() || 0;
        const interest_amount = frm.get_field("interest_amount").get_value() || 0;
        const dunning_fee = frm.get_field("dunning_fee").get_value() || 0;

        const sum = outstanding_amount + interest_amount + dunning_fee;
        frm.set_value("sum", flt(sum, precision('sum')));
    },
    calculate_interest: function (frm) {
        const interest_rate = frm.get_field("interest_rate").get_value() || 0;
        const outstanding_amount = frm.get_field("outstanding_amount").get_value() || 0;
        const overdue_days = frm.get_field("overdue_days").get_value() || 5;

        const interest_per_year = outstanding_amount * interest_rate / 100;
        const interest_amount = interest_per_year / 360 * overdue_days;
        frm.set_value("interest_amount", flt(interest_amount, precision('interest_amount')));
    }
});
//create a handler for removing items from dunning_items
//does not work as expected:
//https://frappe.io/docs/user/en/guides/app-development/trigger-event-on-deletion-of-grid-row

frappe.ui.form.on("Dunning Items", "sales_invoice", function (frm, cdt, cdn) {
    var d = locals[cdt][cdn];
    var total = 0;
    var interest_amount = 0;
    var d1 = 0;
    var d2 = 0;
    frm.doc.dunning_items.forEach(function(d) {
        var overdue_d;

        //d1 = d.invoice_total || 0;
        total += d.invoice_total || 0;
        //d1 += d.invoice_total || 0;
        if (d.sales_invoice) {
            frappe.call({
                method: "german_accounting.german_accounting.report.op_list.op_list.get_dunning_items_data",
                args: {
                    invoice: d.sales_invoice
                },
                callback: function(r) {
                    var res = r.message;
                    frappe.model.set_value(d.doctype, d.name, "dunning_stage", res["stage"]);
                    frappe.model.set_value(d.doctype, d.name, "overdue_days", res["over_due"]);
                    overdue_d = d.overdue_days;

                }
            });
            if (d.dunning_stage === 1) {
                d1 = d.invoice_total || 0;
            } else if (d.dunning_stage == 2) {
                d2 += d.invoice_total || 0;
            }
            const interest_rate = frm.get_field("interest_rate").get_value() || 0;
            const outstanding_amount = d.outstanding_amount || 0;
            const overdue_days = overdue_d || 0;

            const interest_per_year = outstanding_amount * interest_rate / 100;
            interest_amount += interest_per_year / 360 * overdue_days || 0;
        }
    });
    frm.set_value('total_1', d1);
    frm.set_value('total_2', d2);
    frm.set_value('outstanding_amount', total);
    frm.set_value('interest_amount', interest_amount);
});
