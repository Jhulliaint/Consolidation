"""Couche de PRESENTATION.

Regle d'architecture : ce module ne connait que des ``Decimal`` deja calcules.
Il ne modifie jamais un montant consolide ; il produit uniquement une chaine
(ou un format de cellule Excel). Changer ``config/presentation.yaml`` ne peut
donc pas alterer les resultats.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any

SCALES = {"units": Decimal(1), "thousands": Decimal(1000), "millions": Decimal(1000000)}

MONTHS = {
    "fr_FR": ["janv.", "fevr.", "mars", "avr.", "mai", "juin", "juil.", "aout",
              "sept.", "oct.", "nov.", "dec."],
    "en_GB": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
              "Oct", "Nov", "Dec"],
}


@dataclass
class NumberFormatter:
    """Applique les reglages de presentation a une valeur numerique."""

    settings: dict[str, Any]

    # ------------------------------------------------------------ helpers
    def _get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    @property
    def scale_divisor(self) -> Decimal:
        return SCALES.get(str(self._get("scale", "units")), Decimal(1))

    @property
    def decimals(self) -> int:
        return int(self._get("decimals", 0))

    def quantize(self, value: Decimal) -> Decimal:
        """Mise a l'echelle + arrondi, pour l'AFFICHAGE uniquement."""
        with localcontext() as ctx:
            ctx.prec = 34
            scaled = Decimal(value) / self.scale_divisor
            exp = Decimal(1).scaleb(-self.decimals)
            return scaled.quantize(exp, rounding=str(self._get("rounding", "ROUND_HALF_UP")))

    # -------------------------------------------------------------- number
    def format(self, value: Decimal | None, *, is_total: bool = False) -> str:
        if value is None:
            return self._placeholder(str(self._get("null_display", "blank")))

        q = self.quantize(value)

        if q == 0:
            if not self._get("show_zeros", True):
                return self._placeholder(str(self._get("zero_display", "-")))
            zd = str(self._get("zero_display", "-"))
            if zd not in ("zero", "0"):
                return self._placeholder(zd)

        negative = q < 0
        digits = self._group(abs(q))
        if negative:
            # convention comptable : les parentheses encadrent le nombre,
            # le symbole monetaire reste a l'exterieur.
            if str(self._get("negative_format", "minus")) == "parentheses":
                return self._with_currency(f"({digits})")
            return self._with_currency(f"-{digits}")
        return self._with_currency(digits)

    def _placeholder(self, token: str) -> str:
        return {"blank": "", "dash": "-", "zero": "0"}.get(token, token)

    def _group(self, value: Decimal) -> str:
        txt = f"{value:.{self.decimals}f}"
        int_part, _, frac = txt.partition(".")
        sep = str(self._get("thousands_separator", " "))
        chunks = []
        while len(int_part) > 3:
            chunks.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        chunks.insert(0, int_part)
        out = sep.join(chunks)
        if self.decimals:
            out = f"{out}{self._get('decimal_separator', ',')}{frac}"
        return out

    def _with_currency(self, digits: str) -> str:
        scale_sfx = (self._get("scale_suffix") or {}).get(
            str(self._get("scale", "units")), ""
        )
        if scale_sfx:
            # "(1 234)" + "k" -> "(1 234k)"
            digits = (
                f"{digits[:-1]}{scale_sfx})" if digits.endswith(")")
                else f"{digits}{scale_sfx}"
            )
        pos = str(self._get("currency_position", "none"))
        sym = str(self._get("currency_symbol", ""))
        if pos == "none" or not sym:
            return digits
        gap = " " if self._get("currency_space", True) else ""
        return f"{sym}{gap}{digits}" if pos == "prefix" else f"{digits}{gap}{sym}"

    # ------------------------------------------------------------ percent
    def format_percent(self, value: Decimal | None) -> str:
        cfg = self._get("percent") or {}
        if value is None:
            return ""
        dec = int(cfg.get("decimals", 1))
        pct = (Decimal(value) * 100).quantize(
            Decimal(1).scaleb(-dec), rounding=str(self._get("rounding", "ROUND_HALF_UP"))
        )
        if pct == 0 and str(cfg.get("zero_display", "")) == "blank":
            return ""
        sep = str(self._get("decimal_separator", ","))
        txt = f"{pct:.{dec}f}".replace(".", sep)
        gap = " " if cfg.get("symbol_space") else ""
        return f"{txt}{gap}{cfg.get('symbol', '%')}"

    # ------------------------------------------------------- excel format
    def excel_number_format(self) -> str:
        """Format de nombre Excel equivalent aux reglages courants.

        Permet d'exporter la VALEUR brute (auditable dans Excel) tout en
        respectant la presentation demandee.
        """
        dec = "0" + ("." + "0" * self.decimals if self.decimals else "")
        thousands = "#," + "#" * 2 + dec if self._get("thousands_separator") else dec
        base = thousands if self._get("thousands_separator") else dec
        sym = str(self._get("currency_symbol", ""))
        pos = str(self._get("currency_position", "none"))
        if pos == "prefix" and sym:
            base = f'"{sym} "{base}'
        elif pos == "suffix" and sym:
            base = f'{base}" {sym}"'
        zero = base
        zd = str(self._get("zero_display", "-"))
        if zd == "dash" or zd == "-":
            zero = '"-"'
        elif zd == "blank":
            zero = '""'
        if str(self._get("negative_format", "minus")) == "parentheses":
            return f"{base};({base});{zero}"
        return f"{base};-{base};{zero}"

    # ---------------------------------------------------------- period label
    def period_label(self, year: int, month: int | None) -> str:
        if month is None:
            return f"FY{year}"
        names = MONTHS.get(str(self._get("locale", "fr_FR")), MONTHS["en_GB"])
        return f"{names[month - 1]} {year}"

    def order_periods(self, periods: list[Any]) -> list[Any]:
        rev = str(self._get("period_order", "chronological")) == "reverse"
        return sorted(periods, key=lambda p: (p.year, p.month or 0), reverse=rev)


def formatter(presentation: dict[str, Any], **overrides: Any) -> NumberFormatter:
    """Fabrique un formateur, avec surcharges ponctuelles (CLI, tests)."""
    merged = dict(presentation or {})
    merged.update({k: v for k, v in overrides.items() if v is not None})
    return NumberFormatter(merged)
