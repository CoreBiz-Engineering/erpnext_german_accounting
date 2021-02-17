# -*- coding: utf-8 -*-
# Copyright (c) 2019, Alyf and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json
from six import string_types

class Dunning(Document):
	pass

@frappe.whitelist()
def get_text_block(dunning_type, language, doc):
	"""
		This allows the rendering of parsed fields in the jinja template
	"""
	if isinstance(doc, string_types):
		doc = json.loads(doc)

	text_block = frappe.db.get_value('Dunning Type Text Block',
			{'parent': dunning_type, 'language': language},
			['top_text_block', 'bottom_text_block'], as_dict = 1)

	if text_block:
		return {
			'top_text_block': frappe.render_template(text_block.top_text_block, doc),
			'bottom_text_block': frappe.render_template(text_block.bottom_text_block, doc)
		}

@frappe.whitelist()
def get_address(name, party):
	print(name, party)
	address = frappe.db.sql(	"""
								select
									parent
								from
									`tabDynamic Link`
								where
									link_doctype = %s
									and parenttype = "Address"
									and link_name = %s
								""", (party, name), as_dict=1)
	if address:
		return address[0].get("parent")


@frappe.whitelist()
def get_dunning_text(name, doc):
	doc = json.loads(doc)
	dunning_type = frappe.get_doc("Dunning Type", name)
	text = ''
	due_date = frappe.utils.formatdate(doc.get('due_date'), "dd.MM.YYYY")
	if name == '1':
		text = dunning_type.dunning_text.replace('#2', due_date)
	elif name == '2':
		posting_date = frappe.utils.formatdate(doc.get('posting_date'), "dd.MM.YYYY")
		text = dunning_type.dunning_text.replace('#2', due_date).replace('#5', posting_date)

	return text
