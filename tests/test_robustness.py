"""Scenarios de robustesse : les incidents courants d'une cloture reelle.

Chaque test part du jeu de demonstration et y introduit UN defaut realiste, pour
verifier que le moteur ne produit jamais un etat faussement propre.
"""
from __future__ import annotations

from decimal import Decimal

import make_samples as ms
import pytest

from mageconso.controls import run_controls
from mageconso.engine import ConsolidationEngine
from mageconso.importers.excel import ManagementAccountsReader
from mageconso.models import Severity, Statement
from mageconso.reports import build_statement
from mageconso.suggest import suggest

CENT = Decimal("0.01")


def _consolidate(cfg, tmp_path, **tb):
    files = ms.build(tmp_path, **tb)
    reader = ManagementAccountsReader(cfg)
    wbs = [reader.read(p) for p in files]
    res = ConsolidationEngine(cfg).consolidate(wbs)
    bs = build_statement(cfg, res, Statement.BALANCE_SHEET)
    pl = build_statement(cfg, res, Statement.PROFIT_AND_LOSS)
    ctl = {c.code: c for c in run_controls(cfg, res, bs=bs, pl=pl, workbooks=wbs)}
    return res, bs, pl, ctl


# ------------------------------------------------------ ecart de reciprocite
def test_reciprocity_gap_keeps_balance_sheet_balanced(cfg, tmp_path):
    """Dette filiale 14 067 000 JPY au lieu de 14 069 700 : ~17 EUR d'ecart.
    Cas quotidien (change, decalage). Le bilan doit rester equilibre."""
    jp = [(c, -14_067_000.0) if c.startswith("Accounts Payable - Inter") else (c, v)
          for c, v in ms.MAGE_JAPON_TB]
    res, bs, _, ctl = _consolidate(cfg, tmp_path, jp_tb=ms.rebalance(jp))

    assert ctl["C1"].passed, ctl["C1"].detail
    assert ctl["C4"].passed
    gap = [d for d in res.diagnostics if d.code == "ELIM-RECIPROCITY"]
    assert gap and "Consolidation reserves" in gap[0].message


def test_reciprocity_residual_is_traced(cfg, tmp_path):
    jp = [(c, -14_067_000.0) if c.startswith("Accounts Payable - Inter") else (c, v)
          for c, v in ms.MAGE_JAPON_TB]
    res, *_ = _consolidate(cfg, tmp_path, jp_tb=ms.rebalance(jp))
    residual = [a for a in res.audit
                if a.origin == "elimination" and "reciprocite" in a.transformations]
    assert len(residual) == 1
    # eliminations : creance -90 000,00 / dette +89 982,73 -> somme -17,27 ;
    # le residu qui equilibre l'ecriture est donc +17,27 (debit des reserves).
    assert abs(residual[0].amount_eur - Decimal("17.27")) < CENT


# --------------------------------------------------- flux sans contrepartie
def test_one_sided_flow_is_not_eliminated(cfg, tmp_path):
    """Des management fees factures par la mere sans poste symetrique chez la
    filiale ne doivent pas disparaitre du consolide."""
    sas = ms.rebalance(list(ms.MAGE_SAS_TB) + [("Management fees", -40_000.0)])
    res, _, pl, ctl = _consolidate(cfg, tmp_path, sas_tb=sas,
                                   extra_captions=["Management fees"])

    assert ctl["C1"].passed and ctl["C2"].passed
    assert res.total("Management fees", origin="elimination") == 0
    assert any(d.code == "ELIM-ONE-SIDED" for d in res.diagnostics)


def test_one_sided_can_be_forced_and_stays_balanced(cfg, tmp_path):
    import copy

    forced = copy.deepcopy(cfg)
    forced.eliminations = {**cfg.eliminations, "one_sided": "eliminate"}
    sas = ms.rebalance(list(ms.MAGE_SAS_TB) + [("Management fees", -40_000.0)])
    res, _, _, ctl = _consolidate(forced, tmp_path, sas_tb=sas,
                                  extra_captions=["Management fees"])
    assert ctl["C2"].passed and ctl["C4"].passed


# ------------------------------------------------------- compte non mappe
def test_unmapped_account_is_never_disguised_as_fx_difference(cfg, tmp_path):
    """MAGE SAS est en euros : elle ne peut PAS avoir d'ecart de conversion.
    Un compte exclu doit rester visible (C1 en echec), pas etre absorbe."""
    sas = [("Loyer entrepot" if c == "Rent" else c, v) for c, v in ms.MAGE_SAS_TB]
    res, _, _, ctl = _consolidate(cfg, tmp_path, sas_tb=sas)

    fx_sas = [ln for ln in res.lines
              if ln.entity == "MAGE_SAS" and ln.origin == "fx_translation"]
    assert not fx_sas
    assert not ctl["C1"].passed
    assert "175 000,00" in ctl["C1"].detail
    assert not ctl["C5"].passed


def test_unmapped_account_is_reported_with_amount_and_suggestion(cfg, tmp_path):
    sas = [("Loyer entrepot" if c == "Rent" else c, v) for c, v in ms.MAGE_SAS_TB]
    res, *_ = _consolidate(cfg, tmp_path, sas_tb=sas)
    [u] = res.unmapped
    assert u.local_account == "Loyer entrepot"
    assert u.amount == Decimal(175_000)
    assert u.best == "Rent"
    diag = next(d for d in res.diagnostics if d.code == "MAP-UNKNOWN-ACCOUNT")
    assert diag.severity is Severity.ERROR and "Rent" in diag.message


def test_eur_entity_has_no_translation_difference(result):
    assert not [ln for ln in result.lines
                if ln.entity == "MAGE_SAS" and ln.origin == "fx_translation"]


# ------------------------------------------------------------- doublons
def test_same_entity_twice_is_rejected(cfg, tmp_path):
    files = ms.build(tmp_path)
    reader = ManagementAccountsReader(cfg)
    wbs = [reader.read(p) for p in files + [files[0]]]
    res = ConsolidationEngine(cfg).consolidate(wbs)
    assert any(d.code == "ENT-DUPLICATE" for d in res.diagnostics)
    assert res.entity_codes.count("MAGE_SAS") == 1


# ------------------------------------------------------------ suggestions
@pytest.mark.parametrize("local,expected", [
    ("Frais bancaires", "Bank charges"),
    ("Commissions carte bancaire", "Credit card charges"),
    ("Loyer entrepot", "Rent"),
    ("Cash at bank", "Cash Bank"),
    ("支払家賃/Rent paid", "Rent"),
    ("Honoraires comptables", "Accountancy"),
])
def test_mapping_suggestions(cfg, local, expected):
    assert suggest(local, cfg.mapping_knowledge())[0][0] == expected


def test_no_suggestion_for_meaningless_label(cfg):
    assert suggest("Xyz 123", cfg.mapping_knowledge()) == []
