# 6. Questions de clarification

Classées par thème. Les questions **P1** conditionnent les calculs ou
l'architecture : sans réponse, les montants consolidés peuvent être faux.
Les **P2** affectent le paramétrage, les **P3** le confort.

---

## Priorité 1 — bloquantes pour la justesse des calculs

| Réf. | Thème | Question |
|---|---|---|
| **Q-0.1** | Fichiers | Pouvez-vous déposer les 13 fichiers 2025 (en pièce jointe, ou dans un dossier OneDrive accessible) ? Sans `Mage SAS Consolidated accounts 2025.xlsx` et sa version `by cost center`, le rapprochement chiffré exigé au livrable 15 reste impossible. |
| **Q-6.1** | Devises | Confirmez-vous : **bilan au taux de clôture (EOM)**, **résultat au taux moyen** ? C'est déduit de la présence des deux jeux de taux, pas lu explicitement. |
| **Q-6.3** | Devises | Le **capital et les primes d'émission** sont-ils bien convertis au **taux historique** (table « Historical exchange rates for Capital ») ? Quels autres postes suivent ce taux ? |
| **Q-6.4** | Devises | L'**écart de conversion** est-il imputé à `Consolidation reserves` (−5 954 210 € en 2025) ou à `Accumlated other comprehensive profit/loss` (1 572 109 €) ? Quelle est la différence entre ces deux postes ? |
| **Q-7.1** | Éliminations | Les soldes réciproques sont-ils éliminés à **100 %**, y compris pour `CORTHAY MIDDLE EAST JV` ? |
| **Q-2.3** | Entités | Quels sont les **pourcentages de détention** et la **méthode de consolidation** de chaque entité ? Aucun fichier analysé ne les porte. |
| **Q-2.4** | Entités | `CORTHAY MIDDLE EAST JV` est-elle mise en équivalence ? Est-ce l'origine du poste `Securities in equity method` (961 927 €) ? |
| **Q-5.1** | Centres de coûts | Existe-t-il des **clés de répartition** (refacturation de frais de siège, quote-part de loyer…) ? Je n'en ai trouvé aucune : l'affectation semble directe. Si des clés existent, où sont-elles ? |
| **Q-3.1** | Plans comptables | Le **plan de comptes groupe de référence** est-il formalisé quelque part ? Je l'ai reconstitué comme l'union des lignes des états consolidés (156 libellés filiale + 82 propres à MAGE SAS). |
| **Q-1.1** | Périmètre | La consolidation porte-t-elle sur les **10 entités** identifiées, ou d'autres entrent-elles dans le périmètre 2025 ? |

## Priorité 2 — paramétrage

| Réf. | Thème | Question |
|---|---|---|
| **Q-1.2** | Périmètre | `ARDILLAT LTD` et `MAGE CHINA` n'apparaissent que comme comptes de liaison (`26791000`, `26780000`), sans colonne dans les états. Entrent-elles dans le périmètre ? Sont-elles dormantes ? |
| **Q-1.3** | Périmètre | `MAGE MIDDLE EAST` et `CORTHAY MIDDLE EAST JV` ont chacune une colonne `DUBAI`. Deux structures distinctes sur un même point de vente ? |
| **Q-5.2** | Centres de coûts | Les centres mélangent des **fonctions** (Headquarters, Manufacture, Wholesales) et des **points de vente** (Landmark, Aoyama…). Est-ce voulu, ou faut-il un axe à deux niveaux (entité → fonction → magasin) ? |
| **Q-5.3** | Centres de coûts | Cinq codes (`921S0/1/2/4/5`) pointent vers `HEADQUARTERS` et deux (`921S6`, `921S12`) vers `Volney`. Est-ce un héritage à consolider, ou ces codes portent-ils une distinction à préserver ? |
| **Q-5.4** | Centres de coûts | Les **filiales** transmettent-elles un axe analytique dans leurs management accounts ? Le classeur Mage Japon KK analysé n'en porte aucun — d'où proviennent alors les colonnes `AOYAMA`, `ISETAN`, `HANKYU…` de l'état par centre de coûts ? **Cette question est déterminante pour produire l'état par centre de coûts.** |
| **Q-6.2** | Devises | Le nombre de mois de la période est lu par lien externe dans `Cashflow statements!Cover!$F$41`. Doit-il rester piloté par ce fichier, ou devenir un paramètre saisi ? |
| **Q-6.5** | Devises | Les taux sont-ils saisis manuellement depuis banque-france.fr, ou souhaitez-vous une récupération automatique ? |
| **Q-7.2** | Éliminations | `Shipment charge subsidiaries` et `Management fees` n'ont pas de contrepartie en charges. Comment sont-ils éliminés aujourd'hui ? |
| **Q-7.3** | Éliminations | Quelle **tolérance** acceptez-vous sur un écart de réciprocité intragroupe, et comment le traitez-vous (écart de change, décalage d'enregistrement) ? |
| **Q-7.4** | Éliminations | Y a-t-il un retraitement de la **marge interne sur stocks** ? Les stocks filiales sont isolés (`Stock … subsidiaries`), ce qui le permettrait. Si oui, quel taux ? |
| **Q-7.5** | Éliminations | Les éliminations sont-elles saisies manuellement dans la colonne `ELIMINATION`, ou calculées ? Existe-t-il un fichier d'écritures d'élimination ? |
| **Q-8.1** | Périodicité | La consolidation est-elle produite **mensuellement** ou seulement à la clôture annuelle ? Les sources sont mensuelles, les états consolidés annuels. |
| **Q-8.2** | Périodicité | Les exercices sont-ils tous calés sur l'année civile ? Le fichier Mage Japon KK 2025 porte `11/30` en « period ended » alors que la période va du 01/01 au 31/12. |
| **Q-9.1** | Arrondis | Mode d'arrondi d'affichage : `HALF_UP` (0,5 → 1) ou `HALF_EVEN` (arrondi bancaire) ? |
| **Q-9.2** | Arrondis | Faut-il un **forçage d'équilibre** après arrondi (ajustement d'un centime sur une ligne pour que les totaux affichés se bouclent), ou tolérez-vous un écart d'affichage ? |

## Priorité 3 — restitution et exploitation

| Réf. | Thème | Question |
|---|---|---|
| **Q-10.1** | Formats de sortie | Faut-il reproduire les classeurs de référence **à l'identique** (mêmes onglets, mêmes positions de cellules, feuilles `very hidden` incluses), ou un classeur propre et lisible convient-il ? |
| **Q-10.2** | Formats de sortie | Conserve-t-on le libellé `EBITA` malgré sa définition non standard (anomalie A-07), ou le renomme-t-on ? |
| **Q-10.3** | Formats de sortie | Les états doivent-ils être produits en **devise locale** en plus de l'euro (comme la feuille `CC-local cur`) ? |
| **Q-10.4** | Formats de sortie | Faut-il aussi générer le **tableau de flux de trésorerie** (méthodes directe et indirecte) ? Hors périmètre du prototype actuel. |
| **Q-10.5** | Formats de sortie | Faut-il produire les colonnes comparatives (N-1, budget, « ACTUAL estimation ») visibles dans les fichiers de travail ? |
| **Q-11.1** | Utilisateurs | Qui utilisera l'application : vous seul, l'équipe comptable, les filiales ? Combien de personnes ? |
| **Q-11.2** | Utilisateurs | Une **interface graphique** est-elle nécessaire, ou la ligne de commande plus l'export Excel suffisent-ils ? Le prototype est en ligne de commande, avec un cœur réutilisable pour une interface web. |
| **Q-12.1** | Droits d'accès | Faut-il restreindre l'accès par entité (une filiale ne voit que ses données) ? |
| **Q-13.1** | Technique | L'application tourne-t-elle sur un poste Windows, un serveur, ou dans Microsoft 365 ? Les fichiers restent-ils sur `G:\` / SharePoint ? |
| **Q-13.2** | Technique | Python est-il acceptable dans votre environnement, ou faut-il rester dans Excel/VBA/Power Query ? |
| **Q-13.3** | Technique | Les fichiers `.xlsm` (`PRI MAGE`, `PRI SICCA`) contiennent des macros : portent-elles de la logique de consolidation à reprendre ? |
| **Q-14.1** | Sécurité | Les données consolidées sont-elles confidentielles au point d'interdire tout stockage hors SharePoint (le journal d'audit est une base SQLite locale) ? |
| **Q-14.2** | Sécurité | Faut-il une durée de conservation ou une purge du journal d'audit ? |

---

## Ce que je peux faire avancer sans réponse

- Le moteur, les contrôles, la traçabilité et les exports : **faits**.
- Le paramétrage est en place avec les valeurs déduites, chaque hypothèse étant
  marquée dans les fichiers de configuration et reliée à sa question.
- Modifier une réponse ci-dessus revient à changer une ligne de configuration,
  pas le code.

## Ce qui reste bloqué

- Le **rapprochement chiffré** aux états 2025 (Q-0.1).
- L'**état par centre de coûts pour les filiales** (Q-5.4) : sans savoir d'où
  vient l'axe analytique des filiales, l'état se produit mais reste non ventilé
  pour elles.
- Les **méthodes de consolidation** (Q-2.3) : l'intégration globale est
  appliquée par défaut à toutes les entités.
