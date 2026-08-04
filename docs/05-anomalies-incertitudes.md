# 5. Anomalies, incohérences et zones d'incertitude

## 5.1 Anomalies relevées dans les fichiers

| Réf. | Anomalie | Où | Impact | Conduite tenue |
|---|---|---|---|---|
| **A-01** | **Les fichiers 2025 demandés sont inaccessibles.** Chemins `G:\` = lecteur réseau local ; le répertoire de pièces jointes était vide. | — | **Majeur** : le rapprochement chiffré au fichier de référence (livrable 15) est impossible en l'état. | Analyse menée sur les mêmes familles de fichiers, exercices 2019/2023/2025. Voir §1.1. |
| **A-02** | **Cinq codes analytiques pour un seul centre de coûts** : `921S0`, `921S1`, `921S2`, `921S4`, `921S5` pointent tous vers `HEADQUARTERS` ; `921S6` et `921S12` tous deux vers `Volney`. | `MAPPING MAGE SAS.xlsx`, onglet `Mapping`, colonnes D:E | Agrégation correcte, mais toute analyse plus fine que « Headquarters » est impossible. Soit c'est un héritage historique, soit une distinction utile a été perdue. | Les 12 codes sont conservés en configuration et agrégés vers 8 centres. À arbitrer — Q-5.3. |
| **A-03** | **Trois comptes parasites dans la table des centres de coûts** : les lignes `29610000 PROV. POUR DEPREC. TITRES PARTICIP.`, `29670000 PROV. DEPR. CREANCE. DE PARTICIP.` et `68662000 PROV. DEPREC. IMMO. FINANCIERES` figurent dans la plage D:E réservée aux sections analytiques. | idem | Un import naïf créerait trois centres de coûts fictifs portant des numéros de compte. | Filtrés (un centre de coûts ne peut pas être un numéro de compte à 8 chiffres). |
| **A-04** | **Fautes de frappe dans les libellés servant de clé de jointure** : `Stock shoes subsisdairies`, `Mage Asia Pacfic`, `Sandal Sales distriubutors`, `Temporay staff`, `Refresments`, `Accumlated other comprehensive`, `Accum. Depreciation -office et computer  equipment` (double espace), titre `MAGE CONSOIIDATED ACCOUNTS`. | `MAPPING MAGE SAS.xlsx`, `Group COA`, `EC+/2025.xlsx` | Le mapping se faisant **par libellé**, la moindre correction orthographique d'un côté casse la jointure. | Libellés conservés **à l'identique** ; le rapprochement normalise espaces et casse (règle M-4). Ne pas « corriger » sans mettre à jour les deux côtés simultanément. |
| **A-05** | **Flux intragroupe sans contrepartie identifiable** : `Shipment charge subsidiaries` et `Management fees` figurent en produits, sans poste de charge symétrique dans le plan groupe. | `Group COA`, `Detailed Consolidated PL` | Ces produits ne peuvent pas être éliminés automatiquement : ils resteraient dans le résultat consolidé. | Déclarés dans `eliminations.yaml` avec `expense_lines: []` et signalés. Q-7.2. |
| **A-06** | **Formule référençant une cellule vide** : `Detailed Consolidated PL!C48 = SUM(C13:C47)+H129`, or `H129` appartient au bloc d'analyse de marge et est vide. Le total du chiffre d'affaires comporte donc un terme correctif inactif. | `EC+/2025.xlsx` | Nul aujourd'hui, mais toute saisie en `H129` fausserait silencieusement le chiffre d'affaires consolidé. | Non reproduit. Le moteur somme uniquement les lignes de produits. |
| **A-07** | **`EBITA` mal nommé** : la formule ajoute au résultat d'exploitation les amortissements **mais aussi** le résultat de change (−437 450 €), les cessions d'actifs, les autres produits/charges et la restructuration. L'indicateur affiché (−560 700 €) est donc très inférieur au résultat d'exploitation (+33 199 €). | `EC+/2025.xlsx`, `Consolidated PL!C42` | Un lecteur qui interprète « EBITA » au sens usuel se tromperait de près de 600 k€. | Formule reproduite **à l'identique** (fidélité aux fichiers) et documentée dans `statement_pl.yaml`. Renommage à arbitrer — Q-10.2. |
| **A-08** | **Texte parasite en zone de données** : la cellule à droite de `Long term Bank loans` contient `Bybank` (annotation), dans une colonne par ailleurs numérique. | `EC+/2025.xlsx`, `Consolidated BS!D` | Un import par position lirait `Bybank` comme une valeur. | L'import est piloté par en-tête ; les non-numériques sont ignorés. |
| **A-09** | **Logique métier dans des feuilles `very hidden`** : `Detailed Consolidated BS` et `Detailed Consolidated PL` sont masquées en mode `veryHidden`, invisible depuis l'interface Excel. | `EC+/2025.xlsx` | Risque opérationnel : la logique réelle est invisible pour l'utilisateur, non documentée et non revue. | Le lecteur de l'application ouvre les feuilles masquées et `veryHidden`, et les liste en `inspect`. |
| **A-10** | **Liens externes vers un chemin SharePoint en dur** : `=MONTH('https://mage3-my.sharepoint.com/CORTHAY/CLOTURE MENSUELLES/2023/[Cashflow statements Mage SAS 2023.xlsx]Cover'!$F$41)`. | `AA Mage SAS Consolidated accounts 2023 MARGIN.xlsx`, `Annual average rate!B4` | Le nombre de mois de la période — donc **tous les taux moyens** — dépend d'un fichier externe. Renommage, déplacement ou fichier fermé ⇒ valeur périmée ou `#REF!` sans alerte. | Le nombre de mois devient un paramètre explicite de l'application. |
| **A-11** | **Deux conventions de signe dans un même processus** : balances sources en `DEBIT (+)/CREDIT (-)`, feuilles de travail en `DEBIT (-)/CREDIT (+)`, états finaux en présentation mixte (actif débiteur positif, passif créditeur positif). | ensemble de la chaîne | Source d'erreur de signe classique lors d'une reprise manuelle. | Convention interne unique (`DEBIT (+)/CREDIT (-)`) ; signe appliqué **par section** au seul moment du rendu (règle R-3). |
| **A-12** | **Taux mensuels incomplets** : la table AED 2022 s'arrête en septembre, GBP 2022 en juin, KRW 2022 en avril, tandis que la moyenne est calculée sur 12 mois (`=SUM(B25:B36)/B4`). | `Annual average rate` | Une moyenne divisée par 12 alors que seuls 9 mois sont renseignés sous-évalue le taux d'environ 25 %. À vérifier si ces colonnes ont réellement servi. | Signalé. Le moteur exige un taux explicite par devise et par clôture, et refuse de convertir à défaut (contrôle C8, erreur bloquante). |
| **A-13** | **Constantes en dur dans des formules de calcul** : `B7: =1/0.27667` (taux AED), `C20: =28230000/261150`, `J78: =-2750*2*0.8-2750`, `W36: =15-3+1`, et une expression `C23` additionnant sept montants sur huit autres. | `Rate`, `Feuil1` | Aucune traçabilité : l'origine de ces nombres est perdue. Impossible à auditer ou reproduire. | Non repris. Tout taux vient de `config/fx.yaml`, tout montant d'un fichier source. |
| **A-14** | **Périmètre incertain** : `ARDILLAT LTD` et `MAGE CHINA` n'existent que sous forme de comptes de liaison (`26791000`, `26780000`), sans colonne dédiée dans les états. `CORTHAY MIDDLE EAST JV` a une colonne mais un statut de coentreprise. | `MAPPING MAGE SAS.xlsx`, états par entité | Périmètre et méthode de consolidation indéterminés. | `in_scope: false` pour les deux premières, `method: equity` en hypothèse pour la JV. Q-1.2 / Q-2.4. |
| **A-15** | **Plan de comptes groupe divergent entre parent et filiale** : 82 des 177 libellés MAGE SAS sont absents du `Group COA` de Mage Japon KK. | comparaison des deux référentiels | Attendu (le parent a une activité industrielle), mais aucun fichier ne définit le plan groupe **de référence**. | Le plan groupe est reconstitué comme l'**union** des lignes des états consolidés (règle M-2). À valider — Q-3.1. |

## 5.2 Zones d'incertitude

| Réf. | Sujet | Ce qui manque |
|---|---|---|
| U-01 | **Pourcentages de détention et méthodes** | Aucun fichier analysé ne porte de taux de détention ni de méthode (intégration globale, mise en équivalence). `Non-controlling interest` existe en ligne mais vaut 0 en 2025. |
| U-02 | **Origine de `Securities in equity method` (961 927 €)** | Le poste suppose une mise en équivalence, sans que le calcul soit visible. |
| U-03 | **Origine de `Consolidation reserves` (−5 954 210 €)** | Montant considérable ; mécanisme d'alimentation non observé. Écart de conversion cumulé ? Écarts d'acquisition ? |
| U-04 | **Traitement de `Accumlated other comprehensive profit/loss` (1 572 109 €)** | Distinction avec les réserves de consolidation non établie. |
| U-05 | **Marge interne sur stocks** | Les stocks filiales sont isolés, mais aucun taux de marge ni retraitement n'apparaît. |
| U-06 | **Périodicité réelle** | Les sources sont mensuelles (13 colonnes), les états consolidés annuels/YTD. La consolidation est-elle produite chaque mois ou seulement à la clôture ? |
| U-07 | **Rôle exact de `PRI MAGE` / `PRI SICCA`** | Alimentent-ils le coût des ventes consolidé, ou servent-ils uniquement à l'analyse de marge ? |
| U-08 | **Articulation avec `LIASFISCVMAGE`** | La liasse fiscale est un flux **social** (MAGE SAS seule) ; son lien avec la consolidation n'est pas établi. |
| U-09 | **Tableau de flux de trésorerie** | Deux méthodes (directe, indirecte) demandées. La version indirecte 2023 a été repérée, la directe non trouvée. Hors périmètre du prototype. |
| U-10 | **`A.FILL` / `M.FILL`** | Repères de navigation du classeur consolidé, probablement « Annual fill » / « Monthly fill ». Signification à confirmer. |

## 5.3 Risques identifiés

1. **Mapping par libellé texte** (A-04). Une correction orthographique côté
   filiale suffit à faire disparaître un compte du consolidé. Le contrôle C5
   (exhaustivité du mapping) est la parade : il doit être **bloquant**.
2. **Écart de conversion en hypothèse** (FX-8). Si le poste d'imputation est
   faux, le bilan reste équilibré mais la ventilation des capitaux propres est
   erronée. À confirmer avant toute production.
3. **Éliminations à 100 % supposées** (E-5). Si une entité est consolidée par
   mise en équivalence, l'élimination intégrale est incorrecte.
4. **Logique en feuilles masquées** (A-09) et **constantes en dur** (A-13) : le
   modèle actuel n'est pas auditable en l'état. C'est le principal argument en
   faveur de l'application.
5. **Absence de rapprochement chiffré** (A-01) : tant que les fichiers 2025 ne
   sont pas fournis, la conformité de l'application aux états de référence
   n'est **pas démontrée**. Elle est seulement démontrée sur un jeu de test
   contrôlé.
