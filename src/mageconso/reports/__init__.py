"""Construction des etats consolides.

Restitutions, correspondant aux classeurs de reference :

 * ``build_statement``        -> "Mage SAS Consolidated accounts"
   bilan et compte de resultat, niveau synthese ou detail ; avec
   ``by_entity=True``, une colonne par entite puis ELIMINATION et TOTAL
   (feuille "Conso <date> legal entity") ;
 * ``build_by_cost_centre``   -> "Mage Consolidated accounts by cost center"
   une colonne par centre de couts, puis ELIMINATION et TOTAL ;
 * ``build_margin_analysis``  -> analyse de marge par famille de produits
   (bloc F:M de "Detailed Consolidated PL").

Toutes les vues partagent le meme moteur de construction (``_build``) : seule
change la facon de repartir les montants en colonnes. Le compte de resultat par
centre de couts beneficie ainsi, lui aussi, de la cascade de resultat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable

from ..config import AppConfig, StatementStructure, norm
from ..models import ZERO, ConsolidatedLine, ConsolidationResult, Statement

TOTAL = "TOTAL"
ELIMINATION = "ELIMINATION"


@dataclass
class ReportRow:
    caption: str
    # section | line | total | grand_total | cascade | cascade_total | percent
    kind: str
    values: dict[str, Decimal] = field(default_factory=dict)
    level: int = 0

    def value(self, column: str = TOTAL) -> Decimal:
        return self.values.get(column, ZERO)


@dataclass
class StatementReport:
    title: str
    statement: Statement | None
    columns: list[str]
    rows: list[ReportRow]
    totals: dict[str, Decimal] = field(default_factory=dict)
    currency: str = "EUR"
    period_label: str = ""
    period_end: date | None = None
    # libelle affiche de chaque colonne (nom d'entite plutot que son code)
    column_labels: dict[str, str] = field(default_factory=dict)
    # base du "% du chiffre d'affaires", par colonne (compte de resultat)
    percent_base: dict[str, Decimal] = field(default_factory=dict)

    def label(self, column: str) -> str:
        return self.column_labels.get(column, column)

    def total(self, caption: str, column: str = TOTAL) -> Decimal:
        key = norm(caption)
        if column == TOTAL:
            for c, v in self.totals.items():
                if norm(c) == key:
                    return v
        for r in self.rows:
            if norm(r.caption) == key and r.kind != "section":
                return r.value(column)
        return ZERO

    def percent(self, row: ReportRow, column: str) -> Decimal | None:
        """Part du chiffre d'affaires de la colonne, ou None si non pertinent."""
        base = self.percent_base.get(column)
        if not base or row.kind in ("section", "percent"):
            return None
        return row.value(column) / base


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


def _add(target: dict[str, Decimal], values: dict[str, Decimal]) -> None:
    for col, v in values.items():
        target[col] = target.get(col, ZERO) + v


def _bucket(
    result: ConsolidationResult,
    statement: Statement,
    column_of: Callable[[ConsolidatedLine], str],
) -> dict[str, dict[str, Decimal]]:
    """libelle normalise -> {colonne -> montant}, colonne TOTAL incluse."""
    out: dict[str, dict[str, Decimal]] = {}
    for ln in result.lines:
        if ln.statement is not statement:
            continue
        col = ELIMINATION if ln.origin == "elimination" else column_of(ln)
        bucket = out.setdefault(norm(ln.group_coa), {})
        bucket[TOTAL] = bucket.get(TOTAL, ZERO) + ln.amount_eur
        if col != TOTAL:  # une vue sans ventilation ne doit pas compter deux fois
            bucket[col] = bucket.get(col, ZERO) + ln.amount_eur
    return out


def _build(
    cfg: AppConfig,
    result: ConsolidationResult,
    statement: Statement,
    *,
    level: str,
    column_of: Callable[[ConsolidatedLine], str],
    columns: list[str],
    column_labels: dict[str, str],
    title: str,
) -> StatementReport:
    struct: StatementStructure = cfg.structure(statement)
    data = _bucket(result, statement, column_of)
    rows: list[ReportRow] = []
    totals: dict[str, Decimal] = {}

    def line_values(captions: list[str]) -> dict[str, Decimal]:
        agg: dict[str, Decimal] = {}
        for cap in captions:
            _add(agg, data.get(norm(cap)) or {})
        return agg

    # Le compte de resultat ne definit pas de bloc "summary" : sa synthese est
    # la cascade de resultat. On calcule alors sur les lignes de detail.
    use_summary = level == "summary" and bool(struct.summary_sections)
    sections = struct.summary_sections if use_summary else struct.detail_sections

    for sec in sections:
        rows.append(ReportRow(caption=sec.get("section", ""), kind="section"))
        section_total: dict[str, Decimal] = {}
        sign = Decimal(str(sec.get("sign", 1)))
        for item in sec.get("lines") or []:
            caption, sources = (
                (item["caption"], item.get("from") or []) if use_summary
                else (item, [item])
            )
            vals = _signed(line_values(sources), sign)
            rows.append(ReportRow(caption=caption, kind="line", values=vals, level=1))
            _add(section_total, vals)
        label = sec.get("total")
        if label:
            rows.append(ReportRow(caption=label, kind="total", values=section_total))
            totals[label] = section_total.get(TOTAL, ZERO)

    # sous-totaux transverses (Total assets, Total liabilities & equity...)
    for label, parts in (struct.subtotals or {}).items():
        agg: dict[str, Decimal] = {}
        for r in rows:
            if r.kind == "total" and r.caption in parts:
                _add(agg, r.values)
        rows.append(ReportRow(caption=label, kind="grand_total", values=agg))
        totals[label] = agg.get(TOTAL, ZERO)

    # cascade de resultat (compte de resultat uniquement)
    cascade_vals: dict[str, dict[str, Decimal]] = {}
    if struct.cascade:
        pl_sign = Decimal(str((struct.detail_sections or [{}])[0].get("sign", 1)))
        for step in struct.cascade:
            cap = step["caption"]
            if "from_total" in step:
                vals = next(
                    (dict(r.values) for r in rows
                     if r.caption == step["from_total"] and r.kind == "total"),
                    {},
                )
            elif "from_line" in step:
                vals = _signed(line_values([step["from_line"]]), pl_sign)
            else:
                vals = {}
                for part in step.get("sum_of") or []:
                    _add(vals, cascade_vals.get(part) or {})
            cascade_vals[cap] = vals
            kind = "cascade_total" if "sum_of" in step else "cascade"
            rows.append(ReportRow(caption=cap, kind=kind, values=vals))
            totals[cap] = vals.get(TOTAL, ZERO)

        if struct.ebita:
            vals = dict(cascade_vals.get(struct.ebita.get("base", ""), {}))
            for cap in struct.ebita.get("add_back") or []:
                for col, v in _signed(line_values([cap]), pl_sign).items():
                    vals[col] = vals.get(col, ZERO) - v
            for cap in struct.ebita.get("plus") or []:
                _add(vals, _signed(line_values([cap]), pl_sign))
            rows.append(ReportRow(caption="EBITA", kind="cascade", values=vals))
            totals["EBITA"] = vals.get(TOTAL, ZERO)

    # Le compte de resultat de synthese du classeur de reference ne comporte QUE
    # la cascade (42 lignes) : les lignes de detail ont servi aux totaux mais ne
    # sont pas presentees a ce niveau.
    if level == "summary" and not struct.summary_sections and struct.cascade:
        rows = [r for r in rows if r.kind.startswith("cascade")]

    percent_base: dict[str, Decimal] = {}
    if statement is Statement.PROFIT_AND_LOSS:
        base = cascade_vals.get("Revenue")
        if not base:
            revenue_total = (struct.detail_sections or [{}])[0].get("total")
            base = next((r.values for r in rows
                         if r.caption == revenue_total and r.kind == "total"), {})
        percent_base = {c: v for c, v in base.items() if v}

    return StatementReport(
        title=title,
        statement=statement,
        columns=columns,
        rows=rows,
        totals=totals,
        currency=cfg.reporting_currency,
        period_label=result.period.key,
        period_end=result.period.end_date if result.period.year else None,
        column_labels=column_labels,
        percent_base=percent_base,
    )


_TITLES = {
    Statement.BALANCE_SHEET: "UNAUDITED CONSOLIDATED BALANCE SHEET",
    Statement.PROFIT_AND_LOSS: "UNAUDITED PROFIT & LOSS REPORT CONSOLIDATED ACCOUNTS",
}


def build_statement(
    cfg: AppConfig,
    result: ConsolidationResult,
    statement: Statement,
    *,
    level: str = "summary",
    by_entity: bool = False,
    columns: list[str] | None = None,
) -> StatementReport:
    """Etat consolide. ``by_entity`` : une colonne par entite + ELIMINATION."""
    if by_entity:
        found = result.entity_codes or [
            e for e in result.entities() if e != ELIMINATION
        ]
        # ordre du perimetre (mere en tete, comme dans le classeur de reference),
        # et non ordre de lecture des fichiers
        rank = {code: i for i, code in enumerate(cfg.entities)}
        ents = sorted(found, key=lambda e: rank.get(e, len(rank)))
        has_elim = any(ln.origin == "elimination" for ln in result.lines)
        cols = ents + ([ELIMINATION] if has_elim else []) + [TOTAL]
        labels = {e: (cfg.entity(e).name if cfg.entity(e) else e) for e in ents}
        title = f"{_TITLES[statement]} - BY LEGAL ENTITY"
    else:
        cols = columns or [TOTAL]
        labels = {}
        title = _TITLES[statement]
    return _build(
        cfg, result, statement,
        level=level,
        column_of=lambda ln: ln.entity,
        columns=cols,
        column_labels=labels,
        title=title,
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
    used = {ln.cost_centre for ln in result.lines
            if ln.statement is statement and ln.origin != "elimination"}
    ordered = [cc for cc in cfg.cost_centres if cc in used]
    extra = sorted(used - set(ordered))
    has_elim = any(ln.origin == "elimination" and ln.statement is statement
                   for ln in result.lines)
    columns = ordered + extra + ([ELIMINATION] if has_elim else []) + [TOTAL]
    labels = {cc: cfg.cost_centres[cc].label for cc in ordered}
    labels.update({"UNALLOCATED": "NON AFFECTE"})
    return _build(
        cfg, result, statement,
        level=level,
        column_of=lambda ln: ln.cost_centre,
        columns=columns,
        column_labels=labels,
        title=f"MAGE CONSOLIDATED ACCOUNTS - {statement.value} BY COST CENTER",
    )


def build_margin_analysis(cfg: AppConfig, result: ConsolidationResult) -> StatementReport:
    """Analyse de marge par famille de produits.

    Reproduit le bloc F:M lignes 28-31 de "Detailed Consolidated PL" (FAIT
    OBSERVE) : pour chaque famille, chiffre d'affaires, cout des ventes, marge
    brute et taux de marge. Les regroupements de lignes sont ceux des formules
    d'origine (``margin_families`` dans statement_pl.yaml).
    """
    struct = cfg.pl
    data = _bucket(result, Statement.PROFIT_AND_LOSS, lambda ln: TOTAL)
    sign = Decimal(str((struct.detail_sections or [{}])[0].get("sign", -1)))

    def amount(captions: list[str]) -> Decimal:
        return sum(((data.get(norm(c)) or {}).get(TOTAL, ZERO) for c in captions),
                   ZERO) * sign

    families = struct.margin_families or {}
    rev, cost, margin, rate = {}, {}, {}, {}
    for name, spec in families.items():
        members = spec.get("combine")
        if members:
            rev[name] = sum((rev.get(m, ZERO) for m in members), ZERO)
            cost[name] = sum((cost.get(m, ZERO) for m in members), ZERO)
        else:
            rev[name] = amount(spec.get("revenue") or [])
            cost[name] = amount(spec.get("cost") or [])
        margin[name] = rev[name] + cost[name]
        if rev[name]:
            rate[name] = margin[name] / rev[name]

    rows = [
        ReportRow("Revenue", "line", rev),
        ReportRow("Cost of sales", "line", cost),
        ReportRow("Gross margin", "total", margin),
        ReportRow("Gross margin %", "percent", rate),
    ]
    return StatementReport(
        title="GROSS MARGIN BY PRODUCT FAMILY",
        statement=None,
        columns=list(families),
        rows=rows,
        currency=cfg.reporting_currency,
        period_label=result.period.key,
        period_end=result.period.end_date if result.period.year else None,
    )
