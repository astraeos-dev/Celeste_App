# Céleste — wiki

Céleste est une application de bureau (Python, PyQt6) qui calcule les positions du Soleil, de la Lune, des
planètes et des planètes mineures avec les éphémérides **JPL DE440** et **JPL Horizons**. Ce wiki rassemble des
**fiches pratiques** pour modifier l'application : chacune dit quels fichiers toucher, dans quel ordre, et
comment vérifier le résultat.

## Fiches

| Fiche | Pour… |
|---|---|
| [Architecture](Architecture.md) | se repérer : quel fichier fait quoi, d'où viennent les données |
| [Textes et infobulles](Textes-et-infobulles.md) | changer un libellé, une infobulle, un message ; ajouter un texte |
| [Ajouter une planète mineure](Ajouter-une-planete-mineure.md) | ajouter un astéroïde ou une planète naine (Hygie, Quaoar…) |
| [Ajouter une comète](Ajouter-une-comete.md) | suivre une comète de plus pendant son passage (tables JPL Horizons) |
| [Ajouter une étoile](Ajouter-une-etoile.md) | une étoile pour les rapprochements de la Lune, ou nommée sur la carte |
| [Ajouter une pluie d'étoiles filantes](Ajouter-une-pluie-d-etoiles-filantes.md) | une pluie de plus parmi les évènements (calendrier de l'IMO) |
| [Ajouter une langue](Ajouter-une-langue.md) | traduire l'interface dans une cinquième langue |
| [Tester ses modifications](Tester-ses-modifications.md) | lancer les tests, l'auto-test, vérifier contre JPL Horizons |
| [Publier une version](Publier-une-version.md) | numéro de version, tag, exécutable et programme d'installation Windows |

## Règles d'or

1. **Le moteur ne connaît pas l'interface** : les calculs vont dans `engine.py`, l'affichage dans `gui.py` et
   `charts.py`.
2. **Tout texte affiché passe par les traductions** (`locales/*.json`), dans les quatre langues à la fois.
3. **Pas d'emoji** dans l'interface : les symboles astronomiques viennent de la police *Astraeos Symboles*.
4. **Chaque valeur calculée se vérifie** contre une référence (JPL Horizons, USNO, NASA) dans un test.
5. Les tests passent avant chaque commit : `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/`.

Ces pages viennent du dossier [`docs/wiki`](https://github.com/astraeos-dev/Celeste_App/tree/master/docs/wiki) du
dépôt : c'est là qu'on les modifie, le wiki est mis à jour tout seul.
