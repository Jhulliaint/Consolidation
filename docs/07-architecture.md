# 7. Architecture technique

## 7.1 Principe directeur

**Aucune règle métier dans le code.** Le périmètre, les mappings, la politique de
change, les éliminations, la structure des états et la présentation vivent tous
dans `config/`. Le code sait *comment* consolider ; la configuration dit *quoi*
consolider. Répondre à une question du §6 doit se traduire par la modification
d'une ligne de YAML, jamais par une reprise de code.

Second principe : **la présentation ne touche jamais au calcul**. Le moteur
produit des `Decimal` à pleine précision ; l'échelle, l'arrondi, les séparateurs
et les signes d'affichage sont appliqués au seul moment du rendu.

## 7.2 Modules

```
src/mageconso/
├── models.py            modèle de domaine (Period, Entity, SourceLine,
│                        ConsolidatedLine, AuditRecord, ControlResult…)
├── config.py            chargement du paramétrage, normalisation des libellés
├── importers/excel.py   lecture des classeurs, détection par en-tête
├── engine.py            mapping · analytique · change · éliminations · agrégation
├── controls.py          contrôles C1 à C9
├── reports/             construction des états (par entité, par centre de coûts)
├── formatting.py        couche de présentation, isolée du calcul
├── exporters/excel.py   export Excel (synthèse, états, contrôles, audit…)
├── pipeline.py          chaîne complète, partagée par CLI et interface
├── rates.py             taux : fichier, besoins, contrôle de vraisemblance
├── reconcile.py         rapprochement à un classeur de référence
├── suggest.py           suggestions de mapping
├── checks.py            vérification du paramétrage
├── audit.py             journal d'audit SQLite, interrogeable
├── cli.py               interface en ligne de commande
├── webui.py             interface graphique locale (serveur HTTP stdlib)
└── web/index.html       page unique, sans ressource externe
```

Correspondance avec la séparation demandée au cahier des charges :

| Exigence | Module |
|---|---|
| import des fichiers | `importers/excel.py` |
| validation des données | `importers` (structure) + `controls.py` (cohérence) |
| normalisation | `importers` → `SourceLine` |
| mappings | `config.py` + `engine._map_account` |
| règles métier | `config/` (données) + `engine.py` (application) |
| moteur de consolidation | `engine.py` |
| contrôles | `controls.py` |
| génération des états | `reports/` |
| mise en forme | `formatting.py` |
| exports | `exporters/` |
| journal d'audit | `audit.py` |

## 7.3 Choix techniques et justifications

### Langage : Python 3.10+

- Seul écosystème offrant à la fois une lecture Excel fine (formules, feuilles
  `very hidden`, formats) et une arithmétique décimale exacte en bibliothèque
  standard.
- Alternative écartée — **VBA / Power Query** : c'est ce qui produit déjà les
  anomalies A-09 (logique masquée), A-10 (liens en dur) et A-13 (constantes non
  traçables). Rester dans Excel reconduirait le problème au lieu de le résoudre.
  À reconsidérer si votre environnement l'impose (Q-13.2).
- Alternative écartée — **C# / .NET** : équivalent techniquement, mais plus lourd
  à faire évoluer par une équipe comptable.

### Arithmétique : `decimal.Decimal`

Obligatoire. Un `float` binaire ne représente pas `0,01` exactement ; sur un
bilan de 2,6 M€ avec des milliers de lignes, les contrôles d'équilibre au centime
deviennent non déterministes. `Decimal` rend les rapprochements reproductibles.
Les taux de change sont eux aussi des `Decimal` : `156.33` n'est pas
`156.32999999`.

### Excel : `openpyxl`

- Lit et écrit `.xlsx` / `.xlsm`, expose `sheet_state` (donc les feuilles
  `hidden` **et** `veryHidden` — indispensable ici, cf. A-09), les formules
  (`data_only=False`) et les valeurs calculées (`data_only=True`).
- Écrit des **valeurs numériques avec un format de nombre**, ce qui garde le
  résultat auditable et réutilisable dans Excel, plutôt que du texte pré-formaté.
- Alternative écartée — **pandas** : oriente vers des `float64` et masque la
  structure (cellules fusionnées, en-têtes superposés sur trois lignes) qui est
  précisément ce qu'il faut lire ici. Ajoute une dépendance lourde pour un
  bénéfice nul sur ce volume.
- Limite connue : `openpyxl` ne recalcule pas les formules. Les classeurs sources
  sont lus en `data_only=True` (valeurs mises en cache par Excel). Si un fichier
  n'a jamais été ouvert par Excel après modification, les valeurs peuvent être
  absentes — le contrôle C3 le détecte (balance non équilibrée).

### Configuration : YAML + CSV

- YAML pour les structures (états, périmètre, change, éliminations) : lisible et
  commentable, ce qui permet d'inscrire le statut **[FAIT] / [DÉDUIT] /
  [HYPOTHÈSE]** au plus près de chaque règle.
- CSV pour les tables volumineuses (748 comptes MAGE SAS) : éditable directement
  dans Excel par l'équipe comptable, sans outil particulier.

### Persistance : SQLite pour le seul journal d'audit

- Pas de base de données pour les données consolidées : le traitement est un
  batch sans état, rejouable à l'identique. Introduire un SGBD ajouterait de
  l'exploitation sans bénéfice.
- SQLite **pour l'audit**, en revanche, parce que la traçabilité demandée est
  une exigence de *requêtage* : « quelles lignes sources composent les 268 029 €
  de créances ? ». Un fichier plat ne répond pas à cette question, une table
  indexée oui. SQLite est dans la bibliothèque standard, sans serveur, et le
  fichier `.db` s'archive avec la clôture.
- Chaque exécution est un `run` horodaté : deux consolidations sont comparables.

### Interfaces : graphique locale et ligne de commande

Les deux appellent `pipeline.run()` : elles ne peuvent pas diverger sur le
calcul. L'interface graphique (`mageconso ui`) repose sur le serveur HTTP de la
**bibliothèque standard** — aucune dépendance ajoutée — et sur une page unique
sans ressource externe :

- écoute sur `127.0.0.1` seulement ; en-tête `Host` vérifié (parade au *DNS
  rebinding*) ; écritures en `application/json` uniquement (pas d'action
  déclenchable par un formulaire tiers) ; fichiers déposés dans un répertoire
  temporaire supprimé à l'arrêt ;
- tout le calcul **et toute la mise en forme des nombres** sont faits côté
  serveur, par le même formateur que l'export Excel : l'écran et le classeur
  affichent la même chose.

Framework web écarté (Flask, Streamlit) : une dépendance de plus pour un usage
local mono-utilisateur, sans bénéfice fonctionnel ici. À reconsidérer pour un
usage multi-utilisateurs sur serveur (Q-11.1, Q-12.1).

## 7.4 Stratégie de tests

Cinq niveaux, 97 tests actuellement au vert :

1. **Lecture** — extraction du `Cover`, mapping local, variantes numériques
   (`1 234,56`, `1,234.56`, `(1 234)`, `-`, `#DIV/0!`).
2. **Règles** — le bilan est converti au taux de clôture *sauf* le capital au
   taux historique ; les éliminations sont équilibrées par état ; l'écart de
   conversion est imputé.
3. **Rapprochement** — les états produits sont comparés à un **calcul manuel
   indépendant** posé dans le test, pas à une sortie antérieure du programme :
   `850 000 + 24 600 000 / 156,33 − 90 000 = 917 359,43`.
4. **Présentation** — deux paramétrages radicalement différents donnent des
   rendus différents et des montants identiques.
5. **Robustesse** — chaque incident réaliste de clôture (écart de réciprocité,
   flux sans contrepartie, compte non mappé, fichier en double, taux inversé)
   est injecté dans le jeu de démonstration ; on vérifie que le moteur ne
   produit jamais un état faussement propre.

L'interface graphique est testée par son API et sa couche HTTP, et a été
parcourue dans un navigateur (Chromium, via Playwright).

Un test vérifie que le journal d'audit **se réconcilie ligne à ligne** avec les
états : pour chaque compte groupe, la somme des enregistrements d'audit égale le
montant consolidé. C'est la garantie que la traçabilité n'est pas décorative.

Ce qui **n'est pas** testé, faute des fichiers : la conformité aux états 2025
réels. L'outil de rapprochement (C9) est prêt et testé sur un classeur de
référence synthétique au même format.

## 7.5 Déploiement

**Cible immédiate — poste de travail.** Python 3.10+, `pip install -e .`, les
fichiers restent sur `G:\` / SharePoint. Aucun serveur, aucune donnée ne quitte
le poste. C'est le mode le plus simple et le plus sûr pour un usage par une
personne.

**Évolution si usage collectif** (selon Q-11.1 / Q-13.1) : exécution planifiée
sur un serveur avec dépôt des sources dans un dossier SharePoint surveillé, et
publication des états dans un dossier de sortie. Le journal d'audit centralisé
devient alors la mémoire des clôtures.

**Non retenu** : un service exposé sur Internet. Les données sont des états
financiers non publiés ; l'exécution locale évite toute question de transfert
(Q-14.1).

## 7.6 Ce que l'architecture ne couvre pas encore

- Tableau de flux de trésorerie, méthodes directe et indirecte (Q-10.4).
- Flux `PRI` et `LIASFISCVMAGE` : tables de mapping extraites, traitements non
  implémentés.
- Multipériode : le moteur consolide **une** clôture par exécution. Les colonnes
  mensuelles des sources sont lues mais l'agrégation se fait sur la balance de
  clôture. L'extension est prévue par le modèle (`Period` est déjà porté par
  chaque ligne) mais n'est pas faite.
- Reproduction pixel par pixel des classeurs de référence (Q-10.1).
