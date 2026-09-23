"""Interface graphique locale : ``mageconso ui``.

Serveur HTTP de la bibliotheque standard, lie a 127.0.0.1 uniquement, et page
unique sans ressource externe : l'application fonctionne hors ligne et aucune
donnee ne quitte le poste.

Tout le calcul ET toute la mise en forme des nombres sont faits ici, par le
meme pipeline que la ligne de commande : l'ecran et le classeur Excel ne
peuvent pas diverger.

Protections :
 - ecoute sur 127.0.0.1 seulement ;
 - en-tete Host verifie (parade au "DNS rebinding") ;
 - requetes d'ecriture en application/json uniquement (un formulaire d'un
   autre site ne peut pas declencher d'action sans requete de controle CORS,
   que ce serveur refuse) ;
 - fichiers deposes dans un repertoire temporaire supprime a l'arret.
"""
from __future__ import annotations

import atexit
import base64
import json
import re
import shutil
import tempfile
import threading
import uuid
import webbrowser
from dataclasses import dataclass, field
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .config import AppConfig, load_config, norm
from .formatting import formatter
from .models import Severity, Statement, eur
from .pipeline import RunOptions, RunOutput, default_closing, export, read_sources, run
from .rates import check_rate, rate_needs, write_rates_template
from .reports import ELIMINATION, TOTAL, StatementReport
from .suggest import write_mapping_template

MAX_BODY = 80 * 1024 * 1024  # 80 Mo par requete
ALLOWED_EXT = {".xlsx", ".xlsm"}

REPORT_TITLES = {
    "Consolidated BS": "Bilan consolidé",
    "Consolidated PL": "Compte de résultat consolidé",
    "Detailed BS": "Bilan détaillé",
    "Detailed PL": "Compte de résultat détaillé",
    "BS by entity": "Bilan par entité",
    "PL by entity": "Compte de résultat par entité",
    "BS by cost center": "Bilan par centre de coûts",
    "PL by cost center": "Compte de résultat par centre de coûts",
    "Gross margin": "Marge brute par famille",
}


def _safe_name(name: str) -> str:
    base = Path(name).name
    return re.sub(r"[^\w .()+\-&àâäéèêëîïôöùûüç]", "_", base)[:180] or "fichier.xlsx"


def _dec(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ".").replace(" ", ""))
    except Exception:  # noqa: BLE001 - saisie utilisateur
        return None


@dataclass
class Session:
    id: str
    dir: Path
    sources: dict[str, Path] = field(default_factory=dict)
    reference: Path | None = None
    output: RunOutput | None = None
    export_path: Path | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class App:
    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = config_dir
        self.cfg: AppConfig = load_config(config_dir)
        self.root = Path(tempfile.mkdtemp(prefix="mageconso-"))
        self.sessions: dict[str, Session] = {}
        atexit.register(self.cleanup)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # ------------------------------------------------------------ sessions
    def session(self, sid: str | None, create: bool = False) -> Session:
        if sid and sid in self.sessions:
            return self.sessions[sid]
        if not create:
            raise KeyError("Session inconnue ou expirée : rechargez la page.")
        new_id = uuid.uuid4().hex
        d = self.root / new_id
        d.mkdir(parents=True)
        s = Session(new_id, d)
        self.sessions[new_id] = s
        return s

    # ------------------------------------------------------------------ API
    def meta(self) -> dict:
        cfg = self.cfg
        pres = cfg.presentation or {}
        return {
            "version": __version__,
            "reporting_currency": cfg.reporting_currency,
            "entities": [
                {"code": e.code, "name": e.name, "currency": e.currency,
                 "in_scope": e.in_scope}
                for e in cfg.entities.values()
            ],
            "presentation": {k: pres.get(k) for k in (
                "scale", "decimals", "negative_format", "currency_position",
                "zero_display", "percent_of_revenue")},
        }

    def add_files(self, body: dict) -> dict:
        s = self.session(body.get("session"), create=True)
        kind = body.get("kind", "source")
        with s.lock:
            for f in body.get("files") or []:
                name = _safe_name(f.get("name", ""))
                if Path(name).suffix.lower() not in ALLOWED_EXT:
                    raise ValueError(f"{name} : seuls les classeurs .xlsx / .xlsm sont acceptés.")
                data = base64.b64decode(f.get("data", "").split(",")[-1])
                folder = s.dir / ("reference" if kind == "reference" else "sources")
                folder.mkdir(exist_ok=True)
                path = folder / name
                path.write_bytes(data)
                if kind == "reference":
                    s.reference = path
                else:
                    s.sources[name] = path
            s.output = None
        return self.inspect({"session": s.id, "entities": body.get("entities") or {}})

    def remove_file(self, body: dict) -> dict:
        s = self.session(body.get("session"))
        with s.lock:
            name = body.get("name")
            if body.get("kind") == "reference":
                s.reference = None
            elif name in s.sources:
                s.sources.pop(name).unlink(missing_ok=True)
            s.output = None
        return self.inspect({"session": s.id, "entities": body.get("entities") or {}})

    def inspect(self, body: dict) -> dict:
        s = self.session(body.get("session"))
        overrides = {k: v for k, v in (body.get("entities") or {}).items() if v}
        wbs = read_sources(self.cfg, list(s.sources.values()), overrides)
        closing = body.get("closing") or default_closing(wbs) if wbs else None
        codes = [wb.entity_code for wb in wbs if wb.entity_code]
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        sources = []
        for wb in wbs:
            total = sum((ln.amount for ln in wb.lines), Decimal(0))
            sources.append({
                "name": wb.path.name,
                "entity": wb.entity_code,
                "entity_read": wb.entity_name,
                "currency": wb.currency,
                "period_start": wb.period_start.isoformat() if wb.period_start else None,
                "period_end": wb.period_end.isoformat() if wb.period_end else None,
                "lines": len(wb.lines),
                "balanced": abs(total) < Decimal("0.01"),
                "imbalance": str(total),
                "hidden_sheets": wb.hidden_sheets,
                "duplicate": wb.entity_code in dupes,
                "messages": [{"severity": d.severity.value, "code": d.code,
                              "message": d.message} for d in wb.diagnostics],
            })
        needs = []
        if wbs and closing:
            for n in rate_needs(self.cfg, [wb for wb in wbs if wb.entity_code], closing):
                needs.append({
                    "currency": n.currency,
                    "entities": n.entities,
                    "known": {k: (str(v) if v is not None else None) for k, v in n.known.items()},
                    "suggested": {k: (str(v) if v is not None else None)
                                  for k, v in n.suggested.items()},
                })
        return {
            "session": s.id,
            "sources": sources,
            "reference": s.reference.name if s.reference else None,
            "closing": closing,
            "rates": needs,
            "duplicates": dupes,
        }

    def check_rates(self, body: dict) -> dict:
        closing = body.get("closing") or ""
        out = []
        for cur, kinds in (body.get("rates") or {}).items():
            for kind, value in (kinds or {}).items():
                dec = _dec(value)
                if value not in (None, "") and dec is None:
                    out.append({"currency": cur, "kind": kind, "severity": "ERROR",
                                "message": f"Taux illisible : {value!r}"})
                    continue
                if dec is None:
                    continue
                diag = check_rate(self.cfg, cur, kind, dec, closing)
                if diag:
                    out.append({"currency": cur, "kind": kind,
                                "severity": diag.severity.value, "message": diag.message})
        return {"checks": out}

    def format_preview(self, body: dict) -> dict:
        fmt = formatter(self.cfg.presentation, **self._presentation(body))
        samples = [Decimal("2587674.874"), Decimal("-640378.2"), Decimal("0"),
                   Decimal("1234.5")]
        return {"examples": [{"raw": str(v), "text": fmt.format(v)} for v in samples],
                "percent": fmt.format_percent(Decimal("0.5212"))}

    @staticmethod
    def _presentation(body: dict) -> dict:
        p = body.get("presentation") or {}
        out: dict[str, Any] = {}
        for key in ("scale", "negative_format", "currency_position", "zero_display"):
            if p.get(key):
                out[key] = p[key]
        if p.get("decimals") not in (None, ""):
            out["decimals"] = int(p["decimals"])
        if "percent_of_revenue" in p:
            out["percent_of_revenue"] = bool(p["percent_of_revenue"])
        return out

    def consolidate(self, body: dict) -> dict:
        s = self.session(body.get("session"))
        if not s.sources:
            raise ValueError("Déposez au moins un fichier de management accounts.")
        opts_in = body.get("options") or {}
        rates = {cur: {k: v for k, v in kinds.items() if _dec(v) is not None}
                 for cur, kinds in (body.get("rates") or {}).items()}
        pres = self._presentation(body)
        opts = RunOptions(
            closing=body.get("closing") or None,
            entities={k: v for k, v in (body.get("entities") or {}).items() if v},
            level=opts_in.get("level", "summary"),
            by_entity=bool(opts_in.get("by_entity", True)),
            by_cost_centre=bool(opts_in.get("by_cost_centre", False)),
            margins=bool(opts_in.get("margins", True)),
            reference=s.reference,
            reconciliation_tolerance=_dec(opts_in.get("tolerance")) or Decimal("1"),
            rates=rates,
            presentation=pres,
        )
        with s.lock:
            out = run(self.cfg, list(s.sources.values()), opts)
            period = out.result.period
            stamp = f"{period.year}-{period.month:02d}" if period.month else str(period.year)
            s.export_path = export(out, s.dir / f"Mage SAS Consolidated accounts {stamp}.xlsx")
            s.output = out
        return self._view(s, out, show_pct=pres.get("percent_of_revenue", True))

    # ------------------------------------------------------------- vue JSON
    def _view(self, s: Session, out: RunOutput, show_pct: bool = True) -> dict:
        fmt = out.fmt
        res = out.result
        blocking = out.blocking
        warnings = [c for c in res.controls if not c.passed and c not in blocking]
        if blocking:
            level, headline = "error", (f"Ne pas diffuser : {len(blocking)} contrôle(s) "
                                        "bloquant(s) en échec")
        elif warnings:
            level, headline = "warning", (f"États produits - {len(warnings)} point(s) "
                                          "à examiner")
        else:
            level, headline = "ok", "Tous les contrôles sont satisfaits"

        reports = []
        for key, rep in out.reports.items():
            reports.append(self._report_view(key, rep, fmt, show_pct))

        rec = None
        if out.reconciliation is not None:
            r = out.reconciliation
            rec = {
                "file": r.reference_file,
                "tolerance": str(r.tolerance),
                "counts": r.counts(),
                "lines": [{
                    "statement": "Bilan" if ln.statement is Statement.BALANCE_SHEET else "Résultat",
                    "caption": ln.caption,
                    "reference": fmt.format(ln.reference) if ln.reference is not None else "",
                    "computed": fmt.format(ln.computed) if ln.computed is not None else "",
                    "difference": fmt.format(ln.difference) if ln.difference is not None else "",
                    "status": ln.status(r.tolerance),
                    "source": ln.source,
                } for ln in sorted(r.lines, key=lambda x: (x.status(r.tolerance) == "OK",
                                                           -(abs(x.difference or 0))))],
            }

        return {
            "status": {"level": level, "headline": headline,
                       "blocking": len(blocking), "warnings": len(warnings)},
            "period_end": fmt.period_end_label(res.period.end_date),
            "closing": out.closing,
            "kpis": [{"label": k, "text": fmt.format(v)} for k, v in out.kpis()],
            "controls": [{"code": c.code, "label": c.label, "passed": c.passed,
                          "severity": c.severity.value, "detail": c.detail}
                         for c in res.controls],
            "diagnostics": [{"severity": d.severity.value, "code": d.code,
                             "entity": d.entity, "file": d.source_file,
                             "message": d.message}
                            for d in sorted(res.diagnostics, key=lambda d: (
                                {"ERROR": 0, "WARNING": 1}.get(d.severity.value, 2)))],
            "reports": reports,
            "unmapped": [{"entity": u.entity, "file": u.source_file,
                          "local_account": u.local_account,
                          "amount": fmt.format(Decimal(u.amount)).replace("€", u.currency)
                          if u.currency != "EUR" else fmt.format(Decimal(u.amount)),
                          "currency": u.currency,
                          "suggestions": [{"caption": c, "score": round(sc * 100)}
                                          for c, sc in u.suggestions]}
                         for u in res.unmapped],
            "reconciliation": rec,
            "rates_used": [{"currency": c, "kind": k, "rate": str(r)}
                           for c, k, r in out.rates_used()],
            "sources": [{"name": wb.path.name, "entity": wb.entity_code,
                         "currency": wb.currency, "lines": len(wb.lines)}
                        for wb in out.workbooks],
            "download": f"/api/download?session={s.id}&what=xlsx",
            "download_name": s.export_path.name if s.export_path else "",
        }

    def _report_view(self, key: str, rep: StatementReport, fmt, show_pct: bool) -> dict:
        struct = self.cfg.structure(rep.statement) if rep.statement else None
        summary_sources: dict[str, list[str]] = {}
        if struct:
            for sec in struct.summary_sections:
                for item in sec.get("lines") or []:
                    summary_sources[item["caption"]] = item.get("from") or []
        pct = show_pct and bool(rep.percent_base)
        rows = []
        for row in rep.rows:
            cells = []
            for col in rep.columns:
                val = row.values.get(col)
                if row.kind == "section":
                    cells.append(None)
                    continue
                text = (fmt.format_percent(val) if row.kind == "percent"
                        else fmt.format(val) if val is not None else "")
                p = rep.percent(row, col) if pct else None
                cells.append({"text": text, "pct": fmt.format_percent(p) if p is not None else "",
                              "negative": bool(val is not None and val < 0)})
            traceable = row.kind == "line" and struct is not None
            rows.append({
                "caption": row.caption, "kind": row.kind, "level": row.level,
                "cells": cells, "traceable": traceable,
                "sources": summary_sources.get(row.caption, [row.caption]) if traceable else [],
            })
        return {
            "key": key,
            "title": REPORT_TITLES.get(key, key),
            "statement": rep.statement.value if rep.statement else None,
            "columns": [{"key": c, "label": rep.label(c)} for c in rep.columns],
            "percent": pct,
            "rows": rows,
            "note": " ".join(x for x in (rep.currency, fmt.scale_note()) if x),
        }

    def trace(self, body: dict) -> dict:
        s = self.session(body.get("session"))
        out = s.output
        if out is None:
            raise ValueError("Aucune consolidation en mémoire.")
        report = out.reports.get(body.get("report", ""))
        statement = report.statement if report else None
        captions = {norm(c) for c in body.get("captions") or []}
        column = body.get("column") or TOTAL
        struct = self.cfg.structure(statement) if statement else None
        sign_of: dict[str, int] = {}
        if struct:
            for sec in struct.detail_sections:
                for ln in sec.get("lines") or []:
                    sign_of[norm(ln)] = int(sec.get("sign", 1))
        fmt = out.fmt
        rows, total = [], Decimal(0)
        for a in out.result.audit:
            if norm(a.group_coa) not in captions:
                continue
            if column == ELIMINATION and a.origin != "elimination":
                continue
            if column not in (TOTAL, ELIMINATION) and column not in (a.entity, a.cost_centre):
                continue
            sign = sign_of.get(norm(a.group_coa), 1)
            presented = a.amount_eur * sign
            total += presented
            rows.append({
                "entity": a.entity, "file": a.source_file, "sheet": a.source_sheet,
                "row": a.source_row, "local_account": a.local_account,
                "group_coa": a.group_coa,
                # montant d'origine en unites, pleine precision (pas d'echelle)
                "amount_source": f"{eur(a.amount_source * sign)} {a.currency}",
                "rate": str(a.rate) if a.rate is not None and a.rate != 1 else "",
                "rate_type": ({"eom": "clôture", "average": "moyen", "historical": "historique"}
                              .get(a.rate_type or "", "") if a.rate not in (None, 1) else ""),
                "amount_eur": fmt.format(presented),
                "origin": a.origin, "transformations": a.transformations,
            })
        return {"rows": rows, "total": fmt.format(total), "count": len(rows)}

    def download(self, query: dict) -> tuple[Path, str]:
        s = self.session((query.get("session") or [None])[0])
        what = (query.get("what") or ["xlsx"])[0]
        if what == "xlsx":
            if not s.export_path:
                raise ValueError("Aucun classeur produit.")
            return s.export_path, s.export_path.name
        if what == "mapping":
            if not s.output or not s.output.result.unmapped:
                raise ValueError("Aucun compte non mappé.")
            p = write_mapping_template(s.dir / "mapping à compléter.csv", s.output.result.unmapped)
            return p, p.name
        if what == "rates":
            wbs = read_sources(self.cfg, list(s.sources.values()))
            closing = (query.get("closing") or [None])[0] or default_closing(wbs)
            p = write_rates_template(s.dir / f"taux {closing}.xlsx",
                                     rate_needs(self.cfg, wbs, closing), closing)
            return p, p.name
        raise ValueError(f"Telechargement inconnu : {what}")


# ------------------------------------------------------------------ HTTP layer
def _json_default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, Path):
        return o.name
    if isinstance(o, Severity):
        return o.value
    raise TypeError(type(o))


def make_handler(app: App, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    routes = {
        "/api/files": app.add_files,
        "/api/files/remove": app.remove_file,
        "/api/inspect": app.inspect,
        "/api/rates/check": app.check_rates,
        "/api/format": app.format_preview,
        "/api/consolidate": app.consolidate,
        "/api/trace": app.trace,
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "mageconso"

        def log_message(self, fmt, *args):  # silencieux (donnees financieres)
            return

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def _send(self, status: int, body: bytes, ctype: str,
                  extra: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                             "script-src 'self' 'unsafe-inline'; img-src 'self' data:")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload, default=_json_default).encode(),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "Hote refuse."})
            url = urlparse(self.path)
            try:
                if url.path in ("/", "/index.html"):
                    html = resources.files("mageconso.web").joinpath("index.html").read_bytes()
                    return self._send(HTTPStatus.OK, html, "text/html; charset=utf-8")
                if url.path == "/api/meta":
                    return self._json(HTTPStatus.OK, app.meta())
                if url.path == "/api/download":
                    path, name = app.download(parse_qs(url.query))
                    ctype = ("text/csv; charset=utf-8" if path.suffix == ".csv" else
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    disp = f"attachment; filename*=UTF-8''{_quote(name)}"
                    return self._send(HTTPStatus.OK, path.read_bytes(), ctype,
                                      {"Content-Disposition": disp})
                return self._json(HTTPStatus.NOT_FOUND, {"error": "Introuvable."})
            except (KeyError, ValueError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": _msg(exc)})

        def do_POST(self):  # noqa: N802
            if not self._host_ok():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "Hote refuse."})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                                  {"error": "JSON attendu."})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                  {"error": "Fichiers trop volumineux (80 Mo maximum)."})
            route = routes.get(urlparse(self.path).path)
            if route is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "Introuvable."})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                return self._json(HTTPStatus.OK, route(body))
            except (KeyError, ValueError) as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": _msg(exc)})
            except Exception as exc:  # noqa: BLE001 - l'utilisateur doit voir l'erreur
                return self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                                  {"error": f"Erreur inattendue : {type(exc).__name__}: {exc}"})

    return Handler


def _msg(exc: Exception) -> str:
    return str(exc.args[0]) if exc.args else str(exc)


def _quote(name: str) -> str:
    from urllib.parse import quote

    return quote(name)


def create_server(config_dir: str | Path | None = None, port: int = 8765):
    app = App(config_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), None)
    actual = server.server_address[1]
    server.RequestHandlerClass = make_handler(app, actual)
    return server, app


def serve(config_dir: str | Path | None = None, port: int = 8765,
          open_browser: bool = True) -> None:
    server, app = create_server(config_dir, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Interface Mage Consolidation : {url}")
    print("Les fichiers restent sur ce poste. Ctrl+C pour arreter.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArret.")
    finally:
        server.server_close()
        app.cleanup()
