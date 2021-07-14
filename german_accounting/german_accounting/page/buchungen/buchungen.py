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




def create_gl_entry(data, values):

    hash = make_autoname(key='hash', doctype='Journal Entry', doc=data.get('doc'))

    gl_entry = frappe.get_doc({
        'doctype': 'GL Entry',
    })
    sql =   """
            insert into `tabGL Entry` (
                name,
                creation,
                modified,
                modified_by,
                owner,
                docstatus,
                debit_in_account_currency,
                credit_in_account_currency,
                cost_center,
                account,
                is_advance,
                fiscal_year,
                voucher_type,
                company,
                debit,
                voucher_no,
                against,
                account_currency,
                remarks,
                credit,
                posting_date
            ) values (
                "{hash}",
                CURRENT_TIMESTAMP(),
                CURRENT_TIMESTAMP(),
                "{modified_by}",
                "{owner}",
                1,
                {debit},
                {credit},
                "{cost_center}",
                "{account}",
                "No",
                {fiscal_year},
                "Journal Entry",
                "{company}",
                {debit},
                "{voucher_no}",
                "{a_account}",
                "EUR",
                "{posting_text}",
                {credit},
                STR_TO_DATE("{posting_date}","%Y-%m-%d") 
            )
            """.format(naming_series=data.get('name'), modified_by=data.get('user'), owner=data.get('user'),
                       debit=values.get('debit'), credit=values.get('credit'), a_account=values.get('a_account'),
                       account=values.get('account'), hash=hash, cost_center="Haupt - LISen",
                       posting_text=data.get('posting_text'), posting_date=data.get('voucher_date')[:10],
                       fiscal_year=data.get('fiscal_year'), company=data.get('company'), voucher_no=data.get('name'))

    frappe.db.sql(sql)

    return

def create_journal_entry_account(data):

    journal_entry_account = []
    for elem in data:
        if elem in ['acc_soll', 'acc_haben', 'acc_tax_vs', 'acc_tax_us']:
            # create hash for naming in DB without naming_series
            hash = make_autoname(key='hash', doctype='Journal Entry', doc=data.get('doc'))
            credit = 0.00
            debit = 0.00
            idx = 0
            account = ''
            a_account = ''
            #setting params
            if data.get('tax_code')[:3] in ['326', '118']:
                if elem == 'acc_tax_vs':
                    debit = data.get('tax_value')
                    account = data.get('acc_tax_vs')
                    a_account = data.get('acc_haben')
                elif elem == 'acc_tax_us':
                    credit = data.get('tax_value')
                    account = data.get('acc_tax_us')
                    a_account = data.get('acc_haben')
                elif elem == 'acc_haben':
                    credit = data.get('value')
                    account = data.get(elem)
                    a_account = data.get('acc_soll')+', '+data.get('acc_haben')
                elif elem == 'acc_soll':
                    debit = data.get('value')
                    account = data.get(elem)
                    a_account = data.get('acc_haben')
            else:
                if data.get('tax_kind') == 'US':
                    if elem == 'acc_soll':
                        debit = data.get('value')
                        account = data.get(elem)
                        a_account = data.get('acc_haben')
                        idx = 1
                    elif elem == 'acc_haben':
                        credit = data.get('debit_value')
                        account = data.get(elem)
                        a_account = data.get('acc_soll')+', '+data.get('acc_haben')
                        idx = 3
                    elif elem == 'acc_tax_us':
                        credit = data.get('tax_value')
                        account = data.get('acc_tax_us')
                        a_account = data.get('acc_haben')
                        idx = 2
                elif data.get('tax_kind') == 'VS':
                    if elem == 'acc_soll':
                        debit = data.get('debit_value')
                        account = data.get(elem)
                        a_account = data.get('acc_haben')
                    elif elem == 'acc_haben':
                        credit = data.get('value')
                        account = data.get(elem)
                        a_account = data.get('acc_soll')+', '+data.get('acc_haben')
                        idx = 3
                    elif elem == 'acc_tax_vs':
                        debit = data.get('tax_value')
                        account = data.get('acc_tax_vs')
                        a_account = data.get('acc_haben')
                        idx = 2
                elif data.get('tax_kind') == '0':
                    if elem == 'acc_soll':
                        debit = data.get('value')
                        account = data.get(elem)
                        a_account = data.get('acc_haben')
                        idx = 1
                    elif elem == 'acc_haben':
                        credit = data.get('value')
                        account = data.get(elem)
                        a_account = data.get('acc_soll')+', '+data.get('acc_haben')
                        idx = 2
            idx = len(journal_entry_account) + 1
            values = {'debit_in_account_currency': debit, 'credit_in_account_currency': credit, 'account': account,
                      'a_account': a_account, 'idx': 1}

            account_information = frappe.get_value('Account', account,
                                                   ['name', 'parent_account', 'account_number', 'report_type'], as_dict=1)

            if 'Kreditorenkonten' in account_information.get('parent_account'):
                sql = '''select name from `tabSupplier` 
                                            where name like "%{acc_no}"'''.format(
                    acc_no=account_information.get('account_number'))

                supplier = frappe.db.sql(sql, as_dict=1)[0]
                values['party_type'] = 'Supplier'
                values['party'] = supplier.get('name')
            elif 'Debitorenkonten' in account_information.get('parent_account'):
                sql = '''select name from `tabCustomer` 
                            where name like "%{acc_no}"'''.format(acc_no=account_information.get('account_number'))
                customer = frappe.db.sql(sql, as_dict=1)[0]
                values['party_type'] = 'Customer'
                values['party'] = customer.get('name')

            #'parent_account': 'Kreditorenkonten - L
            #'party_type': 'Supplier', 'party': 'LC-LI71002'
            if data.get('cost_center'):
                values['cost_center'] = data.get('cost_center')
            if data.get('accounting_dimension') and account_information.get('report_type') == 'Profit and Loss':
                values['kostentraeger'] = data.get('accounting_dimension')
                values['idx'] = 2
            if data.get('project') and account_information.get('report_type') == 'Profit and Loss':
                values['project'] = data.get('project')

            journal_entry_account.append(values)

    return(journal_entry_account)

def get_tax_code_data(data):
    #get taxinformation from db-doctype
    tax_data = frappe.get_value('Steuercodes', data.get('tax_code'),
                                ['title', 'tax_code', 'account_ust', 'account_vst', 'tax_rate'],
                                as_dict=1)

    data['tax_rate'] = tax_data.get('tax_rate')
    if data.get('tax_kind') == "US" or tax_data.get('tax_code') in ['326', '118']:
        data['acc_tax_us'] = tax_data.get('account_ust')
    if data.get('tax_kind') == "VS" or tax_data.get('tax_code') in ['326', '118']:
        data['acc_tax_vs'] = tax_data.get('account_vst')

    for tax in ['acc_tax_us', 'acc_tax_vs']:
        if data.get(tax):
            try:
                tax_account = (
                    frappe.get_value('Account', filters={"account_number": data.get(tax)}, as_dict=1)).get(
                    'name')
                data[tax] = tax_account
            except:
                data[tax] = ''

    return data

def calc_account_values(tax_data):
    """
    calculate the tax-, debit and credit value
    """

    if tax_data.get('tax_rate') is None:
        debit_value = float(tax_data.get('value'))
        tax_value = 0.00
    elif tax_data.get('tax_code')[:3] in ['326', '118']:
        tax_value = round(float(tax_data.get('value')) * (float(tax_data.get('tax_rate'))/100), 2)
        debit_value = float(tax_data.get('value'))
        pass
    elif float(tax_data.get('tax_rate')) != 0.00:

        debit_value = round((float(tax_data.get('value')) / (1+float(tax_data.get('tax_rate'))/100)), 2)
        tax_value = float(tax_data.get('value')) - debit_value
        # tax_value = round(float(tax_data.get('value')) * (float(tax_data.get('tax_rate'))/100),2)
        # debit_value = float(tax_data.get('value')) - tax_value

    tax_data['tax_value'] = round(tax_value, 2)
    tax_data['debit_value'] = round(debit_value, 2)

    return tax_data

def create_journal_entry(data, entry_account):

    journal_entry = frappe.get_doc({
        'doctype': 'Journal Entry',
        'voucher_type':'Journal Entry',
        'modified_by':data.get('user'),
        'company':data.get('company'),
        'total_debit':data.get('value'),
        'total_credit':data.get('value'),
        'remark':data.get('posting_text'),
        'cheque_no':data.get('voucher_id'),
        'is_opening': data.get('is_opening'),
        'bill_no':data.get('voucher_id'),
        'posting_date': data.get('voucher_date'),
        'bill_date':data.get('voucher_date'),
        'cheque_date':data.get('voucher_date'),
        'user_remark':data.get('posting_text'),
        'accounts': entry_account
    })

    if data.get('due_date'):
        journal_entry.set('due_date', data.get('due_date'))

    journal_entry.insert()
    #journal_entry.submit()
    #journal_entry.save()
    return

def update_invoice(doc_data):

    invoice = {}

    if len(doc_data.get('voucher_id')) == 14:
        invoice = frappe.get_doc("Sales Invoice",doc_data.get('voucher_id'))
    else:
        sql =   '''
                select name, naming_series
                from tabSales Order
                where name like "%{voucher_no}"
                '''.format(voucher_no=doc_data.get('voucher_id'))
        frappe.db.sql(sql)

    if invoice:
        if invoice.status == 'Paid':
            return
        #'Payment Entry Reference'
        #
        #Reference No and Reference Date is mandatory for Bank transaction
        #'''
        else:
            payment = frappe.get_doc({
                'doctype': 'Payment Entry',
                'payment_type': 'Receive',
                'base_paid_amount': invoice.outstanding_amount,
                'party_type': 'Customer',
                'title': invoice.customer,
                'base_total_allocated_amount': doc_data.get('value'),
                'paid_to': doc_data.get('acc_soll'),
                'reference_no': invoice.name,
                'party_name': invoice.customer,
                'paid_to_account_currency': 'EUR',
                'party': invoice.customer,
                'reference_date': doc_data.get('voucher_date'),
                'total_allocated_amount': '',
                'paid_from': doc_data.get('acc_haben'),
                'received_amount': doc_data.get('value'),
                'paid_amount': doc_data.get('value'),
                'company': invoice.company,
                'kostentraeger': invoice.kostentraeger,
                'references': [{'reference_doctype': 'Sales Invoice',
                                'reference_name': invoice.name,
                                'due_date': invoice.due_date,
                                'bill_no': invoice.name,
                                'total_amount': invoice.grand_total,
                                'outstanding_amount': invoice.outstanding_amount,
                                'allocated_amount': doc_data.get('value')}]
                })
            #insert Eintrag
            payment.insert()
            #submit Eintrag
            payment.submit()

@frappe.whitelist()
def change_event_value(value, tax_kind, tax_code):

    data = {'value': value.replace('.', '').replace(',', '.'),
            'tax_kind': tax_kind,
            'tax_code': tax_code}

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
def generate_journal_entries(user, acc_soll,voucher_id, voucher_date, acc_haben, value, tax_kind, tax_code,
                             country_code, tax_value, posting_text, fiscal_year, voucher_netto_value, booking_type,
                             is_opening, cost_center, accounting_dimension, project, due_date):
    #get the metadata from doctype
    doc = frappe.get_meta('Journal Entry')

    # generate autokey depending on "naming_series":
    key = 'ACC-JV-.YYYY.-'
    naming_series = make_autoname(key=key, doctype='Journal Entry', doc=doc)
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    voucher_date = datetime.strptime(voucher_date, '%d.%m.%Y').strftime('%Y-%m-%d')
    if due_date:
        due_date = datetime.strptime(due_date, '%d.%m.%Y').strftime('%Y-%m-%d')
    #map data from Frontend
    doc_data = {
        "name": naming_series,
        "user": user,
        "acc_soll": acc_soll,
        "voucher_id": voucher_id,
        "voucher_date": voucher_date,
        "acc_haben": acc_haben,
        "value":value.replace('.','').replace(',','.'),
        "tax_kind":tax_kind,
        "tax_code": tax_code,
        "company": company,
        "debit_value": voucher_netto_value,
        "country_code": country_code,
        "tax_value": tax_value,
        "posting_text": posting_text,
        "fiscal_year": fiscal_year,
        "naming_series_key": key,
        "cost_center": cost_center,
        "accounting_dimension": accounting_dimension,
        "project": project,
        "due_date": due_date,
        "doc": doc}

    doc_data['is_opening'] = 'Yes' if is_opening == '1' else 'No'

    if booking_type == 'Ausgangsrechnung':
        update_invoice(doc_data)
    else:
        # get the tax-account data/name
        if doc_data.get('tax_kind'):
            pass
        else:
            doc_data['tax_kind'] = '0'

        if doc_data.get('tax_kind') != '0':
            doc_data = get_tax_code_data(doc_data)

        entry_account = create_journal_entry_account(doc_data)
        create_journal_entry(doc_data, entry_account)

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
            """.format(account = account, fiscal_year=fiscal_year)

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
