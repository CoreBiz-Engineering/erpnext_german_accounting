# Copyright (c) 2022, LIS Engineering and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from erpnext import get_default_company
from erpnext.accounts.doctype.journal_entry.journal_entry import get_payment_entry_against_invoice
from frappe import _
import json, csv, time, datetime, os, re, datetime, hashlib


@frappe.whitelist()
def read_csv_file(file_url):
    file = file_url.split("/")[-1]
    path = frappe.get_site_path('private', 'files', file)

    # get and prepare naming_series for regex
    invoice = frappe.get_meta("Sales Invoice")
    pre_fix = invoice.get_field("naming_series").options.split("\n")[0].split(".")[0]
    pattern = '('+pre_fix.replace("-",".?")+'\d{5})'

    paid_invoices = []
    with open(path) as f:
        bank_file = list(csv.DictReader(f, delimiter=';'))

    for row in bank_file:

        if not row.get("Buchungstext") == "Gutschrift":
            continue
        print()
        print()
        print(row.get("Buchungstag"))
        print(datetime.datetime.strptime(row.get("Buchungstag"), '%d.%m.%Y'))
        print()
        print(">>>>>")
        print()
        row["Buchungstag"] = datetime.datetime.strptime(row.get("Buchungstag"), '%d.%m.%Y')
        invoice_list = re.findall(pattern, row.get("Verwendungszweck"))
        row["Betrag"] = float(row.get("Betrag").replace(",","."))
        if invoice_list:
            invoice_list = [invoice[:2] + '-' + invoice[2:] if "-" not in invoice else invoice for invoice in invoice_list]
            # create `Bank Account`
            check_bank_account(row, frappe.get_doc("Sales Invoice", invoice_list[0]))

        if not invoice_list:
            invoice_list = re.findall(r'([\,|\s]?3\d{4}[\,|\s|\n]?)', row.get("Verwendungszweck"))
            invoice_list = [pre_fix+invoice.strip().replace(",","") for invoice in invoice_list]

        # Try to find invoices via IBAN to select customer and invoice
        if not invoice_list:
            # last try to find voucher with IBAN
            bank_account = frappe.get_list("Bank Account", filters={"iban": row.get("IBAN Zahlungsbeteiligter")})
            if bank_account:
                bank_account = frappe.get_doc("Bank Account", bank_account[0].name)
                invoice_list = frappe.get_list(
                    "Sales Invoice",
                    filters={
                        "customer": bank_account.party,
                        "outstanding_amount": row.get("Betrag")
                    }
                )
                if invoice_list:
                    invoice_list = [invoice.name for invoice in invoice_list]
                    row["hint"] = "Vorschlag, RE wurde mittels IBAN ermittelt!"


        # Try to find invoices via transfer amount
        if not invoice_list:
            invoice_list = frappe.get_list(
                "Sales Invoice",
                filters={
                    "outstanding_amount":row.get("Betrag"),
                    "status":["in",["Overdue", "Unpaid"]]
                }
            )
            if invoice_list:
                invoice_list = [invoice.name for invoice in invoice_list]
                row["hint"] = "Vorschlag, RE wurde mittels Betrag ermittelt!"

        if invoice_list:
            accumulated = 0
            for invoice in invoice_list:
                if not frappe.db.exists("Sales Invoice", invoice):
                    continue
                doc = frappe.get_doc("Sales Invoice", invoice)

                if doc.status == "Paid":
                    continue
                date = datetime.datetime.strftime(row.get("Buchungstag"), "%Y-%d-%m")
                #id = (hashlib.md5((date+"-"+row.get("IBAN Zahlungsbeteiligter")+"-"+doc.name).encode())).hexdigest()
                id = date + "-" + row.get("IBAN Zahlungsbeteiligter") + "-" + doc.name
                if not frappe.db.exists("Bank Assignment", id):
                    # create hash of multiple field data for shorter id
                    create_log_entry(id, row, doc)

                bank_assignment = frappe.get_doc("Bank Assignment", id)
                if bank_assignment.status == "Paid":
                    continue
                accumulated += doc.outstanding_amount
                op_row = frappe._dict()
                op_row.id = id
                op_row.customer = doc.customer
                op_row.customer_name = doc.customer_name
                op_row.sales_invoice = doc.name
                op_row.account = doc.debit_to
                op_row.customer_bank = row.get("Name Zahlungsbeteiligter")
                op_row.status = _(bank_assignment.status)
                op_row.grand_total = doc.grand_total
                op_row.outstanding_amount = doc.outstanding_amount
                op_row.bank_posting_date = row.get("Buchungstag")
                op_row.bank_total = row.get("Betrag")
                op_row.purpose_of_use = row.get("Verwendungszweck")
                if row.get("hint"):
                    op_row.hint = row.get("hint")
                paid_invoices.append(op_row)
        else:
            # show row as information in report
            op_row = frappe._dict()
            op_row.customer_name = row.get("Name Zahlungsbeteiligter")
            op_row.status = _("Unknown")
            op_row.bank_posting_date = row.get("Buchungstag")
            op_row.bank_total = row.get("Betrag")
            op_row.purpose_of_use = row.get("Verwendungszweck")
            op_row.hint = "Keine Rechnung gefunden!"
            paid_invoices.append(op_row)
    if os.path.exists(path):
        '''for file in frappe.get_list("File", filters={"file_url": file_url}):
            frappe.delete_doc("File", file.name)
            frappe.db.commit()'''

    columns = [
        {
          "label": "ID",
          "fieldname": "id",
          "fieldtype": "Data",
          "hidden": 1
        },{
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer"
        },{
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data"
        },{
            "label": "Account",
            "fieldname": "account",
            "fieldtype": "Data"
        },{
            "label": "Sales Invoice",
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice"
        },{
            "label": "Grand Total",
            "fieldname": "grand_total",
            "fieldtype": "Currency"
        },{
            "label": "Outstanding Amount",
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency"
        },{
            "label": "Kunde Überweisung",
            "fieldname": "customer_bank",
            "fieldtype": "Data"
        },{
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data"
        },{
            "label": _("Hint"),
            "fieldname": "hint",
            "fieldtype": "Data"
        },{
            "label": "Posting Date",
            "fieldname": "bank_posting_date",
            "fieldtype": "Date"
        },{
            "label": "Amount",
            "fieldname": "bank_total",
            "fieldtype": "Currency"
        },{
            "label": "Verwendungszweck",
            "fieldname": "purpose_of_use",
            "fieldtype": "Data",
            "width": "500px"
        }
    ]
    if not paid_invoices:
        return
    return columns, paid_invoices


def check_bank_account(row, doctype):
    bank_account = frappe.get_list("Bank Account", filters={"iban": row.get("IBAN Zahlungsbeteiligter")})
    print(bank_account)
    if not bank_account:
        bank_account = frappe.get_doc({"doctype": "Bank Account"})
        bank_account.bank = "Kunden Bank"
        bank_account.iban = row.get("IBAN Zahlungsbeteiligter")
        bank_account.branch_code = row.get("BIC (SWIFT-Code) Zahlungsbeteiligter")
        if doctype.doctype == "Sales Invoice":
            bank_account.account_name = doctype.customer + " " + row.get("IBAN Zahlungsbeteiligter")
            bank_account.party_type = "Customer"
            bank_account.party = doctype.customer
        bank_account.insert()
        frappe.db.commit()
    return


@frappe.whitelist()
def reconcile_bank(invoice_list):
    invoice_list = json.loads(invoice_list)

    for reconcile in invoice_list:
        reconcile = frappe._dict(reconcile)
        if not frappe.db.exists("Bank Assignment", reconcile.id):
            continue
        bank_assignment = frappe.get_doc("Bank Assignment", reconcile.id)

        if bank_assignment.status == "Paid":
            continue

        invoice = frappe.get_doc("Sales Invoice", reconcile.voucher_no)
        # "erpnext.accounts.doctype.journal_entry.journal_entry.get_payment_entry_against_invoice"
        payment = get_payment_entry_against_invoice(invoice.doctype, invoice.name)
        je = frappe.get_doc(payment)
        je.cheque_date = je.posting_date = bank_assignment.posting_date
        je.cheque_no = invoice.name
        je.user_remark = reconcile.remark
        if reconcile.bank:
            for account in je.accounts:
                if account.account_type == "Bank":
                    account.account = reconcile.bank
        je.save()

        bank_assignment.status = "Paid"
        bank_assignment.save()


def create_log_entry(id, row, invoice):
    assignment = frappe.get_doc({"doctype": "Bank Assignment"})
    assignment.name = id
    assignment.status = "Open"
    assignment.reference_type = invoice.doctype
    assignment.reference_name = invoice.name
    assignment.invoice_total = invoice.outstanding_amount
    assignment.bank_type = row.get("Buchungstext")
    assignment.iban = row.get("IBAN Zahlungsbeteiligter")
    assignment.purpose_of_use = row.get("Verwendungszweck")
    assignment.posting_date = datetime.datetime.strftime(row.get("Buchungstag"), "%Y-%d-%m")
    assignment.bank_total = row.get("Betrag")
    assignment.insert(ignore_permissions=True)
    frappe.db.commit()


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