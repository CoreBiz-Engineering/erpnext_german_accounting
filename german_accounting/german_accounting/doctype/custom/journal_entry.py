# -*- coding: utf-8 -*-
# Copyright (c) 2013, LIS and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime

"""
Status einer Rechnung aus dem Vorjahr ändern,
wenn diese über den Saldenvortrag bezahlt wurde.
"""
# TODO: Für Eingangsrechnungen auch umsetzen.

def set_invoice_status(doc, hook=None, is_opening="No"):
    if hook == "on_submit":
        if is_opening == "Yes" or doc.is_opening == "Yes":
            doc.is_opening = "Yes"

        if frappe.db.exists("Journal Entry", doc.cheque_no):
            journal_entry = frappe.get_doc("Journal Entry", doc.cheque_no)
            set_invoice_status(journal_entry, hook="on_submit", is_opening="Yes")
        elif frappe.db.exists("Sales Invoice", doc.cheque_no) and doc.is_opening == "Yes":
            sales_invoice = frappe.get_doc("Sales Invoice", doc.cheque_no)
            sales_invoice.db_set("status", "Paid", update_modified=True)
        else:
            return

def check_valid_posting_date(doc, hook):
    if not hook == "on_submit" and doc.voucher_type != "Bank Entry":
        return

    datetime_object = datetime.strptime(doc.posting_date, '%Y-%m-%d').date()
    for row in doc.accounts:
        if not row.party_type and not row.reference_type:
            continue
        if not row.reference_due_date:
            if row.reference_type == "Sales Invoice":

                invoice = frappe.get_doc("Sales Invoice", row.reference_name)
                if datetime_object < invoice.posting_date:
                    msg = "Rechnungsbuchungsdatum: {0}".format(frappe.format(invoice.posting_date, "Date"))
                    msg += "<br>"
                    msg += "Geldeingang: {0}".format(frappe.format(doc.posting_date, "Date"))
                    frappe.throw(msg, title="Falsches Buchungsdatum!")
        else:
            if  datetime_object < row.reference_due_date:
                msg = "Rechnungsbuchungsdatum: {0}".format(row.posting_date)
                msg += "<br>"
                msg += "Geldeingang: {0}".format(doc.posting_date)
                frappe.throw(msg, title="Falsches Buchungsdatum!")
    return