# -*- coding: utf-8 -*-
# Copyright (c) 2013, LIS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext, json, time, datetime
from frappe import _, scrub, qb
from frappe.query_builder.functions import IfNull
from frappe.query_builder.custom import ConstantColumn
from frappe.utils import cint, cstr, flt, formatdate, get_number_format_info, getdate, now, nowdate
from .op_list_columns import get_supplier_columns
import erpnext
from erpnext.accounts.utils import QueryPaymentLedger


def get_supplier_data(supplier_list=None, party_type="Supplier", fiscal_year=None):
    # select all supplier or just the supplier from filter
    if not supplier_list:
        supplier_list = [supplier.name for supplier in frappe.get_all("Supplier")]

    op = []
    row = 1

    payment_entries = get_payment_entries(supplier_list, fiscal_year)
    journal_entries = get_jv_entries(supplier_list, fiscal_year)
    dr_or_cr_notes = get_dr_or_cr_notes(supplier_list, fiscal_year)
    invoices = get_outstanding_invoices(supplier_list, fiscal_year)
    party_op = payment_entries + journal_entries + dr_or_cr_notes + invoices


    op_supplier_list = []
    for voucher in party_op:
        if voucher.get('supplier') is None:
            continue
        if voucher.get('supplier') not in op_supplier_list:
            op_supplier_list.append(voucher.get('supplier'))

    op_supplier_list.sort()
    for supplier in op_supplier_list:
        debit = credit = payed = outstanding_amount = 0
        for voucher in party_op:
            if supplier != voucher.get("supplier"):
                continue
            voucher["account"] = voucher.get('account')
            voucher["supplier_name"] = voucher.get('supplier')
            voucher["voucher_type_hidden"] = voucher.get("reference_type") or voucher.get("voucher_type")
            voucher["voucher_type"] = _(voucher.get("reference_type")) or _(voucher.get("voucher_type"))
            voucher["order_count"] = row

            if voucher.get("invoice_amount"):
                voucher["credit"] = voucher.get("invoice_amount")
            if voucher.get("payment_amount"):
                voucher["paid_amount"] = voucher.get("payment_amount")
            if voucher.get("amount"):
                voucher["debit"] = voucher.get("amount")
                voucher["outstanding_amount"] = voucher.get("amount")*(-1)
            if voucher.get("reference_name"):
                voucher["voucher_no"] = voucher.get("reference_name")

            debit -= voucher.get("debit") or 0
            credit += voucher.get("credit") or 0
            payed += voucher.get("paid_amount") or 0
            outstanding_amount += voucher.get("outstanding_amount") or 0

        party_op += [
            {
                "cheque_no": "Summe",
                "order_count": row + 1,
                "debit": debit,
                "credit": credit,
                "paid_amount": payed,
                "outstanding_amount": outstanding_amount
            },
            {
                "order_count": row + 2,
            }
        ]
        row += 3

    op = op + party_op

    op = sorted(op, key=lambda k: ("order_count" not in k, k.get("order_count", None), "posting_date" not in k, k.get("posting_date", None)))
    # op = sorted(op, key=lambda k: (k['order_count'], k['posting_date']))

    columns = get_supplier_columns()

    return columns, op


def get_payment_entries(party, fiscal_year=None):
    payment_reconciliation = frappe.new_doc("Payment Reconciliation")
    condition = payment_reconciliation.get_conditions(get_payments=True)
    if fiscal_year:
        condition = condition.replace("company", "t1.company")
        condition += " and gl.fiscal_year = '%s'" % fiscal_year
    payment_entries_against_order = frappe.db.sql(
        """
        select
            "Payment Entry" as reference_type, t1.name as reference_name,
            t1.remarks, t1.party as 'supplier', t1.paid_to as 'account', t2.allocated_amount as amount,
            t2.name as reference_row, t2.reference_name as against_order, t1.posting_date,
            t1.paid_to_account_currency as currency, t1.target_exchange_rate as exchange_rate   
        from `tabPayment Entry` t1, `tabPayment Entry Reference` t2, `tabGL Entry` gl
        where
            t1.name = t2.parent and t1.payment_type in ('Pay', 'Receive')
            and t1.party_type = gl.party_type
            and gl.voucher_no = t1.name
            and t1.party_type = 'Supplier' and t1.party in %(party)s and t1.docstatus = 1
            and t2.reference_doctype = 'Purchase Order'
        order by t1.posting_date
        """,
        {"party": party},
        as_dict=1)

    unallocated_payment_entries = frappe.db.sql(
        """
        select "Payment Entry" as reference_type, t1.name as reference_name, t1.posting_date,
            t1.remarks, t1.unallocated_amount as amount, t1.target_exchange_rate as exchange_rate, t1.paid_to_account_currency as currency
        from `tabPayment Entry` t1, `tabGL Entry` gl
        where
            t1.party_type = 'Supplier' and t1.party in %(party)s and t1.payment_type in ('Pay', 'Receive')
            and t1.party_type = gl.party_type
            and gl.voucher_no = t1.name
            and t1.docstatus = 1 and t1.unallocated_amount > 0
        order by t1.posting_date
        """.format({"condition": condition}),
        {"party": party},
        as_dict=1
    )

    return list(payment_entries_against_order) + list(unallocated_payment_entries)


def get_jv_entries(party, fiscal_year=None):
    payment_reconciliation = frappe.new_doc("Payment Reconciliation")
    condition = payment_reconciliation.get_conditions()

    if fiscal_year:
        condition = condition.replace("company", "t1.company")
        condition += " and gl.fiscal_year = '%s'" % fiscal_year

    journal_entries = frappe.db.sql(
        """
        select
            "Journal Entry" as reference_type, t1.name as reference_name,
            t1.posting_date, t1.remark as remarks, t2.name as reference_row,
            t2.debit_in_account_currency as amount, t2.is_advance, t2.account, t2.party as 'supplier',
            t2.account_currency as currency, t1.remark, t1.cheque_no
        from
            `tabJournal Entry` t1, `tabJournal Entry Account` t2, `tabGL Entry` gl
        where
            t1.name = t2.parent and t1.docstatus = 1 and t2.docstatus = 1
            and t2.party_type = 'Supplier' and t2.party in %(party)s
            and t2.party_type = gl.party_type
            and gl.voucher_no = t1.name
            and t2.debit_in_account_currency > 0 {condition}
            and (t2.reference_type is null or t2.reference_type = '' or
                (t2.reference_type in ('Sales Order', 'Purchase Order')
                    and t2.reference_name is not null and t2.reference_name != ''))
            and (CASE
                WHEN t1.voucher_type in ('Debit Note', 'Credit Note')
                THEN 1=1
                ELSE 1=1
            END)
        order by t1.posting_date
        """.format(**{"condition": condition}),
        {"party": party},
        as_dict=1,
    )

    return list(journal_entries)


def get_dr_or_cr_notes(party, fiscal_year=None):
    payment_reconciliation = frappe.new_doc("Payment Reconciliation")
    condition = payment_reconciliation.get_conditions()
    voucher_type = "Purchase Invoice"
    doc = qb.DocType(voucher_type)
    return_invoices = (
        qb.from_(doc)
        .select(ConstantColumn(voucher_type).as_("voucher_type"), doc.name.as_("voucher_no"))
        .where(
            (doc.docstatus == 1)
            & (doc.is_return == 1)
            & (IfNull(doc.return_against, "") == "")
        )
        .run(as_dict=True)
    )

    outstanding_dr_or_cr = []
    if return_invoices:
        ple_query = QueryPaymentLedger()
        return_outstanding = ple_query.get_voucher_outstandings(
            vouchers=return_invoices,
            get_payments=True,
        )

        for inv in return_outstanding:
            if inv.outstanding != 0:
                outstanding_dr_or_cr.append(
                    frappe._dict(
                        {
                            "reference_type": inv.voucher_type,
                            "reference_name": inv.voucher_no,
                            "amount": -(inv.outstanding_in_account_currency),
                            "posting_date": inv.posting_date,
                            "currency": inv.currency,
                            "supplier": inv.party,
                            "account": inv.account
                        }
                    )
                )
    return outstanding_dr_or_cr


def get_outstanding_invoices(party, fiscal_year=None, filters=None):
    outstanding_invoices = []
    precision = frappe.get_precision("Sales Invoice", "outstanding_amount") or 2

    held_invoices = frappe.db.sql(
        "select name from `tabPurchase Invoice` where release_date IS NOT NULL and release_date > CURDATE()",
        as_dict=1,
    )
    held_invoices = set(d["name"] for d in held_invoices)
    condition = ""
    if fiscal_year:
        condition = " and fiscal_year = '%s'" % fiscal_year
    invoice_list = frappe.db.sql(
        """
        select
            voucher_no, voucher_type, posting_date, due_date,
            ifnull(sum(credit_in_account_currency - debit_in_account_currency), 0) as invoice_amount,
            account_currency as currency, party as 'supplier', account
        from
            `tabGL Entry`
        where
            party_type = "Supplier" and party in %(party)s {condition}
            and credit_in_account_currency - debit_in_account_currency > 0
            and is_cancelled=0
            and ((voucher_type = 'Journal Entry'
                    and (against_voucher = '' or against_voucher is null))
                or (voucher_type not in ('Journal Entry', 'Payment Entry')))
        group by voucher_type, voucher_no
        order by posting_date, name""".format(condition=condition), {"party": tuple(party)},
        as_dict=True,
    )

    payment_entries = frappe.db.sql(
        """
        select against_voucher_type, against_voucher,
            ifnull(sum(debit_in_account_currency - credit_in_account_currency), 0) as payment_amount,
            party as 'supplier', account
        from `tabGL Entry`
        where party_type = "Supplier" and party in %(party)s {condition}
            and debit_in_account_currency - credit_in_account_currency > 0
            and against_voucher is not null and against_voucher != ''
            and is_cancelled=0
        group by against_voucher_type, against_voucher
    """.format(condition=condition),
        {"party": tuple(party)},
        as_dict=True,
    )

    pe_map = frappe._dict()
    for d in payment_entries:
        pe_map.setdefault((d.against_voucher_type, d.against_voucher), d.payment_amount)

    for d in invoice_list:
        cheque_no = ""
        if d.voucher_type == "Purchase Invoice":
            invoice = frappe.get_doc("Purchase Invoice", d.voucher_no)
            cheque_no = invoice.bill_no
        payment_amount = pe_map.get((d.voucher_type, d.voucher_no), 0)
        outstanding_amount = flt(d.invoice_amount - payment_amount, precision)
        if outstanding_amount > 0.5 / (10 ** precision):
            if (filters.get("outstanding_amt_greater_than") and not (filters.get("outstanding_amt_greater_than") <= outstanding_amount <= filters.get("outstanding_amt_less_than"))):
                continue

            if not d.voucher_type == "Purchase Invoice" or d.voucher_no not in held_invoices:
                entry = frappe._dict()
                if d.voucher_type == "Journal Entry":
                    entry = frappe.get_doc("Journal Entry", d.voucher_no)
                    cheque_no = entry.cheque_no
                outstanding_invoices.append(
                    frappe._dict(
                        {
                            "supplier": d.supplier,
                            "account": d.account,
                            "voucher_no": d.voucher_no,
                            "voucher_type": d.voucher_type,
                            "posting_date": d.posting_date,
                            "invoice_amount": flt(d.invoice_amount),
                            "payment_amount": payment_amount,
                            "outstanding_amount": outstanding_amount,
                            "due_date": d.due_date,
                            "currency": d.currency,
                            "remark": entry.remark,
                            "cheque_no": cheque_no
                        }
                    )
                )

    outstanding_invoices = sorted(
        outstanding_invoices, key=lambda k: k["due_date"] or getdate(nowdate())
    )

    return outstanding_invoices