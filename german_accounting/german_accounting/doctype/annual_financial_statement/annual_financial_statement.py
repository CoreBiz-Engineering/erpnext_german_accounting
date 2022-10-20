# Copyright (c) 2022, LIS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class AnnualFinancialStatement(Document):
	pass


# Copyright (c) 2022, LIS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import time, calendar
from datetime import datetime, timedelta, date

class AnnualFinancialStatement(Document):
	def validate(self):
		pass

	@frappe.whitelist()
	def select_entries(self, account_type, fiscal_year, submit):
		# select all accounts with given account_type
		fiscal_year = int(fiscal_year)
		settings = frappe.get_single("Jahresabschlusseinstellungen")
		accounts = []
		if account_type == "Aktiva/Passiva":
			self.closing_account = settings.activa_passiva_account
			for account in settings.activa_passiva_parent_accounts:
				accounts += self.get_all_child_accounts(account.account)
		elif account_type == "Debitor":
			self.closing_account = settings.debitor_account
			for account in settings.debitor_parent_accounts:
				accounts += self.get_all_child_accounts(account.account)
		elif account_type == "Kreditor":
			self.closing_account = settings.creditor_account
			for account in settings.creditor_parent_accounts:
				accounts += self.get_all_child_accounts(account.account)

		# exit if not accounts are defined
		if not accounts:
			return

		# select all GL Entries to close
		entry_list = self.get_account_amount(accounts, account_type, fiscal_year)

		# exit if no entries to close
		if not entry_list:
			return

		posting_date = date(fiscal_year+1, 1, 1) #
		saved_entries = [] # list to update all selected GL Entries to avoid duplication
		log_data = {} # dict to create a small log for history
		value = 0
		for entry in entry_list:
			if entry.debit:
				value = entry.debit
				if entry.sum_entry:
					value -= entry.sum_entry
				# sum debit values for Log
				if log_data.get(entry.account):
					log_data[entry.account]["debit"] += value
					log_data[entry.account]["count"] += 1
				else:
					log_data[entry.account] = {"debit": 0, "credit": 0, "count": 0}
					log_data[entry.account]["debit"] += value
					log_data[entry.account]["count"] += 1

			elif entry.credit:
				value = entry.credit
				if entry.sum_entry:
					value -= entry.sum_entry
				# sum credit values for Log
				if log_data.get(entry.account):
					log_data[entry.account]["credit"] += value
					log_data[entry.account]["count"] += 1
				else:
					log_data[entry.account] = {"debit": 0, "credit": 0, "count": 0}
					log_data[entry.account]["credit"] += value
					log_data[entry.account]["count"] += 1

			# create journal entry for each closing entry
			journal_entry = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": posting_date,
				"cheque_no": entry.voucher_no,
				"cheque_date": posting_date,
				"bill_no": entry.voucher_no,
				"is_opening": "Yes"
			})
			if account_type in ["Debitor", "Kreditor"] and entry.debit:
				# set debit-part
				row = journal_entry.append("accounts", {})
				row.account = entry.account
				row.debit = value
				row.debit_in_account_currency = value
				row.party_type = entry.party_type
				row.party = entry.party

				# set credit-part
				row = journal_entry.append("accounts", {})
				row.account = self.closing_account
				row.credit = value
				row.credit_in_account_currency = value
			elif account_type in ["Debitor", "Kreditor"] and entry.credit:
				# set debit-part
				row = journal_entry.append("accounts", {})
				row.account = entry.account
				row.credit = value
				row.credit_in_account_currency = value
				row.party_type = entry.party_type
				row.party = entry.party

				# set credit-part
				row = journal_entry.append("accounts", {})
				row.account = self.closing_account
				row.debit = value
				row.debit_in_account_currency = value
			saved_entries.append(entry.name)
			if submit:
				journal_entry.save()

		if submit:
			for gl in saved_entries:
				gl_entry = frappe.get_doc("GL Entry", gl)
				gl_entry.closing_submitted = 1
				gl_entry.save()

		# create log entry for current closing process
		closing_log = frappe.get_doc({
			"doctype": "Jahresabschluss Log",
			"closing_type": account_type,
			"posting_date": datetime.now()
		})

		for log in log_data:
			row = closing_log.append("account_closing_detail", {})
			row.account = log
			row.debit = log_data[log]["debit"]
			row.credit = log_data[log]["credit"]
			row.amount_entries = log_data[log]["count"]
		if submit:
			closing_log.save()
		closing_log.save()


	def get_all_child_accounts(self, parent):
		# get all accounts from all parents
		account_names = frappe.get_all("Account", filters={"parent_account": parent}, fields=["name", "is_group"])
		account_list = []
		for account in account_names:
			if account.is_group:
				# get childs of parent with recursive logic
				account_list += self.get_all_child_accounts(account.name)
			else:
				# get data of account (not parent account)
				account_list.append(account.name)
		return account_list


	def get_account_amount(self, accounts, party, fiscal_year):
		# closing submitted
		debit =	"""
				SELECT
					gl1.name,
					gl1.account,
					gl1.voucher_no,
					gl1.against_voucher,
					gl1.debit,
					gl1.credit,
					(SELECT COUNT(*) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no) AS "entry count",
					CASE
						WHEN gl1.debit > 0 THEN (SELECT SUM(credit) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no)
						WHEN gl1.credit > 0 THEN (SELECT SUM(debit) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no)
					END AS sum_entry,
					CASE
						WHEN gl1.debit > 0 THEN "credit"
						WHEN gl1.credit > 0 THEN "debit"
					END AS type,
					gl1.party_type,
					gl1.party
				FROM
					`tabGL Entry` gl1
				WHERE 
					gl1.account IN %s AND
					gl1.closing_submitted != 1 AND
					gl1.fiscal_year = %s AND
					(
						gl1.debit > (
							SELECT sum(gl2.credit)
							FROM `tabGL Entry` gl2
							WHERE gl2.against_voucher = gl1.voucher_no
						) OR 
						gl1.credit > (
							SELECT SUM(gl2.debit)
							FROM `tabGL Entry` gl2
							WHERE gl2.against_voucher = gl1.voucher_no
						)
					)
				GROUP BY
					gl1.voucher_no
				ORDER BY
					gl1.account, gl1.posting_date
				"""

		debit_credit =	"""
						SELECT
							gl1.name,
							gl1.account,
							gl1.voucher_no,
							gl1.against_voucher,
							gl1.debit,
							gl1.credit,
							(SELECT count(*) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no) AS "entry count",
							CASE
								WHEN gl1.debit > 0 THEN (SELECT sum(credit) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no)
								WHEN gl1.credit > 0 THEN (SELECT sum(debit) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no)
							END AS sum_entry,
							CASE
								WHEN gl1.debit > 0 THEN "credit"
								WHEN gl1.credit > 0 THEN "debit"
							END AS type, 
							gl1.party_type,
							gl1.party
						From
							`tabGL Entry` gl1
						WHERE 
							gl1.against_voucher IS NULL AND
							gl1.account IN %s AND
							gl1.closing_submitted != 1 AND
							gl1.fiscal_year = %s AND
							(
								(
									gl1.debit > 0 AND 
									(
										gl1.debit > (
											SELECT SUM(gl2.credit)
											FROM `tabGL Entry` gl2
											WHERE gl2.against_voucher = gl1.voucher_no
											) OR (
											SELECT SUM(gl2.credit)
											FROM `tabGL Entry` gl2
											WHERE gl2.against_voucher = gl1.voucher_no) IS NULL
									)
								) OR (
									gl1.credit > 0 AND 
									(gl1.credit > (
										SELECT sum(gl2.debit)
										FROM `tabGL Entry` gl2
										WHERE gl2.against_voucher = gl1.voucher_no
										) OR (
										SELECT SUM(gl2.debit)
										FROM `tabGL Entry` gl2
										WHERE gl2.against_voucher = gl1.voucher_no) IS NULL
									)
								)
							)
						ORDER BY
							gl1.account, gl1.posting_date
						"""

		aktiva_passiva =	"""
							SELECT
								gl1.name,
								gl1.account,
								sum(gl1.debit) AS debit,
								sum(gl1.credit) AS credit,
								(SELECT count(*) FROM `tabGL Entry` gl2 WHERE gl2.against_voucher = gl1.voucher_no) AS "entry count"
							FROM
								`tabGL Entry` gl1
							WHERE
							gl1.against_voucher is NULL AND
								gl1.account IN %s AND
								gl1.fiscal_year = %s AND
								gl1.credit > 0 AND
								(
									(
										gl1.credit > (
											SELECT sum(gl2.debit)
											FROM `tabGL Entry` gl2
											WHERE gl2.against_voucher = gl1.voucher_no
										) OR (
											SELECT sum(gl2.debit)
											FROM `tabGL Entry` gl2
											WHERE gl2.against_voucher = gl1.voucher_no
											) is NULL
									) OR (
										gl1.debit > (
											SELECT sum(gl2.credit)
											FROM `tabGL Entry` gl2
											WHERE gl2.against_voucher = gl1.voucher_no
										) OR (
										SELECT sum(gl2.credit)
										FROM `tabGL Entry` gl2
										WHERE gl2.against_voucher = gl1.voucher_no
										) is NULL
									)
								)
							GROUP BY
								gl1.account
							"""

		totals = []
		if party == "Debitor":
			totals += frappe.db.sql(debit, (tuple(accounts), fiscal_year), as_dict=1)
		if party in ["Debitor", "Kreditor"]:
			totals += frappe.db.sql(debit_credit, (tuple(accounts), fiscal_year), as_dict=1)
		elif party == "Aktiva/Passiva":
			totals += frappe.db.sql(aktiva_passiva, (tuple(accounts), fiscal_year), as_dict=1)
		return totals