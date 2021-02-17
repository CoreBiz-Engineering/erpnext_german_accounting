# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "german_accounting"
app_title = "German Accounting"
app_publisher = "LIS"
app_description = "Reports for German Accounting like BWA, USt-VA etc."
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "mtraeber@linux-ag.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/german_accounting/css/german_accounting.css"
# app_include_js = "/assets/german_accounting/js/german_accounting.js"

# include js, css files in header of web template
# web_include_css = "/assets/german_accounting/css/german_accounting.css"
# web_include_js = "/assets/german_accounting/js/german_accounting.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "german_accounting.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

#Fixtures
fixtures = ["Steuercodes", "UStVA", "BWA", "BWA Kurzbericht"]

# Installation
# ------------

# before_install = "german_accounting.install.before_install"
# after_install = "german_accounting.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "german_accounting.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"german_accounting.tasks.all"
# 	],
# 	"daily": [
# 		"german_accounting.tasks.daily"
# 	],
# 	"hourly": [
# 		"german_accounting.tasks.hourly"
# 	],
# 	"weekly": [
# 		"german_accounting.tasks.weekly"
# 	]
# 	"monthly": [
# 		"german_accounting.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "german_accounting.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "german_accounting.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "german_accounting.task.get_dashboard_data"
# }

