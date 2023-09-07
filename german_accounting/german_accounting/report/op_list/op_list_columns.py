# -*- coding: utf-8 -*-
# Copyright (c) 2013, LIS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe, erpnext, json
from datetime import datetime
from frappe.utils import cstr, flt, fmt_money, formatdate, getdate, nowdate, cint, get_link_to_form
from frappe import msgprint, _, scrub

def get_customer_columns():
    columns = [
        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Data",
        },
        {
            "label": _("Customer Name"),
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": "250px",
        },
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 120},
        {"label": _("Voucher Type"), "fieldname": "voucher_type_hidden", "hidden": 1, "width": 120},
        {
            "label": _("Voucher No"),
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type_hidden",
            "width": 180,
        },
        {
            "label": _("Voucher No"),
            "fieldname": "cheque_no",
            "fieldtype": "Data",
            "width": "75px",
        },
        {
            "label": "B. Datum",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": "75px",
        },
        {
            "label": "F&auml;lligkeit",
            "fieldname": "due_date",
            "fieldtype": "Date",
            "width": "75px",
        },
        {
            "label": "&Uuml;berf&auml;llig",
            "fieldname": "over_due",
            "fieldtype": "Data",
            "width": "60px",
        },
        {
            "label": _("Invoiced Amount"),
            "fieldname": "invoiced_amount",
            "fieldtype": "Currency",
            "width": "75px",
        },
        {
            "label": _("Payment Amount"),
            "fieldname": "payment_amount",
            "fieldtype": "Currency",
            "width": "75px",
        },
        {
            "label": _("Paid Amount"),
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": "75px",
        },
        {
            "label": _("Outstanding Amount"),
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "width": "75px",
        }
    ]
    return columns


def get_supplier_columns():
    columns = [
        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Data",
            "width": 200
        }, {
            "label": _("Supplier Name"),
            "fieldname": "supplier_name",
            "fieldtype": "Data",
        },
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 120},
        {"label": _("Voucher Type"), "fieldname": "voucher_type_hidden", "width": 120},
        {
            "label": _("Voucher No"),
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type_hidden",
        }, {
            "label": _("Remark"),
            "fieldname": "remark",
            "fieldtype": "Data",
        }, {
            "label": _("Voucher No"),
            "fieldname": "cheque_no",
            "fieldtype": "Data",
            "width": 200
        }, {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": "90px",
        }, {
            "label": _("Soll"),
            "fieldname": "debit",
            "fieldtype": "Currency",
        }, {
            "label": _("Haben"),
            "fieldname": "credit",
            "fieldtype": "Currency",
        }, {
            "label": _("Paid Amount"),
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
        }, {
            "label": _("Outstanding Amount"),
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
        }
    ]
    return columns