# 1. Inventaire des fichiers

## 1.1 Avertissement important sur les pièces jointes

**Les 13 fichiers cités dans la demande n'ont pas pu être ouverts.** Ils sont
référencés par des chemins Windows (`G:\CORTHAY\CLOTURE MENSUELLES\2025\…`)
qui correspondent à un lecteur réseau mappé sur votre poste. La session de
travail est un conteneur Linux isolé : le répertoire de pièces jointes
(`/mnt/attach`) était **vide**, et aucun de ces fichiers n'existe sur le disque.

J'ai donc reconstitué l'analyse à partir des **mêmes familles de fichiers,
réellement accessibles** via vos connecteurs Microsoft 365 (OneDrive
`office@corthay.com`) et Google Drive. Un indice confirme que ces deux
emplacements sont bien le même référentiel : une formule du classeur consolidé
2023 pointe vers

```
='https://mage3-my.sharepoint.com/CORTHAY/CLOTURE MENSUELLES/2023/
   [Cashflow statements Mage SAS 2023.xlsx]Cover'!$F$41
```

soit exactement l'arborescence `G:\CORTHAY\CLOTURE MENSUELLES\<année>\`.
Le lecteur `G:` est donc un montage de ce SharePoint.

**Conséquence sur la fiabilité :** la structure, les règles de mapping, la
politique de change et l'architecture des états sont établies sur des fichiers
Mage authentiques, mais d'**exercices différents** (2019, 2023, 2025 selon le
fichier). Les libellés et les mécanismes sont stables d'un exercice à l'autre ;
les **montants et les taux 2025** doivent être revalidés sur vos fichiers.
Voir §5 (anomalies) et §6 (questions) pour ce qui reste à confirmer.

## 1.2 Fichiers demandés et substituts analysés

| Fichier demandé (`G:\…\2025\`) | Substitut réellement analysé | Exercice | Statut |
|---|---|---|---|
| `Mage SAS Consolidated accounts 2025.xlsx` | `ANALYSE/AA Mage SAS Consolidated accounts 2023 MARGIN.xlsx` (34 onglets) | 2023 | **Analysé** |
| `Mage SAS Consolidated accounts by cost center 2025.xlsx` | `Mage SAS Consolidated accounts 31-12-2019 by cost center (22-06-2020) CLC.xlsx` (Drive) | 2019 | **Analysé** |
| — (état consolidé final) | `ANALYSE/EC+/2025.xlsx` | **2025** | **Analysé — référence principale** |
| `Consolidated Statement of Cash Flows Mage (indirect method) 2025.xlsx` | `Consolidated Statement of Cash Flows Mage (indirect method) 2023.xlsx` | 2023 | Partiellement analysé |
| `Consolidated Statement of Cash Flows Mage (direct method) 2025.xlsx` | non trouvé | — | **Non analysé** |
| `Cashflow statements Mage SAS 2025.xlsx` | non trouvé (référencé en lien externe) | — | **Non analysé** |
| `MA - Mage Japon KK 2025.xlsx` | `INTERCO/2025/11 NOVEMBRE/JAPON/202511 Mage Japon KK monthly report DNT (1).xlsx` | 2025 | **Analysé — référence source** |
| `MA - Mage Asia Pacific-Management accounts 2025.xlsx` | non trouvé (variante Shanghai 2024 disponible) | — | **Non analysé** |
| `Management accounts 2025.xlsx` | `Management accounts December.xlsx` (Drive, 2021) | 2021 | Non analysé en détail |
| `PRI MAGE 2025.xlsm` | `PRI MAGE 2025.xlsx` | **2025** | Repéré, non analysé en détail |
| `PRI SICCA 2025.xlsm` | `ANALYSE/ANALYSE PRI SICCA.xlsx`, `COMPARATIF PRI SICCA.xlsx` | 2024 | Repéré, non analysé en détail |
| `Gross margin Mage SAS 2025.xlsx` | bloc « Gross Margin » interne au classeur consolidé | 2023/2025 | Partiellement analysé |
| `LIASFISCVMAGE 2025.xlsx` | `LIASFISCVMAGE 2023 DRAFT DECEMBRE.xlsx` + onglet `Mapping liasse Mage` | 2023 | Structure identifiée |
| — (table de correspondance) | **`MAPPING MAGE SAS.xlsx`** | 2025 | **Analysé — pièce maîtresse** |

## 1.3 Description des fichiers analysés

### A. `MAPPING MAGE SAS.xlsx` — dictionnaire de correspondance (pièce maîtresse)

Rôle : traduit les plans de comptes locaux vers le plan de comptes groupe.
C'est le pivot de toute la consolidation.

| Onglet | Dim. | Contenu |
|---|---|---|
| `Mapping` | 749 × 11 | MAGE SAS : n° compte (8 chiffres, PCG) → libellé FR → **libellé consolidé EN**. Colonnes D:E = table des sections analytiques `921S*`. |
| `SICCA` | 205 × 3 | Idem pour SICCA SARL (204 comptes). |
| `Mapping PRI` | 342 × 4 | Correspondances alimentant `PRI MAGE`. |
| `Mapping PC` | 344 × 3 | Variante « prix de revient ». |
| `Mapping liasse Mage` | 677 × 5 | Compte → `CODE I` / `CODE II` / `CODE III` de la liasse fiscale (ex. `DA`). Alimente `LIASFISCVMAGE`. |

Répartition des 748 comptes MAGE SAS par classe PCG :

| Classe | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Nombre | 28 | 41 | 18 | 156 | 17 | 245 | 243 |

**177 libellés consolidés distincts** en sortie. Extrait dans
`config/mapping/mage_sas_accounts.csv`, `sicca_accounts.csv`,
`liasse_fiscale.csv`.

### B. `202511 Mage Japon KK monthly report DNT.xlsx` — format source de référence

Rôle : remontée mensuelle d'une filiale. **C'est le format que l'application
doit savoir importer.**

| Onglet | Dim. | Contenu |
|---|---|---|
| `Cover` | 12 lignes | `MAGE JAPON KK`, `MANAGEMENT ACCOUNTS`, `FISCAL YEAR 2025`, `LOCAL CURRENCY JPY`, dates de début/fin de période. |
| `Mapping accounts` | 88 × 3 | `ACCOUNT ID` \| `LOCAL ACCOUNT` (bilingue JP/EN) \| `GROUP MAGE COA`. **Chaque entité embarque son propre mapping.** |
| `Group COA` | 157 × 3 | Plan groupe avec marqueurs de section `BALANCE SHEET ACCOUNTS` / `PROFIT & LOSS ACCOUNTS`. 65 postes de bilan, 91 de résultat. |
| `Balance sheet` | 92 × 16 | 13 colonnes de périodes : déc. N-1 (comparatif) puis janv.→déc. N. Ligne 6 = mois, 7 = année, 8 = devise. 131 formules. |
| `Trial balance` | 164 × 4 | `Account description` \| `Debit` \| `Credit` \| `Ending balance`. En-tête **`DEBIT (+)/CREDIT (-)`**. 347 formules (`D = B - C`). |

Contrôles intégrés observés en pied de `Trial balance` :
total débit = total crédit = 303 775 411 ; ligne `PL` = 17 666 880 ;
ligne `Control :` = 0.

### C. `ANALYSE/EC+/2025.xlsx` — état consolidé final 2025 (référence de sortie)

| Onglet | Dim. | Visibilité |
|---|---|---|
| `Consolidated BS` | 62 × 4 | visible — bilan de synthèse |
| `Detailed Consolidated BS` | 111 × 4 | **very hidden** — bilan ligne à ligne |
| `Consolidated PL` | 42 × 3 | visible — résultat de synthèse |
| `Detailed Consolidated PL` | 202 × 13 | **very hidden** — résultat ligne à ligne + analyse de marge par famille |

Les **feuilles de détail sont masquées en mode `very hidden`** (invisibles depuis
l'interface Excel standard) : c'est là que réside la logique réelle. Les formules
de la feuille de synthèse donnent explicitement les règles de regroupement, par
exemple `Consolidated BS!C10 = SUM('Detailed Consolidated BS'!C10:C12)`.

Le bloc `F:M` lignes 28-31 de `Detailed Consolidated PL` porte l'**analyse de
marge par famille** : SLG, LG, SHOES, SNEAKERS, LOAFERS, BELT, BESPOKE,
BESPOKE & SHOES.

### D. `AA Mage SAS Consolidated accounts 2023 MARGIN.xlsx` — feuille de travail (34 onglets)

| Onglet | Contenu |
|---|---|
| `Feuil1` **[hidden]** | Compte de résultat analytique par entité/magasin (CORTHAY UK / MOTCOMB), colonnes multi-périodes, `%` de chiffre d'affaires, sous-totaux par nature de charge. |
| `Cover` | `MAGE SAS`, `UNAUDITED CONSOLIDATED FINANCIAL STATEMENTS`, `31 December 2023`, et les repères de navigation `A.FILL`, `M.FILL`, `MAPPINGS`, `RESULTS`. |
| `Annual average rate` | Taux moyens **mensuels** par devise, source citée `www.banque-france.fr`. Contient le **lien externe** vers `Cashflow statements Mage SAS 2023.xlsx`. |
| `Rate` | Taux `EOM` et `Average` à la clôture + tables historiques par exercice (2011→2022) + « Historical exchange rates for Capital ». |
| `Moyenne Mensuelle`, `EOM`, `Taux EOM ZAR` | Tables de taux, exposées via les plages nommées `Taux_moyens_mensuels`, `Taux_EOM_ZAR`. |
| 27 autres onglets | Feuilles par entité (dont `' Mage Japan'`), non lues (budget de lecture épuisé). |

### E. `Mage SAS Consolidated accounts 31-12-2019 by cost center.xlsx` — état par centre de coûts

Onglets identifiés : `Rate`, `EOM`, `Conso 31-12-2019 CC-local cur`,
`Conso 31-12-2019 cost center`, `Conso 31-12-2019 legal entity`,
`Gross Margin EURO`.

C'est la structure des **deux états cibles** :
`… legal entity` = *Mage SAS Consolidated accounts* ;
`… cost center` = *Mage Consolidated accounts by cost center*.

Structure de colonnes observée (en-têtes superposés) :

```
ligne « entités »        MAGE SAS | MAGE SHANGHAI | SICCA | CORTHAY UK | MAGE MIDDLE EAST |
                         CORTHAY MIDDLE EAST | MAGE ASIA PACIFIC | MAGE JAPON |
                         MAGE KOREA LIMITED | MAGE DISTRIBUTORS SA
ligne « centres »        HEADQUARTERS | VOLNEY | WHOLESALES | SUB | MANUFACTURE |
                         PRIVATE SALES | BEIJING | TOTAL BEIJING | WUHAN | XIAN |
                         BESPOKES | BESPOKES SUB | MOTCOMB | DUBAI | LANDMARK |
                         HARBOUR CITY | AOYAMA | ISETAN | HANKYU TOKYO | HANKYU OSAKA |
                         GALLERIA/LOTTE | LOTTE | JOHANNESBURG |
                         ELIMINATION | TOTAL MAGE CONSOLIDATED ACCOUNTS
ligne « scénario »       DEBIT (-)/CREDIT (+) — Actual / ACTUAL / ACTUAL estimation
ligne « devise »         EUR | GBP | AED | …
ligne « date »           12/31/2019
```

Le titre porte la coquille d'origine `MAGE CONSOIIDATED ACCOUNTS`.

### F. Fichiers repérés mais non analysés en détail

- `PRI MAGE 2025.xlsx` — prix de revient, alimenté par `Mapping PRI`.
- `LIASFISCVMAGE 2023 DRAFT DECEMBRE.xlsx` — liasse fiscale, alimentée par
  `Mapping liasse Mage`.
- `Consolidated Statement of Cash Flows Mage (indirect method) 2023.xlsx` —
  entités identifiées dans l'en-tête : MAGE SAS, MAGE SHANGHAI, SICCA,
  VOLNEY UK, MAGE ASIA.
- `Réconciliation Mage 31-12-2021/2023.xlsx` — balances Sage rapprochées.
- `2026 BUDGET MOMENTUM MAJ.xlsx` — budget par activité (Volney, …).

## 1.4 Ce qui reste à fournir pour finaliser

1. Les 13 fichiers 2025 d'origine (dépôt dans une pièce jointe, ou copie dans
   un dossier OneDrive accessible au connecteur).
2. En priorité : `Mage SAS Consolidated accounts 2025.xlsx` et
   `Mage SAS Consolidated accounts by cost center 2025.xlsx`, seuls documents
   permettant le rapprochement chiffré exigé au livrable 15.
3. `Cashflow statements Mage SAS 2025.xlsx`, cible du lien externe qui porte le
   nombre de mois de la période.
