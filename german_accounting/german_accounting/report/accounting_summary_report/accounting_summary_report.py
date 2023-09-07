# -*- coding: utf-8 -*-
# Copyright (c) 2022, LIS and contributors
# For license information, please see license.txt

import frappe
import datetime

def execute(filters=None):
	columns, data = [], []
	if not (filters.month and filters.get("report_type") == "Monatsweise") and \
			not (filters.pair and filters.get("report_type") == "Monatspaare") and \
			not (filters.quarter and filters.get("report_type") == "Quartal") and \
			not (filters.year and filters.get("report_type") == "Kalenderjahr"):
		return columns, data
	columns = get_columns()
	data = sorted(get_summary_data(filters), key=lambda k: ("service_type" not in k, k.get("service_type", None)), reverse=True)

	return columns, data


def get_columns():
	columns = [
		{
			"label": "Länderkennzeichen",
			"fieldname": "country_code",
			"fieldtype": "Data",
		},
		{
			"label": "USt-IdNr. des Erwerbers/ Unternehmers in einem anderen EU- Mitgliedstaat",
			"fieldname": "tax_id",
			"fieldtype": "Data",
		},
		{
			"label": "Summe der Bemessungsgrundlagen",
			"fieldname": "summary_total",
			"fieldtype": "Currency",
		},
		{
			"label": "Leistungsart",
			"fieldname": "service_type",
			"fieldtype": "Data",
		},
	]
	return columns


def get_summary_data(filters):
	# Accounting Summary Report
	settings = frappe.get_single("Accounting Summary Report")
	start, end = get_filter_mapping(filters)
	accounts = [account for account in settings.accounts]
	account_list = [account.account for account in settings.accounts]

	gl_entries = frappe.get_list("GL Entry",
								 filters={
									 "voucher_type": "Sales Invoice",
									 "account": ["in", account_list], "posting_date": ["between", (start, end)]},
								 fields=["name", "voucher_type", "voucher_no"])

	detailed_data = []
	ui_list =  []
	for entry in gl_entries:
		gl_entry = frappe.get_doc("GL Entry", entry.name)
		invoice = frappe.get_doc(entry.voucher_type, entry.voucher_no)
		customer = frappe.get_doc("Customer", invoice.customer)
		region = frappe.get_doc("Territory", customer.territory)
		for account in accounts:
			if account.account == gl_entry.account:
				service_type = account.service_type
				data = {
					"country_code": region.country_code,
					"tax_id": (customer.tax_id).replace(region.country_code, ""),
					"summary_total": int(invoice.grand_total),
				}
				if service_type:
					data["service_type"] = service_type
				detailed_data.append(data)
				if (customer.tax_id).replace(region.country_code, "") not in ui_list:
					ui_list.append((customer.tax_id).replace(region.country_code, ""))

	if filters.view in ["Grouped", "Zusammengefasst"]:
		# group all vouchers by customer and by accounts
		grouped_data = []
		for tax_id in ui_list:
			total_0, total_1, total_2  = 0, 0 ,0
			country_code = ""
			for row in detailed_data:
				if row.get("tax_id") != tax_id:
					continue
				country_code = row.get("country_code")
				if row.get("service_type") == "1":
					total_1 += row.get("summary_total")
				elif row.get("service_type") == "2":
					total_2 += row.get("summary_total")
				else:
					total_0 += row.get("summary_total")
			if total_0:
				grouped_data.append({
					"country_code": country_code,
					"tax_id": tax_id,
					"summary_total": total_0
				})
			if total_1:
				grouped_data.append({
					"country_code": country_code,
					"tax_id": tax_id,
					"summary_total": total_1,
					"service_type": 1
				})
			if total_2:
				grouped_data.append({
					"country_code": country_code,
					"tax_id": tax_id,
					"summary_total": total_2,
					"service_type": 2
				})
		return grouped_data
	else:
		return detailed_data


def sum_grouped_totals(tax_id, detailed_data, service_type=None):
	total = 0
	country_code = ""
	for row in detailed_data:
		if row.get("tax_id") != tax_id:
			continue

		country_code = row.get("country_code")
		if row.get("service_type") == service_type:
			total += sum_grouped_totals(row.get("tax_id"), row, 1)
	return  {
		"country_code": country_code,
		"tax_id": tax_id,
		"summary_total": total,
		"service_type": service_type
	}

# mapping for each date-range
def get_filter_mapping(filters):
	start, end = "", ""
	if filters.report_type == "Monatsweise":
		map = {"Jan.": 1,
				 "Feb.": 2,
				 "März": 3,
				 "April": 4,
				 "Mai": 5,
				 "Juni": 6,
				 "Juli": 7,
				 "Aug.": 8,
				 "Sept.": 9,
				 "Okt.": 10,
				 "Nov.": 11,
				 "Dez.": 12}
		start = get_start_date(map.get(filters.month), filters.year)
		end = get_end_date(map.get(filters.month), filters.year)
	elif filters.report_type == "Monatspaare":
		map = {"Jan/Feb": [1, 2],
				"April/Mai": [4, 5],
				"Juli/Aug": [7, 8],
				"Okt/Nov": [10, 11]}
		start = get_start_date(map.get(filters.pair)[0], filters.year)
		end = get_end_date(map.get(filters.pair)[1], filters.year)
	elif filters.report_type == "Quartal":
		map = {"1. Quart.": [1, 3],
				   "2. Quart.": [4, 6],
				   "3. Quart.": [7, 9],
				   "4. Quart.": [10, 12]}
		start = get_start_date(map.get(filters.quarter)[0], filters.year)
		end = get_end_date(map.get(filters.quarter)[1], filters.year)
	elif filters.report_type == "Kalenderjahr":
		start = datetime.date(int(filters.year), 1, 1)
		end = datetime.date(int(filters.year), 12, 31)
	else:
		frappe.throw("Please select correct filters!")
	return start, end


def get_start_date(month, year):
	return datetime.date(int(year), month, 1)


def get_end_date(month, year):
	if month == 12:
		return datetime.date(int(year) + 1, 1, 1) - datetime.timedelta(days=1)
	else:
		return datetime.date(int(year), month + 1, 1) - datetime.timedelta(days=1)
