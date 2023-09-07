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
	validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	columns = [
		{
			"label": _("Rechnungsdatum"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
		},
		{
			"label": _("Rechnungsnummer"),
			"fieldname": "invoice_number",
			"fieldtype": "Link",
			"options": "Sales Invoice"
		},
		{
			"label": _("Kundennummer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"label": _("Kunde"),
			"fieldname": "customer_name",
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"label": _("Projekt"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project"
		},
		{
			"label": _("Nettobetrag"),
			"fieldname": "net_total",
			"fieldtype": "Currency",
		},
		{
			"label": _("Gesamtbetrag"),
			"fieldname": "grand_total",
			"fieldtype": "Currency",
		},
		{
			"label": _("Created On"),
			"fieldname": "created_on",
			"fieldtype": "Date",
		},
	]
	return columns

def get_data(filters):
	created_on = ""
	if filters.get('created_on'):
		created_on = "and DATE_FORMAT(creation, '%Y-%m-%d') = DATE_FORMAT('{created_on}', '%Y-%m-%d')".format(created_on=filters.get('created_on'))

	sql = 	"""
			select
				name as "invoice_number",
				posting_date,
				customer,
				customer_name,
				project,
				net_total,
				grand_total,
				creation as "created_on"
			from
				`tabSales Invoice`
			where 
				posting_date >= str_to_date('{dvon}', '%Y-%m-%d')
				and posting_date <= str_to_date('{dbis}', '%Y-%m-%d')
				{created_on}
			""".format(dvon=filters.get('from_date'), dbis=filters.get('to_date'), created_on=created_on)
	return frappe.db.sql(sql, as_dict=1)

def validate_filters(filters):
	"""Make sure all mandatory filters are present."""
	if not filters.get('from_date'):
		frappe.throw(_('{0} is mandatory').format(_('From Date')))

	if not filters.get('to_date'):
		frappe.throw(_('{0} is mandatory').format(_('To Date')))
