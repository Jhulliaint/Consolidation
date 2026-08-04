# 10. Rapport de rapprochement

## 10.1 État du rapprochement

Le rapprochement exigé — comparer les sorties de l'application aux fichiers
`Mage SAS Consolidated accounts 2025` et `… by cost center 2025` — **n'a pas pu
être réalisé** : ces fichiers ne sont pas accessibles depuis l'environnement de
travail (anomalie A-01, §1.1).

Ce qui a pu être fait à la place, et qui a une valeur propre :

| Vérification | Portée | Résultat |
|---|---|---|
| **A.** Reconstitution de la cascade de résultat 2025 | états réels Mage | ✅ exacte |
| **B.** Reconstitution de la définition de l'EBITA | états réels Mage | ✅ exacte |
| **C.** Rapprochement du moteur à un calcul manuel indépendant | jeu de test | ✅ exact au centime |
| **D.** Invariants comptables | jeu de test | ✅ 10/10 contrôles |
| **E.** Rapprochement aux états 2025 réels | — | ⛔ **non réalisé** |

## 10.2 A. Cascade de résultat 2025 — vérifiée sur les états réels

Reconstituée depuis les formules de `EC+/2025.xlsx`, puis recalculée à partir des
montants publiés dans ce même fichier :

| Poste | Montant publié (€) | Recalcul | Écart |
|---|---|---|---|
| Revenue | 2 921 178 | — | — |
| Cost of revenue | (1 398 541) | — | — |
| **Gross Profit/(Loss)** | **1 522 638** | 2 921 178 − 1 398 541 = 1 522 637 | **1 €** (arrondi) |
| Selling, Marketing & Administrative expenses | (1 489 438) | — | — |
| **Profit/(Loss) from operations** | **33 199** | 1 522 638 − 1 489 438 = 33 200 | **1 €** (arrondi) |
| Interest income | 329 | | |
| Interest expense | (44 682) | | |
| Profit/(loss) on foreign currency | (437 450) | | |
| Other income (expense) net | (188 713) | | |
| **Profit/(Loss) before income tax** | **(637 316)** | 33 199 + 329 − 44 682 − 437 450 − 188 713 = (637 317) | **1 €** (arrondi) |
| Corporate income tax | (3 062) | | |
| **Total Net/(loss) Profit** | **(640 378)** | (637 316) − 3 062 = (640 378) | **0** ✅ |

Les écarts de 1 € proviennent de l'affichage sans décimale de valeurs stockées à
pleine précision (`64 267,874092462749` pour la trésorerie). Ils confirment la
règle A-1 : **l'arrondi est d'affichage, pas de calcul**.

## 10.3 B. Définition de l'EBITA — vérifiée

La formule `Consolidated PL!C42` s'écrit
`= C21 − 'Detailed PL'!C172 + C183 + C184 + C185 + C186`. En y substituant les
montants publiés :

```
  Profit/(Loss) from operations              33 199
+ Depreciation (reprise, C172 = −32 264)     32 264
+ Profit/(loss) on foreign currency        (437 450)
+ Profit/(loss) on Sale of Assets                 0
+ Other income (expense) net               (188 713)
+ Restructuring charges                           0
                                          ──────────
                                           (560 700)
```

Valeur affichée dans le fichier : **(560 700)**. Reconstitution **exacte**.

Cette vérification a une conséquence pratique : elle prouve que l'indicateur
nommé « EBITA » intègre le résultat de change et les éléments non récurrents
(anomalie A-07). La formule est reproduite à l'identique dans
`config/coa/statement_pl.yaml`, avec la mise en garde correspondante.

## 10.4 C. Rapprochement à un calcul manuel indépendant

Faute des fichiers réels, la justesse du moteur est établie contre un calcul posé
à la main, indépendant du code (jeu de test : MAGE SAS en EUR + MAGE JAPON KK en
JPY, avec soldes intragroupe réciproques).

### Bilan

| Composante | Calcul | Montant (€) |
|---|---|---|
| Actif MAGE SAS | 120 000 + 260 000 + 90 000 + 380 000 | 850 000,00 |
| Actif MAGE JAPON KK | 24 600 000 JPY ÷ 156,33 | 157 359,43 |
| Élimination créance intragroupe | − 90 000 | (90 000,00) |
| **Total actif attendu** | | **917 359,43** |
| **Total actif produit** | | **917 359,43** ✅ |
| **Total passif produit** | | **917 359,43** ✅ |
| **Contrôle C1 (actif − passif)** | | **0,00** ✅ |

### Compte de résultat

| Composante | Calcul | Montant (€) |
|---|---|---|
| Ventes MAGE SAS | 1 250 000 + 300 000 | 1 550 000,00 |
| Ventes MAGE JAPON KK | 62 000 000 JPY ÷ 156,30 | 396 673,06 |
| Élimination ventes intragroupe | − 300 000 | (300 000,00) |
| **Revenue attendu** | | **1 646 673,06** |
| **Revenue produit** | | **1 646 673,06** ✅ |
| Variation de stock | 380 000 − 330 000 | 50 000,00 |
| **Gross Profit attendu / produit** | | **1 696 673,06** ✅ |
| Charges MAGE SAS | 560 000 + 175 000 + 30 000 | (765 000,00) |
| Charges MAGE JAPON KK | 12 000 000 JPY ÷ 156,30 | (76 775,43) |
| Impôt | | (3 000,00) |
| **Résultat net attendu / produit** | | **851 897,63** ✅ |

Écart : **0,00 €** sur les quatre agrégats.

### Éliminations générées

| Poste | Montant (€) |
|---|---|
| Account Receivable - subsidiary Mage Japan | (90 000,00) |
| Accounts Payable - Intercompany purchase Mage | 90 000,00 |
| Shoe Sales subsidiaries | 300 000,00 |
| Purchases shoes from Mage | (300 000,00) |
| **Somme, par état** | **0,00** ✅ |

### Lignes calculées par le moteur

| Entité | Poste | Montant (€) | Origine |
|---|---|---|---|
| MAGE_SAS | Profit/loss net income | (832 000,00) | résultat reporté au bilan |
| MAGE_JAPON_KK | Profit/loss net income | (19 897,63) | résultat reporté au bilan |
| MAGE_JAPON_KK | Consolidation reserves | 57 085,25 | écart de conversion |

L'écart de conversion de 57 085,25 € résulte mécaniquement de la conversion du
bilan à 156,33 et du résultat à 156,30. Son **existence** est une conséquence
nécessaire de la politique de change observée ; son **imputation** à
`Consolidation reserves` reste une hypothèse (Q-6.4).

### Traçabilité

Vérifiée par test : pour **chaque** compte du plan groupe, la somme des
enregistrements du journal d'audit égale le montant consolidé (écart < 0,0001 €),
et chaque ligne d'origine `entity` possède exactement un enregistrement d'audit
portant fichier, onglet et numéro de ligne.

## 10.5 D. Contrôles

| Code | Contrôle | Résultat |
|---|---|---|
| C1 | Bilan équilibré | ✅ |
| C2 | Résultat P&L = résultat au bilan | ✅ |
| C3 | Balances sources équilibrées (2 fichiers) | ✅ |
| C4 | Éliminations équilibrées (bilan et résultat) | ✅ |
| C5 | Mapping exhaustif | ✅ |
| C6 | Centres de coûts connus | ✅ |
| C7 | Dates de clôture cohérentes | ✅ |
| C8 | Taux disponibles | ✅ |
| **Total** | | **10/10** |

Suite de tests : **44 tests au vert**.

## 10.6 E. Ce qui reste à démontrer

**Le rapprochement aux états Mage 2025 réels.** Il constitue la seule preuve de
conformité qui compte, et il est prêt à être exécuté : le contrôle **C9** accepte
un dictionnaire de valeurs attendues et produit l'écart poste par poste.

Marche à suivre dès réception des fichiers (§9.2, étape 1) :

1. saisir les taux 2025 réels dans `config/fx.yaml` — les valeurs actuelles sont
   des placeholders explicitement marqués ;
2. exécuter la consolidation sur les management accounts 2025 ;
3. alimenter C9 avec les totaux de `Mage SAS Consolidated accounts 2025` ;
4. documenter et arbitrer chaque écart.

### Écarts déjà anticipés

D'après l'analyse, trois postes présentent un risque d'écart élevé, tous liés à
des règles en hypothèse :

| Poste | Cause probable | Question |
|---|---|---|
| `Consolidation reserves` (−5 954 210 € en 2025) | Le montant est trop élevé pour être un simple écart de conversion annuel : il inclut probablement un cumul historique et/ou des écarts d'acquisition non reconstitués. | Q-6.4, U-03 |
| `Securities in equity method` (961 927 €) | Suppose une mise en équivalence dont le calcul n'est pas observable. Le moteur ne le produira pas. | Q-2.4, U-02 |
| `Accumlated other comprehensive profit/loss` (1 572 109 €) | Mécanisme d'alimentation inconnu. | Q-6.4, U-04 |

Ces trois postes représentent l'essentiel du risque. Les postes d'exploitation
(produits, charges, stocks, créances, dettes) devraient se rapprocher directement,
la chaîne mapping → change → élimination étant reconstituée sur des faits
observés.

## 10.7 Conclusion

La **mécanique** de consolidation est reconstituée et vérifiée : la cascade de
résultat et l'EBITA sont reproduits exactement sur les états 2025 réels, et le
moteur retrouve au centime un calcul manuel indépendant, contrôles d'équilibre
compris.

La **conformité aux états Mage 2025** n'est en revanche pas démontrée, faute
d'accès aux fichiers. Il ne faut pas mettre l'application en production avant
cette étape : un moteur de consolidation dont on n'a pas vérifié qu'il retrouve
les chiffres connus ne doit pas servir à produire des états financiers.
