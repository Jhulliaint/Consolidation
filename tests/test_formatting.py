"""Tests de la couche de presentation.

Point cle : changer un parametre de presentation ne doit JAMAIS changer un
montant consolide.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from mageconso.formatting import formatter
from mageconso.importers.excel import to_decimal
from mageconso.models import Statement
from mageconso.reports import build_statement

BASE = {
    "scale": "units",
    "decimals": 0,
    "rounding": "ROUND_HALF_UP",
    "decimal_separator": ",",
    "thousands_separator": " ",
    "currency_symbol": "€",
    "currency_position": "suffix",
    "currency_space": True,
    "show_zeros": True,
    "zero_display": "-",
    "negative_format": "parentheses",
    "scale_suffix": {"units": "", "thousands": "k", "millions": "M"},
    "percent": {"decimals": 1, "symbol": "%", "zero_display": "blank"},
    "locale": "fr_FR",
}


def test_thousands_separator_and_currency_suffix():
    assert formatter(BASE).format(Decimal("1234567")) == "1 234 567 €"


def test_negative_in_parentheses():
    assert formatter(BASE).format(Decimal("-640378")) == "(640 378) €"


def test_negative_with_minus():
    f = formatter(BASE, negative_format="minus")
    assert f.format(Decimal("-640378")) == "-640 378 €"


def test_zero_as_dash():
    assert formatter(BASE).format(Decimal("0")) == "-"


def test_zero_as_number_when_requested():
    f = formatter(BASE, zero_display="zero")
    assert f.format(Decimal("0")) == "0 €"


def test_blank_for_none():
    assert formatter(BASE, null_display="blank").format(None) == ""


def test_scale_thousands():
    f = formatter(BASE, scale="thousands", currency_position="none")
    assert f.format(Decimal("2587674")) == "2 588k"


def test_scale_millions_with_decimals():
    f = formatter(BASE, scale="millions", decimals=2, currency_position="none")
    assert f.format(Decimal("2587674")) == "2,59M"


def test_decimal_separator_is_configurable():
    f = formatter(BASE, decimals=2, decimal_separator=".", thousands_separator=",",
                  currency_position="prefix")
    assert f.format(Decimal("1234.5")) == "€ 1,234.50"


def test_rounding_mode_is_applied():
    up = formatter(BASE, decimals=0, rounding="ROUND_HALF_UP")
    down = formatter(BASE, decimals=0, rounding="ROUND_DOWN")
    assert up.format(Decimal("0.5"), ) == "1 €"
    assert down.format(Decimal("0.9")) == "-"  # 0 -> zero_display


def test_percent_formatting():
    f = formatter(BASE)
    assert f.format_percent(Decimal("0.5212")) == "52,1%"
    assert f.format_percent(Decimal("0")) == ""


def test_excel_number_format_includes_parentheses():
    fmt = formatter(BASE).excel_number_format()
    assert "(" in fmt and ")" in fmt


def test_period_label_locale():
    assert formatter(BASE).period_label(2025, 1) == "janv. 2025"
    assert formatter(BASE, locale="en_GB").period_label(2025, 1) == "Jan 2025"
    assert formatter(BASE).period_label(2025, None) == "FY2025"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1 234,56", Decimal("1234.56")),
        ("(1 234)", Decimal("-1234")),
        ("1,234.56", Decimal("1234.56")),
        ("-", None),
        ("", None),
        ("#DIV/0!", None),
        (1234.5, Decimal("1234.5")),
    ],
)
def test_to_decimal_handles_source_variants(raw, expected):
    assert to_decimal(raw) == expected


def test_presentation_never_changes_the_amounts(cfg, result):
    """Deux presentations radicalement differentes, memes montants calcules."""
    bs = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    reference = bs.total("Total assets")

    a = formatter(BASE)
    b = formatter(BASE, scale="millions", decimals=3, negative_format="minus",
                  thousands_separator=".", decimal_separator=",",
                  currency_position="prefix")
    assert a.format(reference) != b.format(reference)      # rendu different
    rebuilt = build_statement(cfg, result, Statement.BALANCE_SHEET, level="summary")
    assert rebuilt.total("Total assets") == reference       # montant identique
