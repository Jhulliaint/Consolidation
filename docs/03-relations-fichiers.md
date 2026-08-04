# 3. Relations entre les fichiers

## 3.1 Cartographie

```
                        ┌─────────────────────────────────────┐
                        │      MAPPING MAGE SAS.xlsx          │
                        │  ── pivot du dispositif ──          │
                        │  Mapping ............. MAGE SAS     │
                        │  SICCA ............... SICCA SARL   │
                        │  Mapping PRI ......... prix revient │
                        │  Mapping PC .......... prix revient │
                        │  Mapping liasse Mage . liasse fisc. │
                        └───┬────────┬───────────┬────────────┘
                            │        │           │
        ┌───────────────────┘        │           └──────────────────┐
        ▼                            ▼                              ▼
┌───────────────┐         ┌────────────────────┐         ┌────────────────────┐
│ PRI MAGE      │         │  CONSOLIDATION     │         │ LIASFISCVMAGE      │
│ PRI SICCA     │         │                    │         │ (flux social,      │
│ (prix revient)│         │                    │         │  MAGE SAS seule)   │
└───────────────┘         └────────────────────┘         └────────────────────┘
                                     ▲
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
┌───────────────┐          ┌──────────────────┐         ┌──────────────────┐
│ MA - Mage     │          │ MA - Mage Asia   │         │ Management       │
│ Japon KK      │   ...    │ Pacific          │   ...   │ accounts         │
│ (JPY)         │          │ (HKD)            │         │ (MAGE SAS, EUR)  │
└───────┬───────┘          └────────┬─────────┘         └────────┬─────────┘
        │  Cover / Mapping accounts / Group COA / Trial balance / Balance sheet
        └───────────────────────────┬────────────────────────────┘
                                    ▼
              ┌──────────────────────────────────────────────┐
              │  Mage SAS Consolidated accounts <année>      │
              │  ── feuille de travail, 34 onglets ──        │
              │  Cover · Rate · EOM · Annual average rate ·  │
              │  Moyenne Mensuelle · Taux EOM ZAR ·          │
              │  1 onglet par entité · Feuil1 [hidden]       │
              └───────┬──────────────────────────┬───────────┘
                      │                          │
      ┌───────────────┴──────────┐   ┌───────────┴──────────────────┐
      ▼                          ▼   ▼                              ▼
┌──────────────────┐  ┌──────────────────────┐        ┌──────────────────────┐
│ Conso … legal    │  │ Conso … cost center  │        │ Gross Margin EURO    │
│ entity           │  │ Conso … CC-local cur │        │ (marge par famille)  │
│ = ÉTAT CIBLE 1   │  │ = ÉTAT CIBLE 2       │        └──────────────────────┘
└────────┬─────────┘  └──────────────────────┘
         ▼
┌────────────────────────────────────────────┐        ┌──────────────────────┐
│  EC+/<année>.xlsx — états publiés          │        │ Cashflow statements  │
│  Consolidated BS      (visible)            │◄───────┤ Mage SAS <année>     │
│  Detailed Cons. BS    [very hidden]        │  lien  │ Cover!$F$41 =        │
│  Consolidated PL      (visible)            │ externe│ nb de mois période   │
│  Detailed Cons. PL    [very hidden]        │        └──────────┬───────────┘
└────────────────────────────────────────────┘                   │
                                                                 ▼
                                              ┌──────────────────────────────┐
                                              │ Consolidated Statement of    │
                                              │ Cash Flows (direct/indirect) │
                                              └──────────────────────────────┘
```

## 3.2 Liens établis, avec la preuve

| # | Lien | Preuve | Statut |
|---|---|---|---|
| L-1 | `MAPPING MAGE SAS.xlsx` → consolidation | L'onglet `Mapping` produit les 177 libellés consolidés que l'on retrouve mot pour mot dans `Detailed Consolidated BS/PL`. | **[FAIT]** |
| L-2 | `MAPPING MAGE SAS.xlsx` → `LIASFISCVMAGE` | L'onglet `Mapping liasse Mage` associe 676 comptes à des codes `CODE I/II/III` (`DA`, …), qui sont les repères de la liasse fiscale. | **[FAIT]** |
| L-3 | `MAPPING MAGE SAS.xlsx` → `PRI MAGE` / `PRI SICCA` | Onglets `Mapping PRI` (341 comptes) et `Mapping PC` (343 comptes), tous de classes 6 et 7. | **[FAIT]** |
| L-4 | Management accounts → consolidation | Les libellés `GROUP MAGE COA` du fichier Japon (`Cash Bank`, `Stock shoes subsidiaries`) sont exactement des lignes de `Detailed Consolidated BS`. | **[FAIT]** |
| L-5 | `Cashflow statements` → `Mage SAS Consolidated accounts` | Formule `Annual average rate!B4 = MONTH('…/CLOTURE MENSUELLES/2023/[Cashflow statements Mage SAS 2023.xlsx]Cover'!$F$41)`. | **[FAIT]** |
| L-6 | `Rate` → onglets de taux | `Rate!B9 = EOM!D2`, `Rate!C9 = 'Annual average rate'!B95`, et `INDEX(…, MATCH(…, Taux_moyens_mensuels[#Headers], 0))` sur les plages nommées. | **[FAIT]** |
| L-7 | Onglets par entité → `Rate` | `Rate!B20 = ' Mage Japan'!J46`. | **[FAIT]** |
| L-8 | Détail → synthèse (bilan) | `Consolidated BS!C10 = SUM('Detailed Consolidated BS'!C10:C12)`, et 25 formules du même type. | **[FAIT]** |
| L-9 | Détail → synthèse (résultat) | `Consolidated PL!C12 = 'Detailed Consolidated PL'!C48`, etc. | **[FAIT]** |
| L-10 | Résultat ↔ bilan | `Detailed Consolidated PL!C202 = C198 − 'Detailed Consolidated BS'!C102` : contrôle liant le résultat du P&L à la ligne de résultat du bilan. | **[FAIT]** |
| L-11 | `G:\` ↔ SharePoint | Le lien externe L-5 pointe vers `https://mage3-my.sharepoint.com/CORTHAY/CLOTURE MENSUELLES/2023/`, soit l'arborescence exacte de `G:\CORTHAY\CLOTURE MENSUELLES\2023\`. | **[FAIT]** |
| L-12 | Consolidation → tableau de flux | Le fichier `Consolidated Statement of Cash Flows (indirect method)` liste les mêmes entités (MAGE SAS, MAGE SHANGHAI, SICCA, VOLNEY UK, MAGE ASIA) avec leurs soldes de trésorerie. | **[DÉDUIT]** |
| L-13 | `Gross margin Mage SAS` → consolidation | Un bloc d'analyse de marge par famille est **interne** au classeur consolidé (`Detailed Consolidated PL`, colonnes F:M, lignes 28-31). Le fichier séparé en est probablement une extraction. | **[HYPOTHÈSE]** |

## 3.3 Conventions de nommage observées

Les noms de fichiers portent de l'information exploitable :

```
Mage SAS Consolidated accounts 31-12-2019 by cost center (22-06-2020) CLC.xlsx
│                              │          │              │            └ initiales du préparateur
│                              │          │              └ date de production du fichier
│                              │          └ vue restituée
│                              └ date de clôture
└ périmètre

MA - Mage Japon KK 2025.xlsx        « MA » = Management Accounts
202511 Mage Japon KK monthly report DNT.xlsx    AAAAMM + initiales
```

Les onglets de consolidation intègrent la date de clôture :
`Conso 31-12-2019 legal entity`. L'application ne doit donc pas présumer de noms
d'onglets figés — d'où la détection par motif et par en-tête.

## 3.4 Organisation des dossiers

```
G:\CORTHAY\CLOTURE MENSUELLES\<année>\        clôtures mensuelles (fichiers demandés)
OneDrive office@corthay.com
  ├── ANALYSE\                                travaux d'analyse
  │     ├── EC+\<année>.xlsx                  états consolidés publiés
  │     ├── REPORT\                           reportings
  │     └── AA Mage SAS Consolidated …        feuilles de travail
  ├── INTERCO\<année>\<MM MOIS>\<PAYS>\       remontées mensuelles des filiales
  └── MAPPING MAGE SAS.xlsx                   pivot, à la racine
```

L'arborescence `INTERCO\2025\11 NOVEMBRE\JAPON\` confirme une collecte
**mensuelle et par pays** des management accounts.

## 3.5 Ce que l'application reprend de ces liens

| Lien d'origine | Traduction dans l'application |
|---|---|
| L-1, L-4 (mapping) | `config/mapping/*.csv` + table embarquée dans le fichier source, la seconde primant |
| L-6, L-7 (taux) | `config/fx.yaml` — plus aucune référence inter-onglets |
| L-5 (nombre de mois par lien externe) | paramètre explicite `--closing`, plus de dépendance à un fichier tiers |
| L-8, L-9 (détail → synthèse) | `config/coa/statement_*.yaml`, clé `summary:` |
| L-10 (contrôle résultat/bilan) | contrôle **C2**, bloquant |
| L-2, L-3 (liasse, PRI) | tables extraites (`liasse_fiscale.csv`) mais **flux non implémentés** — hors périmètre du prototype |
