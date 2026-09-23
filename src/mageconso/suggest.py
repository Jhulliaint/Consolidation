"""Suggestions de mapping pour les comptes sources non reconnus.

Un compte non mappe est EXCLU du consolide : c'est l'incident le plus frequent
lors d'une cloture (un nouveau compte ouvert chez une filiale, une faute de
frappe corrigee d'un seul cote). Plutot que de laisser l'utilisateur chercher
le bon libelle parmi ~240 comptes groupe, on lui propose les plus proches.

Les suggestions sont des AIDES A LA SAISIE : elles ne sont jamais appliquees
automatiquement. Le choix reste a l'utilisateur, qui le reporte dans la table
de correspondance.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Sequence

from .config import norm

# mots vides frequents dans les libelles de comptes, sans pouvoir discriminant
_STOP = {"de", "du", "des", "la", "le", "les", "et", "a", "au", "aux", "sur",
         "the", "of", "and", "for", "to", "in", "from", "divers", "diverse",
         "autre", "autres", "other", "net"}

# Glossaire FR -> EN des mots de comptabilite les plus frequents. Le plan groupe
# est redige en anglais, les plans locaux (PCG) en francais : sans traduction,
# "Loyer entrepot" n'a aucune similarite avec "Rent". Aide a la SAISIE
# uniquement - aucune regle de mapping n'en decoule automatiquement.
_GLOSSARY = {
    "loyer": "rent", "location": "rent", "locat": "rent", "immobiliere": "rent",
    "salaire": "wage salarie", "appointement": "wage salarie",
    "remuneration": "wage salarie", "personnel": "staff wage",
    "interimaire": "temporay staff", "interim": "temporay staff",
    "charge": "charge", "frai": "charge fee expense", "cotisation": "contribution",
    "sociale": "employer contribution", "urssaf": "employer contribution",
    "conge": "vacation", "commission": "commission",
    "banque": "bank", "bancaire": "bank", "caisse": "cash", "espece": "cash",
    "carte": "credit card", "cb": "credit card",
    "honoraire": "fee professional", "comptable": "accountancy",
    "comptabilite": "accountancy", "commissaire": "auditor", "avocat": "legal",
    "conseil": "consultancy", "juridique": "legal",
    "achat": "purchase", "vente": "sale", "chiffre": "sale",
    "chaussure": "shoe", "soulier": "shoe", "ceinture": "belt", "sandale": "sandal",
    "mocassin": "loafer", "basket": "sneaker", "maroquinerie": "lg slg",
    "matiere": "material raw", "premiere": "raw", "marchandise": "stock purchase",
    "stock": "stock", "variation": "stock", "encours": "progress",
    "sous": "sub", "traitance": "subcontractor", "reparation": "repair",
    "entretien": "maintenance repair", "nettoyage": "cleaning",
    "assurance": "insurance", "publicite": "advertising",
    "annonce": "advertising", "salon": "event marketing",
    "evenement": "event marketing", "relation": "relation public",
    "presse": "public relation", "vitrine": "shop display",
    "deplacement": "travelling", "voyage": "travelling", "mission": "travelling",
    "reception": "entertainment", "restaurant": "entertainment",
    "transport": "freight", "port": "freight shipment", "douane": "duty freight",
    "telephone": "telephone", "internet": "internet",
    "electricite": "light heat", "energie": "light heat", "eau": "water",
    "fourniture": "stationery printing", "bureau": "office", "postal": "postage",
    "impot": "tax", "taxe": "tax", "tva": "vat", "interet": "interest",
    "emprunt": "loan", "pret": "loan", "amortissement": "depreciation",
    "dotation": "depreciation", "provision": "provision", "depreciation": "provision",
    "client": "receivable", "fournisseur": "payable", "creance": "receivable",
    "dette": "payable", "capital": "capital share", "reserve": "reserve",
    "report": "retained", "resultat": "profit loss", "change": "foreign currency",
    "cession": "sale asset", "abonnement": "subscription", "logiciel": "software",
    "materiel": "equipment", "outillage": "equipment", "agencement": "fixture",
    "boutique": "shop", "magasin": "shop", "filiale": "subsidiary",
    "groupe": "intercompany", "gestion": "management",
}


@dataclass
class UnmappedAccount:
    entity: str
    source_file: str
    local_account: str
    amount: object  # Decimal, en devise locale
    currency: str
    suggestions: list[tuple[str, float]] = field(default_factory=list)

    @property
    def best(self) -> str | None:
        return self.suggestions[0][0] if self.suggestions else None


def _latin_part(label: str) -> str:
    """Pour un libelle bilingue ("普通預金/Ordinary deposit"), garde la partie
    en alphabet latin, seule comparable au plan de comptes groupe."""
    if "/" in label:
        parts = [p for p in label.split("/") if re.search(r"[A-Za-z]", p)]
        if parts:
            return " ".join(parts)
    return label


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _tokens(label: str) -> list[set[str]]:
    """Un ensemble de formes acceptees par mot significatif : le mot lui-meme
    et ses traductions eventuelles."""
    out = []
    for w in re.findall(r"[a-z0-9]+", norm(label)):
        w = _stem(w)
        if w in _STOP or len(w) < 2:
            continue
        forms = {w} | {_stem(x) for x in _GLOSSARY.get(w, "").split()}
        out.append(forms)
    return out


def _hit(forms: set[str], other: list[set[str]]) -> bool:
    """Un mot est retrouve si l'une de ses formes apparait dans l'autre libelle,
    y compris sous forme abregee (PCG : "LOCAT", "IMMO") - prefixe >= 4."""
    for o in other:
        for a in forms:
            for b in o:
                if a == b or (min(len(a), len(b)) >= 4
                              and (a.startswith(b) or b.startswith(a))):
                    return True
    return False


def score(local: str, candidate: str) -> float:
    """Similarite entre 0 et 1.

    Composante principale : le F1 du recouvrement de mots (traductions et
    abreviations comprises), robuste a l'ordre des mots. Composante secondaire :
    la similarite de chaine, qui departage les ex aequo sans pouvoir, a elle
    seule, produire une suggestion (evite les faux amis de caracteres).
    """
    a, b = norm(_latin_part(local)), norm(candidate)
    if not a or not b:
        return 0.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    cov = sum(_hit(f, tb) for f in ta) / len(ta)
    prec = sum(_hit(f, ta) for f in tb) / len(tb)
    f1 = 2 * cov * prec / (cov + prec) if cov and prec else 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    return round(0.85 * f1 + 0.15 * seq, 3) if f1 else 0.0


def suggest(local: str, knowledge: Iterable[tuple[str, str] | str], n: int = 3,
            cutoff: float = 0.35) -> list[tuple[str, float]]:
    """Propose jusqu'a ``n`` comptes groupe pour un libelle local.

    ``knowledge`` contient des couples (libelle de reference, compte groupe) :
    les comptes groupe eux-memes, mais aussi tous les libelles locaux DEJA
    mappes (748 libelles francais de MAGE SAS, 204 de SICCA...). Un libelle
    francais comme "Loyer entrepot" trouve ainsi "Rent" via "LOYERS", alors
    qu'aucune similarite directe n'existe avec le libelle anglais.
    """
    best: dict[str, float] = {}
    for item in knowledge:
        ref, caption = (item, item) if isinstance(item, str) else item
        s = score(local, ref)
        if s > best.get(caption, 0.0):
            best[caption] = s
    ranked = sorted(best.items(), key=lambda x: x[1], reverse=True)
    return [(c, s) for c, s in ranked[:n] if s >= cutoff]


def write_mapping_template(path: str | Path,
                           unmapped: Sequence[UnmappedAccount]) -> Path:
    """CSV a completer puis a coller dans config/mapping/<entite>.csv.

    La colonne ``group_coa`` est pre-remplie avec la meilleure suggestion ;
    l'utilisateur la valide ou la corrige.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["entity", "local_account", "group_coa", "amount", "currency",
                    "suggestion_2", "suggestion_3", "source_file"])
        for u in unmapped:
            sugg = [s for s, _ in u.suggestions] + ["", "", ""]
            w.writerow([u.entity, u.local_account, sugg[0], str(u.amount),
                        u.currency, sugg[1], sugg[2], u.source_file])
    return out
