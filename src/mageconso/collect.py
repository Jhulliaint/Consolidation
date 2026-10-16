"""Dossier de collecte des management accounts (chantier C-A).

Les scenarios Make deposent chaque piece jointe Excel recue des cabinets dans

    CORTHAY/CLOTURE MENSUELLES/<annee>/<mois de reception>/
        20260915-093012 - MAGE_JAPON_KK - Mage Japon report August 2026.xlsx

Le prefixe horodate (date de reception du courriel) et le code entite viennent
du scenario ; le reste est le nom d'origine de la piece jointe. Le mois du
sous-dossier est celui de la RECEPTION, pas la periode comptable : celle-ci est
toujours relue dans l'onglet Cover du classeur.

Ce module inventorie le dossier, identifie entite et periode de chaque fichier
et retient, pour chaque couple (entite, cloture), la version la plus recente.
Les versions anterieures sont conservees sur disque et signalees comme
remplacees (decision validee : tout garder, consolider la derniere, signaler).

    col = collect(cfg, "CLOTURE MENSUELLES/2026", closing="2026-08-31")
    out = run(cfg, col.paths, RunOptions(closing="2026-08-31"), workbooks=col.workbooks)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import AppConfig
from .engine import ConsolidationEngine
from .importers.excel import ManagementAccountsReader, SourceWorkbook
from .models import Diagnostic, Severity

EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
# "20260915-093012 - MAGE_JAPON_KK - nom d'origine.xlsx"
RENAMED_RE = re.compile(r"^(?P<base>.+) (?P<n>\d{1,3})$")
NAME_RE = re.compile(r"^(?P<ts>\d{8}-\d{6}) - (?P<entity>[A-Za-z0-9_]+) - (?P<original>.+)$")


@dataclass
class CollectedFile:
    path: Path
    received: datetime            # horodatage du nom, a defaut date du fichier
    entity_hint: str | None       # code entite pose par le scenario Make
    original_name: str
    workbook: SourceWorkbook | None = None
    entity: str | None = None
    closing: str | None = None
    status: str = "ignored"       # retained | replaced | duplicate | ignored
    reason: str = ""
    replaced_by: Path | None = None

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    @property
    def sort_key(self) -> tuple:
        # a horodatage egal (deux pieces jointes du meme courriel, ou suffixe
        # " 1" ajoute par OneDrive en cas de nom deja pris), le nom tranche de
        # facon reproductible et "x 1.xlsx" vient apres "x.xlsx"
        m = RENAMED_RE.match(self.path.stem)
        base, n = (m["base"], int(m["n"])) if m else (self.path.stem, 0)
        return (self.received, base, n, self.path.suffix)


@dataclass
class Collection:
    root: Path
    files: list[CollectedFile] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def retained(self) -> list[CollectedFile]:
        return [f for f in self.files if f.status == "retained"]

    @property
    def replaced(self) -> list[CollectedFile]:
        return [f for f in self.files if f.status == "replaced"]

    @property
    def duplicates(self) -> list[CollectedFile]:
        return [f for f in self.files if f.status == "duplicate"]

    @property
    def ignored(self) -> list[CollectedFile]:
        return [f for f in self.files if f.status == "ignored"]

    @property
    def paths(self) -> list[Path]:
        return [f.path for f in self.retained]

    @property
    def workbooks(self) -> list[SourceWorkbook]:
        return [f.workbook for f in self.retained if f.workbook is not None]

    def closings(self) -> list[str]:
        return sorted({f.closing for f in self.files if f.closing})


def parse_name(path: Path) -> tuple[datetime, str | None, str]:
    """(horodatage, code entite, nom d'origine) d'un fichier du dossier."""
    m = NAME_RE.match(path.stem)
    if m:
        try:
            ts = datetime.strptime(m["ts"], "%Y%m%d-%H%M%S")
            return ts, m["entity"].upper(), m["original"] + path.suffix
        except ValueError:
            pass
    # fichier depose a la main : la date de modification fait foi
    return datetime.fromtimestamp(path.stat().st_mtime), None, path.name


def scan(root: Path | str) -> list[CollectedFile]:
    """Fichiers Excel du dossier et de ses sous-dossiers (annee/mois)."""
    root = Path(root)
    found = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in EXCEL_SUFFIXES:
            continue
        if p.name.startswith(("~$", ".")):  # verrous Excel, fichiers caches
            continue
        ts, hint, original = parse_name(p)
        found.append(CollectedFile(path=p, received=ts, entity_hint=hint,
                                   original_name=original))
    return found


def collect(cfg: AppConfig, root: Path | str, closing: str | None = None) -> Collection:
    """Inventorie le dossier et retient la derniere version par entite et cloture.

    ``closing`` (ISO) restreint la selection a une cloture ; sans elle, chaque
    entite est representee par sa cloture la plus recente.
    """
    root = Path(root)
    col = Collection(root=root)
    if not root.is_dir():
        col.diagnostics.append(Diagnostic(
            "COLLECT-ROOT", Severity.ERROR,
            f"Dossier de collecte introuvable : {root}"))
        return col
    reader = ManagementAccountsReader(cfg)
    engine = ConsolidationEngine(cfg)

    for f in scan(root):
        col.files.append(f)
        try:
            wb = reader.read(f.path)
        except Exception as exc:  # piece jointe qui n'est pas un classeur lisible
            f.reason = f"illisible ({exc.__class__.__name__})"
            continue
        if not wb.lines:
            f.reason = "pas de balance (Trial balance) : pas un management accounts"
            continue
        cover = wb.entity_code or engine.resolve_entity(wb)
        if cover and f.entity_hint and cover != f.entity_hint:
            col.diagnostics.append(Diagnostic(
                "COLLECT-ENTITY-MISMATCH", Severity.WARNING,
                f"{f.path.name} : depose comme {f.entity_hint} mais l'onglet Cover "
                f"designe {cover}. L'entite du Cover est retenue.",
                entity=cover, source_file=f.path.name))
        entity = cover or (f.entity_hint if f.entity_hint in cfg.entities else None)
        if entity is None:
            f.reason = f"entite non reconnue (Cover : {wb.entity_name!r})"
            col.diagnostics.append(Diagnostic(
                "COLLECT-ENTITY", Severity.WARNING,
                f"{f.path.name} : entite non reconnue, fichier ecarte de la collecte.",
                source_file=f.path.name))
            continue
        if not wb.closing:
            f.reason = "periode illisible dans l'onglet Cover"
            col.diagnostics.append(Diagnostic(
                "COLLECT-PERIOD", Severity.WARNING,
                f"{f.path.name} : periode introuvable, fichier ecarte de la collecte.",
                entity=entity, source_file=f.path.name))
            continue
        wb.entity_code = entity
        f.workbook, f.entity, f.closing = wb, entity, wb.closing
        f.status = "candidate"

    candidates = [f for f in col.files if f.status == "candidate"]
    groups: dict[tuple[str, str], list[CollectedFile]] = {}
    for f in candidates:
        groups.setdefault((f.entity, f.closing), []).append(f)

    # cloture retenue par entite
    wanted: dict[str, str] = {}
    for entity, clo in groups:
        if closing:
            if clo == closing:
                wanted[entity] = clo
        elif clo > wanted.get(entity, ""):
            wanted[entity] = clo

    for (entity, clo), versions in sorted(groups.items()):
        versions.sort(key=lambda f: f.sort_key)
        if wanted.get(entity) != clo:
            for f in versions:
                f.status, f.reason = "ignored", f"autre cloture ({clo})"
            continue
        # meme contenu recu plusieurs fois (courriel en double, renvoi) : ce
        # n'est pas une version corrigee ; seule la premiere copie compte
        distinct: dict[str, CollectedFile] = {}
        for f in versions:
            first = distinct.setdefault(f.digest, f)
            if first is not f:
                f.status, f.replaced_by = "duplicate", first.path
                f.reason = f"copie identique de {first.path.name}"
        versions = sorted(distinct.values(), key=lambda f: f.sort_key)
        latest = versions[-1]
        latest.status = "retained"
        for f in versions[:-1]:
            f.status, f.replaced_by = "replaced", latest.path
            f.reason = f"remplace par {latest.path.name}"
        if len(versions) > 1:
            col.diagnostics.append(Diagnostic(
                "COLLECT-REPLACED", Severity.WARNING,
                f"{entity} au {clo} : {len(versions)} versions recues ; la plus recente "
                f"({latest.received:%d/%m/%Y %H:%M}, {latest.path.name}) est consolidee, "
                f"elle remplace " + ", ".join(f.path.name for f in versions[:-1]) + ".",
                entity=entity, source_file=latest.path.name))

    retained_closings = {f.closing for f in col.retained}
    if len(retained_closings) > 1:
        col.diagnostics.append(Diagnostic(
            "COLLECT-CLOSINGS", Severity.WARNING,
            "Les dernieres versions recues ne portent pas sur la meme cloture ("
            + ", ".join(f"{f.entity} {f.closing}" for f in col.retained)
            + "). Precisez la cloture a consolider."))
    if closing and not col.retained:
        col.diagnostics.append(Diagnostic(
            "COLLECT-EMPTY", Severity.WARNING,
            f"Aucun management accounts au {closing} dans {root}."))
    for code, ent in cfg.entities.items():
        if (ent.in_scope and ent.source == "email" and col.retained
                and code not in {f.entity for f in col.retained}):
            col.diagnostics.append(Diagnostic(
                "COLLECT-MISSING", Severity.WARNING,
                f"{code} : aucun management accounts recu pour la cloture retenue.",
                entity=code))
    return col

