# 8. Modèle de données

## 8.1 Vue d'ensemble

```
        Entity ──────────┐               CostCentre
        (périmètre)      │               (axe analytique)
                         │                     │
                         ▼                     ▼
  fichier source ──► SourceLine ──mapping──► ConsolidatedLine ──► StatementReport
   (Excel)            (brut,              (compte groupe,          (état restitué)
                      devise locale)       EUR, taux appliqué)
                         │                     │
                         └──────► AuditRecord ◄┘
                                (source → montant final)
                                       │
                                  ControlResult · Diagnostic
```

## 8.2 Entités du modèle

### `Period`

Période comptable. `month = None` désigne une période annuelle / YTD.

| Champ | Type | Note |
|---|---|---|
| `year` | `int` | |
| `month` | `int \| None` | `None` = exercice complet |
| `key` | *dérivé* | `2025-12` ou `2025-FY` |
| `end_date` | *dérivé* | dernier jour de la période |

### `Entity` — périmètre de consolidation

| Champ | Type | Origine |
|---|---|---|
| `code` | `str` | clé technique (`MAGE_JAPON_KK`) |
| `name`, `legal_name` | `str` | libellés des en-têtes de colonnes |
| `currency` | `str` | `Cover!LOCAL CURRENCY` |
| `role` | `str` | `parent` / `subsidiary` / `joint_venture` |
| `method` | `str \| None` | `full` / `equity` — **hypothèse** (Q-2.3) |
| `ownership` | `Decimal \| None` | **inconnu** dans les fichiers (Q-2.3) |
| `mapping` | `str \| None` | chemin de la table de correspondance |
| `in_scope` | `bool` | `false` pour ARDILLAT / MAGE CHINA (A-14) |

### `CostCentre`

| Champ | Type | Note |
|---|---|---|
| `code` | `str` | `VOLNEY`, `AOYAMA`, … |
| `label` | `str` | libellé restitué |
| `entity` | `str \| None` | entité de rattachement (déduit) |

Les sections analytiques Sage (`921S*`) sont une table séparée
`analytic_sections : code → centre de coûts`, plusieurs codes pouvant viser le
même centre (A-02).

### `SourceLine` — ligne brute, avant transformation

Porte tout ce qui est nécessaire pour justifier un montant.

| Champ | Type | Note |
|---|---|---|
| `entity` | `str` | |
| `period` | `Period` | |
| `local_account` | `str` | libellé ou numéro, selon l'entité (I-3) |
| `local_label` | `str \| None` | |
| `amount` | `Decimal` | convention `DEBIT (+) / CREDIT (-)` |
| `currency` | `str` | devise locale |
| `cost_centre` | `str \| None` | section analytique si présente |
| `source_file` | `str` | **traçabilité** |
| `source_sheet` | `str` | **traçabilité** |
| `source_row` | `int \| None` | **traçabilité** |

### `ConsolidatedLine` — ligne consolidée

| Champ | Type | Note |
|---|---|---|
| `group_coa` | `str` | libellé du plan groupe — **clé de consolidation** |
| `statement` | `Statement` | `BALANCE_SHEET` / `PROFIT_AND_LOSS` |
| `entity`, `cost_centre` | `str` | axes de restitution |
| `amount_local` | `Decimal` | montant en devise locale |
| `currency` | `str` | |
| `amount_eur` | `Decimal` | montant converti |
| `rate` | `Decimal \| None` | taux appliqué |
| `rate_type` | `RateType \| None` | `eom` / `average` / `historical` |
| `origin` | `str` | `entity` · `elimination` · `derived_result` · `fx_translation` |

`origin` est essentiel : il distingue un montant **lu** d'un montant **calculé
par le moteur**, et alimente la colonne `ELIMINATION` des états.

### `AuditRecord` — journal d'audit

Couvre les treize informations exigées au §7 du cahier des charges :

| Exigence | Champ |
|---|---|
| fichier source | `source_file` |
| onglet source | `source_sheet` |
| entité | `entity` |
| période | `period` |
| compte source | `local_account` |
| compte consolidé | `group_coa` |
| centre de coûts | `cost_centre` |
| montant source | `amount_source` |
| transformations appliquées | `transformations` |
| reclassements | `transformations` (`map(x -> y)`) |
| éliminations | `origin = elimination` |
| taux de change utilisé | `rate`, `rate_type` |
| montant final consolidé | `amount_eur` |

Plus : `source_row` (ligne exacte) et `sign_flip` (inversion de convention).

### `ControlResult` et `Diagnostic`

`ControlResult` : `code`, `label`, `passed`, `severity`, `expected`, `actual`,
`difference` (dérivé), `detail`.
`Diagnostic` : `code`, `severity`, `message`, `entity`, `source_file`, `context`.

Les diagnostics sont **accumulés, jamais levés en exception** : un fichier
imparfait produit un état accompagné d'avertissements, plutôt qu'un échec sec.
Seul `--strict` transforme une erreur en code retour non nul.

## 8.3 Schéma du journal d'audit (SQLite)

```sql
runs         (run_id, started_at, period, config_dir, sources, n_lines, n_errors)
audit_lines  (run_id, entity, period, source_file, source_sheet, source_row,
              local_account, group_coa, cost_centre, amount_source, currency,
              sign_flip, rate, rate_type, amount_eur, transformations, origin)
controls     (run_id, code, label, passed, severity, expected, actual, detail)
diagnostics  (run_id, severity, code, entity, source_file, message, context)
```

Index sur `audit_lines(run_id)` et `audit_lines(group_coa)` : la question
« d'où viennent ces 268 029 € ? » est une requête indexée.

Les montants sont stockés en **texte** (`str(Decimal)`) et non en `REAL`, pour ne
pas réintroduire d'imprécision binaire dans l'archive.

## 8.4 Référentiels de configuration

| Fichier | Contenu | Volume |
|---|---|---|
| `config/entities.yaml` | périmètre, devises, méthodes | 13 entités |
| `config/cost_centers.yaml` | centres, sections `921S*`, règle d'affectation | 25 centres, 12 sections |
| `config/coa/statement_bs.yaml` | bilan : détail, synthèse, sous-totaux, signes | 74 lignes de détail |
| `config/coa/statement_pl.yaml` | résultat : détail, cascade, EBITA, familles de marge | 155 lignes de détail |
| `config/coa/group_coa.csv` | plan groupe + rattachement bilan/résultat | 156 postes |
| `config/mapping/mage_sas_accounts.csv` | compte PCG → libellé groupe | 748 comptes |
| `config/mapping/sicca_accounts.csv` | idem SICCA | 204 comptes |
| `config/mapping/mage_japon_kk_accounts.csv` | libellé local → libellé groupe | 87 comptes |
| `config/mapping/liasse_fiscale.csv` | compte → `CODE I/II/III` | 676 comptes |
| `config/fx.yaml` | taux EOM / moyen / historique, politique par poste | 7 devises |
| `config/eliminations.yaml` | couples réciproques, flux intragroupe | 2 + 13 groupes |
| `config/presentation.yaml` | 20 paramètres d'affichage | — |
| `config/source_format.yaml` | détection des onglets et en-têtes sources | — |

## 8.5 Normalisation des clés

Le rapprochement des libellés passe par `config.norm()` :

```
"Account Receivable  - subsidiary  Mage Japan"   (double espace, insécable)
        │  espaces insécables → espace, espaces multiples → un seul, minuscules
        ▼
"account receivable - subsidiary mage japan"
```

Le libellé **affiché** reste celui du fichier d'origine, fautes comprises (A-04).
Seule la clé de jointure est normalisée. Sans cela, une partie des comptes
resterait non mappée — et cette normalisation est indispensable, les fichiers Mage
contenant effectivement des doubles espaces (`Accum. Depreciation -office et
computer  equipment`).

## 8.6 Invariants

Le modèle garantit, et les tests vérifient :

1. `Σ(SourceLine.amount)` par entité = 0 (balance équilibrée) — contrôle C3.
2. Toute `ConsolidatedLine` d'origine `entity` a exactement un `AuditRecord`.
3. Pour chaque compte groupe, `Σ ConsolidatedLine.amount_eur` =
   `Σ AuditRecord.amount_eur`.
4. `Σ(éliminations)` = 0 par état — contrôle C4.
5. Total actif = Total passif après application des signes de présentation — C1.
6. Résultat du compte de résultat = ligne de résultat du bilan — C2.
7. Aucun montant n'est rattaché à un centre de coûts que la source ne désigne
   pas (à défaut : `UNALLOCATED` et avertissement).
