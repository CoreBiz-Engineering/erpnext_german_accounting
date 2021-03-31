# Copyright (c) 2020, LIS Engineering and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time, datetime
import random
debug = True


def execute(filters=None):
	columns, data = [], []
	if filters.get('view') == 'BWA Kurzbericht':
		data = get_bwa_short_result(filters)
		columns = get_short_columns()
	elif filters.get('view') == 'BWA':
		data = get_bwa_result(filters)
		columns = get_columns()
	elif filters.get('view') == 'BWA Kontenansicht':

		compare = filters.get('comparison')
		data = get_bwa_account_result(filters)
		bwa = get_bwa_result(filters)
		if compare:
			# for the compare between selected time range minus one year
			last_fitlers = {}
			last_fitlers['from_date'] = get_last_year(filters.get('from_date'))
			last_fitlers['to_date'] = get_last_year(filters.get('to_date'))
			last_fitlers['compari'] = 1
			last_data = get_bwa_account_result(last_fitlers)
			last_bwa = get_bwa_result(last_fitlers)
			data = merge_data(data, last_data)
			bwa = merge_bwa(bwa, last_bwa)
		data = data + bwa
		columns = get_bwa_account_columns(compare)

	if data:
		try:
			data = sorted(data, key=lambda k: k['sort_zeile'])
		except:
			data = sorted(data, key=lambda k: k['zeile'])
	return columns, data

def get_last_year(date):
	# set the year to compare
	d = datetime.datetime.strptime(date, "%Y-%m-%d")
	return datetime.datetime.strftime((d.replace(year = d.year - 1)), "%Y-%m-%d")

def merge_data(data, last_data):
	for previous_year in last_data:
		for actual_year in data:
			if actual_year.get('account') == previous_year.get('account'):
				if actual_year.get('sum') and previous_year.get('sum'):
					previous_year['sum'] = round(previous_year.get('sum') + random.randint(-100,1000))
					actual_year['previous_year'] = round(previous_year.get('sum'),2)
					actual_year['absolute'] = actual_year.get('sum') - previous_year.get('sum')

					percentage = round(((actual_year.get('sum') / previous_year.get('sum')) * 100.0), 3)
					if percentage > 100:
						difference = percentage - 100
						pass
					else:
						difference = (100 - percentage)*(-1)

					actual_year['in_percentage'] = difference
	return data

def merge_bwa(bwa, last_bwa):
	for previous_year in last_bwa:
		for actual_year in bwa:
			if actual_year.get('zeile') == previous_year.get('zeile'):

				if actual_year.get('sum') and previous_year.get('sum'):
					previous_year['sum'] = round(previous_year.get('sum') + random.randint(-100, 1000))
					actual_year['previous_year'] = round(previous_year.get('sum'),2)
					actual_year['absolute'] = actual_year.get('sum') - previous_year.get('sum')

					percentage = round(((actual_year.get('sum') / previous_year.get('sum')) * 100.0), 3)
					if percentage > 100:
						difference = percentage - 100
						pass
					else:
						difference = (100 - percentage) * (-1)

					actual_year['in_percentage'] = difference
	return bwa

def get_bwa_account_columns(comparison):
	columns = []
	if not comparison:
		columns = [
			{
				"col": 2,
				"label": "Kontobezeichnung",
				"fieldname": "zeilen_name",
				"fieldtype": "Data",
				"width": 150,
			},
			{
				"col": 3,
				"label": "Konto",
				"fieldname": "account",
				"fieldtype": "Data",
				"width": 60,
				"align": "center",
			},
			{
				"col": 4,
				"label": "",
				"fieldname": "type",
				"fieldtype": "Data",
				"width": 30,
				"align": "center",
			},
			{
				"col": 5,
				"label": "Konten-/Zeilenbeschriftung",
				"fieldname": "name",
				"fieldtype": "Data",
				"width": 300,
			},

			{
				"col": 7,
				"label": "Konten-/Zeilenwerte",
				"fieldname": "sum",
				"fieldtype": "Currency",
			},
			{
				"col": 8,
				"label": "BWA-Werte",
				"fieldname": "subtotal",
				"fieldtype": "Currency",
			},
			{
				"fieldname": "space",
				"fieldtype": "",
				"width": 5,
			},
		]
	elif comparison:
		columns = [
			{
				"col": 2,
				"label": "Kontobezeichnung",
				"fieldname": "zeilen_name",
				"fieldtype": "Data",
				"width": 150,
			},
			{
				"col": 3,
				"label": "Konto",
				"fieldname": "account",
				"fieldtype": "Data",
				"width": 60,
				"align": "center",
			},
			{
				"col": 4,
				"label": "",
				"fieldname": "type",
				"fieldtype": "Data",
				"width": 30,
				"align": "center",
			},
			{
				"col": 5,
				"label": "Konten-/Zeilenbeschriftung",
				"fieldname": "name",
				"fieldtype": "Data",
				"width": 300,
			},
			{
				"col": 7,
				"label": "Konten-/Zeilenwerte",
				"fieldname": "sum",
				"fieldtype": "Currency",
			},
			{
				"col": 8,
				"label": "Vorjahr",
				"fieldname": "previous_year",
				"fieldtype": "Currency",
			},
			{
				"col": 9,
				"label": "absolut",
				"fieldname": "absolute",
				"fieldtype": "Currency",
			},
			{
				"col": 10,
				"label": "in %",
				"fieldname": "in_percentage",
				"width": 75,
				"fieldtype": "Percent",
			},
			{
				"fieldname": "space",
				"fieldtype": "",
				"width": 5,
			},
		]

	return columns

def get_short_columns():
	columns = [
		{
			"label": "Zeile",
			"fieldname": "zeile",
			"fieldtype": "Data",
		},
		{
			"label": "Kontobezeichnung",
			"fieldname": "zeilen_name",
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"label": "sum",
			"fieldname": "sum",
			"fieldtype": "Currency",
			"width": 125,
		},
		{
			"label": "",
			"fieldname": "",
			"fieldtype": "Currency",
		}
	]
	return columns

def get_columns():
	columns = [
		{
			"label": "Zeile",
			"fieldname": "zeile",
			"fieldtype": "Data",
		},
		{
			"label": "Kontobezeichnung",
			"fieldname": "zeilen_name",
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"label": "Debit",
			"fieldname": "debit",
			"fieldtype": "Currency",
		},
		{
			"label": "Credit",
			"fieldname": "credit",
			"fieldtype": "Currency",
		},
		{
			"label": "sum",
			"fieldname": "sum",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "Funktionsschlüssel",
			"fieldname": "funktion",
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"label": "name",
			"fieldname": "account_name",
			"fieldtype": "Data",
			"width": 500,
		}
	]
	return columns

def get_bwa_short_accounts():
	sel =	"""
			select
				zeile,
				zeilen_name,
				konto_von,
				type,
				konto_bis,
				zeile_von,
				zeile_bis,
				funktion,
				bwa_funktion
			from
				`tabBWA Kurzbericht`
			"""
	res = frappe.db.sql(sel, as_dict=1)
	return res

def get_bwa_accounts():
	sel = 	"""
			select
				zeile,
				zeilen_name,
				konto_von,
				type,
				konto_bis,
				zeile_von,
				zeile_bis,
				funktion
			from
				`tabBWA`
			where
				(zeile_von is Null and zeile_bis is Null or zeile_von = '' and zeile_bis = '')
			order by
				zeile
			"""
	bwa_accounts = frappe.db.sql(sel, as_dict=1)
	return bwa_accounts

def get_bwa_sum_rows():
	"""
	select all bwa-rows which are not subtotals
	:return: list of dicts with all accounts
	"""
	sel = 	"""
			select
				zeile,
				zeilen_name,
				konto_von,
				type,
				konto_bis,
				zeile_von,
				zeile_bis,
				funktion
			from
				`tabBWA`
			where
				zeile_von != ''
				and zeile_bis !=''
			order by
				zeile
			"""
	bwa_sum_rows = frappe.db.sql(sel, as_dict=1)
	return bwa_sum_rows

def get_gl_entries(accounts, filters):
	"""
	get the GL Entries from the database
	:param accounts: list of dicts with all accountnumbers
	:return: list of dicts with pre subtotals of all accountnumbers
	"""
	res = []
	rows = []

	for row in accounts:
		if row.get('zeile') not in rows:
			rows.append(row.get('zeile'))

	for row in rows:
		gl_entries = []

		sel =	"""
				select
					gl.account,
					gl.debit,
					gl.credit,
					bwa.type,
					bwa.funktion
				from
					`tabGL Entry` gl,
					`tabAccount` acc,
					`tabBWA` bwa
				where
					gl.account = acc.name
					and gl.posting_date >= str_to_date('{dvon}', '%Y-%m-%d')
                	and gl.posting_date <= str_to_date('{dbis}', '%Y-%m-%d')
					and CAST(acc.account_number AS INTEGER) >= CAST(bwa.konto_von AS INTEGER)
					and CAST(acc.account_number AS INTEGER) <= CAST(bwa.konto_bis AS INTEGER)
					and bwa.zeile = {line}
				""".format(line = row, dvon=filters.get('from_date'), dbis=filters.get('to_date'))
		gl_entries += frappe.db.sql(sel, as_dict=1)

		sum_deb = 0
		sum_cred = 0
		sum_account = 0
		sum = 0

		if gl_entries:
			for account_data in gl_entries:
				if account_data.get('debit'):
					sum += account_data.get('debit')
					sum_account += account_data.get('debit')
				elif account_data.get('credit'):
					sum += account_data.get('credit')*(-1)
					sum_account += account_data.get('credit')*(-1)

			res.append({"zeile": row, 'sum': sum, 'debit_credit': sum_account, 'debit': round(sum_deb,2), 'credit': round(sum_cred,2)})

	return res

def sum_account_to_rows(sum_rows, account_values):
	sum_row_order = []
	account_rows = []

	for row in sum_rows:
		if row.get('zeile') not in sum_row_order:
			sum_row_order.append(row.get('zeile'))

	for account in account_values:
		if account.get('zeile') not in account_rows:
			account_rows.append(account.get('zeile'))

	complete_order = []

	sum_row_order.sort()
	account_rows.sort()

	sum = 0
	for account in sum_row_order:
		for row in sum_rows:
			if account == row.get('zeile'):
				line = int(row.get('zeile_von'))
				while line <= int(row.get('zeile_bis')):
					if str(line) in account_rows and str(line) not in complete_order:
						for elem in account_values:
							if elem.get('zeile') == str(line):
								sum += elem.get('debit') + (-1 * elem.get('credit'))
								complete_order.append(elem.get('zeile'))

					elif str(line) in sum_row_order and str(line) not in complete_order:
						for elem in sum_rows:
							if elem.get('zeile') == str(line):
								sum += elem.get('sum')
								complete_order.append(elem.get('zeile'))
					line += 1
				row['sum'] = sum
				sum = 0

	return sum_rows

def calc_short_bwa(bwa, accounts):
	ordered_list = []
	for row in accounts:
		if row.get('zeile') not in ordered_list and row.get('zeile') != '' and row.get('zeile') is not None:
			ordered_list.append(row.get('zeile'))
	ordered_list.sort()
	for row in ordered_list:
		for bwa_row in accounts:
			if row == bwa_row.get('zeile'):
				if bwa_row.get('zeile_von') and bwa_row.get('zeile_bis') and bwa_row.get('konto_von'):
					bwa_row['sum'] = get_row_5440(bwa_row, bwa, accounts)
				elif bwa_row.get('konto_von') and not bwa_row.get('konto_bis'):
					bwa_row['sum'] = get_row_subtotal(bwa_row.get('konto_von'), bwa)
				elif bwa_row.get('konto_von') and bwa_row.get('konto_bis') and bwa_row.get('funktion') == '1':
					bwa_row['sum'] = get_span_subtotal(bwa_row.get('konto_von'), bwa_row.get('konto_bis'), bwa)
				elif bwa_row.get('konto_von') and bwa_row.get('konto_bis') and bwa_row.get('funktion') == '2':
					bwa_row['sum'] = get_row_addition(bwa_row.get('konto_von'), bwa_row.get('konto_bis'), bwa)
				elif bwa_row.get('zeile_von') and bwa_row.get('zeile_bis') and bwa_row.get('bwa_funktion') == '1':
					bwa_row['sum'] = function_key_1(bwa_row, accounts)
				elif bwa_row.get('zeile_von') and bwa_row.get('zeile_bis') and bwa_row.get('bwa_funktion') == '2':
					bwa_row['sum'] = function_key_2(bwa_row, accounts)

	return accounts

def get_row_5440(bwa_row, bwa, accounts):
	res = 0
	for sum in bwa:
		if sum.get('zeile') == bwa_row.get('konto_von'):
			res += sum.get('sum')

	for sum in accounts:
		if sum.get('zeile') == bwa_row.get('zeile_von') or sum.get('zeile') == bwa_row.get('zeile_bis'):
			res += sum.get('sum')

	return res

def get_row_addition(r_from, r_to, accounts):
	res = 0
	for sum in accounts:
		if sum.get('zeile') == r_from or sum.get('zeile') == r_to:
			res += sum.get('sum')
	return res

def get_span_subtotal(r_from, r_to, accounts):
	res = 0
	for sum in accounts:
		if sum.get('zeile') >= r_from and sum.get('zeile') <= r_to:
			res += sum.get('sum')

	return res

def get_row_subtotal(row, bwa):
	"""
	calculation of the given row for his subtotal
	:param row: the row for which the subtotal is to be calculated
	:param bwa: all accounts with data from database
	:return: the subtotal as value
	"""
	res = 0
	for sum in bwa:
		if sum.get('zeile') == row:
			res += sum.get('sum')

	return round(res, 2)


def calc_bwa(sub_rows, account_totals):
	"""
	calucaltion of all bwa-accounts subtotals
	"""
	ordered_subtotal = []

	for elem in sub_rows:
		if elem.get('zeile') not in ordered_subtotal:
			ordered_subtotal.append(elem.get('zeile'))
	ordered_subtotal.sort()

	res = sub_rows + account_totals
	for subtotal in ordered_subtotal:
		sum = 0
		for sub in sub_rows:
			if sub.get('zeile') == subtotal:
				if int(sub.get('funktion')) == 1:
					#el = function_key_1(sub, res)
					sum += function_key_1(sub, res)
				elif int(sub.get('funktion')) == 2:
					sum += function_key_2(sub, res)
				sub['sum'] = round(sum,2)

	return res

def function_key_1(sub_row, account_totals):
	"""
	Funktionsschlüssel 1 (Addition)

	Mit dem Funktionsschlüssel 1 addieren Sie alle Zeilenwerte, die innerhalb des von Ihnen bestimmten
	Zeilenintervalls liegen.
	Wenn mehrere nicht aufeinander folgende Zeilen addiert werden sollen, sind mehrere Eingabezeilen notwendig.
	Es ist zu beachten, dass vorzeichengerecht addiert wird, d. h. ein Zeilenwert mit positivem Vorzeichen und ein
	Zeilenwert mit negativem Vorzeichen werden saldiert.
	"""

	sum = 0
	zeile = ''
	for sub in account_totals:
		if (sub.get('zeile') or sub.get('sort_zeile')) >= sub_row.get('zeile_von')\
		and (sub.get('zeile') or sub.get('sort_zeile')) <= sub_row.get('zeile_bis'):
			if zeile == '':
				try:
					zeile = sub.get('zeile')
				except:
					zeile = sub.get('sub_zeile')
			if sub.get('sum'):
				sum += sub.get('sum')
			elif sub.get('debit') or sub.get('credit'):
				sum += sub.get('debit') + (-1 * sub.get('credit'))

	#return {'sum': sum, 'zeile': zeile}
	return sum

def function_key_2(sub_row, account_totals):
	"""
	Funktionsschlüssel 2 (Subtraktion)

	Bei Anwendung des Funktionsschlüssels 2 ziehen Sie den Wert der Zeile bis vom Wert der Zeile von ab.
	Subtraktion mehrerer Zeilenwerte von einer anderen Zeile Wenn Sie mehrere Zeilenwerte von einer Zeile abziehen
	möchten, haben Sie 2 Möglichkeiten:

	1. Sie bilden die Summe der zu subtrahierenden Zeilenwerte in einer eigenen BWA-Zeile und subtrahieren dann den
	Wert dieser Summenzeile von der gewünschten BWA-Zeile.

	2. Sie ziehen die zu subtrahierenden Zeilenwerte von einer Leerzeile ab. Dies bewirkt, wie die Subtraktion eines
	Werts von Null, einen Vorzeichenwechsel. Anschließend addieren Sie die Zeilenwerte mit dem gewechselten Vorzeichen
	zu dem Wert, von dem die Zeilenwerte ursprünglich subtrahiert werden sollten. Das Ergebnis entspricht dem einer
	Subtraktion.
	"""
	sum = 0
	for sub in account_totals:
		if sub_row.get('zeile_von') == sub.get('zeile')\
		or sub_row.get('zeile_bis') == sub.get('zeile'):
			sum += sub.get('sum')

	return sum

def function_key_7():
	"""
	Funktionsschlüssel 7

	Der Funktionsschlüssel 7 ermittelt den Gesamtsaldo der Jahresverkehrszahlen (JVZ) ohne Eröffnungsbilanzwerte (EB).
	Zeilenbereich 1000 (Kurzfristige Erfolgsrechnung)

	Im Zeilenbereich 1000 bewirkt der Konten-Funktionsschlüssel 7 die Ermittlung des Gesamtsaldos der
	Jahresverkehrszahlen (JVZ) ohne Berücksichtigung der Eröffnungsbilanzwerte (EB). Der Gesamtsaldo wird sowohl in die
	Spalte des Auswertungsmonats bzw. Auswertungsquartals wie auch in die Spalte der kumulierten Monatswerte
	eingestellt.

	Zeilenbereich 2000 (Bewegungsbilanz)
	Die Ermittlung des Gesamtsaldos der Jahresverkehrszahlen (JVZ) erfolgt ohne Eröffnungsbilanzwerte (EB). Bei
	positivem Gesamtsaldo erfolgt der Ausweis in der Spalte Mittelverwendung, bei negativem Gesamtsaldo in der Spalte
	Mittelherkunft.

	Zeilenbereich 3000 (Statische Liquidität)
	Im Zeilenbereich 3000 wird mit dem Konten-Funktionsschlüssel 7 der Gesamtsaldo der Jahresverkehrszahlen (JVZ) ohne
	Eröffnungsbilanzwerte (EB) ermittelt und in die Spalte des aktuellen Auswertungszeitraums und in die Spalte des
	vorhergehenden Auswertungszeitraums eingestellt.
	"""
	pass

def function_key_18():
	"""
	Funktionsschlüssel 18

	Der Funktionsschlüssel 18 ermittelt den bestimmten Saldo der Monatsverkehrszahlen (MVZ) einschließlich
	Eröffnungsbilanzwerte (EB) bzw. der Jahresverkehrszahlen (JVZ) inklusive Eröffnungsbilanzwerte (EB).

	Zeilenbereich 1000 (Kurzfristige Erfolgsrechnung)
	Hier wird der Bestimmte Saldo auf Basis der Monatsverkehrszahlen (MVZ) inklusive Eröffnungsbilanzwerte (EB)
	ermittelt und in die Spalte des Auswertungsmonats bzw. Auswertungsquartals eingestellt. In die Spalte der
	kumulierten Monatswerte wird der Bestimmte Saldo der Jahresverkehrszahlen (JVZ) unter Berücksichtigung der
	Eröffnungsbilanzwerte (EB) eingetragen.

	Zeilenbereich 2000 (Bewegungsbilanz)
	Im Zeilenbereich 2000 wird der Bestimmte Saldo der Jahresverkehrszahlen (JVZ) einschließlich Eröffnungsbilanzwerte
	(EB) errechnet und in die Spalte Mittelverwendung eingestellt. Die Spalte Mittelherkunft bleibt unberücksichtigt.

	Zeilenbereich 3000 (Statische Liquidität)
	Der Bestimmte Saldo wird aus den Monatsverkehrszahlen (MVZ) unter Einbeziehung der Eröffnungsbilanzwerte (EB)
	errechnet und in der Spalte des aktuellen Auswertungszeitraums des Zeilenbereichs 3000 ausgewiesen. Für die Spalte
	des vorhergehenden Auswertungszeitraums errechnet sich der Bestimmte Saldo aus den Jahresverkehrszahlen (JVZ)
	einschließlich Eröffnungsbilanzwerten.
	"""
	pass

def function_key_28():
	"""
	Funktionsschlüssel 28

	Der Funktionsschlüssel 28 greift bei der Ermittlung des bestimmten Gruppensaldos auf die Salden der
	Monatsverkehrszahlen (MVZ) und der Jahresverkehrszahlen (JVZ) zu. Eröffnungsbilanzwerte (EB) werden nicht
	berücksichtigt.

	Zeilenbereich 1000 (Kurzfristige Erfolgsrechnung) In die Spalte des Auswertungsmonats bzw. Auswertungsquartals wird
	der Bestimmte Gruppensaldo der Monatsverkehrszahlen (MVZ), in die Spalte der kumulierten Monatswerte der Bestimmte
	Gruppensaldo der Jahresverkehrszahlen (JVZ) eingestellt.

	Zeilenbereich 2000
	(Bewegungsbilanz) Es wird nur die Spalte Mittelverwendung berücksichtigt, in der der Bestimmte Gruppensaldo der
	Jahresverkehrszahlen (JVZ) ausgewiesen wird. In die Spalte Mittelherkunft werden keine Werte eingestellt.

	Zeilenbereich 3000 (Statische Liquidität)
	Der Bestimmte Gruppensaldo der Monatsverkehrszahlen (MVZ) wird in der Spalte des aktuellen Auswertungszeitraums
	ausgewiesen. In der Spalte des vorhergehenden Auswertungszeitraums erscheint der Bestimmte Gruppensaldo der
	Jahresverkehrszahlen (JVZ).
	"""
	pass

def get_accounts(zeile, acc_from, acc_to, date_from, date_to):
	sel =	"""
			select
				acc.account_number,
				gl.account,
				sum(gl.debit) as debit,
				sum(gl.credit) as credit,
				bwa.type,
				bwa.funktion
			from
				`tabGL Entry` gl,
				`tabAccount` acc,
				`tabBWA` bwa
			where
				gl.account = acc.name
				and konto_von = {acc_from}
				and konto_bis = {acc_to}
				and acc.account_number >= {acc_from}
				and acc.account_number <= {acc_to}
				and gl.posting_date >= str_to_date('{date_from}', '%Y-%m-%d')
                and gl.posting_date <= str_to_date('{date_to}', '%Y-%m-%d')
			group by gl.account,acc.account_number
			order by acc.account_number
			""".format(acc_from=acc_from, acc_to=acc_to, date_from=date_from, date_to=date_to)
	gl_entries = frappe.db.sql(sel, as_dict=1)

	return gl_entries

def get_space():
	sel =	"""
			select
				zeile,
				zeile as "sort_zeile",
				funktion
			from
				`tabBWA`
			where
				funktion = 9
				and zeile > 1010
				and zeile not in (1094,1301,1321,1331,1350,1390)
			order by
				zeile
			"""
	res = frappe.db.sql(sel, as_dict=1)

	return res

def get_bwa_result(filters):
	accounts = get_bwa_accounts()
	sum_rows = get_bwa_sum_rows()

	account_values = get_gl_entries(accounts, filters)
	res = calc_bwa(sub_rows=sum_rows, account_totals=account_values)
	#res = sum_account_to_rows(sum_rows=sum_rows, account_values=account_values)
	return res

def get_bwa_short_result(filters):
	accounts = get_bwa_short_accounts()
	bwa = get_bwa_result(filters)

	res = calc_short_bwa(bwa, accounts)
	return res

def get_bwa_account_result(filters):
	account_rows = get_bwa_accounts()
	subtotal_rows = get_bwa_sum_rows()
	if not subtotal_rows:
		return
	row_sum = get_gl_entries(account_rows, filters)
	acc_res = []

	for elem in account_rows:
		head = 0
		if elem.get('konto_von') and elem.get('konto_bis'):

			acc_subtotal = get_accounts(zeile=elem.get('zeile'),
										acc_from=elem.get('konto_von'),
										acc_to=elem.get('konto_bis'),
										date_from=filters.get('from_date'),
										date_to=filters.get('to_date'))

			for subtotal in acc_subtotal:
				sum_acc = 0
				sum = 0
				if (subtotal.get('type')).upper() == "S":
					if subtotal.get('debit'):
						sum_acc += subtotal.get('debit')
					if subtotal.get('credit'):
						sum_acc += subtotal.get('credit')*(-1)
				elif (subtotal.get('type')).upper() == "H":
					if subtotal.get('debit'):
						sum_acc += subtotal.get('debit')*(-1)
					if subtotal.get('credit'):
						sum_acc += subtotal.get('credit')

				if head == 0:
					for acc_sum in row_sum:
						if acc_sum.get('zeile') == elem.get('zeile'):
							sum = acc_sum.get('sum')

					acc_res.append(	{
						'zeile': elem.get('zeile'),
						'sort_zeile': elem.get('zeile'),
						'sort_name': elem.get('zeilen_name'),
						'zeilen_name': elem.get('zeilen_name'),
						'account': subtotal.get('account_number'),
						'name': subtotal.get('account'),
						'sum': sum_acc,
						'type': elem.get('type'),
						'funktion': elem.get('funktion'),
						'subtotal': round(sum, 2)
					})
					head = 1
				else:
					acc_res.append({
						'zeile': elem.get('zeile'),
						'sort_zeile': elem.get('zeile'),
						'sort_name': elem.get('zeilen_name'),
						'account': subtotal.get('account_number'),
						'name': subtotal.get('account'),
						'sum': sum_acc,
						'type': elem.get('type'),
						'funktion': elem.get('funktion')
					})

	sub_acc = []
	for acc in acc_res:
		if acc.get('zeile') not in sub_acc:
			sub_acc.append(acc.get('zeile'))

	space = get_space()
	acc_res += space
	return acc_res
