"""Export Excel des etats consolides.

Les cellules recoivent la VALEUR numerique (auditable, reutilisable dans Excel)
et un FORMAT de nombre derive de ``config/presentation.yaml``. La presentation
n'altere donc jamais le montant stocke.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..formatting import NumberFormatter
from ..models import ConsolidationResult, ControlResult, Severity
from ..reports import StatementReport

THIN = Side(style="thin")
DOUBLE = Side(style="double")


def _style(styles: dict, name: str) -> dict:
    return (styles or {}).get(name) or {}


def _apply(cell, spec: dict) -> None:
    if spec.get("bold"):
        cell.font = Font(bold=True, size=spec.get("font_size") or 11)
    elif spec.get("font_size"):
        cell.font = Font(size=spec["font_size"])
    if spec.get("fill"):
        cell.fill = PatternFill("solid", fgColor=spec["fill"])
    if spec.get("top_border") == "thin":
        cell.border = Border(top=THIN)
    elif spec.get("top_border") == "double":
        cell.border = Border(top=DOUBLE)


def write_statement(
    ws,
    report: StatementReport,
    fmt: NumberFormatter,
    presentation: dict,
) -> None:
    styles = presentation.get("styles") or {}
    export = presentation.get("export") or {}
    numfmt = fmt.excel_number_format()

    ws["A1"] = "MAGE SAS"
    _apply(ws["A1"], {"bold": True, "font_size": 12})
    ws["A2"] = report.title
    _apply(ws["A2"], {"bold": True})
    ws["A3"] = f"FOR THE PERIOD ENDED {report.period_label}"
    ws["A4"] = report.currency

    header_row = 6
    ws.cell(row=header_row, column=1, value="")
    for i, col in enumerate(report.columns, start=2):
        c = ws.cell(row=header_row, column=i, value=col)
        _apply(c, _style(styles, "header"))
        c.alignment = Alignment(horizontal="right", wrap_text=True)

    r = header_row + 1
    for row in report.rows:
        label_cell = ws.cell(row=r, column=1, value=row.caption)
        kind_style = {
            "section": "section",
            "total": "total",
            "grand_total": "grand_total",
            "cascade": "total",
        }.get(row.kind, "line")
        _apply(label_cell, _style(styles, kind_style))
        if row.level:
            label_cell.alignment = Alignment(indent=row.level)

        if row.kind != "section":
            for i, col in enumerate(report.columns, start=2):
                val = row.values.get(col)
                cell = ws.cell(row=r, column=i)
                if val is not None:
                    # valeur brute, mise a l'echelle d'affichage uniquement
                    cell.value = float(fmt.quantize(val))
                    cell.number_format = numfmt
                _apply(cell, _style(styles, kind_style))
        r += 1

    ws.column_dimensions["A"].width = export.get("column_width_label", 52)
    for i in range(2, len(report.columns) + 2):
        ws.column_dimensions[get_column_letter(i)].width = export.get(
            "column_width_value", 16
        )
    if export.get("freeze_panes", True):
        ws.freeze_panes = ws.cell(row=header_row + 1, column=2)


def write_controls(ws, controls: Sequence[ControlResult], presentation: dict) -> None:
    styles = presentation.get("styles") or {}
    heads = ["Code", "Controle", "Statut", "Severite", "Attendu", "Obtenu", "Ecart", "Detail"]
    for i, h in enumerate(heads, start=1):
        c = ws.cell(row=1, column=i, value=h)
        _apply(c, _style(styles, "header"))
    for r, ctl in enumerate(controls, start=2):
        ws.cell(row=r, column=1, value=ctl.code)
        ws.cell(row=r, column=2, value=ctl.label)
        status = ws.cell(row=r, column=3, value="OK" if ctl.passed else "ECHEC")
        _apply(status, _style(styles, "control_ok" if ctl.passed else "control_ko"))
        ws.cell(row=r, column=4, value=ctl.severity.value)
        if ctl.expected is not None:
            ws.cell(row=r, column=5, value=float(ctl.expected))
        if ctl.actual is not None:
            ws.cell(row=r, column=6, value=float(ctl.actual))
        diff = ctl.difference
        if diff is not None:
            ws.cell(row=r, column=7, value=float(diff))
        ws.cell(row=r, column=8, value=ctl.detail)
    ws.column_dimensions["B"].width = 58
    ws.column_dimensions["H"].width = 60


def write_audit(ws, result: ConsolidationResult, limit: int | None = None) -> None:
    heads = [
        "Entite", "Periode", "Fichier source", "Onglet source", "Ligne",
        "Compte source", "Compte consolide", "Centre de couts",
        "Montant source", "Devise", "Inversion de signe", "Taux",
        "Type de taux", "Montant EUR", "Transformations", "Origine",
    ]
    for i, h in enumerate(heads, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True)
    records = result.audit if limit is None else result.audit[:limit]
    for r, a in enumerate(records, start=2):
        ws.cell(row=r, column=1, value=a.entity)
        ws.cell(row=r, column=2, value=a.period)
        ws.cell(row=r, column=3, value=a.source_file)
        ws.cell(row=r, column=4, value=a.source_sheet)
        ws.cell(row=r, column=5, value=a.source_row)
        ws.cell(row=r, column=6, value=a.local_account)
        ws.cell(row=r, column=7, value=a.group_coa)
        ws.cell(row=r, column=8, value=a.cost_centre)
        ws.cell(row=r, column=9, value=float(a.amount_source))
        ws.cell(row=r, column=10, value=a.currency)
        ws.cell(row=r, column=11, value="oui" if a.sign_flip else "non")
        ws.cell(row=r, column=12, value=float(a.rate) if a.rate is not None else None)
        ws.cell(row=r, column=13, value=a.rate_type)
        ws.cell(row=r, column=14, value=float(a.amount_eur))
        ws.cell(row=r, column=15, value=a.transformations)
        ws.cell(row=r, column=16, value=a.origin)
    for col, width in (("C", 34), ("F", 44), ("G", 44), ("O", 58)):
        ws.column_dimensions[col].width = width


def write_diagnostics(ws, result: ConsolidationResult) -> None:
    heads = ["Severite", "Code", "Entite", "Fichier", "Message", "Contexte"]
    for i, h in enumerate(heads, start=1):
        ws.cell(row=1, column=i, value=h).font = Font(bold=True)
    for r, d in enumerate(result.diagnostics, start=2):
        ws.cell(row=r, column=1, value=d.severity.value)
        ws.cell(row=r, column=2, value=d.code)
        ws.cell(row=r, column=3, value=d.entity)
        ws.cell(row=r, column=4, value=d.source_file)
        ws.cell(row=r, column=5, value=d.message)
        ws.cell(row=r, column=6, value=d.context)
        if d.severity is Severity.ERROR:
            ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor="FFC7CE")
    ws.column_dimensions["E"].width = 90


def export_workbook(
    path: str | Path,
    reports: dict[str, StatementReport],
    result: ConsolidationResult,
    fmt: NumberFormatter,
    presentation: dict,
) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    for name, report in reports.items():
        ws = wb.create_sheet(title=name[:31])
        write_statement(ws, report, fmt, presentation)

    export = presentation.get("export") or {}
    if export.get("include_controls_sheet", True) and result.controls:
        write_controls(wb.create_sheet("Controls"), result.controls, presentation)
    if result.diagnostics:
        write_diagnostics(wb.create_sheet("Diagnostics"), result)
    if export.get("include_audit_sheet", True) and result.audit:
        write_audit(wb.create_sheet("Audit trail"), result)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
