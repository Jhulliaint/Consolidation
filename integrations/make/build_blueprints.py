"""Genere les blueprints Make de collecte automatique des management accounts.

Un scenario par dossier Outlook (Make n'admet qu'un declencheur par scenario) :

  Outlook (dossier)  ->  deja traite ? (data store)  ->  pieces jointes
      -> filtre .xlsx / .xlsm  ->  depot OneDrive  ->  journal (data store)

Usage : python build_blueprints.py  ->  ecrit blueprint_<entite>.json
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

CONNECTION = 14526401          # "Julien's Microsoft connection" (office@corthay.com)
DATASTORE = 197179             # "Collecte management accounts"
ROOT = "/CORTHAY/CLOTURE MENSUELLES"

FOLDER_APAC = (
    "/AAMkADY4NDdiNTIyLWY5NDItNDhhOC1hMjNkLTY4Nzg4NDlhM2U0NgAuAAAAAAAxN-vNrO7FQaeNHo2s6nwmAQAMOa6Kl148TKhfgC3hjYvAAAVl0QumAAA="
    "/AAMkADY4NDdiNTIyLWY5NDItNDhhOC1hMjNkLTY4Nzg4NDlhM2U0NgAuAAAAAAAxN-vNrO7FQaeNHo2s6nwmAQAMOa6Kl148TKhfgC3hjYvAAAWxY7nJAAA="
)
FOLDER_JAPON = (
    "/AAMkADY4NDdiNTIyLWY5NDItNDhhOC1hMjNkLTY4Nzg4NDlhM2U0NgAuAAAAAAAxN-vNrO7FQaeNHo2s6nwmAQAMOa6Kl148TKhfgC3hjYvAAAVl0QuhAAA="
)

SCENARIOS = [
    {
        "entity": "MAGE_ASIA_PACIFIC",
        "name": "Consolidation - Collecte MA Mage Asia Pacific",
        "folder": FOLDER_APAC,
        "folder_label": ["Mage Asia Pacific", "Accounting"],
        "senders": ["atac.com.hk", "forwardsec.com"],
    },
    {
        "entity": "MAGE_JAPON_KK",
        "name": "Consolidation - Collecte MA Mage Japon",
        "folder": FOLDER_JAPON,
        "folder_label": ["Mage Japon"],
        "senders": ["forvismazars.com"],
    },
]

CONN_META = {"__IMTCONN__": {"data": {"scoped": "true", "connection": "azure"},
                             "label": "Julien's Microsoft connection (Julien <office@corthay.com>)"}}


def blueprint(s: dict) -> dict:
    year = '{{formatDate(1.receivedDateTime; "YYYY")}}'
    month = '{{formatDate(1.receivedDateTime; "MM")}}'
    stamp = '{{formatDate(1.receivedDateTime; "YYYYMMDD-HHmmss")}}'
    sender_filter = [[{"a": "{{1.from.emailAddress.address}}", "o": "text:contain:ci", "b": d},
                      {"a": "{{1.hasAttachments}}", "o": "boolean:equal", "b": "true"}]
                     for d in s["senders"]]
    flow = [
        {
            "id": 1,
            "module": "microsoft-email:watchMessages",
            "version": 2,
            "parameters": {
                "__IMTCONN__": CONNECTION,
                "select": "all",
                # Last Modified : capte aussi les e-mails CLASSES plus tard dans le
                # dossier (ils arrivent d'abord dans la boite de reception).
                "triggerBy": "lastModifiedDateTime",
                "folder": s["folder"],
                "limit": 20,
            },
            "mapper": {},
            "metadata": {"designer": {"x": 0, "y": 0, "name": f"Outlook - {' / '.join(s['folder_label'])}"},
                         "restore": {"parameters": {**CONN_META,
                                                    "folder": {"path": s["folder_label"]},
                                                    "select": {"label": "All"},
                                                    "triggerBy": {"label": "Last Modified Date"}}}},
        },
        {
            "id": 2,
            "module": "datastore:ExistRecord",
            "version": 1,
            "filter": {"name": "Cabinet expediteur + piece jointe", "conditions": sender_filter},
            "parameters": {"datastore": DATASTORE},
            "mapper": {"key": "{{1.id}}"},
            "metadata": {"designer": {"x": 300, "y": 0, "name": "Deja traite ?"}},
        },
        {
            "id": 3,
            "module": "microsoft-email:listAttachments",
            "version": 2,
            "filter": {"name": "Jamais traite",
                       "conditions": [[{"a": "{{2.exist}}", "o": "boolean:equal", "b": "false"}]]},
            "parameters": {"__IMTCONN__": CONNECTION},
            "mapper": {"message": "{{1.id}}", "limit": 20},
            "metadata": {"designer": {"x": 600, "y": 0, "name": "Pieces jointes"},
                         "restore": {"parameters": CONN_META}},
        },
        {
            "id": 4,
            "module": "onedrive:uploadAFile",
            "version": 2,
            "filter": {"name": "Classeur Excel",
                       "conditions": [[{"a": "{{3.name}}", "o": "text:pattern:ci", "b": "\\.xls[xm]$"},
                                       {"a": "{{3.isInline}}", "o": "boolean:notequal", "b": "true"}]]},
            "parameters": {"__IMTCONN__": CONNECTION},
            "mapper": {
                "enter": "path",
                "select": "my",
                "select1": "no",
                "folder": f"{ROOT}/{year}/{month}",
                # horodatage en tete : aucune version n'en ecrase une autre
                "filename": f"{stamp} - {s['entity']} - {{{{3.name}}}}",
                "data": "{{3.data}}",
                "conflictBehavior": "rename",
            },
            "metadata": {"designer": {"x": 900, "y": 0, "name": "Depot dossier de collecte"},
                         "restore": {"parameters": CONN_META}},
        },
        {
            "id": 5,
            "module": "datastore:AddRecord",
            "version": 1,
            "parameters": {"datastore": DATASTORE},
            "mapper": {
                "key": "{{1.id}}",
                "overwrite": True,
                "data": {
                    "entity": s["entity"],
                    "sender": "{{1.from.emailAddress.address}}",
                    "subject": "{{1.subject}}",
                    "received": "{{1.receivedDateTime}}",
                    "files": "{{4.name}}",
                    "folder": "{{4.parentReference.path}}",
                    "processed": "{{now}}",
                },
            },
            "metadata": {"designer": {"x": 1200, "y": 0, "name": "Journal de collecte"}},
        },
    ]
    return {
        "name": s["name"],
        "flow": flow,
        "metadata": {"version": 1, "instant": False,
                     "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True,
                                  "autoCommitTriggerLast": True, "sequential": True,
                                  "confidential": False, "dataloss": False, "dlq": False}},
    }


if __name__ == "__main__":
    for s in SCENARIOS:
        path = HERE / f"blueprint_{s['entity'].lower()}.json"
        path.write_text(json.dumps(blueprint(s), ensure_ascii=False, indent=2), encoding="utf-8")
        print("ecrit", path.name)
