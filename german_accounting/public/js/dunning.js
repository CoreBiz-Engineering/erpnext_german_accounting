
frappe.ui.form.on('Dunning', {
    setup: function (frm) {
        frm.set_query("sales_invoice", "dunning_item", function () {
            return {
                filters: {"customer": frm.doc.customer, "status": "Overdue"}
            }
        });
        frm.set_query("customer_address",function () {
            return {
                query: "frappe.contacts.doctype.address.address.address_query",
                filters: {link_doctype: "Customer", link_name: frm.doc.customer}
            }
        });
        frm.set_query("company_address",function () {
            return {
                query: "frappe.contacts.doctype.address.address.address_query",
                filters: {link_doctype: "Company", link_name: frm.doc.company}
            }
        });
    },
    customer: function (frm) {
        erpnext.utils.get_party_details(frm,
            "erpnext.accounts.party.get_party_details", {
                party: frm.doc.customer,
                party_type: "Customer",
            });
    },
    calculate_total_outstanding: function (frm) {
        var total = 0;
        frm.doc.dunning_item.forEach(function(d) {
            total += d.outstanding_amount;
        })
        frm.set_value("outstanding_amount", total);
    },
    customer_address: function (frm) {
        erpnext.utils.get_address_display(frm, 'customer_address', 'address_display')
    },
    company_address: function (frm) {
        erpnext.utils.get_address_display(frm, 'company_address', 'company_address_display')
    }
})

frappe.ui.form.on("Dunning Item",{
    dunning_item_remove: function (frm) {
        frm.trigger("calculate_total_outstanding");
    },
    sales_invoice: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.sales_invoice) {
            frappe.call({
                method: "german_accounting.german_accounting.report.op_list.op_list.get_dunning_items_data",
                args: {
                    invoice: row.sales_invoice
                },
                callback: function(r) {
                    var res = r.message;
                    frappe.model.set_value(row.doctype, row.name, "dunning_stage", res["stage"]);
                    frappe.model.set_value(row.doctype, row.name, "overdue_days", res["over_due"]);
                    frm.trigger("calculate_total_outstanding");
                }
            });
        }
    }
})