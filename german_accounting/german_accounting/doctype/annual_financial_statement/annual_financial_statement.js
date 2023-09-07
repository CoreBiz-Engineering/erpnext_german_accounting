// Copyright (c) 2022, LIS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Annual Financial Statement', {
    refresh: function(frm) {
        frm.disable_save();
    },
    annual_report_type: function (frm) {
        frm.save_entries = 0
        if (frm.doc.annual_report_type === "Kreditor") {
            frm.trigger("get_entries");
        } else if (frm.doc.annual_report_type === "Debitor") {
            frm.trigger("get_entries");
        } else if (frm.doc.annual_report_type === "Aktiva/Passiva") {
            frm.trigger("get_entries");
        } else {
            console.log("Nichts");
        }
    },
    create_closing: function (frm) {
        frm.save_entries = 1;
        frm.trigger("get_entries");
    },
    get_entries: function (frm) {
        if (frm.doc.annual_report_type === "Debitor" || frm.doc.annual_report_type === "Kreditor"){
            frappe.call({
                doc: me.frm.doc,
                method: "select_entries",
                args: {
                    account_type: frm.doc.annual_report_type,
                    fiscal_year: frm.doc.fiscal_year,
                    submit: frm.save_entries
                },
                /*callback: function (r) {
                    console.log(r.message);
                }*/
            })
        }
    }
});
