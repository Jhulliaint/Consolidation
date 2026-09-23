# 9. Plan de développement

## 9.1 État actuel

| Lot | Contenu | État |
|---|---|---|
| **L0** | Analyse des fichiers, reconstitution des règles, questions | **Fait** — §1 à §6 |
| **L1** | Socle : modèle de domaine, chargement du paramétrage, lecture Excel | **Fait** |
| **L2** | Moteur : mapping, analytique, change, éliminations, agrégation | **Fait** |
| **L3** | Contrôles C1–C9 | **Fait** |
| **L4** | États : par entité et par centre de coûts, niveaux détail et synthèse | **Fait** |
| **L5** | Présentation paramétrable, séparée du calcul | **Fait** |
| **L6** | Export Excel : états, contrôles, diagnostics, piste d'audit | **Fait** |
| **L7** | Journal d'audit SQLite interrogeable + commande `trace` | **Fait** |
| **L8** | Tests automatisés | **Fait** — 97 tests |
| **L9** | Documentation installation et utilisateur | **Fait** |
| **L10** | Revue : 5 défauts de calcul corrigés (voir `CHANGELOG.md`) | **Fait** |
| **L11** | Interface graphique locale, traçabilité au clic | **Fait** |
| **L12** | Outil de rapprochement à un classeur de référence | **Fait** |
| **L13** | Taux : fichier, pré-contrôle, détection d'erreurs ; suggestions de mapping | **Fait** |
| **L14** | Vues par entité, % du CA, marge par famille ; `mageconso check` ; contrôle C10 | **Fait** |

## 9.2 Suite, par ordre de priorité

### Étape 1 — Rapprochement aux fichiers réels *(bloquée : Q-0.1)*

La seule étape qui démontre la conformité. Dès réception des fichiers 2025 :

1. `mageconso inspect` sur chaque management account pour valider la lecture ;
2. saisie des taux 2025 réels dans `config/fx.yaml` (les valeurs actuelles sont
   des **placeholders** explicitement marqués) ;
3. exécution avec `--reference "EC+/2025.xlsx"` (ou dépôt du classeur de
   référence dans l'interface) : comparaison ligne à ligne, contrôle **C9** et
   onglet *Rapprochement* — **l'outil est prêt** ;
4. analyse et documentation de chaque écart ;
5. arbitrage : écart imputable à l'application, ou à une règle mal reconstituée.

Charge : 2 à 4 jours selon le volume d'écarts. **C'est ici que se joue la
fiabilité du projet.**

### Étape 2 — Validation des règles en hypothèse *(bloquée : §6 P1)*

Chaque réponse aux questions P1 se traduit par une modification de configuration
et un test de non-régression :

| Question | Fichier à ajuster |
|---|---|
| Q-6.1, Q-6.3 | `fx.yaml` → `rate_policy`, `historical_lines` |
| Q-6.4 | `fx.yaml` → `translation_difference_line` |
| Q-7.1, Q-7.4 | `eliminations.yaml` |
| Q-2.3, Q-2.4 | `entities.yaml` → `method`, `ownership` |
| Q-5.1 | `cost_centers.yaml` → `allocation` |

Charge : 1 à 2 jours après réception des réponses.

### Étape 3 — Ventilation analytique des filiales *(bloquée : Q-5.4)*

L'état par centre de coûts est produit, mais non ventilé pour les filiales : leurs
management accounts ne portent pas d'axe analytique. Trois scénarios selon votre
réponse :

- l'axe existe dans un onglet non analysé → extension du lecteur, ~1 jour ;
- un magasin = une entité de reporting → règle de correspondance, ~0,5 jour ;
- la ventilation est saisie manuellement en consolidation → prévoir un fichier
  de ventilation en entrée, ~2 jours.

### Étape 4 — Intégration des méthodes de consolidation

Mise en équivalence, intérêts minoritaires, quote-part. Nécessite Q-2.3 / Q-2.4.
Les lignes `Non-controlling interest B/S` et `P/L` existent déjà dans les états
(à 0 en 2025) ; le moteur applique aujourd'hui l'intégration globale à 100 %.

Charge : 2 à 3 jours.

### Étape 5 — Consolidation multipériode

Le modèle porte déjà `Period` sur chaque ligne, et les colonnes mensuelles des
sources sont lues. Reste à agréger et restituer 12 colonnes plutôt qu'une, avec
les comparatifs N-1. Dépend de Q-8.1.

Charge : 3 à 4 jours.

### Étape 6 — Interface utilisateur *(faite en 0.2)*

Interface locale livrée (`mageconso ui`). Évolutions possibles selon Q-11.1 /
Q-12.1 : accès multi-utilisateurs sur un serveur, droits par entité.

### Étape 7 — Extensions fonctionnelles

Par ordre de valeur décroissante :

1. tableau de flux de trésorerie, méthodes directe et indirecte (Q-10.4) — 4 à 6 j ;
2. ~~analyse de marge par famille~~ — faite en 0.2 ;
3. génération de la liasse fiscale depuis `liasse_fiscale.csv` — 3 j ;
4. reprise des flux `PRI MAGE` / `PRI SICCA` — à cadrer (Q-7.7, Q-13.3).

## 9.3 Chemin critique

```
Q-0.1 (fichiers 2025) ──► Étape 1 (rapprochement) ──► mise en production
        │
§6 P1 (règles) ────────► Étape 2 (validation)  ──────┘
        │
Q-5.4 (analytique) ────► Étape 3 ──► état par centre de coûts complet
```

Les étapes 4 à 7 sont des extensions : elles ne conditionnent pas la mise en
service des deux états demandés.

## 9.4 Recommandation

Ne pas mettre en production avant l'étape 1. Le prototype est complet et
cohérent, mais **sa conformité aux états Mage n'est pas encore démontrée** : elle
l'est seulement sur un jeu de test contrôlé. Un moteur de consolidation dont on
n'a pas vérifié qu'il retrouve les chiffres connus n'est pas utilisable pour
produire des états financiers.

Ordre suggéré : fournir les fichiers → rapprocher → arbitrer les écarts →
répondre aux questions P1 → mise en service sur une clôture en double avec le
processus Excel actuel → bascule.
