"""Construction des etats consolides.

Deux restitutions, correspondant aux deux fichiers de reference :

 * ``build_statement``  -> "Mage SAS Consolidated accounts"
   (bilan + compte de resultat consolides, niveau synthese et/ou detail)

 * ``build_by_cost_centre`` -> "Mage Consolidated accounts by cost center"
   (une colonne par entite/centre de couts, puis ELIMINATION, puis TOTAL)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..config import AppConfig, StatementStructure, norm
from ..models import ZERO, ConsolidationResult, Statement


@dataclass
class ReportRow:
    caption: str
    kind: str  # section | line | total | grand_total | cascade | control
    values: dict[str, Decimal] = field(default_factory=dict)
    level: int = 0

    def value(self, column: str = "TOTAL") -> Decimal:
        return self.values.get(column, ZERO)


@dataclass
class StatementReport:
    title: str
    statement: Statement
    columns: list[str]
    rows: list[ReportRow]
    totals: dict[str, Decimal] = field(default_factory=dict)
    currency: str = "EUR"
    period_label: str = ""

    def total(self, caption: str) -> Decimal:
        key = norm(caption)
        for c, v in self.totals.items():
            if norm(c) == key:
                return v
        for r in self.rows:
            if norm(r.caption) == key:
                return r.value()
        return ZERO


def _signed(values: dict[str, Decimal], sign: Decimal) -> dict[str, Decimal]:
    """Applique le signe de PRESENTATION d'une section.

    Le moteur stocke les montants en convention comptable DEBIT (+)/CREDIT (-).
    Les etats de reference presentent l'actif en debit positif (sign = +1) et le
    passif, les capitaux propres et le compte de resultat en credit positif
    (sign = -1). Cette fonction n'intervient qu'a la restitution.
    """
    if sign == 1:
        return dict(values)
    return {k: v * sign for k, v in values.items()}


def _amounts(
    result: ConsolidationResult, statement: Statement
) -> dict[str, dict[str, Decimal]]:
    """caption normalisee -> {colonne -> montant}, colonne = entite|ELIMINATION."""
    out: dict[str, dict[str, Decimal]] = {}
    for ln in result.lines:
        if ln.statement is not statement:
            continue
        col = "ELIMINATION" if ln.origin == "elimination" else ln.entity
        bucket = out.setdefault(norm(ln.group_coa), {})
        bucket[col] = bucket.get(col, ZERO) + ln.amount_eur
        bucket["TOTAL"] = bucket.get("TOTAL", ZERO) + ln.amount_eur
    return out


def build_statement(
    cfg: AppConfig,
    result: ConsolidationResult,
    statement: Statement,
    *,
    level: str = "summary",
    columns: list[str] | None = None,
) -> StatementReport:
    struct: StatementStructure = cfg.structure(statement)
    data = _amounts(result, statement)
    cols = columns or ["TOTAL"]
    rows: list[ReportRow] = []
    totals: dict[str, Decimal] = {}

    def line_values(captions: list[str]) -> dict[str, Decimal]:
        agg: dict[str, Decimal] = {}
        for cap in captions:
            for col, val in (data.get(norm(cap)) or {}).items():
                agg[col] = agg.get(col, ZERO) + val
        return agg

    # Le compte de resultat ne definit pas de bloc "summary" : sa synthese est
    # la cascade de resultat. On retombe alors sur les lignes de detail.
    use_summary = level == "summary" and bool(struct.summary_sections)
    sections = struct.summary_sections if use_summary else struct.detail_sections

    for sec in sections:
        rows.append(ReportRow(caption=sec.get("section", ""), kind="section"))
        section_total: dict[str, Decimal] = {}
        sign = Decimal(str(sec.get("sign", 1)))
        if use_summary:
            for item in sec.get("lines") or []:
                vals = _signed(line_values(item.get("from") or []), sign)
                rows.append(
                    ReportRow(caption=item["caption"], kind="line", values=vals, level=1)
                )
                for col, v in vals.items():
                    section_total[col] = section_total.get(col, ZERO) + v
        else:
            for cap in sec.get("lines") or []:
                vals = _signed(line_values([cap]), sign)
                rows.append(ReportRow(caption=cap, kind="line", values=vals, level=1))
                for col, v in vals.items():
                    section_total[col] = section_total.get(col, ZERO) + v

        label = sec.get("total")
        if label:
            rows.append(ReportRow(caption=label, kind="total", values=section_total))
            totals[label] = section_total.get("TOTAL", ZERO)

    # sous-totaux transverses (Total assets, Total liabilities & equity...)
    for label, parts in (struct.subtotals or {}).items():
        agg: dict[str, Decimal] = {}
        for r in rows:
            if r.kind == "total" and r.caption in parts:
                for col, v in r.values.items():
                    agg[col] = agg.get(col, ZERO) + v
        rows.append(ReportRow(caption=label, kind="grand_total", values=agg))
        totals[label] = agg.get("TOTAL", ZERO)

    # cascade de resultat (compte de resultat uniquement)
    if struct.cascade:
        pl_sign = Decimal(
            str((struct.detail_sections[0] or {}).get("sign", 1))
            if struct.detail_sections
            else 1
        )
        cascade_vals: dict[str, dict[str, Decimal]] = {}
        for step in struct.cascade:
            cap = step["caption"]
            if "from_total" in step:
                src = step["from_total"]
                vals = next(
                    (dict(r.values) for r in rows if r.caption == src and r.kind == "total"),
                    {},
                )
            elif "from_line" in step:
                vals = _signed(line_values([step["from_line"]]), pl_sign)
            else:
                vals = {}
                for part in step.get("sum_of") or []:
                    for col, v in (cascade_vals.get(part) or {}).items():
                        vals[col] = vals.get(col, ZERO) + v
            cascade_vals[cap] = vals
            rows.append(ReportRow(caption=cap, kind="cascade", values=vals))
            totals[cap] = vals.get("TOTAL", ZERO)

        if struct.ebita:
            vals = dict(cascade_vals.get(struct.ebita.get("base", ""), {}))
            for cap in struct.ebita.get("add_back") or []:
                for col, v in _signed(line_values([cap]), pl_sign).items():
                    vals[col] = vals.get(col, ZERO) - v
            for cap in struct.ebita.get("plus") or []:
                for col, v in _signed(line_values([cap]), pl_sign).items():
                    vals[col] = vals.get(col, ZERO) + v
            rows.append(ReportRow(caption="EBITA", kind="cascade", values=vals))
            totals["EBITA"] = vals.get("TOTAL", ZERO)

    title = (
        "UNAUDITED CONSOLIDATED BALANCE SHEET"
        if statement is Statement.BALANCE_SHEET
        else "UNAUDITED PROFIT & LOSS REPORT CONSOLIDATED ACCOUNTS"
    )
    return StatementReport(
        title=title,
        statement=statement,
        columns=cols,
        rows=rows,
        totals=totals,
        currency=cfg.reporting_currency,
        period_label=result.period.key,
    )


def build_by_cost_centre(
    cfg: AppConfig,
    result: ConsolidationResult,
    statement: Statement,
    *,
    level: str = "detail",
) -> StatementReport:
    """Etat par centre de couts : une colonne par centre, ELIMINATION, TOTAL.

    Reproduit la structure de colonnes observee dans la feuille
    "Conso <date> cost center" du classeur de reference.
    """
    struct = cfg.structure(statement)
    per_cc: dict[str, dict[str, Decimal]] = {}
    for ln in result.lines:
        if ln.statement is not statement:
            continue
        col = "ELIMINATION" if ln.origin == "elimination" else ln.cost_centre
        bucket = per_cc.setdefault(norm(ln.group_coa), {})
        bucket[col] = bucket.get(col, ZERO) + ln.amount_eur
        bucket["TOTAL"] = bucket.get("TOTAL", ZERO) + ln.amount_eur

    ordered = [
        cc for cc in cfg.cost_centres if any(cc in v for v in per_cc.values())
    ]
    extra = sorted(
        {
            c
            for v in per_cc.values()
            for c in v
            if c not in ordered and c not in ("TOTAL", "ELIMINATION")
        }
    )
    columns = ordered + extra + ["ELIMINATION", "TOTAL"]

    rows: list[ReportRow] = []
    totals: dict[str, Decimal] = {}
    use_summary = level == "summary" and bool(struct.summary_sections)
    sections = struct.summary_sections if use_summary else struct.detail_sections

    for sec in sections:
        rows.append(ReportRow(caption=sec.get("section", ""), kind="section"))
        section_total: dict[str, Decimal] = {}
        sign = Decimal(str(sec.get("sign", 1)))
        captions = (
            [i["caption"] for i in sec.get("lines") or []]
            if use_summary
            else sec.get("lines")
        )
        for cap in captions or []:
            src = (
                next(
                    (
                        i.get("from") or []
                        for i in sec.get("lines") or []
                        if i["caption"] == cap
                    ),
                    [],
                )
                if use_summary
                else [cap]
            )
            raw: dict[str, Decimal] = {}
            for s in src:
                for col, v in (per_cc.get(norm(s)) or {}).items():
                    raw[col] = raw.get(col, ZERO) + v
            vals = _signed(raw, sign)
            rows.append(ReportRow(caption=cap, kind="line", values=vals, level=1))
            for col, v in vals.items():
                section_total[col] = section_total.get(col, ZERO) + v
        label = sec.get("total")
        if label:
            rows.append(ReportRow(caption=label, kind="total", values=section_total))
            totals[label] = section_total.get("TOTAL", ZERO)

    for label, parts in (struct.subtotals or {}).items():
        agg: dict[str, Decimal] = {}
        for r in rows:
            if r.kind == "total" and r.caption in parts:
                for col, v in r.values.items():
                    agg[col] = agg.get(col, ZERO) + v
        rows.append(ReportRow(caption=label, kind="grand_total", values=agg))
        totals[label] = agg.get("TOTAL", ZERO)

    return StatementReport(
        title=f"MAGE CONSOLIDATED ACCOUNTS - {statement.value} BY COST CENTER",
        statement=statement,
        columns=columns,
        rows=rows,
        totals=totals,
        currency=cfg.reporting_currency,
        period_label=result.period.key,
    )
