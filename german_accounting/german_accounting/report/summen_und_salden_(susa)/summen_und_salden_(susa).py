# Copyright (c) 2013, LIS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
import json
import time, datetime
from frappe import _, scrub

month_map = {
	"Januar": '01',
	"Februar": '02',
	"März": '03',
	"April": '04',
	"Mai": '05',
	"Juni": '06',
	"Juli": '07',
	"August": '08',
	"September": '09',
	"Oktober": '10',
	"November": '11',
	"Dezember": '12'
}


def execute(filters=None):
	columns, data = [], [{}]
	year = filters.get("year")
	month = month_map.get(filters.get("month"))
	party = filters.get('party')
	opening = get_opening_entries(year, party)
	monthly = get_monthly_entries(year, month, party)
	data = get_account_data(opening, monthly, party)
	columns = get_columns()
	return columns, data


def get_columns():

	columns = [
		{
			"label": _("Konto"),
			"fieldname": "account_number",
			"fieldtype": "Data",
		},{
			"label": _("Bezeichnung"),
			"fieldname": "account_name",
			"fieldtype": "Data",
		},{
			"label": _("Eröffnungsbilanzwert"),
			"fieldname": "opening_value",
			"fieldtype": "Currency",
		},{
			"label": _("S/H"),
			"fieldname": "opening_s_h",
			"fieldtype": "Data",
		},{
			"label": _("Monatswert Soll"),
			"fieldname": "month_debit",
			"fieldtype": "Currency",
		},{
			"label": _("Monatswert Haben"),
			"fieldname": "month_credit",
			"fieldtype": "Currency",
		},{
			"label": _("Kumulierter Wert Soll"),
			"fieldname": "cumulative_debit",
			"fieldtype": "Currency",
		},{
			"label": _("Kumulierter Wert Haben"),
			"fieldname": "cumulative_credit",
			"fieldtype": "Currency",
		},{
			"label": _("Saldo"),
			"fieldname": "saldo",
			"fieldtype": "Currency",
			"width": 80,
		},{
			"label": _("S/H"),
			"fieldname": "saldo_s_h",
			"fieldtype": "Data",
		}
	]

	return columns

def select_opening_entries(year, party):
	range = get_filter(option=party)
	sql =	"""
			select
				CAST(ac.account_number AS INT) as "account_number",
				ac.account_name,
				sum(gl.debit) as opening_debit,
				sum(gl.credit) as opening_credit
			from
				`tabGL Entry` gl,
				`tabAccount` ac
			where gl.account = ac.name
				and gl.is_opening = "Yes"
				and gl.fiscal_year = "{fiscal_year}"
				{range}
			group by ac.account_number, ac.account_name order by CAST(ac.account_number AS INT);
			""".format(fiscal_year=year, range=range)

	return frappe.db.sql(sql, as_dict=1)

def get_opening_entries(year, party):

	entries = select_opening_entries(year, party)

	for entry in entries:
		if entry.get('opening_debit') and not entry.get('opening_credit'):
			entry['opening_s_h'] = 'S'
			entry['opening_value'] = entry.get('opening_debit')
		elif entry.get('opening_credit') and not entry.get('opening_debit'):
			entry['opening_s_h'] = 'H'
			entry['opening_value'] = entry.get('opening_credit')
		elif entry.get('opening_debit') > entry.get('opening_credit'):
			entry['opening_value'] = entry.get('opening_credit')
			entry['opening_value'] = entry.get('opening_debit') - entry.get('opening_credit')
			entry['opening_s_h'] = 'S'
		elif entry.get('opening_debit') < entry.get('opening_credit'):
			entry['opening_value'] = entry.get('opening_credit') - entry.get('opening_debit')
			entry['opening_s_h'] = 'H'


	return entries

def get_filter(year=None, month=None, option=None):

	if option == 'start':
		return year + '-' + month + '-' + '01'
	elif option == 'end':
		return year + '-' + month + '-' + '31'
	elif option == 'Sachkonten':
		return 'and ac.account_number >= 1 and ac.account_number <= 9999'
	elif option == 'Debitor':
		return 'and ac.account_number >= 10000 and ac.account_number <= 38999'
	elif option == 'Kreditor':
		return 'and ac.account_number >= 70000 and ac.account_number <= 98999'

def select_cumulative_entries(year, month, party):
	# setting filters for select
	start = year + '-01-' + '01'
	end = get_filter(year=year, month=month, option='end')
	range = get_filter(option=party)

	sql =	"""
			select
				CAST(ac.account_number AS INT) as "account_number",
				ac.account_name,
				sum(gl.debit) as cumulative_debit,
				sum(gl.credit) as cumulative_credit
			from
				`tabGL Entry` gl,
				`tabAccount` ac
			where gl.account = ac.name
				and gl.is_opening != "Yes"
				and gl.fiscal_year = "{fiscal_year}"
				and gl.posting_date >= "{start}"
				and gl.posting_date <= "{end}"
				{range}
			group by ac.account_number, ac.account_name order by CAST(ac.account_number AS INT);
			""".format(fiscal_year=year, start=start, end=end, range=range)
	return frappe.db.sql(sql, as_dict=1)

def select_monthly_entries(year, month, party):

	start = get_filter(year=year, month=month, option='start')
	end = get_filter(year=year, month=month, option='end')
	range = get_filter(option=party)
	sql =	"""
			select
				CAST(ac.account_number AS INT) as "account_number",
				ac.account_name,
				sum(gl.debit) as month_debit,
				sum(gl.credit) as month_credit
			from
				`tabGL Entry` gl,
				`tabAccount` ac
			where gl.account = ac.name
				and gl.is_opening != "Yes"
				and gl.fiscal_year = "{fiscal_year}"
				and gl.posting_date >= "{start}"
				and gl.posting_date <= "{end}"
				{range}
			group by ac.account_number, ac.account_name order by CAST(ac.account_number AS INT);
			""".format(fiscal_year=year, start=start, end=end, range=range)
	return frappe.db.sql(sql, as_dict=1)

def get_monthly_entries(year, month, party):

	monthly_entries = select_monthly_entries(year, month, party)
	cumulative_entries = select_cumulative_entries(year, month, party)
	for cumulative_entry in cumulative_entries:
		upd = False
		for monthly_entry in monthly_entries:
			if cumulative_entry.get('account_number') == monthly_entry.get('account_number'):
				monthly_entry.update(cumulative_entry)
				upd = True
		if not upd:
			monthly_entries.append(cumulative_entry)
	return monthly_entries

def get_account_data(opening, monthly, party):

	for monthly_entry in monthly:
		upd = False
		for opening_entry in opening:
			if opening_entry.get('account_number') == monthly_entry.get('account_number'):
				opening_entry.update(monthly_entry)
				upd = True
		if not upd:
			opening.append(monthly_entry)
	calculate_saldo(opening)

	data = sorted(opening, key=lambda k: k['account_number'])
	sum_list = []
	total_ope_d = total_ope_c = total_mon_d = total_mon_c = total_cum_d = total_cum_c = total_sal_d = total_sal_c = 0
	if party == 'Sachkonten':
		for i in range(0,10):
			sum_ope_d = sum_ope_c = sum_mon_d = sum_mon_c = sum_cum_d = sum_cum_c = sum_sal_d = sum_sal_c = 0
			for entry in data:
				if entry.get('account_number') < 1000 and i == 0:
					entry["index"] = i
					sum_ope_d += entry.get('opening_debit', 0)
					sum_ope_c += entry.get('opening_credit', 0)
					sum_mon_d += entry.get('month_debit', 0)
					sum_mon_c += entry.get('month_credit', 0)
					sum_cum_d += entry.get('cumulative_debit', 0)
					sum_cum_c += entry.get('cumulative_credit', 0)
					sum_sal_d += entry.get('saldo', 0) if entry.get('saldo_s_h') == "S" else 0
					sum_sal_c -= entry.get('saldo', 0) if entry.get('saldo_s_h') == "H" else 0
				elif str(entry.get('account_number')).startswith(str(i)) and entry.get('account_number') >= 1000:
					entry["index"] = i
					sum_ope_d += entry.get('opening_debit', 0)
					sum_ope_c += entry.get('opening_credit', 0)
					sum_mon_d += entry.get('month_debit', 0)
					sum_mon_c += entry.get('month_credit', 0)
					sum_cum_d += entry.get('cumulative_debit', 0)
					sum_cum_c += entry.get('cumulative_credit', 0)
					sum_sal_d += entry.get('saldo', 0) if entry.get('saldo_s_h') == "S" else 0
					sum_sal_c -= entry.get('saldo', 0) if entry.get('saldo_s_h') == "H" else 0


			if sum_ope_d or sum_ope_c or sum_mon_d or sum_mon_c or sum_cum_d or sum_cum_c or sum_sal_d or sum_sal_c:

				sum_sal = 0
				sum_sal_s_h = ""
				if sum_sal_d or sum_sal_c:
					sum_sal = sum_sal_d + sum_sal_c
					if sum_sal < 0:
						sum_sal = sum_sal * (-1)
						sum_sal_s_h = "H"
					else:
						sum_sal_s_h = "S"
				opening_sum = 0
				if sum_ope_d or sum_ope_c:
					if sum_ope_d:
						opening_sum += sum_ope_d
					if sum_ope_c:
						opening_sum -= sum_ope_c
					s_h = "H" if opening_sum < 0 else "S"
					opening_sum = opening_sum * (-1) if opening_sum < 0 else opening_sum

				sum_list += [{'index': i + 0.1},
							 {'index': i + 0.2, 'opening_value': opening_sum, 'opening_s_h': s_h, 'month_debit': sum_mon_d,
							  'month_credit': sum_mon_c,'cumulative_debit': sum_cum_d, 'cumulative_credit': sum_cum_c,
							  'saldo': sum_sal, 'saldo_s_h': sum_sal_s_h, 'account_name': 'Summe Klasse ' + str(i)},
							 {'index': i + 0.4}]

				total_ope_d += sum_ope_d
				total_ope_c += sum_ope_c
				total_mon_d += sum_mon_c
				total_mon_c += sum_mon_d
				total_cum_d += sum_cum_d
				total_cum_c += sum_cum_c
				total_sal_d += sum_sal_d
				total_sal_c += sum_sal_c

		sum_list += [{'index': 10, 'account_name': "Sachkonten", 'opening_value': total_ope_d, 'opening_s_h': 'S',
					  'month_debit': total_mon_d, 'month_credit': total_mon_c,'cumulative_debit': total_cum_d,
					  'cumulative_credit': total_cum_c, 'saldo': total_sal_d, 'saldo_s_h': 'S'},
					 {'index': 10.1, 'opening_value': total_ope_c, 'opening_s_h': 'H', 'saldo': total_sal_c, 'saldo_s_h': 'H'}]
	else:
		sum_ope_d = sum_ope_c = sum_mon_d = sum_mon_c = sum_cum_d = sum_cum_c = sum_sal_d = sum_sal_c = 0
		for entry in data:
			entry["index"] = 1
			sum_ope_d += entry.get('opening_debit', 0)
			sum_ope_c += entry.get('opening_credit', 0)
			sum_mon_d += entry.get('month_debit', 0)
			sum_mon_c += entry.get('month_credit', 0)
			sum_cum_d += entry.get('cumulative_debit', 0)
			sum_cum_c += entry.get('cumulative_credit', 0)
			sum_sal_d += entry.get('saldo', 0) if entry.get('saldo_s_h') == "S" else 0
			sum_sal_c -= entry.get('saldo', 0) if entry.get('saldo_s_h') == "H" else 0

		if sum_ope_d or sum_ope_c or sum_mon_d or sum_mon_c or sum_cum_d or sum_cum_c or sum_sal_d or sum_sal_c:
			sum_sal = 0
			sum_sal_s_h = ""
			if sum_sal_d or sum_sal_c:
				sum_sal = sum_sal_d + sum_sal_c
				if sum_sal < 0:
					sum_sal = sum_sal * (-1)
					sum_sal_s_h = "H"
				else:
					sum_sal_s_h = "S"
			sum_list += [{'index': 2},
						 {'index': 3, 'opening_value': sum_ope_d, 'opening_s_h': 'S', 'month_debit': sum_mon_d,
						  'month_credit': sum_mon_c,'cumulative_debit': sum_cum_d, 'cumulative_credit': sum_cum_c,
						  'saldo': sum_sal, 'saldo_s_h': sum_sal_s_h, 'account_name': party},
						 {'index': 4}]

			total_ope_d += sum_ope_d
			total_ope_c += sum_ope_c
			total_mon_d += sum_mon_c
			total_mon_c += sum_mon_d
			total_cum_d += sum_cum_d
			total_cum_c += sum_cum_c
			total_sal_d += sum_sal_d
			total_sal_c += sum_sal_c

	data += sum_list

	data = sorted(data, key=lambda k: k['index'])

	return data

def calculate_saldo(entries):

	for entry in entries:
		saldo = 0
		if entry.get('cumulative_debit') or entry.get('cumulative_credit'):
			if entry.get('opening_value') and entry.get('opening_s_h') == "S":
				saldo += entry.get('opening_value', 0) - entry.get('cumulative_credit', 0) + entry.get('cumulative_debit', 0)
				entry['saldo_s_h'] = "S"
			elif entry.get('opening_value') and entry.get('opening_s_h') == "H":
				saldo += entry.get('opening_value', 0) - entry.get('cumulative_debit', 0) + entry.get('cumulative_credit', 0)
				entry['saldo_s_h'] = "H"
			elif entry.get('cumulative_debit') or entry.get('cumulative_credit'):
				if entry.get('cumulative_debit') > entry.get('cumulative_credit'):
					saldo += entry.get('cumulative_debit', 0) - entry.get('cumulative_credit', 0)
					entry['saldo_s_h'] = "S"
				else:
					saldo += entry.get('cumulative_credit', 0) - entry.get('cumulative_debit', 0)
					entry['saldo_s_h'] = "H"


		if saldo < 0 and entry.get('saldo_s_h') == "S":
			entry['saldo'] = saldo * (-1)
			entry['saldo_s_h'] = "H"
		elif saldo < 0 and entry.get('saldo_s_h') == "H":
			entry['saldo'] = saldo * (-1)
			entry['saldo_s_h'] = "S"
		else:
			entry['saldo'] = saldo

	return
