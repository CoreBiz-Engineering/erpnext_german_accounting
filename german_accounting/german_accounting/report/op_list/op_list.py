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

def execute(filters=None):
	if filters.get("attach"):
		return read_csv_file(filters.get("attach"))
	else:
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
		data = sorted(self.data, key=lambda k: ("order_count" not in k, k.get("order_count", None), "posting_date" not in k, k.get("posting_date", None)))
		# data = sorted(self.data, key=lambda k: k['order_count'])
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
				"label": _("Account"),
				"fieldname": "account",
				"fieldtype": "Data",
			},
			{
				"label": _("Customer Name"),
				"fieldname": "customer_name",
				"fieldtype": "Data",
				"width": "50px",
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
			},{
				"label": _("Remark"),
				"fieldname": "remark",
				"fieldtype": "Data",
				"width": 150,
			},{
				"label": _("Voucher No"),
				"fieldname": "cheque_no",
				"fieldtype": "Data",
				"width": "75px",
			},{
				"label": _("Posting Date"),
				"fieldname": "posting_date",
				"fieldtype": "Date",
				"width": "75px",
			},{
				"label": _("Soll"),
				"fieldname": "soll",
				"fieldtype": "Currency",
			},{
				"label": _("Haben"),
				"fieldname": "haben",
				"fieldtype": "Currency",
			},{
				"label": _("Paid Amount"),
				"fieldname": "paid_amount",
				"fieldtype": "Currency",
				"width": "75px",
			},{
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
						   'cheque_no': 'Summe: ',
						   'order_count': order_count+0.1,
						   'soll': total_debit,
						   'haben': total_credit},
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
			# debit_credit = 'and gl.credit > 0.00'
			debit_credit = ''
			p_type = 'Supplier'
			party = 'gl.credit'


		if self.filters.get('party'):
			party_list = "'" + "','".join(self.filters.get('party')) + "'"
			party_filter = 'and gl.party in ({0})'.format(party_list)

		sql =	"""
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
					gl.party_type = '{party_type}'
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
						   debit_credit=debit_credit, party=party)
		return frappe.db.sql(sql, as_dict=1)

	def select_payment_entries(self, party_type):
		sql = 	"""
				select name, posting_date, reference_no, party, party_name,
				paid_amount, unallocated_amount, paid_from,	total_allocated_amount
				from `tabPayment Entry`
				where unallocated_amount > 0
				and party_type = "Customer"
				and docstatus = 1
				""".format()
		return frappe.db.sql(sql, as_dict=1)

	def get_sales_inovice_data(self):
		customer_filter = ''
		if self.filters.get('party'):
			customer_list = "'" + "','".join(self.filters.get('party')) + "'"
			customer_filter = 'and customer in ({0})'.format(customer_list)

		sql =	"""
				select name, customer, customer_name, posting_date, due_date, po_no, debit_to,
					datediff(due_date, curdate()) as over_due, grand_total, outstanding_amount 
				from `tabSales Invoice` 
				where (
							(
								due_date <= curdate() and
								status in ('Overdue', 'Unpaid') and
								outstanding_amount > 0
							) 
							or
							(
							   status = "Return"
							   and outstanding_amount < 0 
							)
						) {0}
				order by debit_to""".format(customer_filter)

		self.invoice_entries = frappe.db.sql(sql,as_dict=1)
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
			if elem.get('customer_name') not in customer_list:
				customer_list.append(elem.get('customer_name'))
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
						sum['d_'+account] = payment.get('unallocated_amount') * (-1)

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

					if sum.get('d_'+account):
						sum['grand_total'] += sales_invoice.get('grand_total')
						sum['d_'+account] += sales_invoice.get('grand_total')
					else:
						if account not in booked_accounts: booked_accounts.append(account)
						sum['grand_total'] += sales_invoice.get('grand_total')
						sum['d_'+account] = sales_invoice.get('grand_total')

					dunning = {	'posting_date': sales_invoice.get('posting_date'),
									'order_count': order_count,
									'account': account,
									'customer': sales_invoice.get('customer'),
									'customer_name': sales_invoice.get('customer_name'),
									'voucher_type_hidden':  "Sales Invoice",
									'voucher_type':  _("Sales Invoice"),
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
				from `tabDunning Item`
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
	sql =	'''
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
		#stage = int(db_stage[0].get('dunning_stage')) + 1
	else:
		stage = {"dunning_stage": 1, "docstatus": 0}
	return stage

@frappe.whitelist()
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

	outstanding_total = 0
	d_stages = []
	d_stages_sum = {}
	for customer in customer_list:
		dunning = frappe.get_doc({'doctype': 'Dunning'})
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
def create_payment(voucher_list,party_type,bank, value, posting_date, skonto, remark, allocate):
	if not bank or not posting_date:
		frappe.throw("Ee fehlt Bank oder Buchungsdatum oder beides!")
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
				for voucher in liabilities:
					journal_entry = frappe.get_doc({"doctype": "Journal Entry"})
					journal_entry.voucher_type = "Credit Note"
					journal_entry.posting_date = posting_date
					if credit_total <= 0:
						break
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
				elif frappe.db.exists('GL Entry', voucher.get("name")):

					gl_entry = frappe.get_doc('GL Entry', voucher.get("name"))
					customer = frappe.get_doc('Customer', gl_entry.party)

					if float(value): debit_value = value
					else: debit_value = gl_entry.debit

					if float(value) > gl_entry.debit:
						if frappe.db.exists("Journal Entry", gl_entry.voucher_no):
							j_entry = frappe.get_doc("Journal Entry", gl_entry.voucher_no)
							reference_no = j_entry.cheque_no
						else:
							reference_no = gl_entry.voucher_no
						payment = frappe.get_doc({
							'doctype': 'Payment Entry',
							'title': gl_entry.party,
							'payment_type': 'Receive',
							'posting_date': posting_date,
							'party_type': 'Customer',
							'party': gl_entry.party,
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
						row.reference_name = gl_entry.voucher_no
						payment.insert()
					elif gl_entry.debit:
						journal_entry = frappe.get_doc({
							'doctype': 'Journal Entry',
							'voucher_type': 'Bank Entry',
							'posting_date': posting_date,
							'cheque_no': gl_entry.voucher_no,
							'user_remark': remark,
							'cheque_date': posting_date,
							'user_remark': remark,
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
							'posting_date': posting_date,
							'base_total_allocated_amount': gl_entry.credit,
							'paid_to': gl_entry.get('account'),
							'reference_no': gl_entry.voucher_no,
							'party_name': customer.customer_name,
							'paid_to_account_currency': 'EUR',
							'party': gl_entry.party,
							'reference_date': posting_date, #frappe.utils.nowdate(),
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
		for voucher in voucher_list:
			if not frappe.db.exists("GL Entry", voucher.get("name")):
				voucher = frappe.get_list("GL Entry", filters={"voucher_no": voucher.get("name"), "party_type": "Supplier"})[0].name
			gl_entry = frappe.get_doc('GL Entry', voucher)
			supplier = frappe.get_doc('Supplier', gl_entry.party)
			bank_account = frappe.get_all('Bank Account', filters={'account': bank})[0]
			if float(value):
				credit_value = float(value)
			elif gl_entry.credit:
				credit_value = gl_entry.credit
			else:
				credit_value = gl_entry.debit
			# frappe.logger().debug("gl_entry.credit: %s - value: %s" % (gl_entry.credit, value))

			payment = frappe.get_doc({
				'doctype': 'Payment Entry',
				'payment_type': 'Pay',
				'base_paid_amount': credit_value,
				'party_type': 'Supplier',
				'title': gl_entry.party,
				'posting_date': posting_date,
				'base_total_allocated_amount': credit_value,
				'paid_to': gl_entry.get('account'),
				'reference_no': gl_entry.voucher_no,
				'party_name': supplier.supplier_name,
				'paid_to_account_currency': 'EUR',
				'party': gl_entry.party,
				'bank_account': bank_account.name,
				'bank': bank_account.account_name,
				'bank_account_no': bank_account.bank_account_no,
				'reference_date': posting_date, #frappe.utils.nowdate(),
				'total_allocated_amount': credit_value,
				'paid_from': bank,
				'received_amount': credit_value,
				'paid_amount': credit_value,
				'remarks': remark,
				'references': [{'reference_doctype': 'Journal Entry',
								'reference_name': gl_entry.voucher_no,
								'total_amount': gl_entry.credit,
								'outstanding_amount': gl_entry.credit,
								'allocated_amount': credit_value}]
			})
			payment.insert()
		#payment.submit()
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
	#allocation.amount = payment.unallocated_amount
	#allocation.unreconciled_amount = unreconciled_amount
	return allocation


def return_reconciliation(j_entry, c_note, voucher, total_credit, value, bank):
	if voucher.outstanding_amount <= total_credit:
		create_journal_entry(j_entry, voucher=voucher, credit=voucher.outstanding_amount)
		if not value or voucher.outstanding_amount <= (c_note.outstanding_amount*(-1)):
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
		if c_note.outstanding_amount < 0:
			create_journal_entry(j_entry, voucher=voucher, credit=(c_note.outstanding_amount * (-1)))
			create_journal_entry(j_entry, voucher=c_note, debit=(c_note.outstanding_amount * (-1)))
			c_note.outstanding_amount = 0
			total_credit += c_note.outstanding_amount
		else:
			create_journal_entry(j_entry, voucher=voucher, credit=total_credit)
			create_journal_entry(j_entry, bank=bank, debit=total_credit)
			total_credit = 0
	else:
		frappe.throw("Fall nicht berücksichtigt. Bitte Melden!")

	j_entry.save()
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
			invoice = frappe.get_doc("Sales Invoice", voucher.get("name"))
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