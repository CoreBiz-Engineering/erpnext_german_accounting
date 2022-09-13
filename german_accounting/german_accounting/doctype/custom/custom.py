# -*- coding: utf-8 -*-
import frappe
from frappe import _
from erpnext import get_default_company

def get_last_bank_entry():
    company = frappe.get_doc("Company", get_default_company())
    sql =   """
            select
                name, account, posting_date
            from
                `tabGL Entry`
            where
                account = '%s'
            order by
                posting_date desc
            limit 1
            """ % company.default_bank_account

    return (frappe.db.sql(sql, as_dict=1)[0]).get("posting_date")