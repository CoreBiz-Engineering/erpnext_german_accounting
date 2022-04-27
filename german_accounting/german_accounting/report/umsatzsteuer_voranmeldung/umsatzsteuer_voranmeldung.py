# coding: utf-8
# Copyright (c) 2020, LIS Engineering and contributors
# For license information, please see license.txt
'''
Provide a report for the german Umsatzsteuervoranmeldung
'''

from __future__ import unicode_literals
import json
from datetime import datetime
from six import string_types
import frappe
from frappe import _

def execute(filters=None):
    """Entry point for frappe."""
    result = {}
    print("FILTERS: ", filters)
    validate_filters(filters)
    if filters.get('view') == 'Kontenansicht':
        result = get_kontenansicht(filters)

    elif filters.get('view') == 'Kurzansicht':
        result = get_kurzansicht(filters)

    columns = get_columns()
    result = sorted(result, key=lambda k: k['row'])

    return columns, result

def validate_filters(filters):
    """Make sure all mandatory filters are present."""
    if not filters.get('company'):
        frappe.throw(_('{0} is mandatory').format(_('Company')))

    if not filters.get('from_date'):
        frappe.throw(_('{0} is mandatory').format(_('From Date')))

    if not filters.get('to_date'):
        frappe.throw(_('{0} is mandatory').format(_('To Date')))

def get_columns():
    """Return the list of columns that will be shown in query report."""
    columns = [
        {
            "label": "Zeile",
            "fieldname": "row",
            "fieldtype": "Data",
        },
        {
            "label": "account",
            "fieldname": "account_number",
            "fieldtype": "Data",
        },
        {
            "label": "name",
            "fieldname": "account_name",
            "fieldtype": "Data",
            "width": 500,
        },
        {
            "label": "KZ",
            "fieldname": "mark",
            "fieldtype": "Data",
        },
        {
            "label": "S/H",
            "fieldname": "s_h",
            "fieldtype": "Data",

        },
        {
            "label": "Umsatz",
            "fieldname": "account_value",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "KZ",
            "fieldname": "tax_mark",
            "fieldtype": "Data",
        },
        {
            "label": "Steuer",
            "fieldname": "tax_value",
            "fieldtype": "Currency",
            "width": 120,
        }
    ]

    return columns

def get_mark_header(gl_entries):
    # TODO: create this as a DocType for better maintenance
    # key = Kennzeichen; value = Beschreibung
    header = {  "41": "Innergemeinschaftliche Lieferung (§ 4 Nr. 1 Buchst. b UStG) an Abnehmer mit USt-IdNr.",
                "44": "Innergemeinschaftliche Lieferungen neuer Fahrzeuge an Abnehmer ohne USt-IdNr.",
                "43": "Weitere steuerfreie Umsätze mit Vorsteuerabzug (z. B. Ausfuhrlieferungen Umsätze nach § 4 Nr. 2 bis 7 UStG)",
                "48": "z. B.Umsätze nach § 4 Nr. 8 bis 28 UStG",
                "81": "zum Steuersatz von 19 %",
                "86": "zum Steuersatz von 7 %",
                "35": "zu anderen Steuersätzen",
                "77": "Lieferungen land- und forstwirtschaftlicher Betriebe nach § 24 UStG an Abnehmer mit USt-IdNr.",
                "76": "Umsätze, für die eine Steuer nach § 24 UStG zu entrichten ist (Sägewerkserzeugnisse, Getränke und alkohol. Flüssigkeiten, z. B. Wein)",
                "91": "Erwerbe nach §§ 4b UStG und 25c UStG",
                "89": "zum Steuersatz von 19 %",
                "93": "zum Steuersatz von 7 %",
                "95": "zu anderen Steuersätzen",
                "94": "neuer Fahrzeuge (§ 1b Abs. 2 und 3 UStG) von Lieferern ohne USt-IdNr. zum allgemeinen Steuersatz",
                "42": "Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften (§ 25b UStG)",
                "60": "Steuerpflichtige Umsätze, für die der Leistungsempfänger die Steuer nach § 13b Abs. 5 UStG schuldet",
                "21": "Nicht steuerbare sonstige Leistungen gem. § 18b Satz 1 Nr. 2 UStG",
                "45": "Übrige nicht steuerbare Umsätze (Leistungsort nicht im Inland)",
                "46": "Steuerpflichtige sonstige Leistungen eines im übrigen Gemeinschaftsgebiet ansässigen Unternehmers (§13b Abs. 1 UStG)",
                "73": "Umsätze, die unter das GrEStG fallen (§ 13b Abs. 2 Nr. 3 UStG)",
                "84": "Andere Leistungen (§ 13b Abs. 2 Nr. 1, 2, 4 und 11 UStG)",
                "66": "Vorsteuerbeträge aus Rechnungen von anderen Unternehmern (§ 15 Abs. 1 Satz 1 Nr. 1 UStG) und aus\nLeistungen im Sinne des § 13a Abs. 1 Nr. 6 UStG (§ 15 Abs. 1 Satz 1 Nr. 5 UStG) und aus\ninnergemeinschaftlichen Dreiecksgeschäften (§ 25b Abs. 5 UStG)",
                "61": "Vorsteuerbeträge aus dem innergemeinschaftlichen Erwerb von Gegenständen (§ 15 Abs. 1 Satz 1 Nr. 3 UStG)",
                "62": "Entstandene Einfuhrumsatzsteuer (§ 15 Abs. 1 Satz 1 Nr. 2 UStG)",
                "67": "Vorsteuerbeträge aus Leistungen im Sinne des § 13b UStG (§ 15 Abs. 1 Satz 1 Nr. 4 UStG)",
                "63": "Vorsteuerbeträge, die nach allgemeinen Durchschnittssätzen berechnet sind (§§ 23 und 23a UStG)",
                "64": "Berichtigung des Vorsteuerabzugs (§ 15a UStG)",
                "59": "Vorsteuerabzug für innergemeinschaftliche Lieferungen neuer Fahrzeuge außerhalb eines Unternehmens (§2a UStG) sowie von Kleinunternehmern im Sinne des § 19 Abs. 1 UStG (§ 15 Abs. 4a UStG)",
                "65": "Steuer infolge Wechsels der Besteuerungsform sowie Nachsteuer auf versteuerte Anzahlungen u. ä. wegen Steuersatzänderung",
                "69": "Andere Steuerbeträge - in Rechnungen unrichtig oder unberechtigt ausgewiesene Steuerbeträge (§ 14c UStG) sowie Steuerbeträge, die nach § 6a Abs. 4 Satz 2, § 17 Abs. 1 Satz 6, § 25b Abs. 2 UStG oder von einem Auslagerer oder Lagerhalter nach § 13a Abs. 1 Nr. 6 UStG geschuldet werden",
                "39": "Abzug der festgesetzten Sondervorauszahlung für Dauerfristverlängerung (in der Regel nur in der letzten Voranmeldung des Besteuerungszeitraums auszufüllen)"
            }

    res = []
    marks_list = []

    for entry in gl_entries:
        if entry.get('mark') not in marks_list:
            res.append({'row': entry.get('row'), 'sort': str(int(entry.get('row'))-1)+'.9', 'kz': entry.get('mark'),
                        'account_name': header.get(entry.get('mark'))})
            marks_list.append(entry.get('mark'))
    return res

def get_gl_entries(filters):
    query = """
            select
                acc.account_number,
                acc.tax_rate,
                acc.account_type,
                gl.account as account_name,
                sum(gl.debit) as debit,
                sum(gl.credit) as credit
            from
                `tabGL Entry` gl,
                `tabAccount` acc,
                `tabUStVA` ust
            where
                gl.account = acc.name
                and acc.account_number = ust.account_number
                and gl.posting_date >= str_to_date('{dvon}', '%Y-%m-%d')
                and gl.posting_date <= str_to_date('{dbis}', '%Y-%m-%d')
            group by
                gl.account,
                acc.account_number
            """ .format(dvon=filters.get('from_date'), dbis=filters.get('to_date'))
    gl_entries = frappe.db.sql(query, as_dict=1)

    for elem in gl_entries:
        elem['root_account_value'] = round(elem.get('debit') - elem.get('credit'),2)
        sum = round(elem.get('debit') - elem.get('credit'),2)
        if sum < 0:
            elem['s_h'] = 'H'
            elem['account_value'] = elem.get('root_account_value') * (-1)
        elif sum > 0:
            elem['s_h'] = 'S'
            elem['account_value'] = elem.get('root_account_value')
        else:
            elem['s_h'] = ''

    return gl_entries

def get_account_settings(data):

    accounts = []
    for elem in data:
        accounts.append(elem.get('account_number'))

    account_data = []
    if accounts:
        if len(accounts) > 1:
            acc_nr = 'account_number in {0}'.format(tuple(accounts))
        else:
            acc_nr = 'account_number = {0}'.format(accounts[0])
        #account_number in {0}
        sel =   '''
                select 
                    account_number,
                    tax,
                    mark,
                    row,
                    row as sort,
                    tax_mark
                from
                    `tabUStVA`
                where
                    {0}
                '''.format(acc_nr)
        account_data = frappe.db.sql(sel, as_dict=1)

    return account_data

def get_right_tax(entry):
    if entry.get('tax_rate') and entry.get('account_type') == 'Tax':
        tax = float(entry.get('tax_rate')) / 100
    elif entry.get('tax'):
        if int(entry.get('tax')) > 1:
            tax = float(entry.get('tax')) / 100
        else:
            # default tax value
            tax = 0.19
    else:
        # default tax value
        tax = 0.19

    return tax

def calc_group_sum(gl_entries):
    mark_list = []
    for mark in gl_entries:
        if mark.get('mark') not in mark_list:
            mark_list.append(mark.get('mark'))
    print(mark_list)
    res = []
    tax_res = 0
    for mark in mark_list:
        sum = 0
        tax_sum = 0
        row = ''
        for account in gl_entries:
            if account.get('mark') == mark:
                row = account.get('row')
                # check if tax_rate is given
                tax = get_right_tax(account)
                if account.get('mark') == account.get('tax_mark') or mark in ['81']:
                    sum += account.get('root_account_value')
                    tax_sum += account.get('root_account_value') * tax
                    tax_res += account.get('root_account_value') * tax
                else:
                    sum += account.get('root_account_value')
                    if account.get('tax') and account.get('tax_mark'):
                        tax_sum += account.get('root_account_value') * tax
                        tax_res += account.get('root_account_value') * tax

        if sum < 0 or tax_sum < 0:
            s_h = 'H'
            sum = sum * (-1)
            tax_sum = tax_sum * (-1)
        elif sum > 0 or tax_sum > 0:
            s_h = 'S'
        else:
            s_h = ''

        if row == '59':
            res.append(
                {
                    'row': row,
                    's_h': s_h,
                    'sort': str(row) + '.1',
                    'account_number': 'Summe',
                    'account_value': round(sum, 2),
                    'tax_value': round(sum, 2)
                }
            )
            tax_res += round(sum, 2)
        else:
            res.append(
                {
                    'row': row,
                    's_h': s_h,
                    'sort': str(row)+'.1',
                    'account_number': 'Summe',
                    'account_value': int(sum), # round to 0 because of the of the origin report
                    'tax_value': round(tax_sum,2)
                }
            )
    if res:
        # aktuell wird Vorsteuer minus Umsatzsteuer gerechnet
        # korrekt wird aber Umsatzsteuer minus Vorsteuer gerechnet
        # wird aktuell duch Vorzeichenkorrektur behoben
        tax_res = tax_res * (-1)
        res.append(
            {
                'row': '66',
                'sort': '66',
                'account_name': 'Umsatzsteuer-Vorauszahlung/Überschuss',
                'tax_value': tax_res
            }
        )

    return res

def get_kontenansicht(filters):
    "Function to get the detailed-view of all accounts from the ustva"
    to_date = datetime.strptime(filters.get('to_date'), "%Y-%m-%d").date()
    res = []
    gl_entries = get_gl_entries(filters)
    # 1781 kann vor Dezember gebucht werden, darf jedoch nur im Dezember angezeigt werden
    # deswegen die Überprüfung
    if to_date.month < 12:
        gl_entries = [entry for entry in gl_entries if not (entry['account_number'] == '1781')]
    elif to_date.month == 12:
        account_numbers = []
        for entry in gl_entries:
            account_numbers.append(entry.get('account_number'))

        if '1781' not in account_numbers:
            sql =   """
                    select
                        acc.account_number,
                        acc.tax_rate,
                        acc.account_type,
                        gl.account as account_name,
                        sum(gl.debit) as debit,
                        sum(gl.credit) as credit
                    from
                        `tabGL Entry` gl,
                        `tabAccount` acc,
                        `tabUStVA` ust
                    where
                        gl.account = acc.name
                        and acc.account_number = ust.account_number
                        and gl.fiscal_year = '{year}'
                        and acc.account_number = '1781'
                    group by
                        gl.account,
                        acc.account_number
                    """.format(year=to_date.year)

            acc_1781 = frappe.db.sql(sql, as_dict=1)
            for elem in acc_1781:
                elem['root_account_value'] = round(elem.get('debit') - elem.get('credit'), 2)
                sum = round(elem.get('debit') - elem.get('credit'), 2)
                if sum < 0:
                    elem['s_h'] = 'H'
                    elem['account_value'] = elem.get('root_account_value') * (-1)
                elif sum > 0:
                    elem['s_h'] = 'S'
                    elem['account_value'] = elem.get('root_account_value')
                else:
                    elem['s_h'] = ''
            if acc_1781:
                gl_entries += acc_1781
    account_settings = get_account_settings(gl_entries)

    for account in gl_entries:
        for setting in account_settings:
            if setting.get('account_number') == account.get('account_number'):
                account.update(setting)

    mark_header = get_mark_header(gl_entries)
    res += mark_header

    group_sum = calc_group_sum(gl_entries)
    res += group_sum

    for entry in gl_entries:
        tax = get_right_tax(entry)

        if (entry.get('tax') or entry.get('tax_mark')) and entry.get('account_value'):
            try:
                entry['tax_value'] = round(entry.get('account_value') * tax,2)
            except:
                print('##################### ERROR #####################')
                print(entry)
        if entry.get('mark') == entry.get('tax_mark'):
            entry.pop('account_value')
            entry.pop('mark')

    res += gl_entries
    res = sorted(res, key=lambda k: k['sort'])
    return res

def get_kurzansicht(filters):
    "Function to get the short-view of the ust-va"
    gl_entries = get_gl_entries(filters)
    short_result = []

    account_settings = get_account_settings(gl_entries)
    for account in gl_entries:
        for setting in account_settings:
            if setting.get('account_number') == account.get('account_number'):
                account.update(setting)

    mark_header = get_mark_header(gl_entries)
    group_sum = calc_group_sum(gl_entries)

    short_result += mark_header
    short_result += group_sum

    return short_result
