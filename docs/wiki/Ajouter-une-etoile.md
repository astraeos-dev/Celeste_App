# Ajouter une étoile

Deux cas : une étoile pour les **rapprochements de la Lune** (onglet Évènements), ou une étoile **nommée sur la
carte du ciel**.

## Une étoile pour les rapprochements de la Lune

Aujourd'hui : Aldébaran, Alcyone (les Pléiades), Régulus, Spica et Antarès, les étoiles brillantes que la Lune
peut cacher. La Lune passe à moins de 5,3° de l'écliptique : une étoile plus éloignée (Pollux, à 6,7°) a des
rapprochements, jamais d'occultation.

1. Dans [`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py), ajoutez-la à
   `AstroEngine.MOON_STARS` : la **clé** est le nom de l'évènement, la **valeur** le nom de l'étoile dans
   `star_catalog.CATALOG` :

   ```python
   MOON_STARS = {"Aldebaran": "Aldebaran", "Pleiades": "Alcyone", "Regulus": "Regulus",
                 "Spica": "Spica", "Antares": "Antares", "Pollux": "Pollux"}
   ```

   Vérifiez que l'étoile est bien nommée dans le catalogue :
   `python -c "from star_catalog import CATALOG; print([c for c in CATALOG if c[6] == 'Pollux'])"`.

2. Dans les quatre `locales/*.json`, section `events`, ajoutez `"star_pollux": "Pollux"` (la clé est
   `star_` + la clé de `MOON_STARS` en minuscules).

3. Testez : `tests/test_engine.py`, `TestMoonAndSeasons.test_moon_and_bright_stars` vérifie l'ensemble des
   étoiles trouvées ; ajoutez une conjonction de référence si possible.

Chaque étoile ajoute environ treize rapprochements par an : restez sobre.

## Une étoile nommée sur la carte du ciel

La carte dessine les 513 étoiles de magnitude inférieure à 4 de
[`star_catalog.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/star_catalog.py) et écrit le nom des
plus brillantes (magnitude inférieure à 2) qui en ont un, sans chevaucher les autres étiquettes.

- Le fichier est **généré** par `scripts/make_star_catalog.py` depuis le Yale Bright Star Catalogue : les noms
  viennent des notes du catalogue et de `constellations.STARS` (les étoiles des figures).
- Pour nommer une étoile, ajoutez-la à `STARS` dans
  [`constellations.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/constellations.py) (nom, ascension
  droite, déclinaison, magnitude), puis régénérez le catalogue :

  ```bash
  python scripts/make_star_catalog.py bsc5.json . star_catalog.py
  ```

  (`bsc5.json` : le catalogue complet au format JSON, par exemple celui du dépôt `brettonw/YaleBrightStarCatalog`.)

- Pour une étoile plus faible que la magnitude 4, il faut d'abord relever la limite du générateur, puis vérifier
  que la carte reste lisible et rapide.
