"""Journal d'audit persistant (SQLite).

Choix technique : SQLite est dans la bibliotheque standard, ne demande aucun
serveur, et rend le journal INTERROGEABLE (SQL) plutot que simplement lisible.
Chaque execution est un "run" horodate, ce qui permet de rejouer et de comparer
deux consolidations.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import ConsolidationResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    period      TEXT NOT NULL,
    config_dir  TEXT,
    sources     TEXT,
    n_lines     INTEGER,
    n_errors    INTEGER
);
CREATE TABLE IF NOT EXISTS audit_lines (
    run_id        INTEGER NOT NULL REFERENCES runs(run_id),
    entity        TEXT, period TEXT,
    source_file   TEXT, source_sheet TEXT, source_row INTEGER,
    local_account TEXT, group_coa TEXT, cost_centre TEXT,
    amount_source TEXT, currency TEXT, sign_flip INTEGER,
    rate TEXT, rate_type TEXT, amount_eur TEXT,
    transformations TEXT, origin TEXT
);
CREATE TABLE IF NOT EXISTS controls (
    run_id INTEGER NOT NULL REFERENCES runs(run_id),
    code TEXT, label TEXT, passed INTEGER, severity TEXT,
    expected TEXT, actual TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS diagnostics (
    run_id INTEGER NOT NULL REFERENCES runs(run_id),
    severity TEXT, code TEXT, entity TEXT, source_file TEXT,
    message TEXT, context TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_lines(run_id);
CREATE INDEX IF NOT EXISTS ix_audit_coa ON audit_lines(group_coa);
"""


class AuditJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def record(
        self,
        result: ConsolidationResult,
        *,
        config_dir: str | Path | None = None,
        sources: list[str] | None = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO runs (started_at, period, config_dir, sources, n_lines,"
            " n_errors) VALUES (?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                result.period.key,
                str(config_dir or ""),
                json.dumps(sources or []),
                len(result.lines),
                sum(1 for d in result.diagnostics if d.severity.value == "ERROR"),
            ),
        )
        run_id = int(cur.lastrowid)

        cur.executemany(
            "INSERT INTO audit_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    run_id, a.entity, a.period, a.source_file, a.source_sheet,
                    a.source_row, a.local_account, a.group_coa, a.cost_centre,
                    str(a.amount_source), a.currency, int(a.sign_flip),
                    str(a.rate) if a.rate is not None else None, a.rate_type,
                    str(a.amount_eur), a.transformations, a.origin,
                )
                for a in result.audit
            ],
        )
        cur.executemany(
            "INSERT INTO controls VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    run_id, c.code, c.label, int(c.passed), c.severity.value,
                    str(c.expected) if c.expected is not None else None,
                    str(c.actual) if c.actual is not None else None, c.detail,
                )
                for c in result.controls
            ],
        )
        cur.executemany(
            "INSERT INTO diagnostics VALUES (?,?,?,?,?,?,?)",
            [
                (
                    run_id, d.severity.value, d.code, d.entity, d.source_file,
                    d.message, d.context,
                )
                for d in result.diagnostics
            ],
        )
        self.conn.commit()
        return run_id

    def trace(self, run_id: int, group_coa: str) -> list[tuple]:
        """Toutes les lignes sources ayant contribue a un compte consolide."""
        cur = self.conn.execute(
            "SELECT entity, source_file, source_sheet, source_row, local_account,"
            " amount_source, currency, rate, rate_type, amount_eur"
            " FROM audit_lines WHERE run_id=? AND group_coa=?"
            " ORDER BY entity, source_row",
            (run_id, group_coa),
        )
        return cur.fetchall()

    def close(self) -> None:
        self.conn.close()
