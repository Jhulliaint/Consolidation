# Documentation utilisateur

Deux façons d'utiliser l'application, qui produisent exactement les mêmes
chiffres :

- **l'interface graphique** (`mageconso ui`) — recommandée au quotidien ;
- **la ligne de commande** — pour l'automatisation et les tâches planifiées.

---

## 1. L'interface graphique

```bash
mageconso ui
```

Le navigateur s'ouvre sur `http://127.0.0.1:8765`. L'application tourne sur ce
poste : les fichiers ne sont envoyés nulle part, et elle fonctionne hors ligne.
`Ctrl+C` dans la fenêtre de commande pour l'arrêter.

### Étape 1 — Fichiers

Déposez les *management accounts* de la clôture (glisser-déposer ou clic).
Pour chaque fichier, l'application affiche aussitôt :

| Colonne | À vérifier |
|---|---|
| **Entité** | reconnue d'après la feuille *Cover*. Si elle ne l'est pas, la liste est en rouge : choisissez l'entité. |
| **Devise**, **Période** | cohérentes avec la clôture |
| **Balance** | ✓ *équilibrée* — sinon le fichier source est en cause |

Une même entité déposée deux fois est signalée : un seul fichier serait retenu.

**Classeur de référence (facultatif).** Déposez un classeur consolidé déjà
produit (format EC+) pour comparer les états ligne à ligne. Indispensable lors
de la première utilisation sur une clôture réelle — voir §5.

### Étape 2 — Taux et options

**Taux.** Une ligne par devise à convertir, en cotation indirecte comme dans les
classeurs Mage : **1 EUR = X devise**.

| Aspect de la case | Signification |
|---|---|
| normale | taux déjà connu pour cette clôture |
| **surlignée** | pré-remplie avec le **dernier taux connu** : à remplacer par le taux de la clôture |
| **rouge** | taux manquant ou manifestement faux |

Le bouton **Consolider** reste inactif tant qu'un taux manque ou semble inversé
(0,0064 au lieu de 156,33 pour le yen). Un écart de plus de 30 % avec le dernier
taux connu est signalé sans bloquer (décimale déplacée ?).

*Modèle de taux (Excel)* télécharge un fichier pré-rempli, utile pour préparer
les taux à l'avance ou les faire valider.

**États à produire.** Colonnes par entité (conseillé), états par centre de
coûts, analyse de marge par famille.

**Présentation.** Unité, décimales, négatifs, zéros, position du symbole €,
% du chiffre d'affaires. L'aperçu se met à jour en direct.
La présentation ne modifie jamais les montants : le classeur Excel contient les
valeurs exactes.

### Étape 3 — Résultats

**Le bandeau de statut** dit d'abord si les états sont diffusables :

| Bandeau | Signification |
|---|---|
| vert — *Tous les contrôles sont satisfaits* | diffusable |
| orange — *points à examiner* | contrôles bloquants satisfaits, avertissements à lire |
| rouge — *Ne pas diffuser* | au moins un contrôle bloquant en échec ; l'onglet *Contrôles* s'ouvre automatiquement |

**Les onglets**

| Onglet | Contenu |
|---|---|
| Bilan / Compte de résultat | synthèse ou détail ; *Masquer les lignes à zéro* allège le détail |
| Par entité | une colonne par entité, éliminations, total |
| Par centre de coûts | si demandé à l'étape 2 |
| Marges | marge brute par famille de produits |
| Contrôles | les 10 contrôles, avec leur détail |
| Diagnostics | erreurs et avertissements, filtrables |
| Mapping à compléter | comptes exclus faute de correspondance, avec suggestions |
| Rapprochement | si un classeur de référence a été fourni |
| Sources et taux | fichiers consolidés et taux effectivement appliqués |

**Justifier un montant.** Cliquez sur n'importe quel montant d'un état : un
panneau liste les lignes sources qui le composent — fichier, onglet, numéro de
ligne, compte local, montant d'origine, taux — et leur total, égal au montant
cliqué. Fonctionne aussi colonne par colonne dans les vues par entité.

**Télécharger le classeur Excel** en haut à droite.

---

## 2. La ligne de commande

```bash
mageconso inspect      "MA - *.xlsx"                  # examiner les fichiers
mageconso rates        "MA - *.xlsx" -o taux.xlsx     # préparer le fichier de taux
mageconso consolidate  "MA - *.xlsx" --rates taux.xlsx -o out/consolide.xlsx
mageconso check        --closing 2025-12-31           # vérifier le paramétrage
mageconso trace        --journal out/audit.db --run 1 --account "Cash Bank"
```

### Examiner les fichiers

```bash
mageconso inspect "G:/CORTHAY/CLOTURE MENSUELLES/2025/MA - *.xlsx"
```

Pour chaque fichier : entité reconnue, devise, période, feuilles (y compris
masquées), équilibre de la balance ; puis les taux nécessaires à la clôture, en
indiquant ceux qui manquent.

### Préparer les taux

```bash
mageconso rates "MA - *.xlsx" -o taux.xlsx
```

Produit un fichier *devise ; clôture ; moyen ; historique* pour les seules
devises utiles, pré-rempli avec les derniers taux connus (cellules surlignées à
remplacer). Excel ou CSV ; en-têtes français ou anglais ; virgule décimale
acceptée.

### Consolider

```bash
mageconso consolidate "MA - *.xlsx" --rates taux.xlsx -o out/consolide-2025.xlsx \
    --by-cost-centre --journal out/audit-2025.db
```

| Option | Rôle |
|---|---|
| `--rates FICHIER` | taux de la clôture |
| `--closing AAAA-MM-JJ` | date de clôture (défaut : lue dans les fichiers) |
| `--reference FICHIER` | rapprochement ligne à ligne avec un classeur consolidé |
| `--tolerance 1` | tolérance du rapprochement, en euros |
| `--by-cost-centre` | ajoute les états par centre de coûts |
| `--no-by-entity` | supprime les états par entité |
| `--entity "fichier.xlsx=CODE"` | force l'entité d'un fichier non reconnu (répétable) |
| `--journal FICHIER.db` | piste d'audit interrogeable (nécessaire pour `trace`) |
| `--scale`, `--decimals`, `--negatives`, `--currency-position` | présentation ponctuelle |
| `--open` | ouvre le classeur produit |
| `--strict` | code retour 1 si un contrôle bloquant échoue (tâches planifiées) |
| `--force` | consolide même si des taux manquent |

**Si un taux manque**, la commande s'arrête et indique quoi faire :

```
Taux de change manquants au 2025-12-31 :
  JPY : eom, average

Preparez un fichier de taux pre-rempli :
  mageconso rates 'MA - Mage Japon KK 2025.xlsx' ... -o taux.xlsx
puis relancez avec --rates taux.xlsx  (ou --force pour continuer quand meme).
```

**Si des comptes ne sont pas mappés**, un CSV de propositions est écrit à côté
du classeur (`… - mapping a completer.csv`).

### Vérifier le paramétrage

```bash
mageconso check --closing 2025-12-31
```

À lancer après toute modification de `config/` : libellés orphelins, doublons,
cibles de mapping inconnues, libellés d'élimination inexistants, taux manquants.

---

## 3. Le classeur produit

| Onglet | Contenu |
|---|---|
| **Synthèse** | statut diffusable, chiffres clés, sources, taux appliqués, contrôles — **à lire en premier** |
| Consolidated BS / PL | états de synthèse (le P&L avec sa colonne %) |
| Detailed BS / PL | états ligne à ligne |
| BS / PL by entity | une colonne par entité, ELIMINATION, TOTAL |
| BS / PL by cost center | si demandé |
| Gross margin | marge brute par famille de produits |
| Rapprochement | si un classeur de référence a été fourni |
| Mapping à compléter | si des comptes ont été exclus |
| Controls, Diagnostics, Audit trail | onglets techniques, filtrables |

Les cellules contiennent la **valeur exacte** ; l'échelle (milliers, millions)
est portée par le format de nombre. Un montant copié ou recalculé dans Excel
reste donc juste. Excel applique ses propres séparateurs (ceux du poste).

---

## 4. Les contrôles

| Code | Contrôle | Bloquant | Si en échec |
|---|---|---|---|
| C1 | Bilan équilibré | oui | Souvent la conséquence d'un compte exclu (voir C5) : l'écart affiché égale le montant manquant. |
| C2 | Résultat du P&L = résultat porté au bilan | oui | Incohérence entre les deux états. |
| C3 | Balances sources équilibrées | oui | Le fichier source est en cause. |
| C4 | Éliminations équilibrées | non | Une élimination sans contrepartie. |
| C5 | Tous les comptes sources sont mappés | oui | Voir l'onglet *Mapping à compléter*. |
| C6 | Centres de coûts connus | non | Déclarer le centre dans `cost_centers.yaml`. |
| C7 | Même date de clôture pour tous les fichiers | non | Des fichiers de périodes différentes ont été mélangés. |
| C8 | Taux disponibles | oui | Compléter les taux. |
| C9 | Rapprochement à la référence | oui | Voir l'onglet *Rapprochement*. |
| C10 | Tout montant consolidé figure dans un état | oui | Un compte (souvent intragroupe non éliminé) n'est présenté nulle part. |

**Un contrôle bloquant en échec signifie que les états ne doivent pas être
diffusés.**

### Diagnostics fréquents

| Code | Signification | À faire |
|---|---|---|
| `MAP-UNKNOWN-ACCOUNT` | compte source non mappé, **exclu** | reporter la correspondance (suggestion fournie) |
| `MAP-STATEMENT-UNKNOWN` | compte groupe sans état (bilan ou résultat ?) | l'ajouter à `config/coa/group_coa.csv` |
| `ELIM-RECIPROCITY` | les deux côtés d'un intragroupe ne concordent pas | écart de change ou de date à justifier ; il est porté sur la ligne de résidu |
| `ELIM-ONE-SIDED` | flux intragroupe sans contrepartie, non éliminé | justifier, ou déclarer la contrepartie dans `eliminations.yaml` |
| `ENT-DUPLICATE` | même entité dans deux fichiers | retirer le doublon |
| `FX-RATE-INVERTED` / `FX-RATE-SUSPECT` | taux vraisemblablement faux | vérifier la saisie |
| `CC-NOT-PROVIDED` | pas d'axe analytique dans la source | normal pour les filiales aujourd'hui (Q-5.4) |

---

## 5. Première mise en service : le rapprochement

Avant d'utiliser l'application pour une clôture réelle, consolidez une clôture
**déjà produite** par le processus Excel et comparez :

```bash
mageconso consolidate "2025/MA - *.xlsx" --rates taux-2025.xlsx \
    --reference "ANALYSE/EC+/2025.xlsx" -o out/rapprochement-2025.xlsx
```

ou, dans l'interface, déposez le classeur EC+ comme *classeur de référence*.

L'onglet **Rapprochement** liste chaque poste — référence, calculé, écart —
trié par écart décroissant. Chaque écart doit être expliqué : erreur de
l'application, ou règle métier mal reconstituée (voir
`docs/06-questions-clarification.md`). Les postes les plus exposés sont
identifiés dans `docs/10-rapport-rapprochement.md` §10.6.

---

## 6. Ajuster les règles

| Besoin | Fichier |
|---|---|
| Entités du périmètre | `config/entities.yaml` |
| Taux (alternative au fichier `--rates`) | `config/fx.yaml` |
| Correspondance d'un compte | `config/mapping/<entité>.csv`, ou feuille *Mapping accounts* du fichier source (prioritaire) |
| Couples d'élimination, lignes de résidu | `config/eliminations.yaml` |
| Regroupements de postes | `config/coa/statement_bs.yaml` / `statement_pl.yaml` |
| Familles de marge | `config/coa/statement_pl.yaml`, `margin_families` |
| Centres de coûts | `config/cost_centers.yaml` |
| Présentation par défaut | `config/presentation.yaml` |

Après chaque modification : `mageconso check`.

> **Attention aux libellés** : la clé de consolidation est le *libellé* du compte
> groupe, et certains comportent des fautes présentes dans les fichiers Mage
> (`Stock shoes subsisdairies`, `Mage Asia Pacfic`). Ne les corrigez pas d'un seul
> côté : la correspondance serait rompue (C5 le signalerait).

---

## 7. Clôture mensuelle — marche à suivre

1. Rassembler les management accounts de la période.
2. `mageconso ui` et déposer les fichiers — toutes les balances doivent être
   équilibrées et toutes les entités reconnues.
3. Saisir les taux de la clôture (source banque-france.fr).
4. Consolider. Bandeau vert ? Sinon, traiter l'onglet *Contrôles*, puis
   *Mapping à compléter* et *Diagnostics*.
5. Rapprocher des états de la clôture précédente ; justifier les variations en
   cliquant sur les montants.
6. Télécharger et archiver le classeur (et le journal `.db` si la ligne de
   commande a été utilisée avec `--journal`).
