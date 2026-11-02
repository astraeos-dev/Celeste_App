# ✨ Céleste — observatoire astronomique

> Application de bureau qui calcule et affiche la position du Soleil, de la Lune et des planètes, d'après les algorithmes de Jean Meeus.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-blueviolet)
![Matplotlib](https://img.shields.io/badge/Graphiques-Matplotlib-orange)
![Licence](https://img.shields.io/badge/Licence-MIT-green)
![CI](https://github.com/Greg50100/Celeste_App/actions/workflows/ci.yml/badge.svg)

**Projet actif** · fait partie de la famille Ganymede : [site web](https://greg50100.github.io/personnal-site/) ·
[application Android](https://github.com/Greg50100/Ganymede) · [Céleste pour Home Assistant](https://github.com/Greg50100/Celeste_HA)

---

## Présentation

Céleste calcule en temps réel — ou pour n'importe quelle date — la position du Soleil, de la Lune et de quatre planètes
(Vénus, Mars, Jupiter, Saturne), les événements du jour (lever, coucher, crépuscules), les phases de la Lune, les éclipses,
les conjonctions et les oppositions. Les résultats s'affichent dans une interface PyQt6 aux couleurs Catppuccin, sombre ou
claire, avec des graphiques interactifs et une carte du ciel.

**Fonctionnalités principales :**

- **Positions instantanées** — ascension droite, déclinaison, hauteur, azimut, distance
- **Événements du jour** — lever, coucher, culmination, durée du jour ; crépuscules civil (−6°), nautique (−12°) et astronomique (−18°)
- **Phase de la Lune** — nom de la phase, fraction éclairée, âge et distance de la Lune
- **Mode temps réel** — mise à jour automatique toutes les 2 s (réglable)
- **Géolocalisation automatique** — position et fuseau détectés via ip-api.com
- **Trajectoire sur 24 h** — courbes de hauteur sur un fond coloré selon le moment de la journée (jour, crépuscules, nuit),
  heure locale en haut, info-bulle au survol
- **Carte du ciel polaire** — zénith au centre, étoiles à la taille de leur magnitude, constellations, planètes ;
  info-bulle au survol et fiche détaillée au clic (constellation, magnitude, coordonnées)
- **Planètes** — tableau de Vénus, Mars, Jupiter et Saturne (coordonnées, distance, élongation, visibilité) et système
  solaire vu de dessus, en vue rapprochée et en vue d'ensemble
- **Prévision des éclipses** — type (totale, annulaire, hybride), rapport des diamètres, magnitude, durée de la phase centrale
- **Conjonctions et oppositions** — prochains événements planétaires
- **Équation du temps** — écart entre temps solaire vrai et temps solaire moyen
- **Favoris** — enregistrement des lieux (37 villes préchargées)
- **Fuseaux horaires** — conversion TU → heure locale par sélecteur UTC±N
- **Export PDF** — éphémérides du jour
- **Interface multilingue** — français, anglais, espagnol, allemand ; langue du système par défaut, changement immédiat
  dans les paramètres (ou `--lang`)
- **Thèmes** — Catppuccin Mocha, Frappé (sombres) et Latte (clair), appliqués sans redémarrer (ou `--theme`)
- **Raccourcis clavier** — `F5` calculer, `Ctrl+L` temps réel, `Ctrl+E` export PDF
- **Réglages persistants** — thème, langue, format de l'heure, lieu de démarrage, magnitude limite, intervalle temps réel
  (`settings.json`)

---

## Installation

Prérequis : Python 3.10 ou plus récent, et pip. PyQt6 embarque Qt ; sur un Linux minimal, Qt demande aussi quelques
bibliothèques système (`sudo apt install libegl1 libxkbcommon0` sous Debian ou Ubuntu).

```bash
git clone https://github.com/Greg50100/Celeste_App.git
cd Celeste_App
pip install -r requirements.txt
python main.py
```

Choix de la langue :

```bash
python main.py --lang fr   # français
python main.py --lang en   # anglais
python main.py --lang es   # espagnol
python main.py --lang de   # allemand
python main.py --theme latte   # thème clair (mocha, frape, latte)
```

Sans option, la langue suit celle du système (l'anglais si elle n'est pas traduite) ; la langue et le thème se changent
ensuite dans l'onglet ⚙️ Paramètres, sans redémarrer.

---

## Utilisation

| Champ | Description |
|-------|-------------|
| **Date et heure** | Format `JJ/MM/AAAA HH:MM:SS`, en temps universel (TU) ; la flèche ouvre un calendrier |
| **Latitude** | Degrés décimaux, positif = nord (ex. `48.85` pour Paris), point ou virgule |
| **Longitude** | Degrés décimaux, positif = est (ex. `2.35` pour Paris), point ou virgule |
| **Fuseau** | Décalage UTC±N appliqué aux heures des événements |
| **Favoris** | Choisir un lieu l'applique aussitôt ; 💾 enregistre le lieu saisi, 🗑 supprime le favori choisi |

Une coordonnée invalide s'encadre de rouge, sans fenêtre d'erreur. Changer la date recalcule tout au bout d'un instant.

**Boutons :**

- `🕒` — revient à l'instant présent
- `📍` — remplit la latitude, la longitude et le fuseau à partir de l'adresse IP
- `⚡ CALCULER` (`F5`) — lance les calculs pour la date et le lieu saisis
- `⏱ TEMPS RÉEL` (`Ctrl+L`) — suit l'heure actuelle (intervalle réglable dans les paramètres)
- `📄 EXPORTER EN PDF` (`Ctrl+E`) — exporte les éphémérides du jour en PDF

**Graphiques :**

- Survolez les courbes sur 24 h pour lire la hauteur à toute heure ; le fond suit la hauteur du Soleil
- La carte du ciel place le zénith au centre et l'horizon sur le cercle, le nord en haut ; le curseur règle la
  magnitude limite des étoiles
- Survolez un astre de la carte pour l'identifier, cliquez pour afficher sa fiche

---

## Architecture

Le projet suit le modèle **MVC (modèle-vue-contrôleur)** :

```
Celeste_App/
├── main.py              # Point d'entrée — options --lang / --theme, fenêtre Qt
├── engine.py            # Modèle — calculs astronomiques purs (MeeusEngine)
├── gui.py               # Vue + contrôleur — interface PyQt6 et logique applicative
├── charts.py            # Graphiques matplotlib — trajectoires, carte du ciel, système solaire
├── utils.py             # Utilitaires — formats HMS/DMS, noms des phases
├── config.py            # Configuration — palettes Catppuccin Mocha, Frappé et Latte
├── i18n.py              # Internationalisation — traductions par clé avec repli
├── settings.py          # Préférences persistantes (settings.json)
├── constellations.py    # Catalogue d'étoiles et tracés des constellations
├── export_pdf.py        # Export PDF des éphémérides
├── favorites.json       # Lieux préchargés (37 villes)
├── settings.json        # Préférences (générées automatiquement)
├── locales/             # Traductions (fr.json est la référence)
├── scripts/             # Scripts annexes (fiche haute précision Skyfield/INPOP)
├── requirements.txt     # Dépendances d'exécution
├── requirements-dev.txt # Dépendances de développement (pytest)
└── tests/               # Tests unitaires (moteur, graphiques, interface, i18n, utilitaires)
```

### Modèle : `MeeusEngine`

Moteur de calcul entièrement découplé : uniquement des méthodes de classe ou statiques, sans état interne.

| Méthode | Rôle |
|---------|------|
| `julian_day(dte)` | Jour julien (JJ) |
| `julian_century_j2000(dte)` | T en siècles juliens depuis J2000,0 |
| `sun_position(t)` | Longitude écliptique et distance du Soleil — série courte (~0,01°) |
| `sun_position_hp(t)` | Position du Soleil — VSOP87 tronquée (~1″) |
| `moon_position(t)` | Longitude, latitude et parallaxe de la Lune — Meeus ch. 47, ELP-2000/82 tronquée (~10″) |
| `moon_position_elp2000(t)` | Même calcul, avec la distance de la Lune |
| `ecliptic_to_equatorial(l, b, t)` | Écliptique → équatorial (AD, Déc) |
| `equatorial_to_horizontal(jd, lat, lon, ra, dec)` | Équatorial → horizontal (hauteur, azimut) |
| `elevation_correction(h, p)` | Réfraction atmosphérique et parallaxe |
| `find_events(dte, lat, lon, body)` | Lever, coucher, culmination, crépuscules |
| `planet_heliocentric(t, name)` | Position héliocentrique écliptique (x, y, z en UA) |
| `planet_position(t, name)` | Position géocentrique : AD, Déc et distance (Vénus, Mars, Jupiter, Saturne) |
| `equation_of_time(t)` | Équation du temps en minutes |
| `angular_separation(ra1, dec1, ra2, dec2)` | Séparation angulaire entre deux astres |
| `find_conjunctions(dte_start, num_days)` | Prochaines conjonctions et oppositions |
| `find_eclipses(dte_start, num_months)` | Éclipses de Soleil et de Lune, avec type et magnitude |

### Cache

Le calcul des événements du jour (1 440 itérations × 2 astres) est coûteux. Un cache indexé par `AAAA-MM-JJ_lat_lon`
évite de le refaire tant que la date et le lieu ne changent pas, ce qui est précieux en mode temps réel. Pour la même
raison, seul le graphique de l'onglet affiché est redessiné ; les autres le sont quand on les ouvre.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Les tests de l'interface ouvrent la fenêtre hors écran (`QT_QPA_PLATFORM=offscreen`, réglé par le test lui-même) et
écrivent leurs réglages et favoris dans un dossier temporaire.

| Fichier | Portée |
|---------|--------|
| `test_engine.py` | Jour julien, positions Soleil/Lune, changements de repère, événements, planètes |
| `test_engine_hp.py` | Soleil VSOP87, Lune ELP2000, équation du temps, séparations, conjonctions, éclipses |
| `test_charts.py` | Bandes de crépuscule, géométrie et contenu de la carte du ciel, système solaire, rendu des graphiques |
| `test_gui.py` | Fenêtre PyQt6 : calcul, langue et thème à chaud, favoris, événements, info-bulles, fiches, temps réel, PDF |
| `test_i18n.py` | Chargement des traductions, repli, cohérence des 4 langues, langue automatique |
| `test_utils.py` | Formats HMS/DMS (retenues), noms et normalisation des phases |

---

## Références scientifiques

- **Jean Meeus**, *Astronomical Algorithms*, 2e édition, Willmann-Bell, 1998.
  - Chapitre 7 — Jour julien
  - Chapitre 13 — Changements de coordonnées
  - Chapitre 16 — Réfraction atmosphérique (formule de Bennett)
  - Chapitre 25 — Position du Soleil (série courte, ±0,01°)
  - Chapitre 28 — Équation du temps
  - Chapitre 32 — Position du Soleil VSOP87 (~1″)
  - Chapitre 47 — Position de la Lune (ELP-2000/82 tronquée, ~10″)
  - Chapitre 54 — Prévision des éclipses de Soleil

---

## Dépendances

| Paquet | Version min. | Rôle |
|--------|-------------|------|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | 6.5 | Interface graphique (Qt 6) |
| [matplotlib](https://matplotlib.org/) | 3.10.8 | Graphiques astronomiques interactifs |
| [reportlab](https://www.reportlab.com/) | 4.0 | Export PDF |

`urllib`, `json` et `argparse` font partie de la bibliothèque standard de Python.

---

## Feuille de route

### Données et calculs

- [x] Crépuscules nautique (−12°) et astronomique (−18°)
- [x] **Système solaire** — positions de Vénus, Mars, Jupiter et Saturne
- [x] **Éclipses de Soleil** — type, magnitude, durée de la phase centrale
- [x] **Conjonctions et oppositions** — prochains événements planétaires
- [x] **Précision de la Lune** — termes complets du chapitre 47 de Meeus (ELP-2000/82 tronquée, ~10″)
- [x] **Équation du temps**
- [ ] **Planétaire 2D** — orbites animées
- [ ] **Éclipses de Lune** — étendre la détection à la Lune

### Interface et visualisation

- [x] Étoiles principales sur la carte (32+, taille selon la magnitude)
- [x] Tracés des constellations sur la carte polaire
- [x] Planètes sur la carte du ciel (info-bulle et fiche au clic)
- [x] **Couleurs des crépuscules** — fond du graphique de trajectoire coloré selon le moment de la journée
- [x] **Carte du ciel interactive** — fiche complète d'une étoile au clic
- [x] **Thème clair** — bascule entre Catppuccin Mocha (sombre) et Latte (clair), sans redémarrer

### Confort d'utilisation

- [x] Favoris — enregistrement des lieux (`favorites.json`)
- [x] Fuseaux horaires (TU → heure locale par sélecteur UTC±N)
- [x] **Export** — éphémérides du jour en PDF
- [x] **Interface multilingue** — FR / EN / ES / DE
- [x] **Réglages persistants** — langue, thème, lieu, intervalle temps réel (`settings.json`)
- [ ] **Historique des calculs** — derniers calculs rechargeables en un clic
- [ ] **Recherche de lieu** — géocodage par nom de ville
- [ ] **Calendrier lunaire mensuel** — vue du mois avec la phase de chaque jour

### Technique et qualité

- [x] **Tests unitaires** — pytest sur le moteur, les graphiques, l'interface (hors écran), `utils.py` et `i18n.py`
  (6 fichiers, ~200 cas)
- [ ] **Exécutable** — PyInstaller `.exe` (Windows) / `.app` (macOS)

---

## Licence

Projet distribué sous licence MIT : voir le fichier `LICENSE`.
