"""Tests du moteur : import, mapping, conversion, eliminations, controles."""
from __future__ import annotations

from decimal import Decimal

from mageconso.controls import run_controls
from mageconso.models import Severity, Statement
from mageconso.reports import build_by_cost_centre, build_statement

JPY_EOM = Decimal("156.33")
JPY_AVG = Decimal("156.30")
JPY_HISTORICAL = Decimal("108.0988")
CENT = Decimal("0.01")


# --------------------------------------------------------------------- import
def test_cover_is_parsed(workbooks):
    by_name = {wb.entity_name: wb for wb in workbooks}
    jp = by_name["MAGE JAPON KK"]
    assert jp.currency == "JPY"
    assert jp.fiscal_year == 2025
    assert jp.period_end.isoformat() == "2025-12-31"
    assert jp.closing == "2025-12-31"


def test_source_trial_balances_are_balanced(workbooks):
    for wb in workbooks:
        assert sum((ln.amount for ln in wb.lines), Decimal(0)) == Decimal(0)


def test_local_mapping_sheet_is_used(workbooks):
    """La feuille 'Mapping accounts' du fichier source prime sur la config."""
    jp = next(wb for wb in workbooks if wb.entity_name == "MAGE JAPON KK")
    assert jp.account_map["普通預金/ordinary deposit"] == "Cash Bank"


def test_entity_is_resolved_from_cover(result):
    assert {"MAGE_SAS", "MAGE_JAPON_KK"} <= set(result.entities())


# ------------------------------------------------------------------------ FX
def test_balance_sheet_uses_closing_rate_and_pl_uses_average(result):
    bs_rates = {
        ln.rate
        for ln in result.lines
        if ln.entity == "MAGE_JAPON_KK"
        and ln.statement is Statement.BALANCE_SHEET
        and ln.origin == "entity"
    }
    pl_rates = {
        ln.rate
        for ln in result.lines
        if ln.entity == "MAGE_JAPON_KK"
        and ln.statement is Statement.PROFIT_AND_LOSS
        and ln.origin == "entity"
    }
    # Le bilan est converti au taux de cloture, SAUF le capital et les primes
    # qui suivent le taux historique (fx.yaml: historical_lines).
    assert bs_rates == {JPY_EOM, JPY_HISTORICAL}
    assert pl_rates == {JPY_AVG}


def test_share_capital_uses_historical_rate(result):
    capital = [
        ln
        for ln in result.lines
        if ln.entity == "MAGE_JAPON_KK" and ln.group_coa == "Share capital"
    ]
    assert capital and all(ln.rate == JPY_HISTORICAL for ln in capital)
    assert all(ln.rate_type.value == "historical" for ln in capital)


def test_conversion_is_exact(result):
    """15 400 000 JPY / 156,33 doit se retrouver au centime."""
    got = result.total("Account Receivable", entity="MAGE_JAPON_KK")
    assert abs(got - Decimal(15_400_000) / JPY_EOM) < Decimal("0.0001")


def test_translation_difference_is_posted(result):
    cta = [ln for ln in result.lines if ln.origin == "fx_translation"]
    assert cta, "l'ecart de conversion doit etre porte en reserves"
    assert all(ln.group_coa == "Consolidation reserves" for ln in cta)


# --------------------------------------------------------------- eliminations
def test_intercompany_receivable_and_payable_are_eliminated(result):
    elims = {
        ln.group_coa: ln.amount_eur
        for ln in result.lines
        if ln.origin == "elimination"
    }
    assert elims["Account Receivable - subsidiary Mage Japan"] == Decimal(-90_000)
    assert abs(elims["Accounts Payable - Intercompany purchase Mage"]
               - Decimal(90_000)) < CENT


def test_intragroup_revenue_is_eliminated(result):
    elims = {
        ln.group_coa: ln.amount_eur
        for ln in result.lines
        if ln.origin == "elimination"
    }
    assert elims["Shoe Sales subsidiaries"] == Decimal(300_000)
    assert abs(elims["Purchases shoes from Mage"] + Decimal(300_000)) < CENT


def test_eliminations_are_balanced_per_statement(result):
    for statement in (Statement.BALANCE_SHEET, Statement.PROFIT_AND_LOSS):
        total = sum(
            (
                ln.amount_eur
                for ln in result.lines
                if ln.origin == "elimination" and ln.statement is statement
            ),
            Decimal(0),
        )
        assert abs(total) < CENT, f"eliminations desequilibrees sur {statement}"


# -------------------------------------------------------------------- etats
def test_balance_sheet_balances(cfg, result):
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    assets = bs.total("Total assets")
    liab = bs.total("Total liabilities & shareholders' equity")
    assert abs(assets - liab) < CENT


def test_assets_match_manual_computation(cfg, result):
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    expected = (
        Decimal(850_000)                    # MAGE SAS
        + Decimal(24_600_000) / JPY_EOM     # MAGE JAPON KK
        - Decimal(90_000)                   # elimination creance intragroupe
    )
    assert abs(bs.total("Total assets") - expected) < CENT


def test_pl_cascade_matches_manual_computation(cfg, result):
    pl = build_statement(cfg, result, Statement.PROFIT_AND_LOSS, level="summary")
    revenue = Decimal(1_550_000) + Decimal(62_000_000) / JPY_AVG - Decimal(300_000)
    opex = Decimal(765_000) + Decimal(12_000_000) / JPY_AVG
    assert abs(pl.total("Revenue") - revenue) < CENT
    # variation de stock : cloture 380 000 - ouverture 330 000
    assert abs(pl.total("Gross Profit/(Loss)") - (revenue + 50_000)) < CENT
    assert abs(
        pl.total("Total Net/(loss) Profit") - (revenue + 50_000 - opex - 3_000)
    ) < CENT


def test_assets_are_positive_and_liabilities_too(cfg, result):
    """Les etats de reference presentent actif ET passif en positif."""
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    assert bs.total("Total assets") > 0
    assert bs.total("Total liabilities & shareholders' equity") > 0
    assert bs.total("Total currents assets") > 0


def test_revenue_is_positive_and_costs_negative(cfg, result):
    pl = build_statement(cfg, result, Statement.PROFIT_AND_LOSS, level="detail")
    rows = {r.caption: r.value() for r in pl.rows if r.kind == "line"}
    assert rows["Shoe Sales"] > 0
    assert rows["Wages and salaries"] < 0
    assert rows["Rent"] < 0


def test_cost_centre_report_has_elimination_and_total_columns(cfg, result):
    rep = build_by_cost_centre(cfg, result, Statement.PROFIT_AND_LOSS)
    assert rep.columns[-2:] == ["ELIMINATION", "TOTAL"]


def test_unallocated_when_source_has_no_analytic_axis(result):
    """Aucun montant ne doit etre rattache a un centre de couts que la source
    ne designe pas."""
    assert any(d.code == "CC-NOT-PROVIDED" for d in result.diagnostics)
    assert all(
        ln.cost_centre in ("UNALLOCATED", "ELIMINATION")
        for ln in result.lines
    )


# ----------------------------------------------------------------- controles
def test_all_controls_pass_on_sample(cfg, result, workbooks):
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    pl = build_statement(cfg, result, Statement.PROFIT_AND_LOSS, level="summary")
    controls = run_controls(cfg, result, bs=bs, pl=pl, workbooks=workbooks)
    failed = [c for c in controls if not c.passed]
    assert not failed, [f"{c.code} {c.label}: {c.detail}" for c in failed]


def test_result_control_links_pl_to_balance_sheet(cfg, result, workbooks):
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    pl = build_statement(cfg, result, Statement.PROFIT_AND_LOSS, level="summary")
    c2 = next(
        c
        for c in run_controls(cfg, result, bs=bs, pl=pl, workbooks=workbooks)
        if c.code == "C2"
    )
    assert c2.passed
    assert c2.severity is Severity.ERROR


def test_missing_rate_is_reported_as_error(cfg, workbooks):
    """Une devise sans taux doit produire une ERREUR, pas un montant faux."""
    import copy

    from mageconso.engine import ConsolidationEngine

    broken = copy.deepcopy(cfg)
    broken.fx = {**cfg.fx, "rates": {}}
    res = ConsolidationEngine(broken).consolidate(workbooks)
    codes = {d.code for d in res.diagnostics}
    assert "FX-RATE-MISSING" in codes
    assert res.has_errors


# -------------------------------------------------------------- tracabilite
def test_every_consolidated_amount_has_an_audit_record(result):
    entity_lines = [ln for ln in result.lines if ln.origin == "entity"]
    entity_audit = [a for a in result.audit if a.origin == "entity"]
    assert len(entity_lines) == len(entity_audit)
    for a in entity_audit:
        assert a.source_file and a.source_sheet and a.source_row
        assert a.local_account and a.group_coa


def test_audit_reconciles_to_consolidated_total(result):
    for coa in {ln.group_coa for ln in result.lines}:
        from_lines = sum(
            (ln.amount_eur for ln in result.lines if ln.group_coa == coa), Decimal(0)
        )
        from_audit = sum(
            (a.amount_eur for a in result.audit if a.group_coa == coa), Decimal(0)
        )
        assert abs(from_lines - from_audit) < Decimal("0.0001"), coa
