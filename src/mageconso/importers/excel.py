"""Import des classeurs "Management accounts".

Detection par EN-TETE et par NOM DE FEUILLE (jamais par coordonnees fixes),
afin d'absorber les variantes de colonnage constatees entre entites.

Les feuilles masquees ET "very hidden" sont lues : le classeur consolide de
reference stocke ses lignes de detail dans des feuilles ``very hidden``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

from ..config import AppConfig, norm
from ..models import Diagnostic, Period, Severity, SourceLine, Statement

_NUM_CLEAN = re.compile(r"[\s  ']")


def to_decimal(value: Any) -> Decimal | None:
    """Convertit une valeur de cellule en Decimal.

    Gere les nombres, les chaines francaises ("1 234,56"), les parentheses
    comptables ("(1 234)") et les tirets d'absence ("-", "- ").
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    txt = str(value).strip()
    if txt in ("", "-", "–", "—", "n/a", "N/A", "#DIV/0!", "#REF!", "#VALUE!"):
        return None
    neg = txt.startswith("(") and txt.endswith(")")
    if neg:
        txt = txt[1:-1]
    txt = _NUM_CLEAN.sub("", txt)
    txt = txt.replace("€", "").replace("%", "")
    if "," in txt and "." in txt:
        # le separateur DECIMAL est celui qui apparait en dernier :
        # "1.234,56" (FR) -> 1234.56 ; "1,234.56" (EN) -> 1234.56
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    else:
        txt = txt.replace(",", ".")
    try:
        d = Decimal(txt)
    except InvalidOperation:
        return None
    return -d if neg else d


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _match(label: str, candidates: Iterable[str]) -> bool:
    key = norm(label)
    return any(key == norm(c) for c in candidates)


def _contains(label: str, candidates: Iterable[str]) -> bool:
    key = norm(label)
    return any(norm(c) and norm(c) in key for c in candidates)


@dataclass
class SourceWorkbook:
    """Vue normalisee d'un classeur de management accounts."""

    path: Path
    entity_name: str | None = None
    entity_code: str | None = None
    currency: str | None = None
    fiscal_year: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    account_map: dict[str, str] = field(default_factory=dict)
    group_coa: dict[str, Statement] = field(default_factory=dict)
    lines: list[SourceLine] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    sheet_names: list[str] = field(default_factory=list)
    hidden_sheets: list[str] = field(default_factory=list)

    @property
    def closing(self) -> str | None:
        return self.period_end.isoformat() if self.period_end else None


def _find_sheet(wb, names: Iterable[str]):
    for want in names:
        for sh in wb.worksheets:
            if norm(sh.title) == norm(want):
                return sh
    for want in names:
        for sh in wb.worksheets:
            if norm(want) and norm(want) in norm(sh.title):
                return sh
    return None


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    txt = _text(value)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


class ManagementAccountsReader:
    """Lit un classeur de management accounts vers des ``SourceLine``."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.fmt = cfg.source_format

    # ------------------------------------------------------------------ API
    def read(self, path: str | Path, *, entity_code: str | None = None) -> SourceWorkbook:
        p = Path(path)
        wb = load_workbook(p, data_only=True, read_only=False)
        out = SourceWorkbook(path=p, entity_code=entity_code)
        out.sheet_names = [sh.title for sh in wb.worksheets]
        out.hidden_sheets = [
            sh.title for sh in wb.worksheets if sh.sheet_state != "visible"
        ]

        self._read_cover(wb, out)
        self._read_mapping(wb, out)
        self._read_group_coa(wb, out)
        self._read_trial_balance(wb, out)

        if not out.lines:
            out.diagnostics.append(
                Diagnostic(
                    code="SRC-EMPTY",
                    severity=Severity.ERROR,
                    message=(
                        "Aucune ligne de balance exploitable trouvee. "
                        f"Feuilles presentes : {', '.join(out.sheet_names)}"
                    ),
                    source_file=p.name,
                )
            )
        wb.close()
        return out

    # ---------------------------------------------------------------- cover
    def _read_cover(self, wb, out: SourceWorkbook) -> None:
        spec = self.fmt.get("cover") or {}
        sh = _find_sheet(wb, spec.get("sheet_names") or ["Cover"])
        if sh is None:
            out.diagnostics.append(
                Diagnostic(
                    code="SRC-NO-COVER",
                    severity=Severity.WARNING,
                    message="Feuille 'Cover' absente : entite/devise/periode a preciser.",
                    source_file=out.path.name,
                )
            )
            return
        out.entity_name = _text(sh["A1"].value) or None
        labels = spec.get("labels") or {}
        span = int(spec.get("value_search_offset_max", 4))
        for row in sh.iter_rows():
            for cell in row:
                lab = _text(cell.value)
                if not lab:
                    continue
                for field_name, cands in labels.items():
                    if not _contains(lab, cands):
                        continue
                    val = self._value_right(sh, cell.row, cell.column, span)
                    if val is None:
                        continue
                    if field_name == "fiscal_year":
                        d = to_decimal(val)
                        if d is not None:
                            out.fiscal_year = int(d)
                    elif field_name == "local_currency":
                        out.currency = _text(val).upper() or None
                    elif field_name == "period_start":
                        out.period_start = _as_date(val)
                    elif field_name == "period_end":
                        out.period_end = _as_date(val)
        if out.period_end is None and out.fiscal_year:
            out.period_end = date(out.fiscal_year, 12, 31)

    @staticmethod
    def _value_right(sh, row: int, col: int, span: int) -> Any:
        for off in range(1, span + 2):
            v = sh.cell(row=row, column=col + off).value
            if v is not None and _text(v) != "":
                return v
        return None

    # -------------------------------------------------------------- mapping
    def _read_mapping(self, wb, out: SourceWorkbook) -> None:
        spec = self.fmt.get("mapping_sheet") or {}
        sh = _find_sheet(wb, spec.get("sheet_names") or ["Mapping accounts"])
        if sh is None:
            return
        heads = spec.get("headers") or {}
        cols = self._locate_columns(sh, heads)
        if not cols.get("group_coa"):
            return
        start = cols["_header_row"] + 1
        for r in range(start, sh.max_row + 1):
            target = _text(sh.cell(row=r, column=cols["group_coa"]).value)
            if not target:
                continue
            for key in ("local_account", "account_id"):
                c = cols.get(key)
                if not c:
                    continue
                src = _text(sh.cell(row=r, column=c).value)
                if src:
                    out.account_map.setdefault(norm(src), target)

    def _read_group_coa(self, wb, out: SourceWorkbook) -> None:
        spec = self.fmt.get("group_coa_sheet") or {}
        sh = _find_sheet(wb, spec.get("sheet_names") or ["Group COA"])
        if sh is None:
            return
        markers = spec.get("section_markers") or {}
        current = Statement.BALANCE_SHEET
        for r in range(1, sh.max_row + 1):
            cap = _text(sh.cell(row=r, column=1).value)
            marker = " ".join(
                _text(sh.cell(row=r, column=c).value) for c in (2, 3)
            ).strip()
            if marker:
                for stmt_name, toks in markers.items():
                    if _contains(marker, toks):
                        current = (
                            Statement.BALANCE_SHEET
                            if stmt_name.upper().startswith("BALANCE")
                            else Statement.PROFIT_AND_LOSS
                        )
            if cap and norm(cap) != norm("Account description"):
                out.group_coa.setdefault(norm(cap), current)

    # -------------------------------------------------------- trial balance
    def _read_trial_balance(self, wb, out: SourceWorkbook) -> None:
        spec = self.fmt.get("trial_balance_sheet") or {}
        sh = _find_sheet(wb, spec.get("sheet_names") or ["Trial balance"])
        if sh is None:
            return
        cols = self._locate_columns(sh, spec.get("headers") or {})
        cap_col = cols.get("caption")
        if not cap_col:
            return
        bal_col = cols.get("ending_balance")
        dr_col, cr_col = cols.get("debit"), cols.get("credit")
        flip = (
            str(spec.get("sign_convention", "DEBIT_PLUS_CREDIT_MINUS"))
            != str(self.fmt.get("output_sign_convention", "DEBIT_MINUS_CREDIT_PLUS"))
        )
        period = self._period(out)
        entity = out.entity_code or out.entity_name or out.path.stem

        for r in range(cols["_header_row"] + 1, sh.max_row + 1):
            caption = _text(sh.cell(row=r, column=cap_col).value)
            if not caption:
                continue
            if _contains(caption, ["control", "total general"]):
                continue
            amount = None
            if bal_col:
                amount = to_decimal(sh.cell(row=r, column=bal_col).value)
            if amount is None and dr_col and cr_col:
                dr = to_decimal(sh.cell(row=r, column=dr_col).value) or Decimal(0)
                cr = to_decimal(sh.cell(row=r, column=cr_col).value) or Decimal(0)
                amount = dr - cr
            if amount is None:
                continue
            out.lines.append(
                SourceLine(
                    entity=entity,
                    period=period,
                    local_account=caption,
                    local_label=caption,
                    amount=-amount if flip else amount,
                    currency=out.currency or "EUR",
                    source_file=out.path.name,
                    source_sheet=sh.title,
                    source_row=r,
                )
            )

    @staticmethod
    def _period(out: SourceWorkbook) -> Period:
        if out.period_end:
            return Period(out.period_end.year, out.period_end.month)
        if out.fiscal_year:
            return Period(out.fiscal_year, None)
        return Period(date.today().year, None)

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _locate_columns(sh, headers: dict[str, list[str]]) -> dict[str, int]:
        """Trouve la ligne d'entete et l'index de chaque colonne demandee."""
        best: dict[str, int] = {}
        best_row = 0
        best_score = -1
        limit = min(sh.max_row, 40)
        for r in range(1, limit + 1):
            found: dict[str, int] = {}
            for c in range(1, min(sh.max_column, 40) + 1):
                lab = _text(sh.cell(row=r, column=c).value)
                if not lab:
                    continue
                for name, cands in headers.items():
                    if name in found:
                        continue
                    if _match(lab, cands):
                        found[name] = c
            if len(found) > best_score:
                best_score, best, best_row = len(found), found, r
        best["_header_row"] = best_row
        return best
