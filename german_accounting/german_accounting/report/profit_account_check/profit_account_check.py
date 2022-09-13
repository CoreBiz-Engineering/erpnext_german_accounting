# Copyright (c) 2022, LIS and contributors
# For license information, please see license.txt

import frappe, json
from frappe import _

def execute(filters=None):
	# Report for all `Draft` invoices to check the profit account and edit posting date check
	columns = get_columns()
	data = get_draft_invoice_data()
	return columns, data


def get_draft_invoice_data():
	contract_list = [
		"service_contract",
		"cloud_and_hosting_contract",
		"maintenance_contract",
		"maintenance_contract_various",
		"rental_server_contract"
	]
	data = []
	invoice_list = frappe.get_list("Sales Invoice", filters={"status": "Draft"})
	for invoice in invoice_list:
		invoice = frappe.get_doc("Sales Invoice", invoice)
		invoice_total = 0
		for item in invoice.items:
			i = frappe._dict()
			i.customer = invoice.customer
			i.customer_name = invoice.customer_name
			i.invoice = invoice.name
			i.debit_to = invoice.debit_to
			i.income_account = item.income_account
			i.posting_date = invoice.posting_date
			i.set_posting_date = invoice.set_posting_time
			i.rate = item.amount
			for contract in contract_list:
				if item.get(contract):
					i.accounting_dimension = item.get(contract)
			data.append(i)
		for tax in invoice.taxes:
			i = frappe._dict()
			i.customer = invoice.customer
			i.customer_name = invoice.customer_name
			i.invoice = invoice.name
			i.debit_to = invoice.debit_to
			i.income_account = tax.account_head
			i.rate = tax.tax_amount
			data.append(i)
		data.append({
			"accounting_dimension": "Summe",
			"grand_total": invoice.grand_total,
		})
		data.append({})
	return data


@frappe.whitelist()
def submit_invoice(invoice_list):
	invoice_list = json.loads(invoice_list)
	for invoice in invoice_list:
		if frappe.db.exists("Sales Invoice", invoice):
			doc = frappe.get_doc("Sales Invoice", invoice)
			if not doc.set_posting_time:
				doc.set_posting_time = 1
			doc.submit()
	return


def get_columns():
	columns = [
		{
			"label": _("Sales Invoice"),
			"fieldname": "invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice"
		},{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Data",
		},{
			"label": _("Debit To"),
			"fieldname": "debit_to",
			"fieldtype": "Data",
		},{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
		},{
			"label": "Geändertes Datum",
			"fieldname": "set_posting_date",
			"fieldtype": "Check",
			"width": "20px"
		},{
			"label": _("Income Account"),
			"fieldname": "income_account",
			"fieldtype": "Data",
		},{
			"label": "Kostenstelle",
			"fieldname": "accounting_dimension",
			"fieldtype": "Data",
		},{
			"label": _("Rate"),
			"fieldname": "rate",
			"fieldtype": "Currency",
		},{
			"label": _("Grand Total"),
			"fieldname": "grand_total",
			"fieldtype": "Currency",
		}
	]
	return columns