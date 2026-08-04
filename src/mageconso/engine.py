"""Moteur de consolidation.

Enchainement : normalisation -> mapping -> ventilation analytique -> conversion
de devises -> eliminations intragroupe -> agregation.

Chaque etape ecrit dans le journal d'audit, de sorte que tout montant consolide
soit rattachable a sa ligne source (fichier, onglet, ligne, compte, taux).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Sequence

from .config import AppConfig, norm
from .importers.excel import SourceWorkbook
from .models import (
    ZERO,
    AuditRecord,
    ConsolidatedLine,
    ConsolidationResult,
    Diagnostic,
    Period,
    RateType,
    Severity,
    Statement,
)


class ConsolidationEngine:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    # ------------------------------------------------------------------ API
    def consolidate(
        self,
        workbooks: Sequence[SourceWorkbook],
        *,
        period: Period | None = None,
        closing: str | None = None,
    ) -> ConsolidationResult:
        period = period or self._infer_period(workbooks)
        result = ConsolidationResult(period=period)

        for wb in workbooks:
            result.diagnostics.extend(wb.diagnostics)
            self._ingest(wb, result, closing=closing)

        if self.cfg.eliminations.get("enabled", True):
            self._eliminate(result)

        return result

    # ------------------------------------------------------------- ingestion
    def _ingest(
        self, wb: SourceWorkbook, result: ConsolidationResult, *, closing: str | None
    ) -> None:
        entity_code = wb.entity_code or self._resolve_entity(wb)
        if entity_code is None:
            result.diagnostics.append(
                Diagnostic(
                    code="ENT-UNKNOWN",
                    severity=Severity.ERROR,
                    message=(
                        f"Entite non identifiee pour '{wb.path.name}' "
                        f"(nom lu : {wb.entity_name!r}). Precisez --entity."
                    ),
                    source_file=wb.path.name,
                )
            )
            return

        ent = self.cfg.entity(entity_code)
        if ent is None:
            result.diagnostics.append(
                Diagnostic(
                    code="ENT-NOT-IN-SCOPE",
                    severity=Severity.ERROR,
                    message=f"Entite '{entity_code}' absente de config/entities.yaml.",
                    source_file=wb.path.name,
                )
            )
            return
        if not ent.in_scope:
            result.diagnostics.append(
                Diagnostic(
                    code="ENT-OUT-OF-SCOPE",
                    severity=Severity.WARNING,
                    message=f"Entite '{entity_code}' marquee hors perimetre : ignoree.",
                    entity=entity_code,
                    source_file=wb.path.name,
                )
            )
            return

        currency = wb.currency or ent.currency
        if wb.currency and ent.currency and wb.currency != ent.currency:
            result.diagnostics.append(
                Diagnostic(
                    code="FX-CURRENCY-MISMATCH",
                    severity=Severity.WARNING,
                    message=(
                        f"Devise du fichier ({wb.currency}) differente du "
                        f"parametrage ({ent.currency}) : {wb.currency} retenue."
                    ),
                    entity=entity_code,
                    source_file=wb.path.name,
                )
            )

        closing_key = closing or wb.closing or f"{result.period.year}-12-31"
        unknown_accounts: set[str] = set()

        for line in wb.lines:
            group = self._map_account(entity_code, line.local_account, wb)
            if group is None:
                unknown_accounts.add(line.local_account)
                continue

            statement = (
                wb.group_coa.get(norm(group))
                or self.cfg.statement_of(group)
                or Statement.PROFIT_AND_LOSS
            )
            cost_centre = self._cost_centre(entity_code, line.cost_centre)
            rate_type = self.cfg.rate_type_for(statement, group)
            rate = self.cfg.rate(currency, closing_key, rate_type)

            if rate is None:
                result.diagnostics.append(
                    Diagnostic(
                        code="FX-RATE-MISSING",
                        severity=Severity.ERROR,
                        message=(
                            f"Taux {rate_type.value} manquant pour {currency} "
                            f"au {closing_key} : ligne non convertie."
                        ),
                        entity=entity_code,
                        source_file=wb.path.name,
                        context=group,
                    )
                )
                continue

            amount_eur = line.amount if rate == 1 else (line.amount / rate)

            result.lines.append(
                ConsolidatedLine(
                    group_coa=group,
                    statement=statement,
                    period=line.period,
                    entity=entity_code,
                    cost_centre=cost_centre,
                    amount_local=line.amount,
                    currency=currency,
                    amount_eur=amount_eur,
                    rate=rate,
                    rate_type=rate_type,
                    origin="entity",
                    label=group,
                )
            )
            result.audit.append(
                AuditRecord(
                    entity=entity_code,
                    period=line.period.key,
                    source_file=line.source_file,
                    source_sheet=line.source_sheet,
                    source_row=line.source_row,
                    local_account=line.local_account,
                    group_coa=group,
                    cost_centre=cost_centre,
                    amount_source=line.amount,
                    currency=currency,
                    sign_flip=self._flips_sign(),
                    rate=rate,
                    rate_type=rate_type.value,
                    amount_eur=amount_eur,
                    transformations=(
                        f"map({line.local_account} -> {group}); "
                        f"fx({currency}/{rate_type.value}@{rate})"
                    ),
                )
            )

        for acct in sorted(unknown_accounts):
            result.diagnostics.append(
                Diagnostic(
                    code="MAP-UNKNOWN-ACCOUNT",
                    severity=Severity.WARNING,
                    message=f"Compte source non mappe, exclu du consolide : {acct!r}",
                    entity=entity_code,
                    source_file=wb.path.name,
                )
            )

        default_cc = str(self.cfg.allocation.get("default_cost_center", "UNALLOCATED"))
        if any(
            ln.entity == entity_code
            and ln.origin == "entity"
            and ln.cost_centre == default_cc
            for ln in result.lines
        ):
            result.diagnostics.append(
                Diagnostic(
                    code="CC-NOT-PROVIDED",
                    severity=Severity.WARNING,
                    message=(
                        "Le fichier source ne porte pas d'axe analytique : les "
                        f"montants sont ranges dans '{default_cc}'. L'etat par "
                        "centre de couts sera donc non ventile pour cette entite."
                    ),
                    entity=entity_code,
                    source_file=wb.path.name,
                )
            )

        self._finalise_entity(result, entity_code, wb.path.name)

    # ------------------------------------------------- resultat + ecart de conv.
    def _finalise_entity(
        self, result: ConsolidationResult, entity: str, source: str
    ) -> None:
        """Ajoute, pour une entite, les deux lignes que le bilan ne porte pas
        directement dans la balance source :

        1. "Profit/loss net income" : resultat de l'exercice reporte au bilan.
           REGLE DEDUITE du controle du classeur de reference
           (C202 = C198 - 'Detailed Consolidated BS'!C102), qui impose l'egalite
           entre le resultat du compte de resultat et cette ligne du bilan.

        2. l'ECART DE CONVERSION : le bilan est converti au taux de cloture et le
           compte de resultat au taux moyen ; la balance, equilibree en devise
           locale, ne l'est donc plus en euros. Le residu est porte sur la ligne
           parametree dans fx.yaml (par defaut "Consolidation reserves").
           REGLE DEDUITE - a valider (Q-6.4).
        """
        own = [
            ln
            for ln in result.lines
            if ln.entity == entity and ln.origin == "entity"
        ]
        if not own:
            return

        pl_total = sum(
            (ln.amount_eur for ln in own if ln.statement is Statement.PROFIT_AND_LOSS),
            ZERO,
        )
        result_line = "Profit/loss net income"
        already = any(
            norm(ln.group_coa) == norm(result_line)
            and ln.statement is Statement.BALANCE_SHEET
            for ln in own
        )
        if pl_total != ZERO and not already:
            self._push_derived(
                result, entity, result_line, pl_total, source,
                "resultat de l'exercice reporte au bilan", "derived_result",
            )

        residual = sum((ln.amount_eur for ln in own), ZERO)
        if already:
            residual = sum(
                (
                    ln.amount_eur
                    for ln in own
                    if not (
                        norm(ln.group_coa) == norm(result_line)
                        and ln.statement is Statement.BALANCE_SHEET
                    )
                ),
                ZERO,
            )
            residual += pl_total

        cta_line = self.cfg.fx.get("translation_difference_line")
        if cta_line and residual != ZERO:
            self._push_derived(
                result, entity, cta_line, -residual, source,
                "ecart de conversion (bilan au taux de cloture / resultat au "
                "taux moyen)", "fx_translation",
            )

    def _push_derived(
        self,
        result: ConsolidationResult,
        entity: str,
        caption: str,
        amount: Decimal,
        source: str,
        reason: str,
        origin: str,
    ) -> None:
        cc = self._cost_centre(entity, None)
        result.lines.append(
            ConsolidatedLine(
                group_coa=caption,
                statement=Statement.BALANCE_SHEET,
                period=result.period,
                entity=entity,
                cost_centre=cc,
                amount_local=amount,
                currency=self.cfg.reporting_currency,
                amount_eur=amount,
                rate=Decimal(1),
                rate_type=None,
                origin=origin,
                label=caption,
            )
        )
        result.audit.append(
            AuditRecord(
                entity=entity,
                period=result.period.key,
                source_file=source,
                source_sheet="(moteur)",
                source_row=None,
                local_account="(calcule)",
                group_coa=caption,
                cost_centre=cc,
                amount_source=amount,
                currency=self.cfg.reporting_currency,
                sign_flip=False,
                rate=Decimal(1),
                rate_type=None,
                amount_eur=amount,
                transformations=reason,
                origin=origin,
            )
        )

    def _flips_sign(self) -> bool:
        fmt = self.cfg.source_format
        src = (fmt.get("trial_balance_sheet") or {}).get("sign_convention")
        return str(src) != str(fmt.get("output_sign_convention"))

    # ---------------------------------------------------------------- mapping
    def _map_account(
        self, entity: str, local_account: str, wb: SourceWorkbook
    ) -> str | None:
        """Mapping compte local -> compte groupe.

        Priorite : (1) table du fichier source lui-meme (feuille 'Mapping
        accounts'), (2) table de config de l'entite, (3) identite si le libelle
        est deja un compte du plan groupe.
        """
        key = norm(local_account)
        if key in wb.account_map:
            return wb.account_map[key]
        mapped = self.cfg.group_coa_for(entity, local_account)
        if mapped:
            return mapped
        if key in self.cfg.group_coa:
            return local_account
        return None

    def _cost_centre(self, entity: str, raw: str | None) -> str:
        """Resout le centre de couts d'une ligne.

        Les codes de section analytique de MAGE SAS (921S*) sont traduits en
        libelle de centre de couts via ``cost_centers.yaml``.

        Si la source ne porte AUCUNE section analytique, la ligne est rangee
        dans le centre "non affecte" plutot que rattachee arbitrairement a un
        centre existant : un montant ne doit jamais apparaitre sous un centre de
        couts que la source ne designe pas.
        """
        if raw:
            section = self.cfg.analytic_sections.get(str(raw).strip())
            return section or str(raw).strip()
        return str(self.cfg.allocation.get("default_cost_center", "UNALLOCATED"))

    # ----------------------------------------------------------- eliminations
    def _eliminate(self, result: ConsolidationResult) -> None:
        """Genere la colonne ELIMINATION.

        Regle appliquee (DEDUITE, cf. docs/04) : pour chaque groupe de comptes
        reciproques, l'exposition nette du groupe est ramenee a zero. L'ecriture
        generee est equilibree et tracee ; tout residu est signale.
        """
        cfg = self.cfg.eliminations
        tolerance = Decimal(str(cfg.get("tolerance", 1)))
        totals = result.by_group_coa()

        groups: list[tuple[str, list[str], list[str]]] = []
        for pair in cfg.get("reciprocal_pairs") or []:
            groups.append(
                (
                    pair.get("name", "reciprocal"),
                    pair.get("receivable_lines") or [],
                    pair.get("payable_lines") or [],
                )
            )
        for pair in cfg.get("revenue_expense_pairs") or []:
            groups.append(
                (
                    pair.get("name", "flux"),
                    pair.get("revenue_lines") or [],
                    pair.get("expense_lines") or [],
                )
            )

        for name, side_a, side_b in groups:
            present_a = [c for c in side_a if self._present(totals, c)]
            present_b = [c for c in side_b if self._present(totals, c)]
            if not present_a and not present_b:
                continue

            sum_a = sum((totals.get(c, ZERO) for c in present_a), ZERO)
            sum_b = sum((totals.get(c, ZERO) for c in present_b), ZERO)
            net = sum_a + sum_b

            # Contre-ecriture : on annule chaque cote a 100 %.
            for caption in present_a + present_b:
                amount = totals.get(caption, ZERO)
                if amount == ZERO:
                    continue
                self._push_elimination(result, caption, -amount, name)

            if abs(net) > tolerance:
                result.diagnostics.append(
                    Diagnostic(
                        code="ELIM-RECIPROCITY",
                        severity=Severity.WARNING,
                        message=(
                            f"Ecart de reciprocite sur '{name}' : {net:.2f} EUR "
                            f"(tolerance {tolerance}). Les deux cotes ont ete "
                            "elimines integralement ; l'ecart reste a justifier."
                        ),
                        context=name,
                    )
                )

    @staticmethod
    def _present(totals: dict[str, Decimal], caption: str) -> bool:
        return norm(caption) in {norm(k) for k in totals}

    def _push_elimination(
        self, result: ConsolidationResult, caption: str, amount: Decimal, reason: str
    ) -> None:
        statement = self.cfg.statement_of(caption) or Statement.BALANCE_SHEET
        result.lines.append(
            ConsolidatedLine(
                group_coa=self._canonical(caption, result),
                statement=statement,
                period=result.period,
                entity="ELIMINATION",
                cost_centre="ELIMINATION",
                amount_local=amount,
                currency=self.cfg.reporting_currency,
                amount_eur=amount,
                rate=Decimal(1),
                rate_type=None,
                origin="elimination",
                label=caption,
            )
        )
        result.audit.append(
            AuditRecord(
                entity="ELIMINATION",
                period=result.period.key,
                source_file="(moteur)",
                source_sheet="eliminations.yaml",
                source_row=None,
                local_account=caption,
                group_coa=caption,
                cost_centre="ELIMINATION",
                amount_source=amount,
                currency=self.cfg.reporting_currency,
                sign_flip=False,
                rate=Decimal(1),
                rate_type=None,
                amount_eur=amount,
                transformations=f"elimination intragroupe: {reason}",
                origin="elimination",
            )
        )

    @staticmethod
    def _canonical(caption: str, result: ConsolidationResult) -> str:
        key = norm(caption)
        for ln in result.lines:
            if norm(ln.group_coa) == key:
                return ln.group_coa
        return caption

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _infer_period(workbooks: Iterable[SourceWorkbook]) -> Period:
        for wb in workbooks:
            if wb.period_end:
                return Period(wb.period_end.year, wb.period_end.month)
            if wb.fiscal_year:
                return Period(wb.fiscal_year, None)
        return Period(0, None)

    def _resolve_entity(self, wb: SourceWorkbook) -> str | None:
        """Rapproche le nom lu sur la feuille Cover d'un code d'entite."""
        if not wb.entity_name:
            return None
        target = norm(wb.entity_name)
        for code, ent in self.cfg.entities.items():
            for candidate in (ent.name, ent.legal_name, code.replace("_", " ")):
                if candidate and norm(candidate) == target:
                    return code
        for code, ent in self.cfg.entities.items():
            for candidate in (ent.name, ent.legal_name):
                if candidate and (
                    norm(candidate) in target or target in norm(candidate)
                ):
                    return code
        return None
