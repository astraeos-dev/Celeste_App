# Architecture

Le projet suit le modèle **modèle-vue-contrôleur** : le moteur calcule, l'interface affiche.

| Fichier | Rôle |
|---|---|
| [`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py) | **Modèle** : `AstroEngine`, calculs purs (positions, levers, éclipses, évènements…), sans Qt |
| [`gui.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/gui.py) | **Vue et contrôleur** : fenêtre PyQt6, onglets, tableaux, fiches |
| [`charts.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/charts.py) | Graphiques matplotlib : trajectoires, carte du ciel, système solaire, cartes d'évènements ; `SYMBOL` |
| [`locales/`](https://github.com/astraeos-dev/Celeste_App/tree/master/locales) | Textes de l'interface : `fr.json` (référence), `en.json`, `es.json`, `de.json` |
| [`i18n.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/i18n.py) | `t("clé")`, `tf("clé", valeur=…)`, choix de la langue |
| [`updater.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/updater.py) | Mises à jour : dernière Release GitHub, téléchargement vérifié (SHA-256), installation silencieuse |
| [`places.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/places.py) | Recherche de lieu hors ligne : villes de GeoNames (`assets/cities.tsv.gz`), ville la plus proche d'un point |
| [`satellites.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/satellites.py) | Orbites des satellites (TLE) : téléchargement CelesTrak ou AMSAT, sommes de contrôle, copie dans `~/.celeste` |
| [`settings.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/settings.py) | Préférences enregistrées (`~/.celeste/settings.json`) et leurs valeurs par défaut |
| [`config.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/config.py) | Couleurs des thèmes Astræos, polices, **`APP_VERSION`** |
| [`star_catalog.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/star_catalog.py) | 513 étoiles brillantes (généré par `scripts/make_star_catalog.py`) |
| [`constellations.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/constellations.py) | Tracés des constellations |
| [`assets/minor_planets.npz`](https://github.com/astraeos-dev/Celeste_App/tree/master/assets) | Positions des planètes mineures (JPL Horizons, généré par `scripts/make_minor_planets.py`) |
| [`fonts/`](https://github.com/astraeos-dev/Celeste_App/tree/master/fonts) | IBM Plex et *Astraeos Symboles* (symboles des astres) |
| [`scripts/`](https://github.com/astraeos-dev/Celeste_App/tree/master/scripts) | Générateurs de données, construction de l'exécutable |
| [`installer/celeste.iss`](https://github.com/astraeos-dev/Celeste_App/blob/master/installer/celeste.iss) | Programme d'installation Windows (Inno Setup) |
| [`tests/`](https://github.com/astraeos-dev/Celeste_App/tree/master/tests) | Tests pytest : moteur, graphiques, interface, traductions |

## D'où viennent les positions

- **Soleil, Lune, planètes, Pluton** : éphéméride JPL DE440 (`de440s.bsp`, 1850–2149) lue par Skyfield. Elle est
  cherchée dans `data/`, puis dans `~/.celeste`, et téléchargée au premier lancement (`download_ephemeris()`,
  vérifiée par sa taille et son SHA-256). Elle n'est pas dans le programme d'installation, pour alléger les mises à jour.
- **Planètes mineures** (Cérès … Sedna) : table de JPL Horizons, position et vitesse tous les 10 ou 60 jours,
  interpolées par Hermite (`_TabulatedOrbit` dans `engine.py`).
- **Comètes** (C/2026 O1, 45P, C/2026 C1, 19P) : table de JPL Horizons tous les 2 jours, de 2025 à 2031 seulement
  (`assets/comets.npz`) ; hors de ces années, elles n'apparaissent pas ([fiche](Ajouter-une-comete.md)).
- **Étoiles** : Yale Bright Star Catalogue, ramenées à la date (mouvement propre, précession, nutation, aberration).
- **Objets de Messier** : `assets/messier.csv`, tiré d'OpenNGC (CC BY-SA 4.0) par `scripts/make_messier.py`, ramenés à
  la date comme les étoiles.
- **Satellites** : éléments orbitaux (TLE) téléchargés par `satellites.py`, propagés par SGP4 (Skyfield).
- **Étoiles filantes** : liste de travail de l'IMO (`METEOR_SHOWERS`) ; le maximum est l'instant où le Soleil atteint
  la longitude de la table, chaque année ([fiche](Ajouter-une-pluie-d-etoiles-filantes.md)).

Toutes les positions passent par **`AstroEngine._target(nom)`**, qui rend l'objet Skyfield d'un astre : c'est le
point d'entrée à connaître quand on ajoute un corps.

## Un calcul, de la saisie à l'écran

1. L'utilisateur saisit une date et un lieu ; `AstroApp.calculate()` (dans `gui.py`) lit les champs.
2. Elle appelle le moteur : `AstroEngine.planet_position()`, `horizontal()`, `observations()`, `find_events()`…
3. Les résultats sont rangés dans `self.sun_data`, `self.moon_data`, `self.planets`, `self.minor_planets`.
4. Les tableaux (`_update_planet_table`, `_refresh_coordinates`) et les graphiques (`charts.draw_*`) les affichent.

Les levers et couchers ne sont recalculés que si la date locale, le lieu ou le fuseau changent (cache
`last_cache_key`) : le mode temps réel reste léger.
