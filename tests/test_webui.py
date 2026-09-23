"""Tests de l'interface graphique : API applicative et couche HTTP."""
from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request

import pytest

from mageconso.webui import App, create_server


def _payload(paths):
    return [{"name": p.name,
             "data": "data:application/octet-stream;base64,"
                     + base64.b64encode(p.read_bytes()).decode()} for p in paths]


@pytest.fixture()
def app():
    a = App()
    yield a
    a.cleanup()


def test_upload_inspect_and_rate_needs(app, sample_files):
    insp = app.add_files({"files": _payload(sample_files)})
    assert {s["entity"] for s in insp["sources"]} == {"MAGE_SAS", "MAGE_JAPON_KK"}
    assert all(s["balanced"] for s in insp["sources"])
    assert insp["closing"] == "2025-12-31"
    [jpy] = insp["rates"]
    assert jpy["currency"] == "JPY" and jpy["known"]["eom"] == "156.33"


def test_rejects_non_excel_upload(app, tmp_path):
    bad = tmp_path / "virus.exe"
    bad.write_bytes(b"MZ")
    with pytest.raises(ValueError):
        app.add_files({"files": _payload([bad])})


def test_consolidate_view_and_trace_reconcile(app, sample_files):
    sid = app.add_files({"files": _payload(sample_files)})["session"]
    view = app.consolidate({"session": sid, "rates": {"JPY": {"eom": "156,33",
                                                              "average": "156.30"}}})
    assert view["status"]["level"] == "ok"
    kpi = {k["label"]: k["text"] for k in view["kpis"]}
    assert kpi["Total assets"] == "917 359 €"

    bs = next(r for r in view["reports"] if r["key"] == "Consolidated BS")
    cash = next(r for r in bs["rows"] if r["caption"] == "Cash and cash equivalents")
    assert cash["traceable"] and len(cash["sources"]) == 3
    trace = app.trace({"session": sid, "report": "Consolidated BS",
                       "captions": cash["sources"], "column": "TOTAL"})
    # le total des lignes sources egale le montant affiche
    assert trace["total"] == cash["cells"][0]["text"] == "134 712 €"
    assert {r["entity"] for r in trace["rows"]} == {"MAGE_SAS", "MAGE_JAPON_KK"}


def test_trace_by_entity_column(app, sample_files):
    sid = app.add_files({"files": _payload(sample_files)})["session"]
    app.consolidate({"session": sid})
    trace = app.trace({"session": sid, "report": "BS by entity",
                       "captions": ["Cash Bank"], "column": "MAGE_JAPON_KK"})
    assert trace["count"] == 1 and trace["total"] == "14 712 €"


def test_presentation_changes_display_not_amounts(app, sample_files):
    sid = app.add_files({"files": _payload(sample_files)})["session"]
    a = app.consolidate({"session": sid})
    b = app.consolidate({"session": sid, "presentation": {"scale": "thousands",
                                                          "decimals": 1}})
    ka = {k["label"]: k["text"] for k in a["kpis"]}
    kb = {k["label"]: k["text"] for k in b["kpis"]}
    assert ka["Total assets"] == "917 359 €" and kb["Total assets"] == "917,4k €"


def test_rate_check_endpoint(app):
    checks = app.check_rates({"closing": "2026-12-31",
                              "rates": {"JPY": {"eom": "0,0064", "average": "abc"}}})["checks"]
    codes = {(c["kind"], c["severity"]) for c in checks}
    assert ("eom", "ERROR") in codes and ("average", "ERROR") in codes


def test_download_excel(app, sample_files):
    sid = app.add_files({"files": _payload(sample_files)})["session"]
    app.consolidate({"session": sid})
    path, name = app.download({"session": [sid], "what": ["xlsx"]})
    assert path.exists() and name.endswith(".xlsx")


# ----------------------------------------------------------------- HTTP
@pytest.fixture()
def server():
    srv, app = create_server(port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()
    app.cleanup()


def _req(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_http_serves_page_and_meta(server):
    status, body = _req(server + "/")
    assert status == 200 and b"Consolidation" in body
    status, body = _req(server + "/api/meta")
    assert status == 200 and json.loads(body)["reporting_currency"] == "EUR"


def test_http_rejects_foreign_host(server):
    status, _ = _req(server + "/api/meta", headers={"Host": "evil.example"})
    assert status == 403


def test_http_rejects_non_json_post(server):
    status, _ = _req(server + "/api/consolidate", data=b"{}",
                     headers={"Content-Type": "text/plain"})
    assert status == 415


def test_http_full_flow(server, sample_files):
    body = json.dumps({"files": _payload(sample_files)}).encode()
    status, raw = _req(server + "/api/files", body, {"Content-Type": "application/json"})
    assert status == 200
    sid = json.loads(raw)["session"]
    status, raw = _req(server + "/api/consolidate", json.dumps({"session": sid}).encode(),
                       {"Content-Type": "application/json"})
    assert status == 200 and json.loads(raw)["status"]["level"] == "ok"
    status, xlsx = _req(server + f"/api/download?session={sid}&what=xlsx")
    assert status == 200 and xlsx[:2] == b"PK"


def test_presentation_choice_does_not_leak_between_sessions(app, sample_files):
    """Un reglage d'une session ne doit pas modifier la configuration partagee."""
    before = dict(app.cfg.presentation)
    sid = app.add_files({"files": _payload(sample_files)})["session"]
    app.consolidate({"session": sid, "presentation": {"percent_of_revenue": False,
                                                      "scale": "millions"}})
    assert app.cfg.presentation == before


def test_trace_source_amount_in_full_units(app, sample_files):
    sid = app.add_files({"files": _payload(sample_files)})["session"]
    app.consolidate({"session": sid, "presentation": {"scale": "thousands"}})
    trace = app.trace({"session": sid, "report": "BS by entity",
                       "captions": ["Cash Bank"], "column": "MAGE_JAPON_KK"})
    assert trace["rows"][0]["amount_source"] == "2 300 000,00 JPY"
