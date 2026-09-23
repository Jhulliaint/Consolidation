# Consolidation Mage SAS

Application de consolidation des *management accounts* du groupe Mage. Elle
importe les remontées mensuelles des entités et produit automatiquement les deux
états de référence :

- **Mage SAS Consolidated accounts** — bilan et compte de résultat consolidés,
  niveaux détail et synthèse ;
- **Mage Consolidated accounts by cost center** — mêmes états ventilés par centre
  de coûts, avec colonnes `ELIMINATION` et `TOTAL`.

---

## ⚠️ À lire avant toute utilisation

**Les 13 fichiers 2025 de la demande n'ont pas pu être analysés.** Référencés par
des chemins `G:\CORTHAY\CLOTURE MENSUELLES\2025\` (lecteur réseau du poste), ils
étaient absents de l'environnement de travail. L'analyse a été menée sur les
**mêmes familles de fichiers Mage**, réellement accessibles via OneDrive et Google
Drive, mais d'exercices différents (2019, 2023, 2025 selon le fichier).

Conséquences :

1. Les règles, structures et mécanismes sont établis sur des fichiers Mage
   authentiques et, pour la cascade de résultat, **vérifiés numériquement** sur
   l'exercice 2025.
2. Le **rapprochement chiffré aux états 2025** n'a pas pu être fait. C'est la
   seule preuve de conformité qui compte, et elle manque.
3. Les taux de change 2025 de `config/fx.yaml` sont des **placeholders** à
   remplacer.

**Ne pas mettre en production avant le rapprochement** décrit dans
[`docs/10-rapport-rapprochement.md`](docs/10-rapport-rapprochement.md) §10.6.

---

## Démarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -e .

python samples/make_samples.py samples/data         # jeu de démonstration
mageconso ui                                        # interface graphique
```

Le navigateur s'ouvre : déposez les deux fichiers de `samples/data`, validez les
taux, consolidez. Tout reste sur le poste ; aucune donnée ne sort.

En ligne de commande :

```bash
mageconso consolidate "samples/data/*.xlsx" -o out/demo.xlsx --by-cost-centre
```

```
--- Synthese ---
  Revenue                         :        1 646 673 €
  Gross Profit/(Loss)             :        1 696 673 €
  Profit/(Loss) from operations   :          854 898 €
  Total Net/(loss) Profit         :          851 898 €
  Total assets                    :          917 359 €

  11/11 controles OK
```

Installation détaillée : [`docs/INSTALLATION.md`](docs/INSTALLATION.md).
Mode d'emploi : [`docs/UTILISATEUR.md`](docs/UTILISATEUR.md).
Nouveautés de la version 0.2 : [`CHANGELOG.md`](CHANGELOG.md).

## Ce que fait l'application

```
Management accounts (1 fichier par entité, devise locale)
      │  import piloté par en-tête · validation de structure
      ▼
Normalisation  →  mapping compte local → compte groupe
      │            (table du fichier source, puis MAPPING MAGE SAS)
      ▼
Ventilation analytique (sections 921S* → centres de coûts)
      │
      ▼
Conversion en EUR   bilan → taux de clôture · résultat → taux moyen
      │             capital → taux historique · écart → réserves
      ▼
Éliminations intragroupe (colonne ELIMINATION)
      │
      ▼
Agrégation → états consolidés → 9 contrôles → export Excel → journal d'audit
```

Chaque montant consolidé est rattaché à sa ligne source — fichier, onglet,
numéro de ligne, compte, taux appliqué. Dans l'interface, un clic sur un montant
affiche ces lignes ; en ligne de commande :

```bash
mageconso trace --journal out/audit.db --run 1 --account "Account Receivable"
```

## Fonctionnalités

| | |
|---|---|
| **Interface graphique locale** | dépôt des fichiers, taux, présentation, résultats et traçabilité au clic |
| **États** | bilan et compte de résultat (synthèse, détail), par entité avec éliminations, par centre de coûts, marge par famille, % du chiffre d'affaires |
| **Rapprochement** | comparaison ligne à ligne avec un classeur consolidé de référence (`--reference`) |
| **Taux** | fichier de taux pré-rempli, pré-contrôle des taux manquants, détection des taux inversés ou aberrants |
| **Mapping** | suggestions pour chaque compte non mappé, apprises des 1 267 libellés existants |
| **Contrôles** | 10 contrôles, dont l'équilibre du bilan, la cohérence résultat/bilan, l'exhaustivité du mapping et la complétude des états |
| **Paramétrage** | `mageconso check` vérifie la configuration avant une clôture |
| **Export Excel** | feuille *Synthèse* en tête, valeurs exactes, onglets de contrôle et piste d'audit |

## Principes de conception

**Aucune règle métier dans le code.** Périmètre, mappings, taux, éliminations,
structure des états et présentation vivent dans `config/`. Répondre à une question
métier revient à modifier une ligne de YAML.

**La présentation ne touche jamais au calcul.** Le moteur travaille en `Decimal` à
pleine précision ; échelle, arrondi, séparateurs, symbole monétaire et écriture
des négatifs s'appliquent au seul rendu. Vingt paramètres dans
`config/presentation.yaml`, dont quatre surchargeables en ligne de commande.

**Les hypothèses sont marquées.** Chaque règle porte son statut — `[FAIT]`
observé dans un fichier, `[DÉDUIT]` par recoupement, `[HYPOTHÈSE]` à confirmer —
au plus près de sa définition, avec un renvoi vers la question correspondante.

## Documentation

| Livrable | Document |
|---|---|
| 1. Inventaire des fichiers | [`docs/01-inventaire-fichiers.md`](docs/01-inventaire-fichiers.md) |
| 2. Analyse fonctionnelle et comptable | [`docs/02-analyse-fonctionnelle.md`](docs/02-analyse-fonctionnelle.md) |
| 3. Relations entre les fichiers | [`docs/03-relations-fichiers.md`](docs/03-relations-fichiers.md) |
| 4. Règles de consolidation reconstituées | [`docs/04-regles-consolidation.md`](docs/04-regles-consolidation.md) |
| 5. Anomalies et incertitudes | [`docs/05-anomalies-incertitudes.md`](docs/05-anomalies-incertitudes.md) |
| 6. **Questions de clarification** | [`docs/06-questions-clarification.md`](docs/06-questions-clarification.md) |
| 7. Architecture technique | [`docs/07-architecture.md`](docs/07-architecture.md) |
| 8. Modèle de données | [`docs/08-modele-donnees.md`](docs/08-modele-donnees.md) |
| 9. Plan de développement | [`docs/09-plan-developpement.md`](docs/09-plan-developpement.md) |
| 10. Rapport de rapprochement | [`docs/10-rapport-rapprochement.md`](docs/10-rapport-rapprochement.md) |
| 13. Installation | [`docs/INSTALLATION.md`](docs/INSTALLATION.md) |
| 14. Mode d'emploi | [`docs/UTILISATEUR.md`](docs/UTILISATEUR.md) |

Les règles de mapping (livrable 9) sont dans `config/mapping/` et
`config/coa/` ; le prototype (11) dans `src/` ; les tests (12) dans `tests/`.

## Périmètre reconstitué

10 entités consolidées, 7 devises, 25 centres de coûts, 156 comptes groupe.

| Entité | Devise | Entité | Devise |
|---|---|---|---|
| MAGE SAS *(mère)* | EUR | MAGE ASIA PACIFIC | HKD |
| SICCA SARL | EUR | MAGE JAPON KK | JPY |
| MAGE SHANGHAI | CNY | MAGE KOREA LIMITED | KRW |
| CORTHAY UK | GBP | MAGE DISTRIBUTORS SA | ZAR |
| VOLNEY UK | GBP | MAGE MIDDLE EAST | AED |
| CORTHAY MIDDLE EAST JV | AED | | |

## Tests

```bash
pip install -e ".[dev]" && python -m pytest -q
```

97 tests : lecture des sources, règles de change, éliminations, équilibre du
bilan, cohérence résultat/bilan, réconciliation du journal d'audit,
non-altération des montants par la présentation, scénarios d'incidents de
clôture (écart de réciprocité, compte non mappé, fichier en double, taux
inversé), rapprochement, et interface graphique (API et HTTP). Les états y sont
vérifiés contre un **calcul manuel indépendant**, pas contre une sortie
antérieure du programme.

## Limites connues

- Rapprochement aux états 2025 réels **non réalisé** (fichiers indisponibles).
- Consolidation d'**une clôture** par exécution ; les colonnes mensuelles des
  sources ne sont pas restituées en 12 colonnes.
- **Intégration globale à 100 %** appliquée à toutes les entités : mise en
  équivalence et intérêts minoritaires non implémentés (Q-2.3, Q-2.4).
- État par centre de coûts **non ventilé pour les filiales** : leurs management
  accounts ne portent pas d'axe analytique (Q-5.4).
- Tableau de flux de trésorerie, liasse fiscale et flux `PRI` hors périmètre.
