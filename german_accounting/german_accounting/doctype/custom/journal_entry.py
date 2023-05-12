# -*- coding: utf-8 -*-
# Copyright (c) 2013, LIS and contributors
# For license information, please see license.txt

import frappe

"""
Status einer Rechnung aus dem Vorjahr ändern,
wenn diese über den Saldenvortrag bezahlt wurde.
"""
# TODO: Für Eingangsrechnungen auch umsetzen.

def set_invoice_status(doc, hook=None):
    if hook == "on_submit":
        if frappe.db.exists("Journal Entry", doc.cheque_no):
            journal_entry = frappe.get_doc("Journal Entry", doc.cheque_no)
            set_invoice_status(journal_entry, hook="on_submit")
        elif frappe.db.exists("Sales Invoice", doc.cheque_no) and doc.is_opening:
            sales_invoice = frappe.get_doc("Sales Invoice", doc.cheque_no)
            sales_invoice.db_set("status", "Paid", update_modified=True)
        else:
            return