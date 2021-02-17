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


def execute(filters=None):
	args = {
		"party_type": "Customer",
		"naming_by": ["Selling Settings", "cust_master_name"],
	}
	if filters.get('party_type') == "Customer":
		args = {"party_type": "Customer"}
	elif filters.get('party_type') == "Supplier":
		args = {"party_type": "Supplier"}
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
		data = sorted(self.data, key=lambda k: k['order_count'])
		self.columns = self.columns + self.dunning_columns
		return self.columns, data

	def set_defaults(self):
		if not self.filters.get("company"):
			self.filters.company = frappe.db.get_single_value('Global Defaults', 'default_company')
		self.company_currency = frappe.get_cached_value('Company',  self.filters.get("company"), "default_currency")
		self.currency_precision = get_currency_precision() or 2
		self.dr_or_cr = "debit" if self.filters.party_type == "Customer" else "credit"
		self.party_type = self.filters.party_type
		self.party_details = {}
		self.invoices = set()

	def get_columns_invoice(self):
		"""Return the list of columns that will be shown in query report."""
		self.columns = [
			{
				"label": _("Check"),
				"fieldname": "check",
				"fieldtype": "Data",
			},
			{
				"label": _("Account"),
				"fieldname": "account",
				"fieldtype": "Data",
			},
			{
				"label": _("Customer Name"),
				"fieldname": "customer_name",
				"fieldtype": "Data",
			},
			{
				"label": _("Voucher No"),
				"fieldname": "sales_invoice",
				"fieldtype": "Link",
				"options": "Sales Invoice"
			},
			{
				"label": _("Journal Entry"),
				"fieldname": "journal_entry",
				"fieldtype": "Link",
				"options": "Journal Entry"
			},
			{
				"label": _("Voucher No"),
				"fieldname": "cheque_no",
				"fieldtype": "Data"
			},
			{
				"label": _("Posting Date"),
				"fieldname": "posting_date",
				"fieldtype": "Data",
			},
			{
				"label": _("Due Date"),
				"fieldname": "due_date",
				"fieldtype": "Data",
			},
			{
				"label": _("Over Due"),
				"fieldname": "over_due",
				"fieldtype": "Data",
			},
			{
				"label": _("Invoiced Amount"),
				"fieldname": "invoiced_amount",
				"fieldtype": "Currency",
			},
			{
				"label": _("Payment Amount"),
				"fieldname": "payment_amount",
				"fieldtype": "Currency",
			},
			{
				"label": _("Paid Amount"),
				"fieldname": "paid_amount",
				"fieldtype": "Currency",
			},
			{
				"label": _("Outstanding Amount"),
				"fieldname": "outstanding_amount",
				"fieldtype": "Currency",
			}
		]

	def get_columns_supplier(self):
		self.columns = [
			{
				"label": _("Check"),
				"fieldname": "check",
				"fieldtype": "Data",
			},{
				"label": _("Account"),
				"fieldname": "account",
				"fieldtype": "Data",
				"width": 150
			},{
				"label": _("Against Account"),
				"fieldname": "against",
				"fieldtype": "Data",
				"width": 150
			},{
				"label": _("Supplier Name"),
				"fieldname": "supplier_name",
				"fieldtype": "Data",
			},{
				"label": _("Remark"),
				"fieldname": "remark",
				"fieldtype": "Data",
				"width": 250
			},{
				"label": _("Voucher"),
				"fieldname": "voucher",
				"fieldtype": "Link",
				"options": "Journal Entry"
			},{
				"label": _("Posting Date"),
				"fieldname": "posting_date",
				"fieldtype": "Date",
			},{
				"label": _("Value"),
				"fieldname": "value",
				"fieldtype": "Currency",
			},{
				"label": _("Paid Amount"),
				"fieldname": "paid_amount",
				"fieldtype": "Currency",
			},{
				"label": _("Outstanding Amount"),
				"fieldname": "outstanding_amount",
				"fieldtype": "Currency",
			}]

	def get_data(self):
		if self.filters.get('party_type') == "Customer" or self.filters.get('party_type') == "Kunde":
			self.get_sales_inovice_data()
			self.get_columns_invoice()
		elif self.filters.get('party_type') == "Supplier" or self.filters.get('party_type') == "Lieferant":
			self.get_supplier_data()
			self.get_columns_supplier()

	def get_supplier_data(self):
		sql =	"""
				select
					gl.name,
					gl.voucher_no,
					gl.posting_date,
					gl.party_type,
					gl.remarks,
					gl.against_voucher_type,
					gl.account,
					gl.against,
					gl.against_voucher,
					gl.credit_in_account_currency,
					gl.party,
					s.supplier_name
				from
					`tabGL Entry` gl,
					`tabSupplier` s 
				where
					gl.party_type = 'Supplier'
					and gl.against_voucher_type is NULL
					and gl.against_voucher is NULL
					and s.name = gl.party
					and (select count(*) from `tabGL Entry` gl2 where gl2.against_voucher = gl.voucher_no) = 0
				"""
		#self.gl_entries = frappe.db.sql(sql, as_dict=1)
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
			for gl_entry in self.gl_entries:
				if supplier == gl_entry.get('supplier_name'):
					sql = """select sum(jea.credit) as sum
													from `tabJournal Entry Account` jea
													where jea.reference_name = '%s'
													and jea.docstatus = 1""" % gl_entry.get('voucher_no')
					payed_list = frappe.db.sql(sql, as_dict=1)
					if payed_list:
						# calculate the oustanding value
						payed_val = payed_list[0].get('sum')
						outstanding_val = gl_entry.get('credit_in_account_currency') - (payed_val or 0)
						outstanding_total += (outstanding_val or 0)
						paid_total += (payed_val or 0)

					supplier_total += gl_entry.get('credit_in_account_currency')
					grand_total += gl_entry.get('credit_in_account_currency')

					if gl_entry.get('against').count(',') > 1:
						against = 'Diverse'
					else:
						against = gl_entry.get('against')

					entry = {
						'posting_date': gl_entry.get('posting_date'),
						'order_count': order_count,
						'check': '<input value={0} type="checkbox">'.format(gl_entry.get('name')),
						'account': gl_entry.get('account'),
						'against': against,
						'remark': gl_entry.get('remarks'),
						'supplier': gl_entry.get('supplier'),
						'supplier_name': gl_entry.get('supplier_name'),
						'voucher': gl_entry.get('voucher_no'),
						'value': gl_entry.get('credit_in_account_currency'),
						'paid_amount': (payed_val or 0),
						'outstanding_amount': (outstanding_val or 0)
					}
					self.data.append(entry)
			self.data += [{'value': supplier_total,
						   'voucher': 'Summe: ',
						   'order_count': order_count+0.1},
						  {'order_count': order_count+0.2}]
			order_count += 1
		self.data.append({'voucher': 'Gesamtsumme', 'value': grand_total, 'paid_amount': paid_total, 'outstanding_amount': outstanding_total, 'order_count': order_count})
		return

	def select_journal_entry_data(self, party_type):
		table = attr = party_filter = debit_credit = p_type = party =''

		if party_type in ['Customer','Kunde']:
			table = '`tabCustomer` s'
			attr = 's.customer_name'
			#debit_credit = 'and gl.debit > 0.00'
			p_type = 'Customer'
			party = 'gl.debit'

		elif party_type in ['Supplier','Lieferant']:
			table = '`tabSupplier` s'
			attr = 's.supplier_name'
			debit_credit = 'and gl.credit > 0.00'
			p_type = 'Supplier'
			party = 'gl.credit'


		if self.filters.get('party'):
			party_list = "'" + "','".join(self.filters.get('party')) + "'"
			party_filter = 'and gl.party in ({0})'.format(party_list)

		sql =	"""
				select
					gl.name,
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
    				CASE
						WHEN (select sum(per.allocated_amount)
								from `tabPayment Entry Reference` per
								where per.reference_name = gl.voucher_no
								and per.docstatus = 1) is NULL THEN gl.debit
						ELSE gl.debit - (select sum(per.allocated_amount)
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
					gl.party_type = '{party_type}'
					and gl.voucher_no = jl.name
					and gl.against_voucher_type is NULL
					and gl.against_voucher is NULL
					and s.name = gl.party
					and ((select count(*) from `tabGL Entry` gl2 where gl2.against_voucher = gl.voucher_no) = 0 
					or (select sum(jea.credit) from `tabJournal Entry Account` jea where jea.reference_name = gl.voucher_no and jea.docstatus = 1) < gl.debit)
					{party_filter}
					{debit_credit}
				""".format(table=table, party_type=p_type, attr=attr, party_filter=party_filter,
						   debit_credit=debit_credit, party=party)

		return frappe.db.sql(sql, as_dict=1)

	def get_sales_inovice_data(self):
		'''
		TODO shorten this method
		'''
		'''
		{'company': 'LIS Consulting GmbH', 'ageing_based_on': 'Posting Date', 'report_date': datetime.date(2020, 5, 14),
		'customer': 'FirmaTest2', 'party_type': 'Customer', 'naming_by': ['Selling Settings', 'cust_master_name']}
		'''
		customer_filter = ''
		if self.filters.get('party'):
			customer_list = "'" + "','".join(self.filters.get('party')) + "'"
			customer_filter = 'and customer in ({0})'.format(customer_list)

		sql =	"""
				select name, customer, customer_name, posting_date, due_date, po_no, debit_to,
					datediff(due_date, curdate()) as over_due, grand_total, outstanding_amount 
				from `tabSales Invoice` 
				where due_date <= curdate() and status = 'Overdue' and outstanding_amount > 0 {0}""".format(customer_filter)

		self.invoice_entries = frappe.db.sql(sql,as_dict=1)
		self.journal_entries = self.select_journal_entry_data(self.filters.get('party_type'))
		customer_list = []
		for elem in self.invoice_entries:
			if elem.get('customer_name') not in customer_list:
				customer_list.append(elem.get('customer_name'))
		for elem in self.journal_entries:
			if elem.get('customer_name') not in customer_list:
				customer_list.append(elem.get('customer_name'))
		order_count = 1
		self.data = []
		grand_total = 0
		payment_total = 0
		for customer in customer_list:
			sum = {'grand_total': 0, 'payment_total': 0}
			booked_accounts = []

			for sales_invoice in self.invoice_entries:
				if customer == sales_invoice.get('customer_name'):
					sales_invoice['row'] = order_count
					account = sales_invoice.get('debit_to').split('-')[0]

					if sum.get('d_'+account):
						sum['grand_total'] += sales_invoice.get('grand_total')
						sum['d_'+account] += sales_invoice.get('grand_total')
					else:
						if account not in booked_accounts: booked_accounts.append(account)
						sum['grand_total'] += sales_invoice.get('grand_total')
						sum['d_'+account] = sales_invoice.get('grand_total')

					dunning = {	'posting_date': sales_invoice.get('posting_date'),
									'order_count': order_count,
								  	'check': '<input value={0} type="checkbox">'.format(sales_invoice.get('name')),
									'account': account,
									'customer': sales_invoice.get('customer'),
									'customer_name': sales_invoice.get('customer_name'),
									'sales_invoice': sales_invoice.get('name'),
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
						payed_list = frappe.db.sql(sql,as_dict=1)
						if payed_list:
							#calculate the oustanding value
							payed_val = payed_list[0].get('sum')
							outstanding_val = journal_entry.get('debit_in_account_currency') - (payed_val or 0)
						if sum.get('d_'+account):
							sum['grand_total'] += journal_entry.get('debit_in_account_currency')
							sum['d_'+account] += journal_entry.get('debit_in_account_currency')
						else:
							if account not in booked_accounts: booked_accounts.append(account)
							sum['grand_total'] += journal_entry.get('debit_in_account_currency')
							sum['d_'+account] = journal_entry.get('debit_in_account_currency')
					elif journal_entry.get('credit_in_account_currency'):
						if sum.get('c_'+account):
							sum['payment_total'] += journal_entry.get('credit_in_account_currency')
							sum['c_'+account] += journal_entry.get('credit_in_account_currency')
						else:
							if account not in booked_accounts: booked_accounts.append(account)
							sum['payment_total'] += journal_entry.get('credit_in_account_currency')
							sum['c_'+account] = journal_entry.get('credit_in_account_currency')

					dunning = {'posting_date': journal_entry.get('posting_date'),
							   'order_count': order_count,
							   'check': '<input value={0} type="checkbox">'.format(journal_entry.get('name')),
							   'account': account,
							   'customer': journal_entry.get('customer'),
							   'cheque_no': journal_entry.get('cheque_no'),
							   'customer_name': journal_entry.get('customer_name'),
							   'journal_entry': journal_entry.get('voucher_no'),
							   'invoiced_amount': journal_entry.get('debit_in_account_currency') or 0,
							   'payment_amount': journal_entry.get('credit_in_account_currency') or 0,
							   'paid_amount': payed_val,
							   'outstanding_amount': outstanding_val}
					self.data.append(dunning)

			grand_total += sum.get('grand_total')
			payment_total += sum.get('payment_total')
			if sum:
				for account in booked_accounts:
					self.data += [
						{'posting_date': '',
						 'order_count': order_count+0.1,
						 'account': '',
						 'customer': '',
						 'customer_name': '',
						 'voucher_no': '',
						 'due_date': '',
						 'over_due': 'Summe',
						 'invoiced_amount': sum.get('d_'+account) or 0,
						 'payment_amount': sum.get('c_'+account) or 0,
						 'paid_amount': '',
						 'outstanding_amount': ''},
						{'posting_date': '',
						 'order_count': order_count+0.2,
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
			 'over_due': 'Gesamtsumme',
			 'invoiced_amount': grand_total,
			 'payment_amount': payment_total,
			 'paid_amount': '',
			 'outstanding_amount': ''}
		)

	def get_old_dunnings(self, sales_invoice):

		sql = '''
				select *
				from `tabDunning Items`
				where sales_invoice = "{0}"
				order by dunning_stage asc
				'''.format(sales_invoice)
		dunnings = frappe.db.sql(sql, as_dict=1)
		dunning_stage_list = []

		if dunnings:
			stages = {}
			for doc in dunnings:
				stages.update({'stage'+ str(doc.get('dunning_stage')): doc.get('parent')})

				dunning_stage = {
					"label": _("Mahnung " + str(doc.get('dunning_stage'))),
					"fieldname": "stage"+ str(doc.get('dunning_stage')),
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
	sql =	'''
			select dunning_stage, docstatus
			from `tabDunning Items`
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
		#stage = int(db_stage[0].get('dunning_stage')) + 1
	else:
		stage = {"dunning_stage": 1, "docstatus": 0}
	return stage

def select_overdue_days(invoice):
	sql =	'''
			select
			datediff(curdate(),due_date) as over_due
			from `tabSales Invoice`
			where name = '{0}'
			'''.format(invoice)

	return frappe.db.sql(sql, as_dict=1)[0]

@frappe.whitelist()
def get_dunning_items_data(invoice):
	result={'stage': 0}
	dunning_items = get_last_dunning(invoice)
	if dunning_items.get('docstatus') == 1:
		result['stage'] = int(dunning_items.get('dunning_stage')) + 1
	else:
		result['stage'] = dunning_items.get('dunning_stage')
	result.update(select_overdue_days(invoice))
	return result

@frappe.whitelist()
def create_dunning(sales_invoices):
	ts = time.time()
	posting_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
	#converting the stringobject from frontend into python-list
	sales_invoices = json.loads(sales_invoices)
	invoice_list = "'"+"','".join(sales_invoices)+"'"
	sql =	"""
			select distinct customer, customer_name
			from `tabSales Invoice`
			where name in ({0})
			""".format(invoice_list)

	customer_list = frappe.db.sql(sql, as_dict=1)

	invoice_list = []
	outstanding_total = 0
	d_stages = []
	d_stages_sum = {}
	for customer in customer_list:
		for invoice in sales_invoices:
			doc = frappe.get_doc("Sales Invoice", invoice)
			#counting the stages:
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
				invoice_list.append({
					'sales_invoice': invoice,
					'dunning_stage': stage,
					'invoice_total': doc.grand_total,
					'outstanding_amount': doc.outstanding_amount,
					'posting_date': doc.posting_date,
					'overdue_days': over_due,
					'due_date': doc.due_date,
				})


		dunning = frappe.get_doc({
			'doctype': 'Dunning',
			'customer': customer.get('customer'),
			'customer_name': customer.get('customer_name'),
			'posting_date': posting_date,
			'dunning_items': invoice_list,
			'dunning_type': '1',
			'outstanding_amount': outstanding_total,
			'total_1': d_stages_sum.get('1') or None,
			'total_2': d_stages_sum.get('2') or None,
			'total_3': d_stages_sum.get('3') or None,
		})

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
def create_payment(voucher_list,party_type,bank, value, posting_date, skonto):

	voucher_list = json.loads(voucher_list)
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	user = frappe.session.user

	if party_type == 'Customer' or party_type == 'Kunde':
		for voucher in voucher_list:
			if frappe.db.exists("Sales Invoice", voucher):
				invoice = frappe.get_doc("Sales Invoice", voucher)
				if value:
					debit_value = value
				else:
					debit_value = invoice.outstanding_amount
				if skonto:
					skonto_account = get_skonto_account('8736') #default 19%
					skonto_value = invoice.outstanding_amount - float(value)
					if invoice.taxes:
						tax = invoice.taxes[0].rate
						if tax == 19.0:
							skonto_account = get_skonto_account('8736')
							raw_skonto = round(skonto_value/1.19, 2)
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
								  'credit_in_account_currency': debit_value},
								 {'account': bank,
								  'debit_in_account_currency': debit_value}]
				})
				journal_entry.insert()
			elif frappe.db.exists('GL Entry', voucher):
				gl_entry = frappe.get_doc('GL Entry', voucher)
				customer = frappe.get_doc('Customer', gl_entry.party)
				if value:
					debit_value = value
				else:
					debit_value = gl_entry.debit
				if gl_entry.debit:
					journal_entry = frappe.get_doc({
						'doctype': 'Journal Entry',
						'voucher_type': 'Bank Entry',
						'posting_date': posting_date,
						'cheque_no': gl_entry.voucher_no,
						'cheque_date': posting_date,
						'accounts': [{'account': gl_entry.account,
									  'party_type': 'Customer',
									  'party': gl_entry.party,
									  'reference_type': gl_entry.voucher_type,
									  'reference_name': gl_entry.voucher_no,
									  'credit_in_account_currency': debit_value},
									 {'account': bank,
									  'debit_in_account_currency': debit_value}]
					})
					journal_entry.insert()
				elif gl_entry.credit:
					payment = frappe.get_doc({
						'doctype': 'Payment Entry',
						'payment_type': 'Pay',
						'base_paid_amount': gl_entry.credit,
						'party_type': 'Customer',
						'title': gl_entry.party,
						'base_total_allocated_amount': gl_entry.credit,
						'paid_to': gl_entry.get('account'),
						'reference_no': gl_entry.voucher_no,
						'party_name': customer.customer_name,
						'paid_to_account_currency': 'EUR',
						'party': gl_entry.party,
						'reference_date': frappe.utils.nowdate(),
						'total_allocated_amount': gl_entry.credit,
						'paid_from': bank,
						'received_amount': gl_entry.credit,
						'paid_amount': gl_entry.credit,
						'company': gl_entry.company,
						'references': [{'reference_doctype': 'Journal Entry',
										'reference_name': gl_entry.voucher_no,
										}]
					})
					payment.insert()

	elif party_type == 'Supplier' or party_type == 'Lieferant':

		for voucher in voucher_list:
			gl_entry = frappe.get_doc('GL Entry', voucher)
			supplier = frappe.get_doc('Supplier', gl_entry.party)
			payment = frappe.get_doc({
				'doctype': 'Payment Entry',
				'payment_type': 'Pay',
				'base_paid_amount': gl_entry.credit,
				'party_type': 'Supplier',
				'title': gl_entry.party,
				'base_total_allocated_amount': gl_entry.credit,
				'paid_to': gl_entry.get('account'),
				'reference_no': gl_entry.voucher_no,
				'party_name': supplier.supplier_name,
				'paid_to_account_currency': 'EUR',
				'party': gl_entry.party,
				'reference_date': frappe.utils.nowdate(),
				'total_allocated_amount': gl_entry.credit,
				'paid_from': bank,
				'received_amount': gl_entry.credit,
				'paid_amount': gl_entry.credit,
				'references': [{'reference_doctype': 'Journal Entry',
								'reference_name': gl_entry.voucher_no,
								'total_amount': gl_entry.credit,
								'outstanding_amount': gl_entry.credit,
								'allocated_amount': gl_entry.credit}]
			})
			payment.insert()
		#payment.submit()
	else:
		pass
	return
