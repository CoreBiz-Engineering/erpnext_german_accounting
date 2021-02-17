from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "label": _("German Accounting Reports"),
            "items": [
                {
                    "type": "report",
                    "name": "Betriebswirtschaftliche Auswertungen",
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "Umsatzsteuer Voranmeldung",
                    "is_query_report": True,
                },
                {
                    "type": "report",
                    "name": "OP List",
                    "is_query_report": True,
                },
            ]
        },
        {
            "label": _("German Accounting"),
            "items": [
                {
                    "type": "page",
                    "name": "buchungen",
                    "label": _("Buchungen"),
                },
                {
                    "type": "doctype",
                    "name": "Payment Entry",
                    "label": _("Payment Entry"),
                    "decription": ("Payment Entry")
                },
                {
                    "type": "doctype",
                    "name": "Dunning",
                    "label": _("Dunning"),
                    "decription": ("Dunning")
                },
            ]
        },
        {
            "label": _("German Accounting Doctypes"),
            "items": [
                {
                    "type": "doctype",
                    "name": "BWA",
                    "label": _("BWA"),
                    "description": _("BWA"),
                },
                {
                    "type": "doctype",
                    "name": "UStVA",
                    "label": _("UStVA"),
                    "description": _("UStVA"),
                }
            ]
        },
    ]
