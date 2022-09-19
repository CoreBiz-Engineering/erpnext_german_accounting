# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe, erpnext, json
from datetime import datetime
from frappe.utils import cstr, flt, fmt_money, formatdate, getdate, nowdate, cint, get_link_to_form
from frappe import msgprint, _, scrub
from frappe.model.naming import make_autoname, set_name_from_naming_options,make_autoname
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.accounts.utils import get_balance_on, get_account_currency
from erpnext.accounts.party import get_party_account
from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import get_party_account_based_on_invoice_discounting




def create_journal_entry(args):
    j_entry = frappe.new_doc("Journal Entry")

    debit_account = frappe.get_doc('Account', args.acc_soll)
    credit_account = frappe.get_doc('Account', args.acc_haben)
    tax_account = frappe.get_doc('Account', args.tax)

    if 'Kreditorenkonten' in debit_account.parent_account or 'Debitorenkonten' in debit_account.parent_account:
        party_account_name = frappe.get_value("Party Account", filters={"account": debit_account.name})
        party_account = frappe.get_doc("Party Account", party_account_name)
        create_journal_entry_account(j_entry, debit_account, debit=args.value, party_type=party_account.parenttype, party=party_account.parent, args=args)
        create_journal_entry_account(j_entry, credit_account, credit=args.voucher_netto_value)
        create_journal_entry_account(j_entry, tax_account, credit=args.tax_value)
    else:
        party_account_name = frappe.get_value("Party Account", filters={"account": credit_account.name})
        party_account = frappe.get_doc("Party Account", party_account_name)
        create_journal_entry_account(j_entry, credit_account, credit=args.value, party_type=party_account.parenttype, party=party_account.parent, args=args)
        create_journal_entry_account(j_entry, debit_account, debit=args.voucher_netto_value)
        create_journal_entry_account(j_entry, tax_account, debit=args.tax_value)

    if len(j_entry.accounts) <= 1:
        frappe.msg_print("Ups, hier ist etwas schief gegangen.\nBuchung beinhaltet nur eine Buchungszeile!")
        return

    j_entry.voucher_type = "Journal Entry"
    j_entry.posting_date = args.voucher_date
    j_entry.cheque_no = args.voucher_id
    j_entry.cheque_date = args.voucher_date
    j_entry.is_opening = "Yes" if args.is_opening else "No"
    j_entry.user_remark = args.posting_text
    j_entry.bill_no = args.voucher_id
    j_entry.bill_date = args.voucher_date

    dimension_list = frappe.get_list("Accounting Dimension", fields=["name", "fieldname"])
    dimension_list.append({"name": "Project", "fieldname": "project"})

    j_entry.save()


def create_journal_entry_account(j_entry, account, debit=0, credit=0, party_type="", party="", args={}):
    row = j_entry.append("accounts", {})
    row.account = account.name

    if party_type:
        row.party_type = party_type
        row.party = party
    if debit:
        row.debit_in_account_currency = debit
        row.debit = debit
    if credit:
        row.credit_in_account_currency = credit
        row.credit = credit

    if args:
        dimension_list = frappe.get_list("Accounting Dimension", fields=["name", "fieldname"])
        dimension_list.append({"name": "Project", "fieldname": "project"})
        for dimension in dimension_list:
            if args.get(dimension.get("fieldname")):
                get_accounting_dimension(row, dimension.get("fieldname"), args.get(dimension.get("fieldname")))

    return row


def get_accounting_dimension(row, dimension, dimension_name):
    if dimension == "service_contract":
        row.service_contract = dimension_name
    if dimension == "maintenance_contract":
        row.maintenance_contract = dimension_name
    if dimension == "maintenance_contract_various":
        row.maintenance_contract_various = dimension_name
    if dimension == "rental_server_contract":
        row.rental_server_contract = dimension_name
    if dimension == "cloud_and_hosting_contract":
        row.cloud_and_hosting_contract = dimension_name
    if dimension == "kostentraeger":
        row.kostentraeger = dimension_name
    if dimension == "project":
        row.project = dimension_name
    return row


def get_tax_code_data(args):
    # get taxinformation from db-doctype
    tax_data = frappe.get_value('Steuercodes', args.tax_code,
                                ['title', 'tax_code', 'account_ust', 'account_vst', 'tax_rate'],
                                as_dict=1)

    args.tax_rate = tax_data.get('tax_rate')
    if args.tax_kind == "US" or tax_data.get('tax_code') in ['326', '118']:
        args.acc_tax_us = tax_data.get('account_ust')
    if args.tax_kind == "VS" or tax_data.get('tax_code') in ['326', '118']:
        args.acc_tax_vs = tax_data.get('account_vst')
    if tax_data.get('tax_rate'):
        args.tax = ""
        for tax in ['acc_tax_us', 'acc_tax_vs']:
            if args.get(tax):
                tax_account = (
                        frappe.get_value('Account', filters={"account_number": args.get(tax)}, as_dict=1)).get(
                        'name')
                args.tax = tax_account
    return args


def calc_account_values(tax_data):
    # calculate the tax-, debit and credit value
    debit_value = 0.00
    tax_value = 0.00
    if tax_data.get('tax_rate') is None:
        debit_value = float(tax_data.get('value'))
    elif tax_data.get('tax_code')[:3] in ['326', '118']:
        tax_value = round(float(tax_data.get('value')) * (float(tax_data.get('tax_rate'))/100), 2)
        debit_value = float(tax_data.get('value'))
    elif float(tax_data.get('tax_rate')) != 0.00:
        debit_value = round((float(tax_data.get('value')) / (1+float(tax_data.get('tax_rate'))/100)), 2)
        tax_value = float(tax_data.get('value')) - debit_value
        # tax_value = round(float(tax_data.get('value')) * (float(tax_data.get('tax_rate'))/100),2)
        # debit_value = float(tax_data.get('value')) - tax_value

    tax_data['tax_value'] = round(tax_value, 2)
    tax_data['debit_value'] = round(debit_value, 2)

    return tax_data


@frappe.whitelist()
def change_event_value(value, tax_kind, tax_code):

    data = frappe._dict(
        {
            'value': value.replace('.', '').replace(',', '.'),
            'tax_kind': tax_kind,
            'tax_code': tax_code
        })

    # fuer EG-Buchungen, die VS und US Konten buchen und Netto = Brutto ist
    if tax_code[:3] in ['326', '118']:
        data = get_tax_code_data(data)
        res = calc_account_values(data)
        return {'tax_value': res.get('tax_value'), 'debit_value': value}
    if value and tax_code and tax_kind:
        if tax_kind != '0':
            data = get_tax_code_data(data)
        res = calc_account_values(data)
        return {'tax_value': res.get('tax_value'), 'debit_value': res.get('debit_value')}
    else:
        return


@frappe.whitelist()
def generate_journal_entries(**args):
    args = frappe._dict(args)

    args.company = frappe.db.get_single_value("Global Defaults", "default_company")
    args.voucher_date = datetime.strptime(args.voucher_date, '%d.%m.%Y').strftime('%Y-%m-%d')
    if args.due_date:
        args.due_date = datetime.strptime(args.due_date, '%d.%m.%Y').strftime('%Y-%m-%d')
    # reformat the integer from frontend
    if "," in args.value:
        args.value = args.value.replace('.', '').replace(',', '.')
    if "," in args.voucher_netto_value:
        args.voucher_netto_value = args.voucher_netto_value.replace('.', '').replace(',', '.')
    if "," in args.tax_value:
        args.tax_value = args.tax_value.replace('.', '').replace(',', '.')

    # get the tax-account data/name
    if not args.tax_kind:
        args.tax_kind = '0'

    if args.tax_kind != '0':
        args = get_tax_code_data(args)

    create_journal_entry(args)

    return


def get_account_total_amount(account, fiscal_year):
    sel = """
            select
                name, account, posting_date, fiscal_year, credit, debit
            from
                `tabGL Entry`
            where
                account = '{account}'
                and fiscal_year = '{fiscal_year}'
                and posting_date <= CURRENT_TIMESTAMP()
            """.format(account=account, fiscal_year=fiscal_year)

    entries = frappe.db.sql(sel, as_dict=1)
    return entries


@frappe.whitelist()
def calc_account_total_amount(account, fiscal_year):

    acc_total = 0
    if account:
        if not fiscal_year:
            fiscal_year = datetime.now().year
        entries = get_account_total_amount(account, fiscal_year)

        for entry in entries:
            acc_total += entry.get('debit')
            acc_total -= entry.get('credit')

    return {'value': frappe.format_value(acc_total, {'fieldtype': 'Currency'})}