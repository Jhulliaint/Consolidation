"""Chaine de consolidation complete, en une seule fonction.

La ligne de commande et l'interface graphique appellent toutes deux ``run`` :
elles ne peuvent donc pas diverger sur la facon de calculer.

    out = run(cfg, fichiers, RunOptions(closing="2025-12-31", rates={...}))
    export(out, "out/consolide.xlsx")
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from .config import AppConfig
from .controls import run_controls
from .engine import ConsolidationEngine
from .formatting import NumberFormatter, formatter
from .importers.excel import ManagementAccountsReader, SourceWorkbook
from .models import ConsolidationResult, Diagnostic, Severity, Statement
from .rates import apply_rates, check_rate, load_rates_file, rate_needs
from .reconcile import Reconciliation, reconcile
from .reports import (
    StatementReport,
    build_by_cost_centre,
    build_margin_analysis,
    build_statement,
)


@dataclass
class RunOptions:
    closing: str | None = None
    # nom de fichier -> code entite, pour forcer une entite non reconnue
    entities: dict[str, str] = field(default_factory=dict)
    level: str = "summary"
    by_entity: bool = True
    by_cost_centre: bool = False
    margins: bool = True
    reference: Path | None = None
    reconciliation_tolerance: Decimal = Decimal("1.00")
    rates: dict[str, dict[str, Any]] = field(default_factory=dict)
    rates_file: Path | None = None
    # surcharges ponctuelles de config/presentation.yaml
    presentation: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunOutput:
    cfg: AppConfig
    workbooks: list[SourceWorkbook]
    result: ConsolidationResult
    reports: dict[str, StatementReport]
    fmt: NumberFormatter
    closing: str
    reconciliation: Reconciliation | None = None
    started_at: datetime = field(default_factory=datetime.now)

    @property
    def bs(self) -> StatementReport:
        return self.reports["Consolidated BS"]

    @property
    def pl(self) -> StatementReport:
        return self.reports["Consolidated PL"]

    def kpis(self) -> list[tuple[str, Any]]:
        return [
            ("Revenue", self.pl.total("Revenue")),
            ("Gross Profit/(Loss)", self.pl.total("Gross Profit/(Loss)")),
            ("Profit/(Loss) from operations", self.pl.total("Profit/(Loss) from operations")),
            ("Total Net/(loss) Profit", self.pl.total("Total Net/(loss) Profit")),
            ("Total assets", self.bs.total("Total assets")),
        ]

    @property
    def blocking(self) -> list:
        return [c for c in self.result.controls
                if not c.passed and c.severity is Severity.ERROR]

    def rates_used(self) -> list[tuple[str, str, Decimal]]:
        """(devise, type de taux, taux) effectivement appliques."""
        seen = {}
        for ln in self.result.lines:
            if ln.origin == "entity" and ln.rate_type is not None and ln.rate != 1:
                seen[(ln.currency, ln.rate_type.value)] = ln.rate
        return [(c, k, r) for (c, k), r in sorted(seen.items())]

    def diagnostics_by_severity(self) -> Counter:
        return Counter(d.severity.value for d in self.result.diagnostics)


def read_sources(cfg: AppConfig, paths: Sequence[Path | str],
                 entities: dict[str, str] | None = None) -> list[SourceWorkbook]:
    """Lit les classeurs et identifie l'entite de chacun (forcee ou deduite)."""
    reader = ManagementAccountsReader(cfg)
    engine = ConsolidationEngine(cfg)
    entities = entities or {}
    out = []
    for path in paths:
        p = Path(path)
        forced = entities.get(p.name) or entities.get(str(p))
        wb = reader.read(p, entity_code=forced)
        if wb.entity_code is None:
            wb.entity_code = engine.resolve_entity(wb)
        out.append(wb)
    return out


def default_closing(workbooks: Sequence[SourceWorkbook]) -> str:
    """Date de cloture commune aux fichiers (la plus frequente)."""
    closings = Counter(wb.closing for wb in workbooks if wb.closing)
    if closings:
        return closings.most_common(1)[0][0]
    years = [wb.fiscal_year for wb in workbooks if wb.fiscal_year]
    return f"{max(years) if years else datetime.now().year}-12-31"


def prepare_rates(cfg: AppConfig, closing: str,
                  opts: RunOptions) -> tuple[AppConfig, list[Diagnostic]]:
    """Fusionne taux de fichier et taux saisis, et verifie leur vraisemblance."""
    rates: dict[str, dict[str, Any]] = {}
    if opts.rates_file:
        for cur, kinds in load_rates_file(opts.rates_file).items():
            rates.setdefault(cur, {}).update(kinds)
    for cur, kinds in (opts.rates or {}).items():
        rates.setdefault(cur.upper(), {}).update(
            {k: v for k, v in (kinds or {}).items() if v not in (None, "")})
    if not rates:
        return cfg, []
    new = apply_rates(cfg, closing, rates)
    checks = []
    for cur, kinds in rates.items():
        for kind, value in kinds.items():
            diag = check_rate(cfg, cur, kind, Decimal(str(value).replace(",", ".")), closing)
            if diag:
                checks.append(diag)
    return new, checks


def run(cfg: AppConfig, paths: Sequence[Path | str],
        opts: RunOptions | None = None,
        workbooks: list[SourceWorkbook] | None = None) -> RunOutput:
    opts = opts or RunOptions()
    workbooks = workbooks if workbooks is not None else read_sources(cfg, paths, opts.entities)
    closing = opts.closing or default_closing(workbooks)
    cfg_run, rate_checks = prepare_rates(cfg, closing, opts)

    result = ConsolidationEngine(cfg_run).consolidate(workbooks, closing=closing)
    result.diagnostics.extend(rate_checks)

    reports: dict[str, StatementReport] = {
        "Consolidated BS": build_statement(cfg_run, result, Statement.BALANCE_SHEET,
                                           level="summary"),
        "Consolidated PL": build_statement(cfg_run, result, Statement.PROFIT_AND_LOSS,
                                           level="summary"),
        "Detailed BS": build_statement(cfg_run, result, Statement.BALANCE_SHEET,
                                       level="detail"),
        "Detailed PL": build_statement(cfg_run, result, Statement.PROFIT_AND_LOSS,
                                       level="detail"),
    }
    if opts.by_entity:
        reports["BS by entity"] = build_statement(
            cfg_run, result, Statement.BALANCE_SHEET, level=opts.level, by_entity=True)
        reports["PL by entity"] = build_statement(
            cfg_run, result, Statement.PROFIT_AND_LOSS, level="detail", by_entity=True)
    if opts.by_cost_centre:
        reports["BS by cost center"] = build_by_cost_centre(
            cfg_run, result, Statement.BALANCE_SHEET, level=opts.level)
        reports["PL by cost center"] = build_by_cost_centre(
            cfg_run, result, Statement.PROFIT_AND_LOSS, level="detail")
    if opts.margins and cfg_run.pl.margin_families:
        reports["Gross margin"] = build_margin_analysis(cfg_run, result)

    reconciliation = None
    if opts.reference:
        reconciliation = reconcile(
            opts.reference,
            {Statement.BALANCE_SHEET: reports["Detailed BS"],
             Statement.PROFIT_AND_LOSS: reports["Detailed PL"]},
            tolerance=opts.reconciliation_tolerance,
        )

    result.controls = run_controls(
        cfg_run, result, bs=reports["Consolidated BS"], pl=reports["Consolidated PL"],
        workbooks=workbooks, reconciliation=reconciliation,
    )
    fmt = formatter(cfg.presentation, **(opts.presentation or {}))
    return RunOutput(cfg=cfg_run, workbooks=workbooks, result=result, reports=reports,
                     fmt=fmt, closing=closing, reconciliation=reconciliation)


def missing_rates(cfg: AppConfig, workbooks: Sequence[SourceWorkbook],
                  closing: str) -> list[tuple[str, list[str]]]:
    """[(devise, [types manquants])] pour la cloture donnee."""
    return [(n.currency, n.missing) for n in rate_needs(cfg, workbooks, closing) if n.missing]


def export(out: RunOutput, path: str | Path) -> Path:
    from .exporters.excel import export_workbook

    return export_workbook(path, out)
