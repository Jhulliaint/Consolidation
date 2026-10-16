# Collecte des management accounts par Make

Chantier C-A (`docs/09-plan-developpement.md`). Make relève la boîte mail et
dépose les fichiers. L'application lit ensuite le dossier de collecte
(`mageconso collect`).

## Ce qui tourne

Organisation Make 937102 (zone eu2), équipe 119554.

| Objet | ID | Détail |
|---|---|---|
| Scénario « Consolidation - Collecte MA Mage Japon » | 9984770 | dossier Outlook « Mage Japon » ; expéditeurs `forvismazars.com` |
| Scénario « Consolidation - Collecte MA Mage Asia Pacific » | 9986367 | dossier « Mage Asia Pacific / Accounting » ; expéditeurs `atac.com.hk`, `forvismazars.com` |
| Data store « Collecte management accounts » | 197179 | structure 643807 ; clé = identifiant du message Outlook |
| Connexion Microsoft | 14526401 | « Julien's Microsoft connection » (office@corthay.com) — Outlook et OneDrive |

Planification : toutes les 2 heures (`indefinitely`, 7 200 s). Make n'admet qu'un
déclencheur par scénario, d'où un scénario par dossier Outlook.

## Déroulé d'un scénario

```
1 Outlook - surveiller le dossier     (par date de DERNIÈRE MODIFICATION, 20 e-mails par passage)
      | filtre : expéditeur d'un cabinet ET pièce jointe présente
2 Data store - e-mail déjà traité ?   (clé = id du message)
      | filtre : jamais traité
3 Outlook - lister les pièces jointes
      | filtre : nom en .xlsx / .xlsm, pièce jointe non incorporée
4 OneDrive - déposer le fichier       /CORTHAY/CLOTURE MENSUELLES/AAAA/MM/
                                      "AAAAMMJJ-hhmmss - ENTITE - nom d'origine.xlsx"
                                      (nom déjà pris -> renommé, jamais écrasé)
5 Data store - journal                entité, expéditeur, objet, réception, fichier, dossier, traitement
```

- **Date de dernière modification** plutôt que date de réception : les e-mails
  sont classés à la main dans les dossiers, parfois des semaines plus tard. Un
  déplacement modifie l'e-mail, qui est donc repris au passage suivant.
- Année, mois et horodatage du nom proviennent de la **réception** de l'e-mail
  (fuseau du compte Make). La période comptable n'est pas lisible à ce stade.
  L'application la relit dans la feuille *Cover*.
- Make copie toutes les pièces jointes Excel des cabinets, y compris les relevés
  bancaires et les états de paie. Le tri est fait par l'application, qui écarte
  tout classeur sans balance (*Trial balance*), avec le motif.
- Un e-mail dont aucune pièce jointe n'est un classeur Excel n'est pas journalisé.
  Il n'est pas retraité pour autant : le déclencheur ne le présente qu'une fois.

## Modifier un scénario

Les blueprints sont générés, pas écrits à la main :

```bash
cd integrations/make
python build_blueprints.py        # -> blueprint_mage_asia_pacific.json, blueprint_mage_japon_kk.json
```

Ajouter un expéditeur ou un dossier : modifier `SCENARIOS` dans
`build_blueprints.py`, régénérer, puis importer le blueprint dans Make
(*Scenario → … → Import blueprint*) sur le scénario existant. Cela conserve son
historique et la position de son déclencheur.

## Surveiller

- Historique d'exécution des deux scénarios dans Make : un échec est notifié par
  e-mail au propriétaire. Après 3 erreurs consécutives, le scénario est désactivé.
- Journal de collecte : data store 197179 (un enregistrement par e-mail traité).
- Retraiter un e-mail : supprimer son enregistrement dans le data store, puis le
  déplacer hors du dossier Outlook et l'y remettre.
