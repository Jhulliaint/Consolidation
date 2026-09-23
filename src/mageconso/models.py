"""Modele de donnees du moteur de consolidation.

Toutes les valeurs monetaires sont des ``Decimal`` : aucun calcul n'est fait en
binary float, afin que les rapprochements au centime soient reproductibles.

Convention de signe interne : DEBIT (+) / CREDIT (-), celle des balances
sources ("Trial balance" des management accounts). Le signe de PRESENTATION
depend de la section restituee (actif en debit positif, passif / capitaux
propres / compte de resultat en credit positif) et est applique uniquement a la
restitution, via la cle ``sign`` de ``config/coa/statement_*.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Iterable

ZERO = Decimal("0")


def _norm_caption(caption: str | None) -> str:
    """Meme normalisation que config.norm (dupliquee pour eviter un import
    circulaire) : espaces insecables et multiples, casse."""
    if caption is None:
        return ""
    return " ".join(str(caption).replace("\xa0", " ").split()).lower()


class Statement(str, Enum):
    BALANCE_SHEET = "BALANCE_SHEET"
    PROFIT_AND_LOSS = "PROFIT_AND_LOSS"


class RateType(str, Enum):
    EOM = "eom"
    AVERAGE = "average"
    HISTORICAL = "historical"


class SignConvention(str, Enum):
    DEBIT_PLUS_CREDIT_MINUS = "DEBIT_PLUS_CREDIT_MINUS"
    DEBIT_MINUS_CREDIT_PLUS = "DEBIT_MINUS_CREDIT_PLUS"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Period:
    """Periode comptable. ``month`` a None pour une periode annuelle/YTD."""

    year: int
    month: int | None = None

    @property
    def key(self) -> str:
        return f"{self.year}-{self.month:02d}" if self.month else f"{self.year}-FY"

    @property
    def end_date(self) -> date:
        """Dernier jour de la periode (31/12 pour une periode annuelle)."""
        if self.month is None or self.month == 12:
            return date(self.year, 12, 31)
        return date(self.year, self.month + 1, 1) - timedelta(days=1)

    def __str__(self) -> str:  # pragma: no cover - affichage
        return self.key


@dataclass
class Entity:
    code: str
    name: str
    currency: str
    role: str = "subsidiary"
    method: str | None = "full"
    ownership: Decimal | None = None
    country: str | None = None
    legal_name: str | None = None
    mapping: str | None = None
    in_scope: bool = True


@dataclass
class CostCentre:
    code: str
    label: str
    entity: str | None = None


@dataclass
class SourceLine:
    """Une ligne telle qu'elle a ete lue dans un fichier source, avant mapping.

    Conserve tout ce qu'il faut pour justifier un montant consolide
    (exigence de tracabilite, section 7 du cahier des charges).
    """

    entity: str
    period: Period
    local_account: str
    amount: Decimal
    currency: str
    source_file: str
    source_sheet: str
    source_row: int | None = None
    local_label: str | None = None
    cost_centre: str | None = None
    statement: Statement | None = None


@dataclass
class ConsolidatedLine:
    """Un montant consolide, rattache a son compte groupe."""

    group_coa: str
    statement: Statement
    period: Period
    entity: str
    cost_centre: str
    amount_local: Decimal
    currency: str
    amount_eur: Decimal
    rate: Decimal | None = None
    rate_type: RateType | None = None
    origin: str = "entity"  # entity | elimination | adjustment
    label: str | None = None


@dataclass
class AuditRecord:
    """Une ligne du journal d'audit : source -> montant consolide."""

    entity: str
    period: str
    source_file: str
    source_sheet: str
    source_row: int | None
    local_account: str
    group_coa: str
    cost_centre: str
    amount_source: Decimal
    currency: str
    sign_flip: bool
    rate: Decimal | None
    rate_type: str | None
    amount_eur: Decimal
    transformations: str = ""
    origin: str = "entity"


@dataclass
class ControlResult:
    code: str
    label: str
    passed: bool
    severity: Severity = Severity.ERROR
    expected: Decimal | None = None
    actual: Decimal | None = None
    detail: str = ""

    @property
    def difference(self) -> Decimal | None:
        if self.expected is None or self.actual is None:
            return None
        return self.actual - self.expected


@dataclass
class Diagnostic:
    """Erreur ou avertissement non bloquant remonte a l'utilisateur."""

    code: str
    severity: Severity
    message: str
    entity: str | None = None
    source_file: str | None = None
    context: str = ""


@dataclass
class ConsolidationResult:
    """Sortie complete du moteur."""

    period: Period
    lines: list[ConsolidatedLine] = field(default_factory=list)
    audit: list[AuditRecord] = field(default_factory=list)
    controls: list[ControlResult] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    # comptes sources exclus faute de mapping (suggest.UnmappedAccount)
    unmapped: list = field(default_factory=list)
    # entites effectivement integrees, dans l'ordre de lecture
    entity_codes: list[str] = field(default_factory=list)

    # -- agregations -------------------------------------------------------
    def total(
        self,
        group_coa: str,
        *,
        entity: str | None = None,
        cost_centre: str | None = None,
        origin: str | None = None,
    ) -> Decimal:
        key = _norm_caption(group_coa)
        return sum(
            (
                ln.amount_eur
                for ln in self.lines
                if _norm_caption(ln.group_coa) == key
                and (entity is None or ln.entity == entity)
                and (cost_centre is None or ln.cost_centre == cost_centre)
                and (origin is None or ln.origin == origin)
            ),
            ZERO,
        )

    def by_group_coa(self, statement: Statement | None = None) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for ln in self.lines:
            if statement and ln.statement != statement:
                continue
            out[ln.group_coa] = out.get(ln.group_coa, ZERO) + ln.amount_eur
        return out

    def entities(self) -> list[str]:
        seen: list[str] = []
        for ln in self.lines:
            if ln.entity not in seen:
                seen.append(ln.entity)
        return seen

    def cost_centres(self) -> list[str]:
        seen: list[str] = []
        for ln in self.lines:
            if ln.cost_centre not in seen:
                seen.append(ln.cost_centre)
        return seen

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.diagnostics) or any(
            not c.passed and c.severity is Severity.ERROR for c in self.controls
        )


def sum_amounts(values: Iterable[Decimal]) -> Decimal:
    return sum(values, ZERO)


def eur(value: Decimal | None, decimals: int = 2) -> str:
    """Montant lisible pour les MESSAGES (diagnostics, controles) : "-40 000,00".

    Ne sert jamais au calcul ni aux etats, qui passent par formatting.py.
    """
    if value is None:
        return ""
    value = Decimal(value)
    if abs(value) < Decimal(1).scaleb(-decimals) / 2:
        value = Decimal(0)  # pas de "-0,00"
    txt = f"{value:,.{decimals}f}"
    return txt.replace(",", " ").replace(".", ",")
