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

La carte dessine les étoiles de
[`star_catalog.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/star_catalog.py) (8 404 étoiles jusqu'à
la magnitude 6,5, depuis la version 4.9) plus brillantes que la magnitude limite choisie, et écrit le nom des plus
brillantes (magnitude inférieure à 2) qui en ont un, sans chevaucher les autres étiquettes.

- Le fichier est **généré** par `scripts/make_star_catalog.py` depuis le Yale Bright Star Catalogue : les noms
  viennent de `constellations.STARS` et de ceux déjà présents dans `star_catalog.py`.
- Pour nommer une étoile, ajoutez-la à `STARS` dans
  [`constellations.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/constellations.py) (nom, ascension
  droite, déclinaison, magnitude), puis régénérez le catalogue :

  ```bash
  python scripts/make_star_catalog.py catalog.gz
  ```

  (`catalog.gz` : le catalogue tel que le CDS le distribue, <https://cdsarc.cds.unistra.fr/ftp/V/50/catalog.gz>, ou
  un miroir VizieR.)

- La limite de magnitude est `MAG_LIMIT` dans le script : le catalogue s'arrête à 6,5, l'œil nu aussi.

## Les tracés des constellations

Les figures des 88 constellations sont dans `assets/constellations.json`, tirées de d3-celestial (licence BSD) par
`scripts/make_constellations.py` ; leurs noms sont dans la section `constellations` des fichiers de `locales/`,
par abréviation de l'UAI (`"Ori"`, `"UMa"`).
