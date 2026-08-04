"""Chargement du parametrage.

Toutes les regles metier (perimetre, mapping, taux, eliminations, presentation)
vivent dans ``config/`` : aucune n'est codee en dur dans le moteur.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from .models import CostCentre, Entity, RateType, Statement

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def norm(caption: str | None) -> str:
    """Cle de rapprochement d'un libelle de compte groupe.

    Les fichiers Mage contiennent des espaces surnumeraires et des doubles
    espaces ("Account Receivable  - subsidiary"), ainsi que des variations de
    casse. La comparaison se fait donc sur une forme normalisee, sans jamais
    modifier le libelle affiche.
    """
    if caption is None:
        return ""
    return " ".join(str(caption).replace(" ", " ").split()).strip().lower()


@dataclass
class StatementStructure:
    """Structure d'un etat : lignes de detail, totaux, niveau synthese."""

    statement: Statement
    detail_sections: list[dict[str, Any]] = field(default_factory=list)
    summary_sections: list[dict[str, Any]] = field(default_factory=list)
    subtotals: dict[str, list[str]] = field(default_factory=dict)
    cascade: list[dict[str, Any]] = field(default_factory=list)
    ebita: dict[str, Any] = field(default_factory=dict)
    margin_families: dict[str, Any] = field(default_factory=dict)

    def detail_lines(self) -> list[str]:
        out: list[str] = []
        for sec in self.detail_sections:
            out.extend(sec.get("lines") or [])
        return out

    def section_of(self, line: str) -> str | None:
        key = norm(line)
        for sec in self.detail_sections:
            for ln in sec.get("lines") or []:
                if norm(ln) == key:
                    return sec.get("section")
        return None


@dataclass
class AppConfig:
    config_dir: Path
    reporting_currency: str
    entities: dict[str, Entity]
    cost_centres: dict[str, CostCentre]
    analytic_sections: dict[str, str]
    allocation: dict[str, Any]
    technical_columns: list[str]
    bs: StatementStructure
    pl: StatementStructure
    fx: dict[str, Any]
    eliminations: dict[str, Any]
    presentation: dict[str, Any]
    source_format: dict[str, Any]
    # mapping compte local -> compte groupe, par entite
    account_maps: dict[str, dict[str, str]] = field(default_factory=dict)
    group_coa: dict[str, Statement] = field(default_factory=dict)

    # ------------------------------------------------------------------ FX
    def rate(
        self, currency: str, closing: str, rate_type: RateType
    ) -> Decimal | None:
        """Taux applicable. ``closing`` est une date ISO (ex. '2025-12-31')."""
        if currency == self.reporting_currency:
            return Decimal("1")
        if rate_type is RateType.HISTORICAL:
            return _dec((self.fx.get("historical") or {}).get(currency))
        table = (self.fx.get("rates") or {}).get(closing) or {}
        return _dec((table.get(rate_type.value) or {}).get(currency))

    def rate_type_for(self, statement: Statement, group_coa: str) -> RateType:
        policy = self.fx.get("rate_policy") or {}
        hist = {norm(x) for x in (self.fx.get("historical_lines") or [])}
        if statement is Statement.BALANCE_SHEET and norm(group_coa) in hist:
            return RateType.HISTORICAL
        return RateType(policy.get(statement.value, "eom"))

    # -------------------------------------------------------------- mapping
    def group_coa_for(self, entity: str, local_account: str) -> str | None:
        table = self.account_maps.get(entity) or {}
        return table.get(norm(local_account))

    def statement_of(self, group_coa: str) -> Statement | None:
        return self.group_coa.get(norm(group_coa))

    def entity(self, code: str) -> Entity | None:
        return self.entities.get(code)

    def structure(self, statement: Statement) -> StatementStructure:
        return self.bs if statement is Statement.BALANCE_SHEET else self.pl


def _load_statement(path: Path) -> StatementStructure:
    raw = _yaml(path)
    return StatementStructure(
        statement=Statement(raw["statement"]),
        detail_sections=raw.get("detail") or [],
        summary_sections=raw.get("summary") or [],
        subtotals=raw.get("subtotals") or {},
        cascade=raw.get("cascade") or [],
        ebita=raw.get("ebita") or {},
        margin_families=raw.get("margin_families") or {},
    )


def _load_account_map(path: Path) -> dict[str, str]:
    """Lit un CSV de mapping. La colonne cle peut etre le numero de compte ou
    le libelle local, selon l'entite (FAIT OBSERVE : Mage Japon KK n'a pas de
    numero de compte, seulement un libelle bilingue)."""
    out: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            target = (row.get("group_coa") or "").strip()
            if not target:
                continue
            for key_field in ("local_account", "local_label"):
                key = (row.get(key_field) or "").strip()
                if key:
                    out.setdefault(norm(key), target)
    return out


def load_config(config_dir: str | Path | None = None) -> AppConfig:
    cdir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    ents_raw = _yaml(cdir / "entities.yaml")
    cc_raw = _yaml(cdir / "cost_centers.yaml")

    entities: dict[str, Entity] = {}
    for e in ents_raw.get("entities") or []:
        entities[e["code"]] = Entity(
            code=e["code"],
            name=e.get("name") or e["code"],
            currency=e.get("currency") or "EUR",
            role=e.get("role") or "subsidiary",
            method=e.get("method"),
            ownership=_dec(e.get("ownership")),
            country=e.get("country"),
            legal_name=e.get("legal_name"),
            mapping=e.get("mapping"),
            in_scope=bool(e.get("in_scope", True)),
        )

    cost_centres = {
        c["code"]: CostCentre(
            code=c["code"], label=c.get("label") or c["code"], entity=c.get("entity")
        )
        for c in cc_raw.get("cost_centers") or []
    }

    bs = _load_statement(cdir / "coa" / "statement_bs.yaml")
    pl = _load_statement(cdir / "coa" / "statement_pl.yaml")

    # plan de comptes groupe : deduit de la structure des deux etats, complete
    # par le referentiel group_coa.csv si present.
    group_coa: dict[str, Statement] = {}
    for line in bs.detail_lines():
        group_coa[norm(line)] = Statement.BALANCE_SHEET
    for line in pl.detail_lines():
        group_coa.setdefault(norm(line), Statement.PROFIT_AND_LOSS)
    coa_csv = cdir / "coa" / "group_coa.csv"
    if coa_csv.exists():
        with coa_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                cap = norm(row.get("group_coa"))
                if cap and cap not in group_coa:
                    group_coa[cap] = (
                        Statement.BALANCE_SHEET
                        if (row.get("statement") or "").upper().startswith("BALANCE")
                        else Statement.PROFIT_AND_LOSS
                    )

    account_maps: dict[str, dict[str, str]] = {}
    for code, ent in entities.items():
        if ent.mapping:
            p = cdir / ent.mapping
            if p.exists():
                account_maps[code] = _load_account_map(p)

    return AppConfig(
        config_dir=cdir,
        reporting_currency=ents_raw.get("reporting_currency") or "EUR",
        entities=entities,
        cost_centres=cost_centres,
        analytic_sections={
            str(k): v for k, v in (cc_raw.get("analytic_sections") or {}).items()
        },
        allocation=cc_raw.get("allocation") or {},
        technical_columns=cc_raw.get("technical_columns") or [],
        bs=bs,
        pl=pl,
        fx=_yaml(cdir / "fx.yaml"),
        eliminations=_yaml(cdir / "eliminations.yaml"),
        presentation=_yaml(cdir / "presentation.yaml"),
        source_format=_yaml(cdir / "source_format.yaml"),
        account_maps=account_maps,
        group_coa=group_coa,
    )
