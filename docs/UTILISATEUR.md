# Documentation utilisateur

## 1. Les trois commandes

```bash
mageconso inspect      <fichiers>     # examiner un fichier source sans rien produire
mageconso consolidate  <fichiers>     # produire les états consolidés
mageconso trace        --account ...  # retrouver l'origine d'un montant
```

## 2. Examiner un fichier avant de consolider

Réflexe à avoir avant toute clôture : vérifier que l'application lit
correctement chaque fichier.

```bash
mageconso inspect "G:/CORTHAY/CLOTURE MENSUELLES/2025/MA - Mage Japon KK 2025.xlsx"
```

```
=== MA - Mage Japon KK 2025.xlsx ===
  entite lue      : 'MAGE JAPON KK'
  devise          : JPY
  exercice        : 2025
  periode         : 2025-01-01 -> 2025-12-31
  feuilles        : Cover, Mapping accounts, Group COA, Balance sheet, Trial balance
  feuilles masquees: (aucune)
  mapping interne : 88 correspondances
  plan groupe     : 157 comptes
  lignes de balance: 157
  somme algebrique: 0
```

Points à contrôler :

| Ligne | Ce qu'elle doit montrer |
|---|---|
| `entite lue` | le nom attendu — sinon l'entité ne sera pas reconnue |
| `devise` | la devise locale, non vide |
| `somme algebrique` | **0** — une balance déséquilibrée signale un problème de source |
| `feuilles masquees` | les feuilles `hidden` / `very hidden` sont listées, pas ignorées |

## 3. Produire les états consolidés

```bash
mageconso consolidate "G:/CORTHAY/CLOTURE MENSUELLES/2025/MA - *.xlsx" \
    --closing 2025-12-31 \
    --by-cost-centre \
    --journal out/audit-2025.db \
    -o out/consolide-2025.xlsx
```

| Option | Rôle |
|---|---|
| `--closing` | date de clôture, détermine le jeu de taux |
| `--by-cost-centre` | ajoute les états par centre de coûts |
| `--level detail\|summary` | niveau de finesse (défaut : `summary`, qui produit aussi le détail) |
| `--entity CODE` | force l'entité si la feuille `Cover` ne permet pas de la reconnaître |
| `--journal` | enregistre la piste d'audit (indispensable pour `trace`) |
| `--strict` | code retour non nul si un contrôle bloquant échoue (utile en tâche planifiée) |

### Le classeur produit

| Onglet | Contenu |
|---|---|
| `Consolidated BS` / `Consolidated PL` | états de synthèse |
| `Detailed BS` / `Detailed PL` | états ligne à ligne |
| `BS by cost center` / `PL by cost center` | avec `--by-cost-centre` |
| `Controls` | les 9 contrôles, en vert ou rouge, avec l'écart chiffré |
| `Diagnostics` | avertissements et erreurs |
| `Audit trail` | chaque montant relié à sa ligne source |

Les cellules contiennent la **valeur numérique** et un format d'affichage : les
montants restent réutilisables dans Excel.

## 4. Lire les contrôles

**Commencez toujours par l'onglet `Controls`.**

| Code | Contrôle | Si en échec |
|---|---|---|
| **C1** | Total actif = Total passif | Erreur de conversion ou balance source déséquilibrée. **Bloquant.** |
| **C2** | Résultat du P&L = résultat porté au bilan | Incohérence entre les deux états. **Bloquant.** |
| **C3** | Balance source équilibrée | Le fichier source est en cause, pas l'application. |
| **C4** | Éliminations équilibrées | Une élimination sans contrepartie. |
| **C5** | Mapping exhaustif | Des comptes sources sont **exclus** du consolidé. Voir `Diagnostics`. **Bloquant.** |
| **C6** | Centres de coûts connus | Un centre absent de `cost_centers.yaml`. |
| **C7** | Dates de clôture cohérentes | Des fichiers de périodes différentes ont été mélangés. |
| **C8** | Taux disponibles | Un taux manque : les lignes concernées sont **exclues**. **Bloquant.** |
| **C9** | Rapprochement au fichier de référence | Écart avec les états attendus. |

Un contrôle bloquant en échec signifie que **les états ne doivent pas être
diffusés**.

### Diagnostics les plus fréquents

| Code | Signification | À faire |
|---|---|---|
| `MAP-UNKNOWN-ACCOUNT` | Compte source non mappé, **exclu** du consolidé | Ajouter la correspondance dans le fichier source ou dans `config/mapping/` |
| `FX-RATE-MISSING` | Taux absent pour une devise | Compléter `config/fx.yaml` |
| `ENT-UNKNOWN` | Entité non reconnue | Utiliser `--entity`, ou corriger `Cover!A1` |
| `CC-NOT-PROVIDED` | Pas d'axe analytique dans la source | Normal pour les filiales aujourd'hui ; l'état par centre de coûts reste non ventilé pour elles |
| `ELIM-RECIPROCITY` | Écart entre les deux côtés d'un intragroupe | Écart de change ou décalage d'enregistrement : à justifier |
| `FX-CURRENCY-MISMATCH` | Devise du fichier ≠ devise paramétrée | Vérifier `Cover` ou `entities.yaml` |

## 5. Justifier un montant

C'est la réponse à « d'où viennent ces 268 029 € ? ».

```bash
mageconso trace --journal out/audit-2025.db --run 1 --account "Account Receivable"
```

```
Entite               Fichier                Onglet            Lig  Compte source          Montant  Dev     Taux              EUR
MAGE_SAS             MA - Mage SAS 2025.x   Trial balance       8  Account Receivable   260000.00  EUR        1        260000.00
MAGE_JAPON_KK        MA - Mage Japon KK.x   Trial balance       8  Account Receivable 15400000.00  JPY   156.33         98509.56
TOTAL                                                                                                                 358509.56
```

Chaque ligne donne le fichier, l'onglet, **le numéro de ligne**, le montant
d'origine, le taux appliqué et le montant consolidé. Le total se réconcilie avec
l'état.

Le journal étant une base SQLite, il est aussi interrogeable directement :

```sql
SELECT entity, SUM(CAST(amount_eur AS REAL))
FROM audit_lines WHERE run_id = 1 AND group_coa = 'Cash Bank'
GROUP BY entity;
```

## 6. Paramétrer la présentation

Tout se règle dans `config/presentation.yaml`. **Aucun de ces paramètres ne
modifie un montant consolidé** : le calcul se fait à pleine précision, la
présentation s'applique au rendu.

```yaml
scale: thousands            # units | thousands | millions
decimals: 1
rounding: ROUND_HALF_UP
decimal_separator: ","
thousands_separator: " "
currency_symbol: "€"
currency_position: suffix   # prefix | suffix | none
show_zeros: true
zero_display: "-"           # zero | dash | blank | libellé libre
negative_format: parentheses # minus | parentheses
percent:
  decimals: 1
  zero_display: blank
detail_level: summary       # summary | detail | both
period_order: chronological # chronological | reverse
locale: fr_FR
```

Effet sur un même montant de 1 234 567 € :

| Paramétrage | Rendu |
|---|---|
| défaut | `1 234 567 €` |
| `scale: thousands` | `1 235k €` |
| `scale: millions, decimals: 2` | `1,23M €` |
| `negative_format: minus` (sur −640 378) | `-640 378 €` |
| `negative_format: parentheses` | `(640 378) €` |
| `currency_position: prefix` | `€ 1 234 567` |

Quatre paramètres sont aussi surchargeables en ligne de commande, pour un tirage
ponctuel sans modifier le fichier :

```bash
mageconso consolidate "..." -o out/en-milliers.xlsx \
    --scale thousands --decimals 1 --negatives minus
```

## 7. Ajuster les règles métier

| Besoin | Fichier |
|---|---|
| Ajouter ou retirer une entité | `config/entities.yaml` |
| Saisir les taux d'une clôture | `config/fx.yaml` |
| Ajouter une correspondance de compte | `config/mapping/<entité>.csv` |
| Modifier un couple d'élimination | `config/eliminations.yaml` |
| Changer un regroupement de postes | `config/coa/statement_bs.yaml` / `_pl.yaml` |
| Déclarer un centre de coûts | `config/cost_centers.yaml` |

Les fichiers `.csv` s'ouvrent dans Excel. Les fichiers `.yaml` s'éditent dans un
éditeur de texte ; l'indentation est significative.

> Attention aux libellés : la clé de consolidation est le **libellé** du compte
> groupe, et certains comportent des fautes de frappe présentes dans les fichiers
> Mage (`Stock shoes subsisdairies`, `Mage Asia Pacfic`). **Ne les corrigez pas**
> d'un seul côté : la correspondance serait rompue et les comptes concernés
> disparaîtraient du consolidé (le contrôle C5 le signalerait).

## 8. Clôture mensuelle — marche à suivre

1. Rassembler les management accounts de la période.
2. `mageconso inspect` sur chaque fichier — vérifier entité, devise, somme = 0.
3. Saisir les taux de la clôture dans `config/fx.yaml`.
4. `mageconso consolidate` avec `--closing`, `--by-cost-centre` et `--journal`.
5. Ouvrir l'onglet `Controls` : **tout doit être au vert**.
6. Lire `Diagnostics` et traiter chaque `MAP-UNKNOWN-ACCOUNT`.
7. Rapprocher des états de la clôture précédente ; justifier les variations avec
   `trace`.
8. Archiver le classeur **et** le fichier `.db` : ensemble, ils permettent de
   rejouer et de justifier la clôture.
