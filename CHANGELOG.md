# Journal des modifications

## 0.2.0 — Revue de l'application : fiabilité, ergonomie, fonctionnalités

### Défauts corrigés

Cinq défauts de calcul ont été trouvés à la revue. Chacun a été **reproduit
avant d'être corrigé**, puis verrouillé par un test de non-régression
(`tests/test_robustness.py`, `tests/test_features.py`).

| # | Défaut | Conséquence | Correction |
|---|---|---|---|
| D-1 | Un écart de réciprocité intragroupe n'était pas compensé. | Un écart de **17 €** (change, décalage d'enregistrement — cas quotidien) suffisait à **déséquilibrer le bilan consolidé** (C1 en échec). | Les deux côtés restent éliminés à 100 % ; l'écart est porté sur une ligne de résidu paramétrable (`residual_lines`), si bien que toute écriture d'élimination s'équilibre. L'écart est signalé (`ELIM-RECIPROCITY`) et tracé. |
| D-2 | Un flux intragroupe sans contrepartie était éliminé quand même. | Des *management fees* facturés par la mère **disparaissaient du chiffre d'affaires** (−40 k€ dans le test) et le résultat ne correspondait plus au bilan (C2). | Non éliminé par défaut (`one_sided: warn`), signalé avec son montant (`ELIM-ONE-SIDED`). Option `eliminate` pour forcer, avec écriture équilibrée. |
| D-3 | Un compte non mappé était absorbé comme écart de conversion. | L'écart de conversion était calculé comme « ce qui manque pour équilibrer » : un loyer de **175 000 € exclu** partait en réserves de consolidation — **y compris pour une entité en euros** — et le bilan paraissait équilibré. | Écart de conversion calculé **analytiquement** (seule la part due aux différences de taux). Un montant exclu reste visible : C1 échoue du montant exact. |
| D-4 | Un compte groupe inconnu du plan était classé d'office en compte de résultat. | Les **créances de MAGE SAS sur ses filiales** (`Account Receivable - subsidiary …`), absentes des états de référence, auraient été converties au taux moyen et comptées dans le résultat. Le défaut était masqué par le jeu de démonstration, qui porte son propre plan de comptes. | L'état (bilan / résultat) est déduit de la **classe PCG** des comptes locaux (classes 1-5 bilan, 6-7 résultat — norme légale) ; 267 comptes groupe désormais classés. Un compte encore inclassable est **exclu et signalé** (`MAP-STATEMENT-UNKNOWN`), jamais deviné. |
| D-5 | Les libellés de la configuration des éliminations étaient rapprochés au caractère près. | Un double espace dans un libellé (`Volney  UK`) faisait éliminer un montant de 0. | Rapprochement normalisé, comme partout ailleurs. |

Autres corrections :

- un même fichier ou une même entité chargés deux fois sont **rejetés** au lieu
  d'être additionnés (`ENT-DUPLICATE`) ;
- `--entity` s'appliquait à *tous* les fichiers : il prend désormais la forme
  `--entity "fichier.xlsx=CODE"` (répétable) ;
- l'export Excel **divisait les valeurs** pour afficher les milliers : les
  cellules contiennent maintenant la valeur exacte, l'échelle est portée par le
  format de nombre (`#,##0,"k"`) ;
- les montants des messages et contrôles sont lisibles (`175 000,00 EUR` au lieu
  de `174999.9999999999999999999993`).

### Nouvelles fonctionnalités

**Interface graphique locale** — `mageconso ui`

Parcours en trois étapes : dépôt des fichiers, taux et options, résultats.
Détection de l'entité et de l'équilibre de chaque balance au dépôt ; saisie des
taux pré-remplie avec le dernier taux connu ; aperçu en direct de la
présentation ; statut « diffusable / ne pas diffuser » ; **clic sur un montant →
lignes sources** (fichier, onglet, ligne, taux) dont le total égale le montant
cliqué. Aucune dépendance ajoutée, écoute sur `127.0.0.1` uniquement, aucune
ressource externe.

**Rapprochement à un classeur de référence** — `--reference`

Lit un classeur consolidé au format EC+ (y compris ses feuilles *very hidden*)
et compare chaque ligne des états détaillés. Onglet *Rapprochement* trié par
écart décroissant ; contrôle **C9** bloquant au-delà de la tolérance. C'est
l'outil de la première mise en service.

**Taux de change sans éditer de YAML** — `mageconso rates`, `--rates`

- fichier de taux (Excel ou CSV, en-têtes français ou anglais, virgule
  décimale) généré pré-rempli avec le dernier taux connu ;
- **pré-contrôle** : la consolidation s'arrête avec une consigne claire si un
  taux manque, au lieu de produire un classeur incomplet ;
- **détection des erreurs de saisie** : cotation inversée (0,0064 au lieu de
  156,33 pour le yen — bloquant) et décimale déplacée (écart > 30 % avec le
  dernier taux connu — avertissement).

**Suggestions de mapping**

Chaque compte non mappé est accompagné de trois propositions, apprises des
1 267 libellés déjà mappés (français, anglais, japonais) et d'un glossaire
comptable FR → EN : `Frais bancaires → Bank charges`, `Loyer entrepot → Rent`.
Onglet *Mapping à compléter* et CSV pré-rempli. Les suggestions ne sont jamais
appliquées automatiquement.

**Nouvelles vues**

- **par entité** : une colonne par entité, puis ÉLIMINATION et TOTAL — la
  disposition de la feuille *Conso … legal entity* de référence ;
- **% du chiffre d'affaires** au compte de résultat (écran et Excel) ;
- **marge brute par famille** (SLG, LG, SHOES, SNEAKERS, LOAFERS, BELT,
  BESPOKE, BESPOKE & SHOES), selon les regroupements des formules du classeur
  2025 ;
- le compte de résultat par centre de coûts bénéficie désormais de la cascade.

**Classeur Excel**

Feuille **Synthèse** en tête (statut diffusable, chiffres clés, sources, taux
appliqués, contrôles) ; noms d'entités en en-tête de colonne ; mise en page
d'impression ; filtres sur les onglets techniques.

**Vérification du paramétrage** — `mageconso check`

Références orphelines entre niveaux de détail et de synthèse, doublons, cascade
mal ordonnée, cibles de mapping inconnues, libellés d'élimination inexistants,
taux manquants pour une clôture. S'exécute sans fichier source.

**Contrôle C10** — tout montant consolidé figure dans un état

Un compte groupe absent de la structure des états (créance sur filiale non
éliminée, par exemple) disparaissait du rapport sans signal.

### Architecture

- `pipeline.py` : chaîne complète en une fonction, partagée par la ligne de
  commande et l'interface — les deux ne peuvent pas diverger ;
- `reports/` : un seul moteur de construction pour toutes les vues ;
- nouveaux modules : `rates.py`, `reconcile.py`, `suggest.py`, `checks.py`,
  `webui.py`.

### Tests

97 tests (44 auparavant), dont les scénarios d'incidents de clôture, le
rapprochement sur un classeur de référence synthétique à feuilles *very hidden*,
et l'API et la couche HTTP de l'interface graphique. L'interface a en outre été
parcourue dans un navigateur (Chromium) : flux nominal, taux inversé, compte non
mappé, référence avec écarts.
