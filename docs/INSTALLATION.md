# Documentation d'installation

## Prérequis

- **Python 3.10 ou plus récent** (`python --version`)
- Aucune base de données, aucun serveur, aucun accès réseau.

Sous Windows, installer Python depuis [python.org](https://www.python.org/downloads/)
en cochant **« Add python.exe to PATH »**.

## Installation

```bash
git clone <url-du-depot> Consolidation
cd Consolidation

python -m venv .venv
# Windows :
.venv\Scripts\activate
# macOS / Linux :
source .venv/bin/activate

pip install -e .
```

Deux dépendances seulement : `openpyxl` (Excel) et `PyYAML` (configuration).
L'interface graphique n'en ajoute aucune : elle s'appuie sur le serveur HTTP de
la bibliothèque standard, écoute uniquement sur `127.0.0.1` et ne charge aucune
ressource externe.

## Vérification

```bash
# 1. générer un jeu de démonstration
python samples/make_samples.py samples/data

# 2a. interface graphique
mageconso ui

# 2b. ou ligne de commande
mageconso consolidate "samples/data/*.xlsx" -o out/demo.xlsx --by-cost-centre
```

Sortie attendue de la ligne de commande :

```
  lu : MA - Mage Japon KK 2025.xlsx  -> MAGE_JAPON_KK (10 lignes, JPY)
  lu : MA - Mage SAS 2025.xlsx  -> MAGE_SAS (15 lignes, EUR)

--- Synthese ---
  Revenue                         :        1 646 673 €
  ...
  Total assets                    :          917 359 €

  11/11 controles OK
```

Si les 11 contrôles passent, l'installation est fonctionnelle. Vérifiez aussi le
paramétrage :

```bash
mageconso check
```

## Tests

```bash
pip install -e ".[dev]"
python -m pytest -q
```

Attendu : `97 passed`.

## Sans installation

L'application fonctionne aussi sans `pip install` :

```bash
pip install openpyxl PyYAML
PYTHONPATH=src python -m mageconso.cli consolidate "..." -o out/etats.xlsx
```

Sous Windows PowerShell :

```powershell
$env:PYTHONPATH="src"
python -m mageconso.cli consolidate "..." -o out\etats.xlsx
```

## Arborescence

```
Consolidation/
├── config/            paramétrage — c'est ici qu'on ajuste les règles
│   ├── entities.yaml          périmètre de consolidation
│   ├── cost_centers.yaml      axe analytique
│   ├── fx.yaml                taux de change
│   ├── eliminations.yaml      éliminations intragroupe
│   ├── presentation.yaml      affichage des nombres
│   ├── source_format.yaml     détection des fichiers sources
│   ├── coa/                   plan de comptes et structure des états
│   └── mapping/               correspondances compte local → compte groupe
├── src/mageconso/     code de l'application
├── tests/             tests automatisés
├── samples/           générateur de données de démonstration
├── docs/              analyse, règles, questions, architecture
└── out/               sorties (non versionné)
```

## Avant la première utilisation réelle

Deux points impératifs.

**1. Renseigner les taux de change.** Le plus simple : `mageconso rates … -o
taux.xlsx` produit le fichier à compléter, passé ensuite avec `--rates` (ou
saisissez les taux à l'étape 2 de l'interface). `config/fx.yaml` contient pour
2025 des valeurs de **démonstration**, explicitement marquées :

```yaml
  # A REMPLACER PAR LES TAUX REELS DE LA CLOTURE 2025.
  "2025-12-31":
    eom:
      JPY: 156.3300
```

Il faut y saisir les taux EOM et moyens réels de chaque devise (AED, GBP, HKD,
JPY, KRW, ZAR, CNY), source `banque-france.fr` comme dans les classeurs actuels.
Si un taux manque, l'application **refuse de convertir** et signale une erreur
bloquante (contrôle C8) plutôt que de produire un montant faux.

**2. Lire les règles en hypothèse.** Plusieurs règles sont déduites et non
confirmées, chacune marquée `[HYPOTHÈSE]` dans les fichiers de configuration et
reliée à une question de `docs/06-questions-clarification.md`. Les plus
sensibles : imputation de l'écart de conversion, taux applicable au capital,
éliminations à 100 %, méthodes de consolidation.

## Mise à jour

```bash
git pull
pip install -e .
python -m pytest -q
```

Le paramétrage étant dans `config/`, une mise à jour du code ne modifie pas vos
règles — sauf mention explicite dans le message de commit.
