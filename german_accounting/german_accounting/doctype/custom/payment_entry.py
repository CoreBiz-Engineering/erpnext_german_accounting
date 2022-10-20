# -*- coding: utf-8 -*-
import frappe, json
from frappe import _


@frappe.whitelist()
def create_reverse_entry(doc):
    doc = frappe._dict(json.loads(doc))

    for row in doc.references:
        j_entry = frappe.new_doc("Journal Entry")
        j_entry.voucher_type = "Journal Entry"
        j_entry.posting_date = doc.posting_date
        if doc.payment_type == "Pay":
            debit = j_entry.append("accounts", {})
            debit.account = doc.paid_from
            debit.debit_in_account_currency = row.get("total_amount")
            debit.debit = row.get("total_amount")

            credit = j_entry.append("accounts", {})
            credit.account = doc.paid_to
            credit.credit_in_account_currency = row.get("total_amount")
            credit.credit = row.get("total_amount")
            credit.party_type = doc.party_type
            credit.party = doc.party

        elif doc.payment_type == "Receive":
            debit = j_entry.append("accounts", {})
            debit.account = doc.paid_to
            debit.party_type = doc.party_type
            debit.party = doc.party
            debit.debit_in_account_currency = row.get("total_amount")
            debit.debit = row.get("total_amount")

            credit = j_entry.append("accounts", {})
            credit.account = doc.paid_from
            credit.credit_in_account_currency = row.get("total_amount")
            credit.credit = row.get("total_amount")

        j_entry.save()
