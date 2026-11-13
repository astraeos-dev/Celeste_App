# Architecture

Le projet suit le modèle **modèle-vue-contrôleur** : le moteur calcule, l'interface affiche.

| Fichier | Rôle |
|---|---|
| [`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py) | **Modèle** : `AstroEngine`, calculs purs (positions, levers, éclipses, évènements…), sans Qt |
| [`gui.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/gui.py) | **Vue et contrôleur** : la fenêtre `AstroApp` (panneau latéral, lieu, date, calcul, historique), assemblée à partir des espaces de `ui/` |
| [`ui/`](https://github.com/astraeos-dev/Celeste_App/tree/master/ui) | Un module par espace de l'interface : `tonight.py` (Ce soir), `sky.py` (Ciel), `bodies.py` (Astres), `calendar_tab.py` (Calendrier), `observe.py` (Observer, Atelier), `journal_tab.py` (Observer › Journal), `settings_tab.py` (Réglages) ; `common.py` réunit les composants Astræos, les formats et les widgets partagés |
| [`qt.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/qt.py) | La bibliothèque Qt : PySide6, ou PyQt6 en secours (`CELESTE_QT=pyqt6`) ; tout le code importe Qt par `from qt.QtWidgets import …` |
| [`charts.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/charts.py) | Graphiques matplotlib : trajectoires, carte du ciel (et ses images rapides pour la barre de temps : étoiles tournées par le temps sidéral, `turned_places`), système solaire, cartes d'évènements ; `SYMBOL` |
| [`locales/`](https://github.com/astraeos-dev/Celeste_App/tree/master/locales) | Textes de l'interface : `fr.json` (référence), `en.json`, `es.json`, `de.json` |
| [`i18n.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/i18n.py) | `t("clé")`, `tf("clé", valeur=…)`, choix de la langue |
| [`updater.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/updater.py) | Mises à jour : dernière Release GitHub, téléchargement vérifié (SHA-256), installation silencieuse |
| [`places.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/places.py) | Recherche de lieu hors ligne : villes de GeoNames (`assets/cities.tsv.gz`), ville la plus proche d'un point |
| [`journal.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/journal.py) | Journal d'observation : les observations dans `~/.celeste/journal.json`, export CSV ; sans Qt (l'interface : `ui/journal_tab.py`) |
| [`night_quality.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/night_quality.py) | Qualité de la nuit : obscurité, Lune, nuages et humidité prévus par Open-Meteo (activés par l'utilisateur), classe de Bortle du lieu ; sans Qt |
| [`month_sheet.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/month_sheet.py) | Fiche du mois à imprimer : une page A4 (PDF) pour le lieu, la carte du ciel du 15 à 22 h, la Lune jour par jour, les planètes, les évènements du mois ; sans Qt (boutons : carte Ce soir, mois affiché par le calendrier) |
| [`variables.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/variables.py) | Étoiles variables : les minima d'Algol observables du lieu (éphéméride ajustée aux minima CCD de la base Lichtenknecker du BAV, temps de lumière compris), pour Ce soir et le calendrier ; sans Qt |
| [`planner.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/planner.py) | Onglet Cibles : cibles de la nuit selon les contraintes de l'observateur (d'après uptonight), masque d'horizon, rapport JSON |
| [`instruments.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/instruments.py) | Atelier : géométrie des instruments (carte tournante, cadrans solaires, astrolabe), sans Qt |
| [`workshop.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/workshop.py) | Atelier : pages PDF à l'échelle exacte et fiches d'explications ([fiche](Ajouter-un-instrument.md)) |
| [`mpc.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/mpc.py) | Comètes du Minor Planet Center : téléchargement hebdomadaire de `CometEls.txt`, orbites à deux corps, magnitudes |
| [`history.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/history.py) | Historique : les 20 derniers calculs (date, lieu, fuseau) dans `~/.celeste/history.json` |
| [`satellites.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/satellites.py) | Orbites des satellites (TLE) : téléchargement CelesTrak ou AMSAT, sommes de contrôle, copie dans `~/.celeste` |
| [`settings.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/settings.py) | Préférences enregistrées (`~/.celeste/settings.json`) et leurs valeurs par défaut |
| [`config.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/config.py) | Couleurs des thèmes Astræos, polices, **`APP_VERSION`** |
| [`star_catalog.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/star_catalog.py) | 8 404 étoiles jusqu'à la magnitude 6,5 (généré par `scripts/make_star_catalog.py`) |
| [`constellations.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/constellations.py) | Noms usuels des étoiles brillantes ; les tracés des 88 constellations sont dans `assets/constellations.json` (`scripts/make_constellations.py`, d'après d3-celestial) |
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
- **Lunes de Jupiter** : méthode simplifiée de Meeus (chap. 44), à 0,15 rayon de Jupiter de JPL Horizons au pire (`galilean_moons`).
  **Anneaux de Saturne** : pôle de Saturne de l'UAI et DE440 (`saturn_rings`), inclinaison à 0,0001° d'Horizons.
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
