# Copyright (c) 2013, LIS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
import json
import time, datetime
from frappe import _, scrub
from frappe.utils import getdate, nowdate, flt, cint, formatdate, cstr, now, time_diff_in_seconds
from collections import OrderedDict
from erpnext.accounts.utils import get_currency_precision
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
from .bank_file_reader import read_csv_file
from .op_supplier import get_supplier_data
from erpnext.accounts.party import get_party_details


def execute(filters=None):
    if filters.get("attach"):
        return read_csv_file(filters.get("attach"))
    else:
        args = {
            "party_type": "Customer",
            "naming_by": ["Selling Settings", "cust_master_name"],
        }

        if filters.get('party_type') in ["Customer", "Kunde"]:
            args = {"party_type": "Customer"}
        elif filters.get('party_type') in ["Supplier", "Lieferant"]:
            return get_supplier_data(supplier_list=filters.get('party'), fiscal_year=filters.get('fiscal_year'))
        else:
            args = {}
        return ReceivableSumCustomerReport(filters).run(args)

class ReceivableSumCustomerReport(object):
    def __init__(self, filters=None):
        self.data = []
        self.columns = []
        self.filters = frappe._dict(filters or {})
        self.filters.report_date = getdate(self.filters.report_date or nowdate())
        self.age_as_on = getdate(nowdate()) if self.filters.report_date > getdate(nowdate()) else self.filters.report_date

    def run(self, args):
        self.dunning_columns = []
        self.filters.update(args)
        self.set_defaults()
        self.get_data()
        data = sorted(self.data, key=lambda k: ("order_count" not in k, k.get("order_count", None), "posting_date" not in k, k.get("posting_date", None)))
        self.columns = self.columns + self.dunning_columns
        return self.columns, data

    def set_defaults(self):
        if not self.filters.get("company"):
            self.filters.company = frappe.db.get_single_value('Global Defaults', 'default_company')
        self.company_currency = frappe.get_cached_value('Company', self.filters.get("company"), "default_currency")
        self.currency_precision = get_currency_precision() or 2
        self.dr_or_cr = "debit" if self.filters.party_type == "Customer" else "credit"
        self.party_type = self.filters.party_type
        self.party_details = {}
        self.invoices = set()

    def get_columns_invoice(self):
        """Return the list of columns that will be shown in query report."""
        self.columns = [
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
            {"label": _("Voucher Type"), "fieldname": "voucher_type_hidden", "hidden": 1, "width": 120},
            {
                "label": _("Voucher No"),
                "fieldname": "voucher_no",
                "fieldtype": "Dynamic Link",
                "options": "voucher_type_hidden",
                "width": 180,
            },
            {
                "label": _("Reference Number"),
                "fieldname": "cheque_no",
                "fieldtype": "Data",
                "width": "75px",
            },
            {
                "label": _("Posting Date"),
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
                "hidden": 1
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

    def get_columns_supplier(self):
        self.columns = [
            {
                "label": _("Account"),
                "fieldname": "account",
                "fieldtype": "Data",
                "width": "100px",
            }, {
                "label": _("Against Account"),
                "fieldname": "against",
                "fieldtype": "Data",
                "width": "75px",
            }, {
                "label": _("Supplier Name"),
                "fieldname": "supplier_name",
                "fieldtype": "Data",
            },
            {"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 120},
            {"label": _("Voucher Type"), "fieldname": "voucher_type_hidden", "hidden": 1, "width": 120},
            {
                "label": _("Voucher No"),
                "fieldname": "voucher_no",
                "fieldtype": "Dynamic Link",
                "options": "voucher_type_hidden",
                "width": 180,
            }, {
                "label": _("Remark"),
                "fieldname": "remark",
                "fieldtype": "Data",
                "width": 150,
            }, {
                "label": _("Voucher No"),
                "fieldname": "cheque_no",
                "fieldtype": "Data",
                "width": "75px",
            }, {
                "label": _("Posting Date"),
                "fieldname": "posting_date",
                "fieldtype": "Date",
                "width": "75px",
            }, {
                "label": _("Soll"),
                "fieldname": "soll",
                "fieldtype": "Currency",
            }, {
                "label": _("Haben"),
                "fieldname": "haben",
                "fieldtype": "Currency",
            }, {
                "label": _("Paid Amount"),
                "fieldname": "paid_amount",
                "fieldtype": "Currency",
                "width": "75px",
            }, {
                "label": _("Outstanding Amount"),
                "fieldname": "outstanding_amount",
                "fieldtype": "Currency",
                "width": "75px",
            }]

    def get_data(self):
        if self.filters.get('party_type') == "Customer" or self.filters.get('party_type') == "Kunde":
            self.get_sales_inovice_data()
            self.get_columns_invoice()
        elif self.filters.get('party_type') == "Supplier" or self.filters.get('party_type') == "Lieferant":
            self.get_supplier_data()
            self.get_columns_supplier()

    def get_supplier_data(self):
        self.gl_entries = self.select_journal_entry_data(self.filters.get('party_type'))
        self.data = []
        order_count = 1
        supplier_list = []
        for gl_entry in self.gl_entries:
            if gl_entry.get('supplier_name') not in supplier_list:
                supplier_list.append(gl_entry.get('supplier_name'))

        grand_total = paid_total = outstanding_total = 0
        for supplier in supplier_list:
            supplier_total = 0
            total_debit = 0
            total_credit = 0
            for gl_entry in self.gl_entries:
                outstanding_val = 0
                if supplier == gl_entry.get('supplier_name'):
                    sql = """select sum(jea.credit) as sum
													from `tabJournal Entry Account` jea
													where jea.reference_name = '%s'
													and jea.docstatus = 1""" % gl_entry.get('voucher_no')
                    payed_list = frappe.db.sql(sql, as_dict=1)

                    sql = """
								select
									sum(gl.debit) as sum
								from
									`tabGL Entry` gl
								where
									gl.against_voucher = '%s'
							""" % gl_entry.get('voucher_no')
                    payed_list.append(frappe.db.sql(sql, as_dict=1)[0])
                    payed_val = 0
                    if payed_list:
                        # calculate the oustanding value
                        for sum in payed_list:
                            if sum.get('sum'):
                                payed_val = sum.get('sum')
                        # payed_val = payed_list[0].get('sum')
                        if gl_entry.get('credit_in_account_currency'):
                            outstanding_val = gl_entry.get('credit_in_account_currency') - (payed_val or 0)
                        elif gl_entry.get('debit_in_account_currency'):
                            outstanding_val = -gl_entry.get('debit_in_account_currency')

                        outstanding_total += (outstanding_val or 0)
                        paid_total += (payed_val or 0)

                    supplier_total += gl_entry.get('credit_in_account_currency')
                    grand_total += gl_entry.get('credit_in_account_currency')

                    if gl_entry.get('against').count(',') > 1:
                        against = 'Diverse'
                    else:
                        against = gl_entry.get('against')
                    total_debit += gl_entry.get('debit_in_account_currency')
                    total_credit += gl_entry.get('credit_in_account_currency')
                    entry = {
                        'posting_date': gl_entry.get('posting_date'),
                        'order_count': order_count,
                        'account': gl_entry.get('account'),
                        'against': against,
                        'remark': gl_entry.get('remarks'),
                        'supplier': gl_entry.get('supplier'),
                        'supplier_name': gl_entry.get('supplier_name'),
                        'cheque_no': gl_entry.get('cheque_no'),
                        'voucher_type': _(gl_entry.get('voucher_type')),
                        'voucher_type_hidden': gl_entry.get('voucher_type'),
                        'voucher_no': gl_entry.get('voucher_no'),
                        'soll': gl_entry.get('debit_in_account_currency'),
                        'haben': gl_entry.get('credit_in_account_currency'),
                        'paid_amount': (payed_val or 0),
                        'outstanding_amount': (outstanding_val or 0)
                    }
                    self.data.append(entry)
            self.data += [{'value': supplier_total,
                           'cheque_no': '<b>Summe:</b> ',
                           'order_count': order_count + 0.1,
                           'soll': total_debit,
                           'haben': total_credit},
                          {'order_count': order_count + 0.2}]
            order_count += 1
        self.data.append({
            'voucher': 'Gesamtsumme',
            'value': grand_total,
            'paid_amount': paid_total,
            'outstanding_amount': outstanding_total,
            'order_count': order_count
        })
        return

    def select_journal_entry_data(self, party_type):
        table = attr = party_filter = debit_credit = p_type = party = ''

        if party_type in ['Customer', 'Kunde']:
            table = '`tabCustomer` s'
            attr = 's.customer_name'
            # debit_credit = 'and gl.debit > 0.00'
            p_type = 'Customer'
            party = 'gl.debit'

        elif party_type in ['Supplier', 'Lieferant']:
            table = '`tabSupplier` s'
            attr = 's.supplier_name'
            # debit_credit = 'and gl.credit > 0.00'
            debit_credit = ''
            p_type = 'Supplier'
            party = 'gl.credit'

        if self.filters.get('party'):
            party_list = "'" + "','".join(self.filters.get('party')) + "'"
            party_filter = 'and gl.party in ({0})'.format(party_list)

        sql = """
				select
					gl.name,
					gl.voucher_type,
					gl.voucher_no,
					gl.posting_date,
					gl.party_type,
					gl.remarks,
					gl.against_voucher_type,
					gl.account,
					gl.against,
					gl.against_voucher,
					gl.credit_in_account_currency,
					gl.debit_in_account_currency,
					gl.party,
     				jl.cheque_no,
     				jl.due_date,
     				jl.is_opening,
    				CASE
						WHEN (select sum(per.allocated_amount)
								from `tabPayment Entry Reference` per
								where per.reference_name = gl.voucher_no
								and per.docstatus = 1) is NULL THEN {party}
						ELSE {party} - (select sum(per.allocated_amount)
											from `tabPayment Entry Reference` per
											where per.reference_name = gl.voucher_no
											and per.docstatus = 1)
					END as outstanding_amount,
					{attr}
				from
					`tabGL Entry` gl,
					`tabJournal Entry` jl,
					{table}
				where
					gl.fiscal_year = '{fiscal_year}'
					and gl.party_type = '{party_type}'
					and gl.voucher_no = jl.name
					and gl.against_voucher is NULL
					and s.name = gl.party
					and ((select count(*) from `tabGL Entry` gl2 where gl2.against_voucher = gl.voucher_no) = 0 
					or (select sum(jea.credit) from `tabJournal Entry Account` jea where jea.reference_name = gl.voucher_no and jea.docstatus = 1) < {party}
					or (select sum(pe.total_allocated_amount) as sum from `tabPayment Entry` pe where pe.docstatus = 1 and pe.reference_no = gl.voucher_no) < {party})
					{party_filter}
					{debit_credit}
				order by
					gl.account
				""".format(table=table, party_type=p_type, attr=attr, party_filter=party_filter,
                           debit_credit=debit_credit, party=party, fiscal_year=self.filters.get('fiscal_year'))
        return frappe.db.sql(sql, as_dict=1)

    def select_payment_entries(self, party_type):
        sql = """
				select pe.name, pe.posting_date, pe.reference_no, pe.party, pe.party_name,
				pe.paid_amount, pe.unallocated_amount, pe.paid_from, pe.total_allocated_amount
				from `tabPayment Entry` pe, `tabGL Entry` gl
				where pe.unallocated_amount > 0
				and pe.name = gl.voucher_no
				and gl.fiscal_year = "{fiscal_year}"
				and gl.party_type = "Customer"
				and pe.party_type = "Customer"
				and pe.docstatus = 1
				""".format(fiscal_year=self.filters.get('fiscal_year'))
        return frappe.db.sql(sql, as_dict=1)

    def get_sales_inovice_data(self):
        customer_filter = ''
        if self.filters.get('party'):
            customer_list = "'" + "','".join(self.filters.get('party')) + "'"
            customer_filter = 'and customer in ({0})'.format(customer_list)

        sql = """
				select si.name, si.customer, si.customer_name, si.posting_date, si.due_date, si.po_no, si.debit_to,
				datediff(si.due_date, curdate()) as over_due, si.grand_total, si.outstanding_amount 
				from `tabSales Invoice` si, `tabGL Entry` gl
				where si.name = gl.voucher_no 
				and ((si.status in ('Overdue', 'Unpaid') 
					and si.outstanding_amount > 0) or (si.status = "Return"
					and si.outstanding_amount < 0 ))
				and gl.party_type = "Customer"
				and gl.fiscal_year = "{fiscal_year}"
				{custom_filter}
				order by debit_to""".format(custom_filter=customer_filter, fiscal_year=self.filters.get('fiscal_year'))

        self.invoice_entries = frappe.db.sql(sql, as_dict=1)
        self.journal_entries = self.select_journal_entry_data(self.filters.get('party_type'))
        self.payment_entries = self.select_payment_entries("Customer")

        customer_list = []
        for elem in self.invoice_entries:
            if elem.get('customer_name') not in customer_list:
                customer_list.append(elem.get('customer_name'))
        for elem in self.journal_entries:
            if elem.get('customer_name') not in customer_list:
                customer_list.append(elem.get('customer_name'))
        for elem in self.payment_entries:
            if elem.get('party_name') not in customer_list:
                customer_list.append(elem.get('party_name'))
        order_count = 1
        self.data = []
        grand_total = 0
        payment_total = 0
        for customer in customer_list:
            sum = {'grand_total': 0, 'payment_total': 0}
            booked_accounts = []
            for payment in self.payment_entries:
                if customer == payment.party_name:
                    payment['row'] = order_count
                    account = payment.get('paid_from').split('-')[0]
                    if sum.get('d_' + account):
                        sum['grand_total'] -= payment.get('unallocated_amount')
                        sum['d_' + account] -= payment.get('unallocated_amount')
                    else:
                        if account not in booked_accounts: booked_accounts.append(account)
                        sum['grand_total'] -= payment.get('unallocated_amount')
                        sum['d_' + account] = payment.get('unallocated_amount') * (-1)

                    unallocated = {'posting_date': payment.get('posting_date'),
                                   'order_count': order_count,
                                   'account': account,
                                   'customer': payment.get('party'),
                                   'cheque_no': payment.get('reference_no'),
                                   'customer_name': payment.get('party_name'),
                                   'voucher_type_hidden': "Payment Entry",
                                   'voucher_type': _("Payment Entry"),
                                   'voucher_no': payment.get('name'),
                                   'due_date': payment.get('due_date'),
                                   'invoiced_amount': payment.get('total_allocated_amount'),
                                   'payment_amount': 0,
                                   'paid_amount': payment.get('paid_amount'),
                                   'outstanding_amount': (payment.get('unallocated_amount') * (-1))}

                    self.data.append(unallocated)
            for sales_invoice in self.invoice_entries:
                if customer == sales_invoice.get('customer_name'):
                    sales_invoice['row'] = order_count
                    account = sales_invoice.get('debit_to').split('-')[0]

                    if sum.get('d_' + account):
                        sum['grand_total'] += sales_invoice.get('grand_total')
                        sum['d_' + account] += sales_invoice.get('grand_total')
                    else:
                        if account not in booked_accounts: booked_accounts.append(account)
                        sum['grand_total'] += sales_invoice.get('grand_total')
                        sum['d_' + account] = sales_invoice.get('grand_total')

                    dunning = {'posting_date': sales_invoice.get('posting_date'),
                               'order_count': order_count,
                               'account': account,
                               'customer': sales_invoice.get('customer'),
                               'customer_name': sales_invoice.get('customer_name'),
                               'voucher_type_hidden': "Sales Invoice",
                               'voucher_type': _("Sales Invoice"),
                               'voucher_no': sales_invoice.get('name'),
                               'due_date': sales_invoice.get('due_date'),
                               'over_due': sales_invoice.get('over_due'),
                               'invoiced_amount': sales_invoice.get('grand_total'),
                               'payment_amount': 0,
                               'paid_amount': sales_invoice.get('grand_total') - sales_invoice.get('outstanding_amount'),
                               'outstanding_amount': sales_invoice.get('outstanding_amount')}

                    # check if dunnings are created:
                    old_dunnings = self.get_old_dunnings(sales_invoice.get('name'))
                    if old_dunnings:
                        dunning.update(old_dunnings)
                    self.data.append(dunning)

            for journal_entry in self.journal_entries:
                if customer == journal_entry.get('customer_name'):
                    journal_entry['row'] = order_count
                    account = journal_entry.get('account').split('-')[0]
                    outstanding_val = 0
                    payed_val = 0
                    if journal_entry.get('debit_in_account_currency'):
                        sql = """select sum(jea.credit) as sum
								from `tabJournal Entry Account` jea
								where jea.reference_name = '%s'
								and jea.docstatus = 1""" % journal_entry.get('voucher_no')
                        payed_list = frappe.db.sql(sql, as_dict=1)
                        if payed_list:
                            # calculate the oustanding value
                            payed_val = payed_list[0].get('sum')
                            outstanding_val = journal_entry.get('debit_in_account_currency') - (payed_val or 0)
                        if sum.get('d_' + account):
                            sum['grand_total'] += journal_entry.get('debit_in_account_currency')
                            sum['d_' + account] += journal_entry.get('debit_in_account_currency')
                        else:
                            if account not in booked_accounts: booked_accounts.append(account)
                            sum['grand_total'] += journal_entry.get('debit_in_account_currency')
                            sum['d_' + account] = journal_entry.get('debit_in_account_currency')
                    elif journal_entry.get('credit_in_account_currency'):
                        if sum.get('c_' + account):
                            sum['payment_total'] += journal_entry.get('credit_in_account_currency')
                            sum['c_' + account] += journal_entry.get('credit_in_account_currency')
                        else:
                            if account not in booked_accounts: booked_accounts.append(account)
                            sum['payment_total'] += journal_entry.get('credit_in_account_currency')
                            sum['c_' + account] = journal_entry.get('credit_in_account_currency')

                    # due_date from internal reference
                    over_due = ""
                    due_date = journal_entry.due_date
                    if journal_entry.cheque_no and journal_entry.is_opening and due_date is None:
                        if frappe.db.exists("Sales Invoice", journal_entry.cheque_no):
                            invoice = frappe.get_doc("Sales Invoice", journal_entry.cheque_no)
                            due_date = invoice.due_date
                            over_due = select_overdue_days(journal_entry.cheque_no).get('over_due')

                    dunning = {'posting_date': journal_entry.get('posting_date'),
                               'due_date': due_date,
                               'order_count': order_count,
                               'account': account,
                               'customer': journal_entry.get('customer'),
                               'cheque_no': journal_entry.get('cheque_no'),
                               'customer_name': journal_entry.get('customer_name'),
                               'voucher_type_hidden': "Journal Entry",
                               'voucher_type': _("Journal Entry"),
                               'voucher_no': journal_entry.get('voucher_no'),
                               'invoiced_amount': journal_entry.get('debit_in_account_currency') or 0,
                               'payment_amount': journal_entry.get('credit_in_account_currency') or 0,
                               'paid_amount': payed_val,
							   'over_due': over_due,
                               'outstanding_amount': outstanding_val}
                    # get orig. invoice of opening entry
                    if not frappe.db.exists("Sales Invoice", journal_entry.get("cheque_no")):
                        opening_invoice = get_opening_invoice(journal_entry.get("cheque_no"))
                    else:
                        opening_invoice = journal_entry.get('cheque_no')
                    old_dunnings = self.get_old_dunnings(opening_invoice)
                    if old_dunnings:
                        dunning.update(old_dunnings)
                    self.data.append(dunning)

            grand_total += sum.get('grand_total')
            payment_total += sum.get('payment_total')
            if sum:
                for account in booked_accounts:
                    self.data += [
                        {'posting_date': '',
                         'order_count': order_count + 0.1,
                         'account': '',
                         'customer': '',
                         'customer_name': '',
                         'voucher_no': '',
                         'due_date': '',
                         'over_due': '<b>Summe:</b>',
                         'invoiced_amount': sum.get('d_' + account) or 0,
                         'payment_amount': sum.get('c_' + account) or 0,
                         'paid_amount': '',
                         'outstanding_amount': ''},
                        {'posting_date': '',
                         'order_count': order_count + 0.2,
                         'account': '',
                         'customer': '',
                         'customer_name': '',
                         'voucher_no': '',
                         'due_date': '',
                         'over_due': '',
                         'invoiced_amount': '',
                         'paid_amount': '',
                         'outstanding_amount': ''}
                    ]

            order_count += 1

        self.data.append(
            {'posting_date': '',
             'order_count': order_count + 1,
             'account': '',
             'customer': '',
             'customer_name': '',
             'voucher_no': '',
             'due_date': '',
             'over_due': '<b>Gesamtsumme</b>',
             'invoiced_amount': grand_total,
             'payment_amount': payment_total,
             'paid_amount': '',
             'outstanding_amount': ''}
        )

    def get_old_dunnings(self, sales_invoice):
        sql = '''
				select *
				from `tabDunning Item`
				where sales_invoice = "{0}"
				order by dunning_stage asc
				'''.format(sales_invoice)
        dunnings = frappe.db.sql(sql, as_dict=1)
        dunning_stage_list = []

        if dunnings:
            stages = {}
            for doc in dunnings:
                stages.update({'stage' + str(doc.get('dunning_stage')): doc.get('parent')})

                dunning_stage = {
                    "label": _("Mahnung " + str(doc.get('dunning_stage'))),
                    "fieldname": "stage" + str(doc.get('dunning_stage')),
                    "fieldtype": "Link",
                    "options": "Dunning",
                    "width": 120
                }
                if dunning_stage not in self.dunning_columns:
                    self.dunning_columns.append(dunning_stage)
            return stages
        else:
            return

def get_last_dunning(invoice):
    sql = '''
			select dunning_stage, docstatus
			from `tabDunning Item`
			where sales_invoice = "{0}"
			and docstatus = 1
			order by dunning_stage desc
			limit 1
			'''.format(invoice)
    db_stage = frappe.db.sql(sql, as_dict=1)
    if db_stage:
        stage = db_stage[0]
        if stage.get('docstatus') == 1:
            stage = db_stage[0]
    # stage = int(db_stage[0].get('dunning_stage')) + 1
    else:
        stage = {"dunning_stage": 1, "docstatus": 0}
    return stage

@frappe.whitelist()
def select_overdue_days(invoice):
    sql = '''
			select
			datediff(curdate(),due_date) as over_due
			from `tabSales Invoice`
			where name = '{0}'
			'''.format(invoice)

    return frappe.db.sql(sql, as_dict=1)[0]

@frappe.whitelist()
def get_dunning_items_data(invoice):
    result = {'stage': 0}
    dunning_items = get_last_dunning(invoice)
    if dunning_items.get('docstatus') == 1:
        result['stage'] = int(dunning_items.get('dunning_stage')) + 1
    else:
        result['stage'] = dunning_items.get('dunning_stage')
    result.update(select_overdue_days(invoice))
    return result

def get_opening_invoice(doc):
    if not frappe.db.exists("Journal Entry", doc):
        return
    je_entry = frappe.get_doc("Journal Entry", doc)

    if frappe.db.exists("Sales Invoice", je_entry.cheque_no):
        return je_entry.cheque_no
    else:
        invoice = get_opening_invoice(je_entry.cheque_no)
        if frappe.db.exists("Sales Invoice", invoice):
            return invoice

@frappe.whitelist()
def create_dunning(doc_list=None, company=None):
    if not doc_list:
        return
    doc_list = json.loads(doc_list)

    si_list = []
    for doc in doc_list:
        if not frappe.db.exists("Sales Invoice", doc):
            si_list.append(get_opening_invoice(doc))
        else:
            si_list.append(doc)

    ts = time.time()
    posting_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

    invoice_list = "'" + "','".join(si_list) + "'"
    sql = """
			select distinct customer, customer_name
			from `tabSales Invoice`
			where name in ({0})
			""".format(invoice_list)

    customer_list = frappe.db.sql(sql, as_dict=1)

    outstanding_total = 0
    d_stages = []
    d_stages_sum = {}
    for customer in customer_list:
        dunning = frappe.get_doc({'doctype': 'Dunning'})
        dunning.update(get_party_details(party_type="Customer", party=customer.get("customer"), company=company))
        for invoice in sales_invoices:
            doc = frappe.get_doc("Sales Invoice", invoice)
            # counting the stages:
            if customer.get('customer') == doc.customer:
                stage = get_last_dunning(invoice)
                if stage.get('docstatus') == 1:
                    stage = int(stage.get('dunning_stage')) + 1
                else:
                    stage = stage.get('dunning_stage')
                if stage not in d_stages:
                    d_stages.append(stage)
                    d_stages_sum[str(stage)] = doc.outstanding_amount
                else:
                    d_stages_sum[str(stage)] += doc.outstanding_amount
                over_due = select_overdue_days(invoice).get('over_due')
                outstanding_total += doc.outstanding_amount
                row = dunning.append("dunning_item", {})
                row.sales_invoice = invoice
                row.dunning_stage = stage
                row.invoice_total = doc.grand_total
                row.outstanding_amount = doc.outstanding_amount
                row.posting_date = doc.posting_date
                row.overdue_days = over_due
                row.due_date = doc.due_date

        dunning.customer = customer.get('customer')
        dunning.customer_name = customer.get('customer_name')
        dunning.posting_date = posting_date
        dunning.dunning_type = ""
        dunning.outstanding_amount = outstanding_total
        dunning.grand_total = outstanding_total

        dunning.insert()
    return {'change': 1}

def get_skonto_account(account_no):
    '''
	Gewaehrte Skonto
	16% = 8735 | 19% = 8736
	erhaltene Skonto
	16% = 3737 | 19% = 3736
	'''
    sql = """select name from `tabAccount` where account_number = '%s'""" % account_no
    return frappe.db.sql(sql, as_dict=1)[0].get('name')

@frappe.whitelist()
def create_payment(voucher_list, party_type, bank, value, posting_date, skonto, remark, allocate=0):
    if not bank or not posting_date:
        frappe.throw("Ee fehlt Bank oder Buchungsdatum oder beides!")
    if isinstance(voucher_list, str):
        voucher_list = json.loads(voucher_list)
    value = flt(value)
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    user = frappe.session.user

    if party_type == 'Customer' or party_type == 'Kunde':
        if bool(int(allocate)):
            # get the payment-entry:
            payment = {}
            c_notes = []
            liabilities = []
            credit_total = 0
            for voucher in voucher_list:
                if frappe.db.exists("Payment Entry", voucher.get("name")):
                    payment = frappe.get_doc("Payment Entry", voucher.get("name"))
                    if payment.unallocated_amount > 0:
                        voucher_list.remove(voucher)
                        break
                elif frappe.db.exists("Sales Invoice", voucher.get("name")):
                    invoice = frappe.get_doc("Sales Invoice", voucher.get("name"))
                    if invoice.is_return:
                        c_notes.append(invoice)
                        credit_total += invoice.outstanding_amount
                    else:
                        liabilities.append(invoice)
                elif frappe.db.exists("GL Entry", voucher.get("name")):
                    j_entry = frappe.get_doc("GL Entry", voucher.get("name"))
                    liabilities.append(j_entry)

            if payment:
                payment_reconciliation(payment, voucher_list, bank, posting_date, value=value)
            elif c_notes and len(c_notes) == 1:
                c_note = c_notes[0]
                credit_total = (credit_total * (-1)) + value
                for index, voucher in enumerate(liabilities):
                    journal_entry = frappe.get_doc({"doctype": "Journal Entry"})
                    journal_entry.voucher_type = "Credit Note"
                    journal_entry.posting_date = posting_date
                    journal_entry.cheque_no = voucher.name
                    journal_entry.cheque_date = posting_date
                    if credit_total <= 0:
                        # finish list normally
                        return create_payment(liabilities[index:], party_type, bank, value, posting_date, skonto,
                                              remark)
                    if voucher.doctype == "Sales Invoice":
                        credit_total = return_reconciliation(journal_entry, c_note, voucher, credit_total, value, bank)
                    elif voucher.doctype == "GL Entry":
                        voucher.outstanding_amount = voucher.debit
                        credit_total = return_reconciliation(journal_entry, c_note, voucher, credit_total, value, bank)
            elif c_notes and len(c_notes) > 1:
                p_entry = frappe.new_doc("Payment Entry")
                paid_amount = 0
                reference_no = ""
                for c_note in c_notes:
                    paid_amount += c_note.outstanding_amount
                    reference_no += '%s, ' % c_note.name
                    payment_entry_row(p_entry, c_note)
                for liability in liabilities:
                    paid_amount += liability.outstanding_amount
                    reference_no += '%s, ' % liability.name
                    payment_entry_row(p_entry, liability)
                p_entry.posting_date = posting_date
                p_entry.party_type = "Customer"
                p_entry.party = c_notes[0].customer
                p_entry.paid_to = bank
                p_entry.paid_from = c_notes[0].debit_to
                p_entry.paid_amount = p_entry.received_amount = paid_amount
                p_entry.reference_no = reference_no
                p_entry.reference_date = posting_date
                p_entry.save()
            return
        else:
            for voucher in voucher_list:
                if frappe.db.exists("Sales Invoice", voucher.get("name")):
                    invoice = frappe.get_doc("Sales Invoice", voucher.get("name"))
                    # the value now needs typecast compare because a string 0 returned true...
                    if float(value):
                        debit_value = value
                    else:
                        debit_value = invoice.outstanding_amount
                    if float(skonto):
                        skonto_account = get_skonto_account('8736')  # default 19%
                        skonto_value = invoice.outstanding_amount - float(value)
                        if invoice.taxes:
                            tax = invoice.taxes[0].rate
                            if tax == 19.0:
                                skonto_account = get_skonto_account('8736')
                                raw_skonto = round(skonto_value / 1.19, 2)
                                skonto_tax = skonto_value - raw_skonto
                                skonto_tax_account = get_skonto_account('1776')
                            elif tax == 16.0:
                                skonto_account = get_skonto_account('8735')
                                raw_skonto = round(skonto_value / 1.16, 2)
                                skonto_tax = skonto_value - raw_skonto
                                skonto_tax_account = get_skonto_account('1775')

                        journal_entry = frappe.get_doc({
                            'doctype': 'Journal Entry',
                            'voucher_type': 'Bank Entry',
                            'posting_date': posting_date,
                            'cheque_no': invoice.name,
                            'cheque_date': posting_date,
                            'accounts': [{'account': invoice.debit_to,
                                          'party_type': 'Customer',
                                          'party': invoice.customer,
                                          'reference_type': 'Sales Invoice',
                                          'reference_name': invoice.name,
                                          'credit_in_account_currency': skonto_value},
                                         {'account': skonto_account,
                                          'debit_in_account_currency': raw_skonto},
                                         {'account': skonto_tax_account,
                                          'debit_in_account_currency': skonto_tax}
                                         ]
                        })
                        journal_entry.insert()
                    elif debit_value < 0:
                        value = value * (-1)
                        journal_entry = frappe.get_doc({
                            'doctype': 'Journal Entry',
                            'voucher_type': 'Credit Note',
                            'posting_date': posting_date,
                            'cheque_no': invoice.name,
                            'cheque_date': posting_date,
                            'accounts': [
                                {'account': invoice.debit_to,
                                 'party_type': 'Customer',
                                 'party': invoice.customer,
                                 'reference_name': invoice.name,
                                 'debit_in_account_currency': value},
                                {'account': bank,
                                 'credit_in_account_currency': value
                                 }
                            ]
                        })
                    elif debit_value > invoice.outstanding_amount:
                        payment = frappe.get_doc({
                            'doctype': 'Payment Entry',
                            'title': invoice.customer,
                            'payment_type': 'Receive',
                            'posting_date': posting_date,
                            'party_type': 'Customer',
                            'party': invoice.customer,
                            'paid_to': bank,
                            'paid_from': invoice.debit_to,
                            'paid_to_account_currency': 'EUR',
                            'paid_amount': value,
                            'received_amount': value,
                            'base_paid_amount': value,
                            'base_total_allocated_amount': value,
                            'reference_date': posting_date,
                            'reference_no': invoice.name,
                        })

                        row = payment.append("references", {})
                        row.reference_doctype = "Sales Invoice"
                        row.reference_name = invoice.name
                        row.due_date = invoice.due_date
                        row.total_amount = invoice.grand_total
                        row.outstanding_amount = row.allocated_amount = invoice.outstanding_amount

                        payment.insert()
                    else:
                        journal_entry = frappe.get_doc({
                            'doctype': 'Journal Entry',
                            'voucher_type': 'Bank Entry',
                            'posting_date': posting_date,
                            'cheque_no': invoice.name,
                            'user_remark': remark,
                            'cheque_date': posting_date,
                            'accounts': [{'account': invoice.debit_to,
                                          'party_type': 'Customer',
                                          'party': invoice.customer,
                                          'reference_type': 'Sales Invoice',
                                          'reference_name': invoice.name,
                                          'credit_in_account_currency': debit_value},
                                         {'account': bank,
                                          'debit_in_account_currency': debit_value}]
                        })
                        journal_entry.insert()
                elif frappe.db.exists('Journal Entry', voucher.get("name")):
                    j_entry = frappe.get_doc('Journal Entry', voucher.get("name"))
                    customer = {}
                    debit, credit = 0, 0
                    entry_account = ""
                    for row in j_entry.accounts:
                        if row.party_type == "Customer":
                            customer = frappe.get_doc('Customer', row.party)
                            entry_account = row.account
                            if row.debit:
                                debit = row.debit
                            else:
                                credit = row.credit
                    if not customer and not entry_account:
                        frappe.throw("Kein Kunde in der Buchung zu finden.")

                    if float(value): debit_value = value
                    else: debit_value = debit

                    if float(value) > debit:
                        reference_no = j_entry.cheque_no
                        payment = frappe.get_doc({
                            'doctype': 'Payment Entry',
                            'title': customer.name,
                            'payment_type': 'Receive',
                            'posting_date': posting_date,
                            'party_type': 'Customer',
                            'party': customer.name,
                            'paid_to': bank,
                            'paid_from': "",
                            'paid_to_account_currency': 'EUR',
                            'paid_amount': value,
                            'received_amount': value,
                            'base_paid_amount': value,
                            'base_total_allocated_amount': value,
                            'reference_date': posting_date,
                            'reference_no': reference_no,
                        })
                        row = payment.append("references", {})
                        row.reference_doctype = "Journal Entry"
                        row.reference_name = j_entry.name
                        payment.insert()
                    elif debit:
                        journal_entry = frappe.get_doc({
                            'doctype': 'Journal Entry',
                            'voucher_type': 'Bank Entry',
                            'posting_date': posting_date,
                            'cheque_no': j_entry.name,
                            'user_remark': remark,
                            'cheque_date': posting_date,
                            'accounts': [{'account': entry_account,
                                          'party_type': 'Customer',
                                          'party': customer.name,
                                          'reference_type': "Journal Entry",
                                          'reference_name': j_entry.name,
                                          'credit_in_account_currency': debit_value},
                                         {'account': bank,
                                          'debit_in_account_currency': debit_value}]
                        })
                        journal_entry.insert()
                    elif credit:
                        payment = frappe.get_doc({
                            'doctype': 'Payment Entry',
                            'payment_type': 'Pay',
                            'base_paid_amount': credit,
                            'party_type': 'Customer',
                            'title': customer.name,
                            'posting_date': posting_date,
                            'base_total_allocated_amount': credit,
                            'paid_to': entry_account,
                            'reference_no': j_entry.name,
                            'party_name': customer.customer_name,
                            'paid_to_account_currency': 'EUR',
                            'party': customer.name,
                            'reference_date': posting_date,  # frappe.utils.nowdate(),
                            'total_allocated_amount': credit,
                            'paid_from': bank,
                            'received_amount': credit,
                            'paid_amount': credit,
                            'references': [{'reference_doctype': 'Journal Entry',
                                            'reference_name': j_entry.name,
                                            }]
                        })
                        payment.insert()
                elif frappe.db.exists('Payment Entry', voucher.get("name")):
                    payment = frappe.get_doc("Payment Entry", voucher.get("name"))
                    if payment.unallocated_amount > 0:
                        # create jounral entry:
                        journal_entry = frappe.get_doc({"doctype": "Journal Entry"})
                        journal_entry.voucher_type = "Bank Entry"
                        journal_entry.cheque_no = payment.reference_no
                        journal_entry.cheque_date = posting_date
                        journal_entry.posting_date = posting_date
                        debit = journal_entry.append("accounts", {})
                        debit.account = payment.paid_from
                        debit.party_type = "Customer"
                        debit.party = payment.party
                        debit.debit_in_account_currency = payment.unallocated_amount
                        credit = journal_entry.append("accounts", {})
                        credit.account = bank
                        credit.credit_in_account_currency = payment.unallocated_amount
                        journal_entry.save()
                        journal_entry.submit()

                        reconcile = frappe.get_doc("Payment Reconciliation")
                        reconcile.company = frappe.defaults.get_user_default("Company")
                        reconcile.party_type = "Customer"
                        reconcile.party = payment.party
                        reconcile.receivable_payable_account = payment.paid_from
                        unreconciled_amount = payment.unallocated_amount
                        inv = reconcile.append("invoices", {})
                        inv.invoice_type = "Journal Entry"
                        inv.invoice_number = journal_entry.name
                        inv.amount = journal_entry.total_debit
                        inv.outstanding_amount = journal_entry.total_debit
                        inv.invoice_date = journal_entry.posting_date

                        allo = reconcile.append("allocation", {})
                        allo.reference_type = "Payment Entry"
                        allo.reference_name = payment.name
                        allo.invoice_type = "Journal Entry"
                        allo.invoice_number = journal_entry.name
                        allo.allocated_amount = journal_entry.total_debit
                        allo.amount = payment.unallocated_amount
                        allo.unreconciled_amount = unreconciled_amount
                        reconcile.reconcile()
                    else:
                        pass

    elif party_type == 'Supplier' or party_type == 'Lieferant':
        if bool(int(allocate)):
            c_note = frappe._dict()
            for voucher in voucher_list:
                if voucher.get("reference_type") == "Journal Entry":
                    j_entry = frappe.get_doc("Journal Entry", voucher.get("name"))
                    for account in j_entry.accounts:
                        if account.party_type == "Supplier" and account.reference_name is None:
                            if account.debit_in_account_currency:
                                c_note = account
                                voucher_list.remove(voucher)
                                break
            if not c_note:
                return

            # init reconcile
            reconcile = frappe.get_doc("Payment Reconciliation")
            reconcile.company = frappe.defaults.get_user_default("Company")
            reconcile.party_type = "Supplier"
            reconcile.party = c_note.party
            reconcile.receivable_payable_account = c_note.account

            for voucher in voucher_list:
                outstanding_amount = float(voucher.get("outstanding_amount"))
                if c_note.debit_in_account_currency <= 0:
                    break
                if frappe.db.exists("Journal Entry", voucher.get("name")):
                    j_entry = frappe.get_doc("Journal Entry", voucher.get("name"))
                else:
                    continue

                if c_note.debit_in_account_currency > 0:
                    inv = reconcile.append("invoices", {})
                    inv.invoice_type = "Journal Entry"
                    inv.invoice_number = j_entry.name
                    inv.amount = j_entry.total_debit
                    inv.outstanding_amount = outstanding_amount
                    inv.invoice_date = j_entry.posting_date

                    row = reconcile.append("allocation", {})
                    row.unreconciled_amount = c_note.debit_in_account_currency
                    row.reference_row = c_note.name
                    if c_note.debit_in_account_currency >= outstanding_amount:
                        row.reference_type = c_note.parenttype
                        row.reference_name = c_note.parent
                        row.invoice_type = "Journal Entry"
                        row.invoice_number = j_entry.name
                        row.allocated_amount = outstanding_amount
                        row.amount = c_note.debit_in_account_currency
                        c_note.debit_in_account_currency -= outstanding_amount
                        outstanding_amount = 0
                    elif c_note.debit_in_account_currency <= outstanding_amount:
                        row.reference_type = c_note.parenttype
                        row.reference_name = c_note.parent
                        row.invoice_type = "Journal Entry"
                        row.invoice_number = j_entry.name
                        row.allocated_amount = c_note.debit_in_account_currency
                        row.amount = c_note.debit_in_account_currency
                        outstanding_amount -= c_note.debit_in_account_currency
                        c_note.debit_in_account_currency = 0
                if c_note.debit_in_account_currency == 0 and outstanding_amount:
                    payment = frappe.new_doc("Payment Entry")
                    payment.payment_type = "Pay"
                    payment.posting_date = posting_date
                    payment.party_type = "Supplier"
                    payment.party = c_note.party
                    payment.paid_to = c_note.account
                    payment.paid_from = bank
                    payment.paid_to_account_currency = 'EUR'
                    payment.paid_amount = payment.received_amount = outstanding_amount
                    payment.reference_no = j_entry.name
                    payment.reference_date = posting_date
                    payment.cost_center = c_note.cost_center
                    row = payment.append("references", {})

                    row.reference_doctype = "Journal Entry"
                    row.reference_name = j_entry.name
                    row.allocated_amount = outstanding_amount
                    row.outstanding_amount = outstanding_amount
                    payment.save()

            if len(reconcile.allocation) > 0:
                reconcile.reconcile()
            return
        for voucher in voucher_list:
            if voucher.get("reference_type") == "Journal Entry":
                gl_entry_name = \
                    frappe.get_list("GL Entry", filters={"voucher_no": voucher.get("name"), "party_type": "Supplier"})[
                        0].name
                gl_entry = frappe.get_doc('GL Entry', gl_entry_name)

                supplier = frappe.get_doc('Supplier', gl_entry.party)
                bank_account = frappe.get_all('Bank Account', filters={"account": bank})[0]
                if float(value):
                    payed_total = float(value)
                else:
                    payed_total = voucher.get("outstanding_amount")
                # frappe.logger().debug("gl_entry.credit: %s - value: %s" % (gl_entry.credit, value))
                payment = frappe.get_doc({
                    'doctype': 'Payment Entry',
                    'payment_type': 'Pay',
                    'base_paid_amount': payed_total,
                    'party_type': 'Supplier',
                    'title': gl_entry.party,
                    'posting_date': posting_date,
                    'base_total_allocated_amount': payed_total,
                    'paid_to': gl_entry.get('account'),
                    'reference_no': gl_entry.voucher_no,
                    'party_name': supplier.supplier_name,
                    'paid_to_account_currency': 'EUR',
                    'party': gl_entry.party,
                    'bank_account': bank_account.name,
                    'bank': bank_account.account_name,
                    'bank_account_no': bank_account.bank_account_no,
                    'reference_date': posting_date,
                    'total_allocated_amount': payed_total,
                    'paid_from': bank,
                    'received_amount': payed_total,
                    'paid_amount': payed_total,
                    'remarks': remark
                })
                row = payment.append("references", {})
                row.reference_doctype = "Journal Entry"
                row.reference_name = gl_entry.voucher_no
                row.total_amount = gl_entry.credit
                row.outstanding_amount = payed_total
                row.allocated_amount = payed_total
                payment.save()
            elif voucher.get("reference_type") == "Purchase Invoice":
                p_invoice = frappe.get_doc("Purchase Invoice", voucher.get("name"))
                if float(value):
                    payed_total = float(value)
                else:
                    payed_total = voucher.get("outstanding_amount")
                p_entry = frappe.new_doc("Payment Entry")
                if payed_total < 0:
                    payment_type = "Receive"
                    paid_amount = payed_total * (-1)
                    paid_from = p_invoice.credit_to
                    paid_to = bank
                else:
                    paid_amount = payed_total
                    payment_type = "Pay"
                    paid_from = bank
                    paid_to = p_invoice.credit_to

                p_entry.payment_type = payment_type
                p_entry.posting_date = posting_date
                p_entry.party_type = "Supplier"
                p_entry.party = p_invoice.supplier
                p_entry.paid_from = paid_from
                p_entry.paid_to = paid_to
                p_entry.paid_amount = paid_amount
                p_entry.reference_no = p_invoice.name
                p_entry.reference_date = posting_date
                p_entry.received_amount = payed_total
                p_entry.base_paid_amount_after_tax = payed_total,
                p_entry.base_paid_amount = payed_total,
                p_entry.base_total_allocated_amount = payed_total,
                p_entry.total_allocated_amount = payed_total,
                p_entry.base_received_amount_after_tax = payed_total,
                p_entry.base_received_amount = payed_total

                row = p_entry.append("references", {})
                row.reference_doctype = "Purchase Invoice"
                row.reference_name = p_invoice.name
                row.total_amount = p_invoice.grand_total
                row.outstanding_amount = p_invoice.outstanding_amount
                row.allocated_amount = payed_total
                p_entry.save()
    # payment.submit()
    else:
        pass
    return

def create_allocation(allocation, reference_type, reference_name, invoice_type, invoice_number, amount):
    # create allocation list for payment reconciliation
    allocation.reference_type = reference_type
    allocation.reference_name = reference_name
    allocation.invoice_type = invoice_type
    allocation.invoice_number = invoice_number
    allocation.allocated_amount = amount
    return allocation

def return_reconciliation(j_entry, c_note, voucher, total_credit, value, bank):
    if voucher.outstanding_amount <= total_credit:
        create_journal_entry(j_entry, voucher=voucher, credit=voucher.outstanding_amount)
        if not value or voucher.outstanding_amount <= (c_note.outstanding_amount * (-1)):
            create_journal_entry(j_entry, voucher=c_note, debit=voucher.outstanding_amount)
        elif c_note.outstanding_amount < 0:
            create_journal_entry(j_entry, voucher=c_note, debit=(c_note.outstanding_amount * (-1)))
            create_journal_entry(j_entry, bank=bank, debit=voucher.outstanding_amount + c_note.outstanding_amount)
        elif voucher.outstanding_amount < total_credit:
            create_journal_entry(j_entry, bank=bank, debit=voucher.outstanding_amount)
        else:
            create_journal_entry(j_entry, bank=bank, debit=total_credit)
        c_note.outstanding_amount += voucher.outstanding_amount
        total_credit -= voucher.outstanding_amount
    elif voucher.outstanding_amount > total_credit > 0:
        if c_note.outstanding_amount < 0 and c_note.outstanding_amount * (-1) < voucher.outstanding_amount:
            create_journal_entry(j_entry, voucher=voucher, credit=(c_note.outstanding_amount * (-1)))
            create_journal_entry(j_entry, voucher=c_note, debit=(c_note.outstanding_amount * (-1)))
            total_credit += c_note.outstanding_amount
            voucher.outstanding_amount += c_note.outstanding_amount
            c_note.outstanding_amount = 0
        else:
            create_journal_entry(j_entry, voucher=voucher, credit=total_credit)
            create_journal_entry(j_entry, bank=bank, debit=total_credit)
            total_credit = 0
    else:
        frappe.throw("Fall nicht berücksichtigt. Bitte Melden!")

    j_entry.save()
    if voucher.outstanding_amount:
        outstanding_entry = frappe.get_doc({"doctype": "Journal Entry"})
        outstanding_entry.voucher_type = "Bank Entry"
        outstanding_entry.posting_date = j_entry.posting_date
        outstanding_entry.cheque_no = voucher.name
        outstanding_entry.cheque_date = j_entry.posting_date
        create_journal_entry(outstanding_entry, voucher=voucher, credit=voucher.outstanding_amount)
        create_journal_entry(outstanding_entry, bank=bank, debit=voucher.outstanding_amount)
        outstanding_entry.save()

    return total_credit

def payment_entry_row(p_entry, c_note):
    row = p_entry.append("references", {})
    row.reference_doctype = c_note.doctype
    row.reference_name = c_note.name
    row.due_date = c_note.due_date
    row.total_amount = c_note.grand_total
    row.outstanding_amount = row.allocated_amount = c_note.outstanding_amount

def create_journal_entry(j_entry, voucher={}, bank="", debit=0, credit=0, value=0):
    row = j_entry.append("accounts", {})

    if voucher.get("doctype") == "Sales Invoice":
        # Sales Invoice Data
        row.party_type = "Customer"
        row.party = voucher.get("customer")
        row.account = voucher.get("debit_to")
        row.reference_type = voucher.get("doctype")
        row.reference_name = voucher.get("name")
    elif voucher.get("doctype") == "GL Entry":
        # Journal Entry Data
        row.party_type = voucher.get("party_type")
        row.party = voucher.get("party")
        row.account = voucher.get("account")
        row.reference_type = voucher.get("voucher_type")
        row.reference_name = voucher.get("voucher_no")
    else:
        row.account = bank

    if debit:
        row.debit_in_account_currency = debit
        row.debit = debit

    if credit:
        row.credit_in_account_currency = credit
        row.credit = credit

    if value:
        row.debit_in_account_currency = value
        row.debit = value
    return row

def payment_reconciliation(payment, voucher_list, bank, posting_date, value=0):
    reconcile = frappe.get_doc("Payment Reconciliation")
    reconcile.company = frappe.defaults.get_user_default("Company")
    reconcile.party_type = "Customer"
    reconcile.party = payment.party
    reconcile.receivable_payable_account = payment.paid_from
    unreconciled_amount = payment.unallocated_amount
    unfinished_voucher = []
    unfinished_total = 0
    for voucher in voucher_list:
        if payment.unallocated_amount <= 0:
            invoice = frappe.get_doc("Sales Invoice", voucher.get("name"))
            unfinished_voucher.append(voucher.get("name"))
            unfinished_total += invoice.outstanding_amount
            continue
        if frappe.db.exists("Sales Invoice", voucher.get("name")):
            invoice = frappe.get_doc("Sales Invoice", voucher.get("name"))
            allo = reconcile.append("allocation", {})
            allo.reference_type = "Payment Entry"
            allo.reference_name = payment.name
            allo.invoice_type = "Sales Invoice"
            allo.invoice_number = voucher.get("name")
            if payment.unallocated_amount < invoice.outstanding_amount:
                allo.allocated_amount = payment.unallocated_amount
                unfinished_voucher.append(voucher.get("name"))
                unfinished_total += (invoice.outstanding_amount - payment.unallocated_amount)
            else:
                allo.allocated_amount = invoice.outstanding_amount
            allo.amount = payment.unallocated_amount
            allo.unreconciled_amount = unreconciled_amount
            payment.unallocated_amount -= invoice.outstanding_amount
            inv = reconcile.append("invoices", {})
            inv.invoice_type = "Sales Invoice"
            inv.invoice_number = invoice.name
            inv.amount = invoice.total
            inv.outstanding_amount = invoice.outstanding_amount
            inv.invoice_date = invoice.posting_date
    reconcile.reconcile()
    if unfinished_voucher:
        for voucher in unfinished_voucher:
            invoice = frappe.get_doc("Sales Invoice", voucher)
            journal_entry = frappe.get_doc({"doctype": "Journal Entry"})
            journal_entry.posting_date = posting_date
            journal_entry.voucher_type = "Bank Entry"
            journal_entry.cheque_no = invoice.name
            journal_entry.cheque_date = posting_date
            create_journal_entry(journal_entry, invoice, credit=invoice.outstanding_amount)
            create_journal_entry(journal_entry, bank=bank, debit=invoice.outstanding_amount)
            journal_entry.save()

def create_invoices():
    # create invoices list for payment reconciliation
    return