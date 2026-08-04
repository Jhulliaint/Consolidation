# 2. Analyse fonctionnelle et comptable

## 2.1 Le processus tel qu'il fonctionne aujourd'hui

Le dispositif Mage articule quatre étages, du plus local au plus consolidé.

**Étage 1 — la comptabilité locale.** Chaque entité tient sa comptabilité dans
son propre référentiel : plan de comptes français (PCG, 8 chiffres) sous Sage
pour MAGE SAS et SICCA, plans locaux pour les filiales (le plan japonais est
bilingue, `店舗現金/Cash in Store`). Il n'y a aucune numérotation commune.

**Étage 2 — la remontée « Management accounts ».** Chaque entité produit un
classeur mensuel normalisé. Il ne contient pas seulement des chiffres : il
embarque **sa propre table de correspondance** vers le plan groupe
(`Mapping accounts`) et **le plan groupe lui-même** (`Group COA`). C'est le point
d'architecture le plus important du dispositif : la traduction vers le
référentiel groupe est faite **à la source**, par celui qui connaît ses comptes.

**Étage 3 — la feuille de consolidation.** Un classeur de travail rassemble les
entités en colonnes, applique la conversion de devises, ajoute une colonne
`ELIMINATION` et totalise. Il existe en trois vues : par entité juridique, par
centre de coûts, et en devise locale.

**Étage 4 — les états publiés.** Un bilan et un compte de résultat consolidés,
en euros, à deux niveaux de finesse : un niveau détail (une ligne par compte
groupe) et un niveau synthèse (postes agrégés). Le niveau détail est stocké dans
des feuilles `very hidden`.

En parallèle, trois flux latéraux exploitent les mêmes données sources : le prix
de revient (`PRI MAGE`, `PRI SICCA`), la liasse fiscale (`LIASFISCVMAGE`, flux
social MAGE SAS uniquement) et le tableau de flux de trésorerie.

## 2.2 Le référentiel comptable groupe

### Nature de la clé de consolidation

**La clé de consolidation est un libellé texte anglais**, pas un numéro de
compte. C'est le choix structurant du modèle : `60110000 ACHATS MAT 1ERE FRANCE`
et `60111000 ACHATS MAT 1ERE EXOT France` convergent tous deux vers
`Purchases raw material`. Le mapping est donc **plusieurs-vers-un**, et la
granularité du consolidé est fixée par le libellé cible.

Conséquence pratique : la robustesse du dispositif dépend de la stabilité
orthographique des libellés. Les fautes présentes (`Stock shoes subsisdairies`,
`Mage Asia Pacfic`) font partie de la clé et ne peuvent pas être corrigées
unilatéralement — voir anomalie A-04.

### Structure du plan groupe

| Bloc | Nombre de postes | Exemples |
|---|---|---|
| Bilan — actif circulant | 31 | Cash Bank, Account Receivable, 18 postes de stock |
| Bilan — actif immobilisé | 16 | Leasehold improvements, Goodwill, et leurs amortissements |
| Bilan — passif courant | 16 | Accounts Payable, Accrued expenses, Deposit received |
| Bilan — passif non courant | 3 | Long term Bank loans, Long Term Debt-Noncurrent |
| Bilan — capitaux propres | 8 | Share capital, Consolidation reserves, Retained earnings |
| Résultat — produits | 34 | ventilés par famille × canal |
| Résultat — coût des ventes | 74 | ouverture / achats / clôture par famille |
| Résultat — charges d'exploitation | 40 | Wages and salaries → Depreciation |
| Résultat — hors exploitation | 6 | Interest, change, cessions, restructuration |

### Deux axes structurants dans les produits

Le plan groupe croise systématiquement **famille de produit** et **canal de
vente** :

- familles : Shoe, Sneaker, Loafer, Sandal, Belt, SLG *(small leather goods)*,
  LG *(leather goods)*, Bespoke, Other ;
- canaux : **direct** (`Shoe Sales`), **distributeurs** (`Shoe Sales
  distributors`), **filiales** (`Shoe Sales subsidiaries`).

Le canal « filiales » n'est pas une information commerciale : c'est le
**marqueur d'élimination**. Toute ligne `… subsidiaries` en produit a vocation à
disparaître du consolidé, en regard d'un `Purchases … from Mage` chez la filiale.
Le plan de comptes est donc conçu pour rendre les éliminations mécaniques.

### Le coût des ventes en variation de stock

Chaque famille suit le même triptyque :

```
Opening stock <famille>  +  Purchases / Production costs  −  Closing stock <famille>
= coût des ventes de la famille
```

Le classeur de travail 2023 matérialise ce calcul en une ligne
`Cost of <famille> sold` par famille. Le classeur consolidé 2025 laisse les trois
composantes visibles et les additionne globalement. Les deux approches donnent le
même total ; seule la présentation diffère.

Le triptyque est **dédoublé** entre stocks propres (`Closing stock shoes Mage
SAS`) et stocks détenus par les filiales (`Closing stock shoes subsidiaries`),
ce qui permettrait d'isoler une marge interne — mécanisme non observé (Q-7.4).

## 2.3 L'axe analytique

MAGE SAS tient un axe analytique Sage (sections `921S*`) que les filiales ne
semblent pas alimenter. L'axe mélange deux natures :

- des **fonctions** chez le parent : Headquarters, Manufacture, Wholesales, Sub,
  Private sales, E-commerce, Haute Cordonnerie ;
- des **points de vente** chez les filiales : Motcomb (Londres), Dubai,
  Landmark et Harbour City (Hong Kong), Aoyama, Isetan, Hankyu Tokyo et Osaka
  (Japon), Galleria/Lotte et Lotte (Corée), Johannesburg, Beijing, Wuhan, Xian.

Ce mélange est fonctionnellement cohérent — il s'agit de « centres de résultat »
— mais il n'est pas hiérarchisé : rien ne relie formellement `AOYAMA` à
`MAGE JAPON KK` sinon la position des colonnes. Voir Q-5.2.

**Point ouvert majeur** : le classeur Mage Japon KK analysé ne porte **aucun**
axe analytique, alors que l'état par centre de coûts affiche quatre colonnes
japonaises. L'origine de cette ventilation reste à déterminer (Q-5.4) — c'est le
principal obstacle à la reproduction fidèle du second état de référence.

## 2.4 Les intragroupes

Le plan groupe nomme explicitement chaque contrepartie, dans les deux sens :

| Chez MAGE SAS (parent) | Chez la filiale |
|---|---|
| `26720000 Mage Japan intercompany account` | `MAGE current intercompany account` |
| `41140000 Account Receivable - subsidiary Mage Japan` | `Accounts Payable - Intercompany purchase Mage` |
| `70104300 Shoe Sales subsidiaries` | `Purchases shoes from Mage` |
| `60720000 Purchases Bespokes from SICCA` | *(côté SICCA : ventes)* |

Dix contreparties sont nommées : SICCA, Mage Japan, Corthay UK, Mage Asia
Pacific, Mage Middle East, Mage Korea, Mage South Africa, Mage China, Volney UK,
Ardillat LTD. Les filiales tiennent en plus des comptes « fellow company » entre
elles, ce qui indique des flux **filiale à filiale**, pas seulement parent-filiale.

## 2.5 Le dispositif de change

Trois jeux de taux, ce qui est la signature d'une consolidation multidevise
correcte :

| Jeu | Usage déduit | Observé dans |
|---|---|---|
| `EOM` (fin de mois) | postes de bilan | onglet `Rate`, colonne EOM |
| `Average` (moyen) | postes de résultat | onglet `Rate`, colonne Average |
| `Historical` | capital et primes | table « Historical exchange rates for Capital » |

Les taux moyens sont **recalculés** à partir de moyennes mensuelles issues de
banque-france.fr, divisées par le nombre de mois de la période — lui-même lu
par lien externe dans le fichier Cashflow. Un historique par exercice est
conservé depuis 2011.

Sept devises : AED, GBP, HKD, JPY, KRW, ZAR, CNY. Cotation indirecte
(1 EUR = X devise).

## 2.6 Le dispositif de contrôle existant

Les classeurs Mage embarquent de vrais contrôles, ce qui témoigne d'un processus
mûr :

- `Trial balance` : total débit = total crédit, ligne `Control : 0` ;
- `Balance sheet` : ligne de contrôle à 0 pour **chaque** colonne mensuelle ;
- `Consolidated BS` : `Control : = Total actif − Total passif` ;
- `Detailed Consolidated PL` : `Control = résultat du P&L − ligne de résultat du
  bilan`, qui verrouille la cohérence entre les deux états ;
- `Feuil1` : contrôle des sous-totaux de charges.

Ces cinq contrôles sont repris à l'identique par l'application (C1 à C3), et
complétés par six contrôles supplémentaires (C4 à C9).

## 2.7 Appréciation d'ensemble

**Ce qui est solide.** Le modèle comptable est cohérent et pensé : traduction à
la source, plan groupe croisant famille et canal, marqueurs d'élimination
intégrés au plan de comptes, trois jeux de taux, contrôles d'équilibre à chaque
étage. La logique de consolidation est reconstituable presque intégralement à
partir des seules formules.

**Ce qui fragilise le dispositif.** Quatre points, tous documentés en §5 :

1. la logique métier est enfouie dans des feuilles `very hidden` (A-09), donc
   invisible et non revue ;
2. des constantes sont figées dans des formules sans traçabilité (A-13) ;
3. des liens externes en dur pilotent le calcul des taux (A-10) ;
4. la clé de consolidation étant un libellé texte, une faute de frappe suffit à
   faire disparaître un compte du consolidé (A-04).

C'est précisément ce que l'application corrige : mêmes règles, mais explicites,
paramétrées, contrôlées et traçables.
