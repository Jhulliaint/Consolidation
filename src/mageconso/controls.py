"""Controles de coherence.

Reproduit les controles deja presents dans les classeurs Mage (FAITS OBSERVES) :
 - "Control :" du bilan consolide  -> Total actif - Total passif = 0
 - "Control" du compte de resultat -> resultat P&L = ligne "Profit/loss net
   income" du bilan  (formule C202 = C198 - 'Detailed Consolidated BS'!C102)
 - balance source equilibree       -> Total debit = Total credit
et ajoute les controles demandes au cahier des charges (mappings exhaustifs,
comptes/centres inconnus, equilibre des eliminations, rapprochement aux
fichiers de reference).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from .config import AppConfig, norm
from .importers.excel import SourceWorkbook
from .models import (
    ZERO,
    eur,
    ConsolidationResult,
    ControlResult,
    Severity,
    Statement,
)
from .reports import StatementReport

TOL = Decimal("0.01")


def run_controls(
    cfg: AppConfig,
    result: ConsolidationResult,
    bs: StatementReport | None = None,
    pl: StatementReport | None = None,
    workbooks: Sequence[SourceWorkbook] = (),
    reference: dict[str, Decimal] | None = None,
    tolerance: Decimal = TOL,
) -> list[ControlResult]:
    out: list[ControlResult] = []

    # --- C1 : equilibre du bilan consolide --------------------------------
    if bs is not None:
        assets = bs.total("Total assets")
        liab = bs.total("Total liabilities & shareholders' equity")
        out.append(
            ControlResult(
                code="C1",
                label="Bilan equilibre (Total actif = Total passif)",
                passed=abs(assets - liab) <= tolerance,
                expected=assets,
                actual=liab,
                detail=f"ecart = {eur(liab - assets)} EUR",
            )
        )

    # --- C2 : resultat P&L = resultat porte au bilan -----------------------
    # Reproduit le controle C202 du classeur de reference.
    # Le compte de resultat est restitue en credit positif tandis que le moteur
    # stocke en debit positif : la ligne de bilan est donc l'oppose du resultat
    # presente.
    if bs is not None and pl is not None:
        pl_net = pl.total("Total Net/(loss) Profit")
        bs_net = -result.total("Profit/loss net income")
        out.append(
            ControlResult(
                code="C2",
                label="Resultat net P&L = ligne 'Profit/loss net income' du bilan",
                passed=abs(pl_net - bs_net) <= tolerance,
                expected=pl_net,
                actual=bs_net,
                severity=Severity.ERROR,
                detail=f"ecart = {eur(bs_net - pl_net)} EUR",
            )
        )

    # --- C3 : balances sources equilibrees --------------------------------
    for wb in workbooks:
        total = sum((ln.amount for ln in wb.lines), ZERO)
        out.append(
            ControlResult(
                code="C3",
                label=f"Balance source equilibree - {wb.path.name}",
                passed=abs(total) <= tolerance,
                expected=ZERO,
                actual=total,
                detail=f"{len(wb.lines)} lignes lues",
            )
        )

    # --- C4 : ecritures d'elimination equilibrees par etat ----------------
    for statement in (Statement.BALANCE_SHEET, Statement.PROFIT_AND_LOSS):
        elim = sum(
            (
                ln.amount_eur
                for ln in result.lines
                if ln.origin == "elimination" and ln.statement is statement
            ),
            ZERO,
        )
        if elim == ZERO and not any(
            ln.origin == "elimination" and ln.statement is statement
            for ln in result.lines
        ):
            continue
        out.append(
            ControlResult(
                code="C4",
                label=f"Eliminations equilibrees ({statement.value})",
                passed=abs(elim) <= tolerance,
                expected=ZERO,
                actual=elim,
                severity=Severity.WARNING,
                detail="somme algebrique des eliminations",
            )
        )

    # --- C5 : exhaustivite du mapping -------------------------------------
    unmapped = sorted(
        {
            d.message
            for d in result.diagnostics
            if d.code == "MAP-UNKNOWN-ACCOUNT"
        }
    )
    out.append(
        ControlResult(
            code="C5",
            label="Exhaustivite du mapping des comptes",
            passed=not unmapped,
            severity=Severity.ERROR,
            detail=(
                "tous les comptes sources sont mappes"
                if not unmapped
                else f"{len(unmapped)} compte(s) non mappe(s)"
            ),
        )
    )

    # --- C6 : centres de couts connus -------------------------------------
    known = set(cfg.cost_centres) | {"ELIMINATION"} | set(cfg.technical_columns)
    known |= {str(cfg.allocation.get("default_cost_center", "UNALLOCATED"))}
    unknown_cc = sorted({ln.cost_centre for ln in result.lines} - known)
    out.append(
        ControlResult(
            code="C6",
            label="Centres de couts connus",
            passed=not unknown_cc,
            severity=Severity.WARNING,
            detail=", ".join(unknown_cc) if unknown_cc else "aucun centre inconnu",
        )
    )

    # --- C7 : coherence des periodes --------------------------------------
    periods = {wb.closing for wb in workbooks if wb.closing}
    out.append(
        ControlResult(
            code="C7",
            label="Coherence des dates de cloture entre fichiers",
            passed=len(periods) <= 1,
            severity=Severity.WARNING,
            detail=", ".join(sorted(periods)) if periods else "non renseignee",
        )
    )

    # --- C8 : taux de change disponibles ----------------------------------
    missing_fx = [d for d in result.diagnostics if d.code == "FX-RATE-MISSING"]
    out.append(
        ControlResult(
            code="C8",
            label="Taux de change disponibles pour toutes les devises",
            passed=not missing_fx,
            severity=Severity.ERROR,
            detail=f"{len(missing_fx)} taux manquant(s)",
        )
    )

    # --- C9 : rapprochement au fichier de reference -----------------------
    if reference:
        for caption, expected in reference.items():
            actual = result.total(caption) if not caption.startswith("=") else ZERO
            if bs is not None and caption in bs.totals:
                actual = bs.total(caption)
            elif pl is not None and caption in pl.totals:
                actual = pl.total(caption)
            out.append(
                ControlResult(
                    code="C9",
                    label=f"Rapprochement reference - {caption}",
                    passed=abs(actual - Decimal(str(expected))) <= tolerance,
                    expected=Decimal(str(expected)),
                    actual=actual,
                    detail="comparaison au fichier consolide de reference",
                )
            )

    return out


def controls_summary(controls: Sequence[ControlResult]) -> str:
    ok = sum(1 for c in controls if c.passed)
    ko = [c for c in controls if not c.passed]
    blocking = [c for c in ko if c.severity is Severity.ERROR]
    txt = f"{ok}/{len(controls)} controles OK"
    if ko:
        txt += f" - {len(ko)} en echec ({len(blocking)} bloquant(s))"
    return txt
