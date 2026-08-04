# 4. Règles de consolidation reconstituées

Chaque règle est étiquetée :

- **[FAIT]** — directement lu dans un fichier (valeur, formule, en-tête) ;
- **[DÉDUIT]** — inféré par recoupement, cohérent avec tout ce qui est observé ;
- **[HYPOTHÈSE]** — à confirmer, non vérifiable dans les fichiers analysés.

---

## 4.1 Flux général

```
┌──────────────────────────────────────────────────────────────────────────┐
│  SOURCES : un classeur "Management accounts" par entité                  │
│  Cover (entité, devise, exercice, période)                               │
│  Mapping accounts (compte local → GROUP MAGE COA)                       │
│  Group COA (plan groupe + sections BS / P&L)                            │
│  Trial balance (Débit / Crédit / Solde, DEBIT (+)/CREDIT (-))           │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ 1. import + validation de structure
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  NORMALISATION : une ligne = (entité, période, compte local, montant,    │
│  devise, centre de coûts, fichier/onglet/ligne d'origine)                │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ 2. mapping compte local → compte groupe
                                 │    priorité : feuille du fichier source,
                                 │    puis MAPPING MAGE SAS, puis identité
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  VENTILATION ANALYTIQUE : section 921S* → centre de coûts                │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ 3. conversion en EUR
                                 │    bilan → taux de clôture (EOM)
                                 │    résultat → taux moyen (Average)
                                 │    capital → taux historique
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PAR ENTITÉ : + résultat de l'exercice reporté au bilan                  │
│               + écart de conversion → Consolidation reserves             │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ 4. éliminations intragroupe
                                 │    (colonne ELIMINATION)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  AGRÉGATION  Σ entités + éliminations = TOTAL MAGE CONSOLIDATED ACCOUNTS │
└───────┬──────────────────────────────────────────────────┬───────────────┘
        │ 5a. par entité                                   │ 5b. par centre de coûts
        ▼                                                  ▼
  Mage SAS Consolidated accounts            Mage Consolidated accounts by cost center
  (Consolidated BS / PL, niveaux            (colonnes = centres, + ELIMINATION,
   synthèse et détail)                       + TOTAL)
        │                                                  │
        └────────────────────┬─────────────────────────────┘
                             ▼
        contrôles · mise en forme paramétrable · export Excel · journal d'audit
```

## 4.2 Import des données sources

| # | Règle | Statut |
|---|---|---|
| I-1 | L'entité, la devise locale, l'exercice et les dates de période sont lus sur la feuille `Cover` (`A1` = nom de l'entité). | **[FAIT]** |
| I-2 | Chaque classeur source embarque sa propre table `Mapping accounts` : `LOCAL ACCOUNT` → `GROUP MAGE COA`. | **[FAIT]** |
| I-3 | La colonne `ACCOUNT ID` est vide pour Mage Japon KK : la clé de mapping est le **libellé** local, pas un numéro. La détection doit donc accepter les deux. | **[FAIT]** |
| I-4 | Le mapping est **plusieurs-vers-un** : `普通預金/Ordinary deposit` et `外貨預金/Deposit in foreign currency` pointent tous deux vers `Cash Bank`. L'agrégation est une somme. | **[FAIT]** |
| I-5 | La balance source est en convention **`DEBIT (+)/CREDIT (-)`** et `Ending balance = Debit − Credit`. | **[FAIT]** |
| I-6 | La feuille `Balance sheet` porte 13 colonnes : décembre N-1 en comparatif d'ouverture, puis janvier→décembre N. Lignes d'en-tête 6 = mois, 7 = année, 8 = devise. | **[FAIT]** |
| I-7 | Les zéros sont saisis en format comptable `-` et doivent être lus comme 0, non comme du texte. | **[FAIT]** |

## 4.3 Mapping des comptes

| # | Règle | Statut |
|---|---|---|
| M-1 | Un compte local est traduit en un **libellé de compte groupe** (`GROUP MAGE COA`), pas en un numéro. La clé de consolidation est donc un **libellé texte**. | **[FAIT]** |
| M-2 | Le plan groupe complet est l'**union** des libellés de bilan et de résultat des états consolidés : 65 postes de bilan + 91 de résultat pour une filiale ; MAGE SAS ajoute 82 libellés propres (matières premières, en-cours, créances sur filiales). | **[FAIT]** |
| M-3 | Ordre de priorité retenu : (1) table du fichier source, (2) `MAPPING MAGE SAS.xlsx` pour l'entité, (3) identité si le libellé appartient déjà au plan groupe. | **[DÉDUIT]** |
| M-4 | Le rapprochement des libellés doit être **tolérant** : espaces multiples (`Account Receivable  - subsidiary`), espaces insécables, casse variable. Sinon des postes réels restent non mappés. | **[FAIT]** |
| M-5 | Certains libellés comportent des fautes de frappe reprises à l'identique dans plusieurs fichiers (`Stock shoes subsisdairies`, `Mage Asia Pacfic`, `Sandal Sales distriubutors`, `Temporay staff`, `Refresments`, `Accumlated`, `CONSOIIDATED`). Elles font partie de la clé et doivent être conservées telles quelles. | **[FAIT]** |

## 4.4 Structure des états et règles de regroupement

Les règles ci-dessous sont **lues dans les formules** de `EC+/2025.xlsx`.

### Bilan — détail → synthèse

| Poste de synthèse | Formule d'origine | Lignes de détail agrégées |
|---|---|---|
| Cash and cash equivalents | `SUM(Detail!C10:C12)` | Cash Bank + Cash in Hand petty cash + Cash in Hand cash sales |
| Short-term investments | `Detail!C13` | Short term Investments |
| Accounts receivable, less reserves | `SUM(Detail!C14:C15)` | Account Receivable + Provision for Doubtful Account |
| Inventories net | `SUM(Detail!C16:C34)` | 18 postes de stock + Accum. Depreciation - Stocks |
| Other current assets | `SUM(Detail!C35:C40)` | VAT receivables, Other Receivables, Deposit, Prepaid expenses, Employee advances, Other current assets |
| Long-term investments | `Detail!C45` | Securities in equity method |
| Property, plant and equipment, net | `SUM(C46:C50)+SUM(C52:C56)` | immobilisations corporelles **brutes + amortissements** |
| Intangible assets, net | `SUM(C57:C58)+C51` | Industrial IP + Patent + Accum. Depreciation - Patent |
| Accounts Payable | `SUM(C69:C71)` | Accounts Payable + Expense reports Payable + Other Payable |
| Accrued expenses | `SUM(C72:C76)` | Accrued expenses/vacation/loan interest/commissions/fringe benefits |
| Accrued liabilities | `C78+C79+C80+C83` | VAT payable + Net wage + PAYE Liabilities + Other taxes payable |
| shareholder C/A | `C81+C82` | shareholder C/A + Dividend paid |
| **Retained earnings/losses** | `C100+C102` | **Retained earnings/losses + Profit/loss net income** |

> **R-1 [FAIT]** — Au niveau synthèse, le **résultat de l'exercice est absorbé
> dans les réserves** (`Retained earnings/losses`). Il n'apparaît en ligne
> distincte qu'au niveau détail. Règle non intuitive, encodée dans
> `config/coa/statement_bs.yaml`.

### Compte de résultat — cascade

Vérifiée numériquement sur l'exercice 2025 :

| Ligne | Formule | Valeur 2025 (€) |
|---|---|---|
| Revenue | `SUM(Detail!C13:C47)` | 2 921 178 |
| Cost of revenue | `SUM(Detail!C52:C127)` | (1 398 541) |
| **Gross Profit/(Loss)** | `Revenue + Cost of revenue` | **1 522 638** ✔ |
| Selling, Marketing & Administrative expenses | `SUM(Detail!C133:C174)` | (1 489 438) |
| **Profit/(Loss) from operations** | `Gross Profit + SMA` | **33 199** ✔ |
| + Interest income / expense / FX / Sale of assets / Other / Restructuring | | 329 / (44 682) / (437 450) / 0 / (188 713) / 0 |
| **Profit/(Loss) before income tax** | somme | **(637 316)** ✔ |
| Corporate income tax | | (3 062) |
| **Total Net/(loss) Profit** | | **(640 378)** ✔ |

> **R-2 [FAIT]** — Définition de l'**EBITA** telle qu'implémentée dans le
> classeur : `C200 = C177 − C172 + C183 + C184 + C185 + C186`, soit
> *résultat d'exploitation + amortissements + résultat de change + cession
> d'actifs + autres produits/charges + restructuration*.
> Vérification : `33 199 + 32 264 − 437 450 + 0 − 188 713 + 0 = −560 700`,
> exactement la valeur affichée. **Cette définition n'est pas un EBITA au sens
> usuel** (elle intègre le change et les éléments non récurrents) — voir
> anomalie A-07.

> **R-3 [FAIT]** — La présentation n'obéit **pas** à une convention de signe
> unique. Les feuilles de *travail* portent `DEBIT (-)/CREDIT (+)`, mais les
> **états finaux** présentent l'actif en débit positif (`Cash Bank 55 459`)
> **et** le passif en crédit positif (`Accounts Payable 545 487`), avec
> `Total assets = Total liabilities & shareholders' equity = 2 587 674`.
> Le moteur conserve donc la convention comptable `DEBIT (+)/CREDIT (-)` et
> applique un **signe de présentation par section** (`sign: 1` pour l'actif,
> `sign: -1` pour passif, capitaux propres et compte de résultat).

## 4.5 Conversion de devises

| # | Règle | Statut |
|---|---|---|
| FX-1 | Devises gérées : AED, GBP, HKD, JPY, KRW, ZAR, CNY. Cotation **indirecte** (1 EUR = X devise ; JPY 156,33 / GBP 0,8391). | **[FAIT]** |
| FX-2 | Trois jeux de taux coexistent : `EOM` (fin de mois), `Average` (moyen), et « Historical exchange rates for Capital ». | **[FAIT]** |
| FX-3 | Source des taux : `www.banque-france.fr`, avec une table de moyennes **mensuelles** par devise agrégée en moyenne annuelle (`=SUM(B25:B36)/B4`). | **[FAIT]** |
| FX-4 | Le diviseur `B4` est le **nombre de mois de la période**, lu par lien externe dans `[Cashflow statements Mage SAS <année>.xlsx]Cover!$F$41`. Une clôture intermédiaire utilise donc une moyenne sur les mois écoulés seulement. | **[FAIT]** |
| FX-5 | Postes de **bilan** convertis au taux de **clôture**. | **[DÉDUIT]** — présence du jeu EOM et usage standard |
| FX-6 | Postes de **résultat** convertis au taux **moyen**. | **[DÉDUIT]** |
| FX-7 | **Capital et primes d'émission** convertis au taux **historique** (l'existence d'une table nommée « for Capital » ne laisse guère d'autre lecture). | **[DÉDUIT]** — Q-6.3 |
| FX-8 | L'écart né des taux différents (bilan à la clôture, résultat au taux moyen) est porté en **`Consolidation reserves`**. Le poste existe bien au bilan consolidé 2025 : `(5 954 210)`. | **[HYPOTHÈSE]** — Q-6.4 : à confirmer que c'est bien ce poste, et non `Accumlated other comprehensive profit/loss` (1 572 109) |

## 4.6 Centres de coûts

| # | Règle | Statut |
|---|---|---|
| CC-1 | MAGE SAS utilise des sections analytiques Sage `921S*`. Correspondances lues : `921S0/1/2/4/5` → HEADQUARTERS, `921S3` → MANUFACTURE, `921S6` et `921S12` → VOLNEY, `921S9` → WHL, `921S11` → SUB, `921S14` → E COMMERCE, `921S15` → HAUTE CORDONNERIE. | **[FAIT]** |
| CC-2 | Les centres de coûts de restitution mêlent deux natures : des **fonctions** chez MAGE SAS (Headquarters, Manufacture, Wholesales, Sub, Private sales) et des **points de vente** chez les filiales (Motcomb, Dubai, Landmark, Harbour City, Aoyama, Isetan, Hankyu Tokyo/Osaka, Galleria/Lotte, Johannesburg, Beijing, Wuhan, Xian). | **[FAIT]** |
| CC-3 | Chaque centre de coûts appartient à une entité ; le rattachement se lit dans la superposition des en-têtes de colonnes. | **[DÉDUIT]** |
| CC-4 | **Aucune clé de répartition** (driver, ratio, quote-part) n'apparaît dans les fichiers analysés : l'affectation semble **directe**, chaque écriture portant sa section. | **[HYPOTHÈSE]** — Q-5.1 / Q-5.2 |
| CC-5 | Une ligne source sans section analytique est rangée dans `UNALLOCATED`, jamais rattachée d'office à un centre existant. | Choix d'implémentation, justifié en §5 |

## 4.7 Éliminations intragroupe

| # | Règle | Statut |
|---|---|---|
| E-1 | Une colonne **`ELIMINATION`** précède `TOTAL MAGE CONSOLIDATED ACCOUNTS` dans les trois feuilles de consolidation. Le total consolidé est donc `Σ entités + éliminations`. | **[FAIT]** |
| E-2 | Les comptes de liaison sont identifiés nommément : `267xxxxx` (SICCA, Mage Japan, Corthay UK, Mage Asia Pacific, Mage Middle East, Mage Korea, Mage South Africa, Mage China, Volney UK, Ardillat LTD) et leurs symétriques `411xxxxx` « Account Receivable - subsidiary … ». | **[FAIT]** |
| E-3 | Côté filiale, les contreparties existent : `Accounts Payable - … purchase fellow company`, `MAGE current intercompany account`, `Account Receivable - fellow company …`. | **[FAIT]** |
| E-4 | Les flux de résultat intragroupe sont isolés par des libellés symétriques : `Shoe Sales subsidiaries` ↔ `Purchases shoes from Mage`, et de même pour sneakers, loafers, sandales, ceintures, SLG, LG, autres, services. | **[FAIT]** |
| E-5 | L'élimination porte sur **100 %** des soldes réciproques. | **[HYPOTHÈSE]** — Q-7.1 |
| E-6 | Les stocks détenus par les filiales sont isolés (`Stock … subsidiaries`), ce qui **permettrait** un retraitement de la marge interne, mais aucun calcul de ce type n'a été observé. Désactivé par défaut. | **[HYPOTHÈSE]** — Q-7.4 |
| E-7 | `Shipment charge subsidiaries` et `Management fees` n'ont pas de contrepartie identifiée dans le plan groupe. | Anomalie A-05 / Q-7.2 |

## 4.8 Contrôles de cohérence existants

Repris à l'identique dans l'application :

| Origine | Contrôle | Code app |
|---|---|---|
| `Consolidated BS!D62 = D27−D59` | Total actif − Total passif = 0 | **C1** |
| `Detailed PL!C202 = C198 − Detailed BS!C102` | Résultat du P&L = ligne `Profit/loss net income` du bilan | **C2** |
| `Trial balance` pied de feuille | Total débit = total crédit ; `Control : 0` | **C3** |
| `Balance sheet` ligne 92 | ligne de contrôle à 0 par colonne de mois | C1 (par période) |
| `Feuil1` « Control : » | contrôle des sous-totaux de charges | — |

Contrôles ajoutés : **C4** équilibre des écritures d'élimination, **C5**
exhaustivité du mapping, **C6** centres de coûts connus, **C7** cohérence des
dates de clôture entre fichiers, **C8** disponibilité des taux, **C9**
rapprochement au fichier de référence.

## 4.9 Arrondis

| # | Règle | Statut |
|---|---|---|
| A-1 | Les états de référence affichent l'euro **sans décimale**, mais les valeurs stockées sont à pleine précision (`Cash and cash equivalents 64 267,874092462749`). L'arrondi est donc **d'affichage seulement**. | **[FAIT]** |
| A-2 | Le moteur calcule en `Decimal` et n'arrondit qu'au rendu. | Choix d'implémentation |
| A-3 | Mode d'arrondi effectivement utilisé par Mage (`HALF_UP` ou `HALF_EVEN`) non déterminable depuis les fichiers. Défaut retenu : `ROUND_HALF_UP`. | **[HYPOTHÈSE]** — Q-9.1 |
