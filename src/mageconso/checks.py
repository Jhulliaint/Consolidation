"""Verification du parametrage (commande ``mageconso check``).

Le parametrage porte toutes les regles metier : une faute de frappe dans un
libelle y est aussi grave qu'un bug. Ces verifications s'executent sans aucun
fichier source et detectent les incoherences AVANT une cloture.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass

from .config import AppConfig, norm
from .models import Severity


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str


def check_config(cfg: AppConfig, closing: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    presented = {norm(x) for x in cfg.bs.detail_lines() + cfg.pl.detail_lines()}
    known = set(cfg.group_coa)

    # 1. structures des etats : references internes
    for struct in (cfg.bs, cfg.pl):
        detail = {norm(x) for x in struct.detail_lines()}
        name = struct.statement.value
        for sec in struct.summary_sections:
            for item in sec.get("lines") or []:
                for src in item.get("from") or []:
                    if norm(src) not in detail:
                        out.append(Finding(Severity.ERROR, "STRUCT-ORPHAN",
                                           f"{name} : '{item['caption']}' agrege "
                                           f"'{src}', absent du niveau detail."))
        steps = set()
        totals = {norm(sec.get("total") or "") for sec in struct.detail_sections}
        for step in struct.cascade:
            for part in step.get("sum_of") or []:
                if part not in steps:
                    out.append(Finding(Severity.ERROR, "CASCADE-ORDER",
                                       f"{name} : '{step['caption']}' utilise '{part}' "
                                       "avant qu'il soit calcule."))
            if "from_total" in step and norm(step["from_total"]) not in totals:
                out.append(Finding(Severity.ERROR, "CASCADE-TOTAL",
                                   f"{name} : total '{step['from_total']}' introuvable."))
            if "from_line" in step and norm(step["from_line"]) not in detail:
                out.append(Finding(Severity.ERROR, "CASCADE-LINE",
                                   f"{name} : ligne '{step['from_line']}' introuvable."))
            steps.add(step["caption"])
        seen: dict[str, int] = {}
        for line in struct.detail_lines():
            seen[norm(line)] = seen.get(norm(line), 0) + 1
        for line, n in seen.items():
            if n > 1:
                out.append(Finding(Severity.ERROR, "STRUCT-DUPLICATE",
                                   f"{name} : '{line}' apparait {n} fois (double comptage)."))

    for fam, spec in (cfg.pl.margin_families or {}).items():
        for cap in (spec.get("revenue") or []) + (spec.get("cost") or []):
            if norm(cap) not in presented:
                out.append(Finding(Severity.WARNING, "MARGIN-LINE",
                                   f"Famille {fam} : '{cap}' n'est pas une ligne du P&L."))

    # 2. tables de correspondance : cibles connues et presentees
    for code, ent in cfg.entities.items():
        if not ent.mapping:
            continue
        path = cfg.config_dir / ent.mapping
        if not path.exists():
            out.append(Finding(Severity.ERROR, "MAP-FILE",
                               f"{code} : table de correspondance introuvable ({ent.mapping})."))
            continue
        unknown, hidden = set(), set()
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                target = (row.get("group_coa") or "").strip()
                if not target:
                    continue
                if norm(target) not in known:
                    unknown.add(target)
                elif norm(target) not in presented:
                    hidden.add(target)
        for t in sorted(unknown):
            out.append(Finding(Severity.WARNING, "MAP-TARGET-UNKNOWN",
                               f"{code} : cible '{t}' absente du plan de comptes groupe."))
        if hidden:
            out.append(Finding(
                Severity.INFO, "MAP-TARGET-HIDDEN",
                f"{code} : {len(hidden)} compte(s) groupe cibles ne figurent sur aucune "
                "ligne des etats (ex. " + ", ".join(sorted(hidden)[:3]) + "). Normal pour "
                "des comptes intragroupe elimines ; sinon le controle C10 les signalera."))

    # 3. eliminations : libelles existants
    elim = cfg.eliminations or {}
    for group in (elim.get("reciprocal_pairs") or []) + (elim.get("revenue_expense_pairs") or []):
        caps = [c for k in ("receivable_lines", "payable_lines", "revenue_lines",
                            "expense_lines") for c in (group.get(k) or [])]
        for cap in caps:
            if norm(cap) not in known:
                out.append(Finding(Severity.WARNING, "ELIM-CAPTION",
                                   f"Elimination '{group.get('name')}' : '{cap}' "
                                   "absent du plan groupe (jamais elimine)."))
    for stmt, cap in (elim.get("residual_lines") or {}).items():
        if norm(cap) not in presented:
            out.append(Finding(Severity.ERROR, "ELIM-RESIDUAL",
                               f"Ligne de residu {stmt} '{cap}' absente des etats."))

    # 4. change
    cta = (cfg.fx or {}).get("translation_difference_line")
    if cta and norm(cta) not in presented:
        out.append(Finding(Severity.ERROR, "FX-CTA-LINE",
                           f"Ligne d'ecart de conversion '{cta}' absente du bilan."))
    currencies = {e.currency for e in cfg.entities.values()
                  if e.in_scope and e.currency != cfg.reporting_currency}
    if closing:
        table = ((cfg.fx or {}).get("rates") or {}).get(closing) or {}
        for cur in sorted(currencies):
            miss = [k for k in ("eom", "average") if cur not in (table.get(k) or {})]
            if miss:
                out.append(Finding(Severity.WARNING, "FX-RATE-MISSING",
                                   f"{cur} : taux {'/'.join(miss)} absent(s) au {closing}."))
    for cur in sorted(currencies):
        if cur not in ((cfg.fx or {}).get("historical") or {}):
            out.append(Finding(Severity.WARNING, "FX-HISTORICAL-MISSING",
                               f"{cur} : pas de taux historique (capital)."))

    # 5. perimetre
    for code, ent in cfg.entities.items():
        if ent.in_scope and ent.method not in ("full", None):
            out.append(Finding(Severity.WARNING, "ENT-METHOD",
                               f"{code} : methode '{ent.method}' non implementee - "
                               "integration globale appliquee (Q-2.3)."))
    return out
