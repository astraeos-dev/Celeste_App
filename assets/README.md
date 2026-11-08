# Images de l'interface

## Logo Astræos

Fichiers SVG du groupe Logos du design system Astræos, copiés sans modification :

| Fichier | Usage dans Céleste |
|---|---|
| `astraeos-icone.svg` | Icône de la fenêtre et de la barre des tâches |
| `astraeos-symbole-nuit.svg` | Symbole de l'en-tête ; `icons.py` remplace à l'affichage l'encre `#e8ecf2` et l'étoile `#f2b84b` par les couleurs `encre` et `or` du thème actif |

Règles du design system : l'étoile reste en `or` et à sa place, jamais d'ombre, de contour,
de dégradé ni de déformation ; symbole d'au moins 20 px de haut.

## Icônes

Les icônes des actions viennent de [Material Design Icons](https://pictogrammers.com/library/mdi/)
(paquet `@mdi/js` 7.4.47), recopiées dans `icons.py`. Licence : Pictogrammers Free License,
icônes sous licence Apache 2.0 — voir `LICENSE-MDI.txt`.

## Fond de carte du monde

`world_land.json` : contours des terres de **Natural Earth** au 1/110 000 000 (naturalearthdata.com, domaine public),
réduits à leur contour extérieur et à deux décimales ; fond de la carte des éclipses projetées au sol (`charts.py`).


## Villes

`cities.tsv.gz` : les 34 205 villes de plus de 15 000 habitants de **GeoNames** (`cities15000`, www.geonames.org,
licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), réduites par `scripts/make_cities.py` : nom,
autres noms en écriture latine (villes de plus de 100 000 habitants), pays, région, coordonnées, altitude,
population. Elles servent à la recherche de lieu par son nom (`places.py`) et à nommer un point sans réseau.

## Comètes

`comets.npz` : positions et vitesses héliocentriques (ICRF, UA, TDB) des comètes suivies, tous les 2 jours de 2025 à
2031, et leurs paramètres de magnitude M1, K1 ; tirées de **JPL Horizons** et de la Small-Body Database par
`scripts/make_comets.py`. Voir la fiche du wiki « Ajouter une comète ».

## Messier catalogue

`messier.csv`: the 110 Messier objects (type, J2000 coordinates, visual magnitude, apparent size, English common
name), extracted by `scripts/make_messier.py` from **OpenNGC** (github.com/mattiaverga/OpenNGC, fixed commit),
© Mattia Verga, licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This file is shared under
the same licence. Seven magnitudes OpenNGC lacks (M22, M35, M62, M69, M70, M71, M107) come from the SEDS Messier
database (messier.seds.org); M102 is taken to be NGC 5866.
