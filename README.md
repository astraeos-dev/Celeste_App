# ✨ Céleste — observatoire astronomique

> Application de bureau qui calcule et affiche la position du Soleil, de la Lune et des planètes, d'après l'éphéméride JPL DE440 (via Skyfield).

[![Version](https://img.shields.io/github/v/release/astraeos-dev/Celeste_App?label=version&color=f2b84b)](https://github.com/astraeos-dev/Celeste_App/releases/latest)
[![Télécharger pour Windows](https://img.shields.io/badge/T%C3%A9l%C3%A9charger-Windows-0078D6?logo=windows)](https://github.com/astraeos-dev/Celeste_App/releases/latest)
[![CI](https://github.com/astraeos-dev/Celeste_App/actions/workflows/ci.yml/badge.svg)](https://github.com/astraeos-dev/Celeste_App/actions/workflows/ci.yml)
[![Licence MIT](https://img.shields.io/github/license/astraeos-dev/Celeste_App?label=licence)](LICENSE)
[![Dépôt GitHub](https://img.shields.io/github/stars/astraeos-dev/Celeste_App?style=social&label=D%C3%A9p%C3%B4t)](https://github.com/astraeos-dev/Celeste_App)
[![Wiki](https://img.shields.io/badge/Wiki-fiches%20pratiques-1f2a3b)](https://github.com/astraeos-dev/Celeste_App/wiki)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-blueviolet)

<a href="https://buymeacoffee.com/gregorychau"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="40"></a>

**Télécharger** : le programme d'installation Windows est sur la page
[Releases](https://github.com/astraeos-dev/Celeste_App/releases/latest) ; Céleste se met ensuite à jour tout seul.
Une idée, un problème, un astre à ajouter ? [Ouvrir une demande](https://github.com/astraeos-dev/Celeste_App/issues/new/choose).

**Projet actif** · fait partie de la famille Ganymede : [site web](https://astraeos-dev.github.io/personnal-site/) ·
[application Android](https://github.com/astraeos-dev/Ganymede) · [Céleste pour Home Assistant](https://github.com/astraeos-dev/Celeste_HA)

---

## Présentation

Céleste calcule en temps réel — ou pour n'importe quelle date — la position du Soleil, de la Lune, des planètes
(de Mercure à Neptune) et des planètes mineures, les événements du jour (lever, coucher, crépuscules), les phases de la
Lune, les éclipses (vues du lieu choisi) et les évènements de l'année : conjonctions, oppositions, rapprochements de la
Lune, saisons. Les résultats s'affichent dans une interface PyQt6 au design Astræos (thèmes Nuit,
Jour et Observation), avec des graphiques interactifs et une carte du ciel.

**Fonctionnalités principales :**

- **Positions instantanées** — ascension droite, déclinaison, hauteur, azimut, distance
- **Événements du jour** — lever, coucher, culmination, durée du jour ; crépuscules civil (−6°), nautique (−12°) et astronomique (−18°)
- **Phase de la Lune** — nom de la phase, fraction éclairée, âge et distance de la Lune
- **Mode temps réel** — mise à jour automatique toutes les 2 s (réglable)
- **Géolocalisation** — position de l'appareil par le service de localisation du système (GPS, Wi-Fi), nom de la
  commune par OpenStreetMap ; à défaut, sa dernière position connue, puis la position approximative de l'adresse IP
  (ip-api.com), signalée comme telle : une fenêtre dit alors pourquoi (accès refusé par Windows, service désactivé,
  délai) et ouvre les réglages de localisation
- **Trajectoire sur 24 h** — courbes de hauteur sur un fond coloré selon le moment de la journée (jour, crépuscules, nuit),
  sur le jour local (heure locale en bas, TU en haut), info-bulle au survol
- **Carte du ciel polaire** — zénith au centre, 513 étoiles jusqu'à la magnitude 4 (Yale Bright Star Catalogue, ramenées
  à la date : mouvement propre, précession, nutation, aberration) à la taille de leur magnitude, constellations, planètes ;
  info-bulle au survol et fiche détaillée au clic (constellation, magnitude, coordonnées)
- **Planètes** — Mercure, Vénus, Mars, Jupiter, Saturne, Uranus et Neptune : coordonnées, hauteur et azimut, distance,
  élongation, magnitude, heures de lever, de culmination et de coucher (nom atténué sous l'horizon) ; tous les astres
  ou un groupe, « Visibles seulement », tri par clic sur un en-tête ; système solaire vu de dessus, interne et externe
- **Fenêtre de données** — un clic sur un astre (carte du ciel, onglets Planètes et Coordonnées) ouvre sa fiche :
  magnitude, constellation, diamètre apparent, fraction éclairée et angle de phase, temps de lumière, distance au
  Soleil, coordonnées, lever, culmination et coucher
- **Planètes mineures** — Cérès, Pallas, Junon, Vesta, les planètes naines Pluton, Éris, Hauméa et Makémaké, et
  Sedna, au choix dans l'onglet Planètes, dans l'onglet Coordonnées et, assez brillantes pour la magnitude limite, sur
  la carte du ciel : positions de JPL Horizons (à 0,001″ près), magnitudes du système H, G ; leur numéro du Minor
  Planet Center (« (1) Cérès ») dans leur fiche et leur infobulle
- **Coordonnées** — Soleil, Lune, planètes, planètes mineures et Terre, avec en même temps x, y, z et distance
  (héliocentriques, géocentriques ou topocentriques) et deux angles (équatoriaux ou horizontaux vus du lieu, écliptiques
  vus du Soleil ou de la Terre), magnitude, angle au Soleil et constellation ; angles au format des paramètres, ou en
  dd° mm′ ss″, dd° mm,mm′ ou dd,ddddd° pour ce tableau seulement
- **Format des angles** — choisi dans les paramètres (dd° mm′ ss″, dd° mm,mm′ ou dd,ddddd°), pour tout le logiciel
- **Prévision des éclipses** — éclipses de Soleil (totale, annulaire, hybride, partielle ; magnitude, durée de la phase
  centrale) et de Lune (totale, partielle, pénombrale ; magnitudes d'ombre et de pénombre, durée de chaque phase), avec
  l'heure du maximum ; **vues d'ici** : heures locales du début, du maximum et de la fin, magnitude, part du Soleil caché,
  totalité ou annularité, hauteur du Soleil ou de la Lune
- **Éclipse projetée au sol** — bouton « Carte » de chaque éclipse : bande de totalité ou d'annularité, ligne de
  centralité, magnitude maximale de la partialité et point du maximum (éclipses de Soleil) ; zone où la Lune est levée
  (éclipses de Lune) ; sur un fond Natural Earth, avec le lieu choisi
- **Conjonctions, oppositions et élongations** — instant à la minute (en TU et à l'heure du lieu) des conjonctions
  entre planètes (laquelle passe au nord de l'autre) et avec le Soleil (inférieure ou supérieure pour Mercure et Vénus,
  avec les transits), des oppositions et des plus grandes élongations de Mercure et de Vénus (est le soir, ouest le
  matin) ; oppositions des planètes mineures ; bouton « Carte » : le trajet des astres parmi les étoiles autour de
  l'évènement
- **Lune et saisons** — rapprochements de la Lune avec les planètes et Aldébaran, les Pléiades, Régulus, Spica et
  Antarès, occultations vues d'ici ; périgées, apogées et super lunes ; équinoxes, solstices, périhélie et aphélie
- **Visibilité d'ici** — pour chaque évènement, la nuit où le voir (le soir, le matin ou toute la nuit), avec la
  hauteur, la direction et l'heure ; filtres par groupe et « Visibles d'ici seulement » ; export vers un agenda (.ics)
- **Équation du temps** — écart entre temps solaire vrai et temps solaire moyen
- **Mise à jour automatique** — une nouvelle version publiée est proposée au démarrage, installée en un clic
- **Liens** — Paramètres › À propos : site web, code source, café, et demandes sur GitHub (problème, fonctionnalité,
  astre à ajouter) préremplies avec la version et le système
- **Favoris** — enregistrement des lieux (37 villes préchargées)
- **Fuseaux horaires** — conversion TU → heure locale par sélecteur UTC±N
- **Interface multilingue** — français, anglais, espagnol, allemand ; langue du système par défaut, changement immédiat
  dans les paramètres (ou `--lang`)
- **Thèmes** — Nuit (sombre), Jour (clair) et Observation (rouge sur noir, pour garder la vision de nuit), choisis en bas
  de la barre latérale sans redémarrer (ou `--theme`)
- **Raccourcis clavier** — `F5` calculer, `Ctrl+L` temps réel
- **Réglages persistants** — thème, langue, format de l'heure, lieu de démarrage, magnitude limite, intervalle temps réel
  (`~/.celeste/settings.json`, hors du dépôt)

---

## Installation

Prérequis : Python 3.10 ou plus récent, et pip. PyQt6 embarque Qt ; sur un Linux minimal, Qt demande aussi quelques
bibliothèques système (`sudo apt install libegl1 libxkbcommon0` sous Debian ou Ubuntu).

```bash
git clone https://github.com/astraeos-dev/Celeste_App.git
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
python main.py --theme jour   # thème clair (nuit, jour, observation)
```

Sans option, la langue suit celle du système (l'anglais si elle n'est pas traduite) et le thème est Nuit. La langue se
change ensuite dans l'onglet Paramètres et le thème en bas de la barre latérale, sans redémarrer. Les anciens noms de
thème (`mocha`, `frape`, `latte`) restent acceptés.

---

## Utilisation

| Champ | Description |
|-------|-------------|
| **Date et heure** | Format `JJ/MM/AAAA HH:MM:SS`, en temps universel (TU) ; la flèche ouvre un calendrier |
| **Latitude** | Degrés décimaux, positif = nord (ex. `48.85` pour Paris), point ou virgule |
| **Longitude** | Degrés décimaux, positif = est (ex. `2.35` pour Paris), point ou virgule |
| **Fuseau** | Décalage UTC±N appliqué aux heures des événements |
| **Favoris** | Choisir un lieu l'applique aussitôt ; l'étoile ajoute le lieu saisi aux favoris, la corbeille supprime le favori choisi |

Une coordonnée invalide s'encadre de la couleur d'alerte et un message s'affiche sous le champ, sans fenêtre d'erreur.
Changer la date recalcule tout au bout d'un instant.

**Boutons :**

- Horloge, à droite de la date — revient à l'instant présent
- Viseur, à droite de la longitude — remplit la latitude, la longitude et le fuseau à partir du service de localisation
  de l'appareil (à autoriser dans les réglages de confidentialité de Windows ou de macOS) ; sinon, de l'adresse IP
- **Calculer** (`F5`) — lance les calculs pour la date et le lieu saisis
- **Suivre en temps réel** (`Ctrl+L`) — bouton à bascule : suit l'heure actuelle tant qu'il reste enfoncé (intervalle
  réglable dans les paramètres)
- **Nuit · Jour · Observation** — sélecteur de thème, en bas de la barre latérale

**Événements :** les deux boutons de l'onglet cherchent les éclipses des 12 prochaines lunaisons et les évènements de
l'année à venir ; « Exporter (.ics) » les enregistre dans un agenda. Chaque éclipse indique son type, l'heure du maximum (en temps universel), les magnitudes et la durée
des phases. Une éclipse pénombrale si faible que son existence tient à la précision du calcul (magnitude de pénombre
inférieure à 0,01) est marquée « Incertaine ».

Les conjonctions suivent la définition des almanachs : même longitude écliptique apparente vue du centre de la Terre
(opposition : 180° du Soleil). Repérés jour par jour, les évènements sont affinés heure par heure puis interpolés :
sur l'année 2026, leurs instants s'écartent d'au plus une seconde de ceux de JPL Horizons (une à trois minutes pour les
plus grandes élongations, dont le maximum est très plat). La carte montre les trajets en coordonnées équatoriales de la
date, nord en haut et est à gauche, avec les étoiles du catalogue, l'écliptique et des repères datés (toutes les
6 heures pour la Lune).

Un évènement est **visible d'ici** quand l'astre se tient à 5° au moins au-dessus de l'horizon alors que le Soleil est
6° sous l'horizon (12° pour les planètes mineures, plus faibles), dans la nuit de l'évènement ; la carte en donne le
meilleur moment. Une conjonction de la Lune devient une **occultation** quand, vue du lieu (parallaxe comprise), l'astre
passe derrière le disque lunaire : heures de disparition et de réapparition. Les **circonstances locales des éclipses**
suivent le Soleil et la Lune vus du lieu toutes les 20 s ; les contacts sont interpolés avec les rayons de la Lune des
prédictions de la NASA (bord moyen, vallées pour la totalité) : sur la ligne de centralité du 12 août 2026, la durée de
la totalité s'écarte de moins de 0,1 s de celle de la NASA.

**Graphiques :**

- Survolez les courbes sur 24 h pour lire la hauteur à toute heure ; le fond suit la hauteur du Soleil
- La carte du ciel place le zénith au centre et l'horizon sur le cercle, le nord en haut ; le curseur règle la
  magnitude limite des étoiles
- Survolez un astre de la carte pour l'identifier, cliquez pour afficher sa fiche

---

## Design Astræos

L'interface et les graphiques suivent le design system Astræos :

- **Thèmes** — Nuit (sombre, par défaut), Jour (clair) et Observation (rouge sur noir, pour garder la vision de nuit
  dehors). Les couleurs sont les jetons du design system (`ciel-000`, `ciel-100`, `ciel-200`, `encre`,
  `encre-attenuee`, `or`, `lune`, `signal-ok`, `signal-alerte`), définis une seule fois dans `config.py` et partagés
  par Qt et matplotlib.
- **Typographie** — IBM Plex Sans pour le texte, IBM Plex Mono pour les valeurs chiffrées, Astraeos Symboles pour les
  symboles astronomiques (☉ ☽ ♀ ♂ ♃ ♄ ⊕ ♈ ☌ ☍). Les polices sont fournies dans `fonts/`, pour un rendu identique sur
  toutes les machines.
- **Composants** — boutons (principal, secondaire, discret, danger), champs de saisie avec libellé, unité et message
  d'erreur, cartes de données, pastilles d'état, jauge, onglets et sélecteur de thème.
- **Règles** — pas d'emoji (des icônes Material Design Icons à la place) ; une seule zone dorée par écran, le bouton
  Calculer ; des filets plutôt que des ombres ; un symbole accompagne toujours le nom de l'astre, sans le remplacer ;
  des libellés sans capitales ; un contraste du texte d'au moins 4,5:1 dans les trois thèmes (vérifié par
  `tests/test_config.py`).

Polices IBM Plex (© IBM) et Astraeos Symboles (d'après Noto Sans Symbols)
sous licence SIL Open Font License 1.1 ; icônes Material Design Icons (Pictogrammers) sous licence Apache 2.0 : voir
`fonts/README.md` et `assets/README.md`.

---

## Architecture

> **Modifier Céleste** : des fiches pratiques (textes et infobulles, ajouter une planète mineure, une comète, une
> étoile, une langue, tester, publier une version) sont dans [`docs/wiki`](docs/wiki/Home.md) et dans le
> [wiki](https://github.com/astraeos-dev/Celeste_App/wiki) du dépôt.

Le projet suit le modèle **MVC (modèle-vue-contrôleur)** :

```
Celeste_App/
├── main.py              # Point d'entrée — options --lang / --theme, fenêtre Qt
├── engine.py            # Modèle — calculs astronomiques purs (AstroEngine)
├── gui.py               # Vue + contrôleur — interface PyQt6 et logique applicative
├── charts.py            # Graphiques matplotlib — trajectoires, carte du ciel, système solaire
├── utils.py             # Utilitaires — formats HMS/DMS, noms des phases
├── config.py            # Design Astræos — couleurs des thèmes Nuit, Jour et Observation, espacements, styles de texte
├── icons.py             # Icônes Material Design (SVG) et symbole Astræos aux couleurs du thème
├── i18n.py              # Internationalisation — traductions par clé avec repli
├── updater.py           # Mises à jour : dernière Release GitHub, téléchargement vérifié, installation
├── settings.py          # Préférences persistantes (~/.celeste/settings.json)
├── constellations.py    # Tracés des constellations et noms de leurs étoiles
├── star_catalog.py      # 513 étoiles brillantes (Yale Bright Star Catalogue, magnitude < 4), généré
├── favorites_default.json # Lieux préchargés (36 villes), copiés dans ~/.celeste au premier enregistrement
├── locales/             # Traductions (fr.json est la référence)
├── fonts/               # Polices IBM Plex Sans, IBM Plex Mono et Astraeos Symboles (licence OFL)
├── assets/              # Symbole et icône Astræos (SVG), terres, planètes mineures (JPL Horizons), licence des icônes
├── scripts/             # Construction de l'application, catalogue d'étoiles, table des planètes mineures
├── celeste.spec         # Recette PyInstaller de Celeste.exe (Windows)
├── installer/           # Programme d'installation Inno Setup (celeste.iss)
├── requirements.txt     # Dépendances d'exécution
├── requirements-dev.txt # Dépendances de développement (pytest)
├── docs/wiki/           # Fiches pratiques, publiées dans le wiki GitHub
└── tests/               # Tests unitaires (moteur, graphiques, interface, thèmes, i18n, utilitaires)
```

### Modèle : `AstroEngine`

Moteur de calcul entièrement découplé : uniquement des méthodes de classe ou statiques, sans état interne. Les positions
viennent de l'éphéméride **JPL DE440** (fichier `de440s.bsp`,
1850–2149) par [Skyfield] : précession IAU 2006, nutation IAU 2000A, temps de lumière, aberration, déflexion ; TU1 et ΔT
de l'IERS. Précision : planètes à 0,07″ de JPL Horizons, levers et couchers à la seconde (à moins de 30 s des heures
arrondies de l'USNO).

Les planètes mineures (sauf Pluton, dans DE440) viennent d'une table de **JPL Horizons** (`assets/minor_planets.npz`,
2,4 Mo, `scripts/make_minor_planets.py`) : position et vitesse héliocentriques tous les 10 jours (60 pour Éris, Haumea,
Makemake et Sedna), interpolées par Hermite ; positions à 0,001″ d'Horizons de 1850 à 2149.

L'éphéméride (32 Mo) est cherchée dans `data/` à côté du programme, puis dans `~/.celeste` (ou `$CELESTE_DATA`), où elle
est téléchargée depuis le serveur JPL/NAIF au premier lancement.

| Méthode | Rôle |
|---------|------|
| `julian_day(dte)` | Jour julien (JJ) |
| `julian_century_j2000(dte)` | T en siècles juliens depuis J2000,0 |
| `delta_t(year)` | ΔT = TT − TU en secondes (IERS ; Stephenson, Morrison et Hohenkerk 2016 avant 1973) |
| `sun_position(t)` / `sun_position_tt(t)` | Longitude apparente et distance du Soleil (t en TU / en TT) |
| `moon_position(t)` | Longitude, latitude et parallaxe apparentes de la Lune (t en TU) |
| `moon_position_tt(t)` | Même calcul en TT, avec la distance de la Lune |
| `ecliptic_to_equatorial(l, b, t)` | Écliptique → équatorial (AD, Déc), obliquité vraie (IAU 2006 + nutation) |
| `equatorial_to_horizontal(jd, lat, lon, ra, dec)` | Équatorial → horizontal (hauteur, azimut), temps sidéral apparent |
| `elevation_correction(h, p)` | Parallaxe en hauteur (π cos h), puis réfraction atmosphérique |
| `find_events(dte, lat, lon, body, tz, elevation_m)` | Soleil, Lune ou planète : lever, coucher (bord supérieur), culmination, crépuscules sur le jour local (fuseau IANA, heure d'été comprise), à la seconde ; l'altitude abaisse l'horizon |
| `horizontal(t, lat, lon, body, elevation_m, refraction)` | Hauteur et azimut topocentriques (vus du lieu, parallaxe comprise) |
| `coordinates(t, body, center, frame, lat, lon)` | Coordonnées dans le système choisi : héliocentriques (géométriques, J2000) ou géo/topocentriques (apparentes, de la date) ; écliptiques, équatoriales ou horizontales ; angles et x, y, z |
| `eclipse_map(greatest, kind)` | Éclipse projetée au sol : ligne de centralité, bande d'ombre, partialité (Soleil) ; Lune levée (Lune) |
| `body_details(t, body)` | Fenêtre de données : distance, temps de lumière, diamètre apparent, distance au Soleil, angle de phase, fraction éclairée |
| `observations(t, bodies)` | Magnitude visuelle, angle au Soleil et constellation (UAI), vus de la Terre |
| `moon_phase(t)` | Fraction éclairée de la Lune (%) et âge depuis la dernière nouvelle lune vraie |
| `altitudes(dtes, lat, lon, elevation_m)` | Hauteurs du Soleil et de la Lune à une série d'instants, en un calcul vectorisé |
| `planet_heliocentric(t, name)` | Position héliocentrique écliptique J2000 (x, y, z en UA), Terre comprise |
| `planet_position(t, name)` | Position géocentrique apparente : AD, Déc et distance (Mercure à Pluton) |
| `equation_of_time(t)` | Équation du temps en minutes |
| `angular_separation(ra1, dec1, ra2, dec2)` | Séparation angulaire entre deux astres |
| `find_conjunctions(dte_start, num_days, max_separation)` | Conjonctions (inférieure, supérieure, transit ; nord ou sud), oppositions et plus grandes élongations, à la minute |
| `find_moon_events(dte_start, num_days, max_separation)` | Conjonctions de la Lune avec les planètes et les étoiles brillantes de son chemin, périgées, apogées, super lunes |
| `find_seasons(dte_start, num_days)` | Équinoxes, solstices, périhélie et aphélie de la Terre |
| `event_visibility(events, lat, lon, elevation_m, tz)` | Visibilité de chaque évènement depuis le lieu, la nuit venue (soir, matin, toute la nuit), occultations |
| `moon_occultation(event, lat, lon, elevation_m)` | Occultation vue du lieu : disparition, réapparition, hauteur de la Lune |
| `eclipse_local(eclipse, lat, lon, elevation_m)` | Circonstances locales d'une éclipse : contacts, magnitude, obscuration, durée de la totalité |
| `event_scene(event, star_catalog)` | Trajets des deux astres autour d'un évènement, étoiles du champ et écliptique (pour sa carte) |
| `find_eclipses(dte_start, num_months)` | Éclipses de Soleil (éléments besséliens) et de Lune (ombre et pénombre de la Terre, règle de Danjon) : type, magnitudes, durées, heure du maximum en TU |

[Skyfield]: https://rhodesmill.org/skyfield/

### Cache

Un cache indexé par la date locale, le lieu, le fuseau et l'altitude évite de recalculer les événements du jour tant que la date, le lieu et le
fuseau ne changent pas, ce qui est précieux en mode temps réel. Pour la même raison, seul le graphique de l'onglet
affiché est redessiné ; les autres le sont quand on les ouvre.

## Références scientifiques

- **R. S. Park et al.** (2021), *The JPL Planetary and Lunar Ephemerides DE440 and DE441*, AJ 161, 105 — positions
- **B. Rhodes**, *Skyfield* — réduction des positions (IAU 2006/2000A), levers, couchers et phases de la Lune
- **F. R. Stephenson, L. V. Morrison et C. Y. Hohenkerk** (2016), Proc. R. Soc. A 472 — ΔT historique ; IERS ensuite
- **Jean Meeus**, *Astronomical Algorithms*, 2e édition, Willmann-Bell, 1998 — chapitre 54 (règles des éclipses),
  chapitres 13 et 16 (changements de coordonnées, réfraction)
- **Explanatory Supplement to the Astronomical Almanac** (1992), chapitre 8 — éléments besséliens des éclipses de Soleil
- **André Danjon** — agrandissement de l'ombre de la Terre par l'atmosphère (1/85 du rayon terrestre), retenu pour les
  éclipses de Lune
- **Fred Espenak et Jean Meeus**, *Five Millennium Canon of Solar Eclipses* et *Five Millennium Canon of Lunar
  Eclipses*, NASA — valeurs de référence des tests d'éclipses
- **JPL Horizons** et **USNO** (aa.usno.navy.mil) — valeurs de référence des tests de positions, levers et couchers
- **D. Hoffleit et W. H. Warren** (1991), *Yale Bright Star Catalogue*, 5e éd. — étoiles de la carte du ciel (domaine public)
- **Natural Earth** (naturalearthdata.com), terres au 1/110 000 000 — fond de carte des éclipses (domaine public)
- **E. Bowell et al.** (1989), *Application of photometric models to asteroids*, Asteroids II — magnitudes H, G des
  planètes mineures (paramètres de la JPL Small-Body Database)

---

## Application Windows

Céleste se construit en application Windows autonome (`Celeste.exe`) avec [PyInstaller]. L'éphéméride JPL est incluse :
l'application fonctionne hors ligne dès le premier lancement.

- **Depuis GitHub** : onglet *Actions*, workflow « Build — application Windows », bouton *Run workflow* (ou pousser un
  tag `v*`). Deux artefacts : `Celeste-Windows-Setup`, le programme d'installation `Celeste-<version>-Setup.exe`
  (raccourcis du menu Démarrer et du Bureau, désinstallation depuis les paramètres de Windows), et `Celeste-Windows`,
  le dossier de l'application à lancer sans installer (`Celeste.exe`).
- **Nouvelle version** : changer `APP_VERSION` dans `config.py` (seul endroit : fenêtre, installateur, demandes
  GitHub) et fusionner : le workflow publie la Release `v<version>` (installateur et empreinte SHA-256).
- **Mise à jour automatique** : Céleste installé cherche une version plus récente au démarrage (ou par Paramètres ›
  À propos › Vérifier les mises à jour), la télécharge, vérifie son empreinte, l'installe par-dessus l'ancienne et
  se rouvre, réglages et favoris conservés (`updater.py`). Voir le wiki,
  [Publier une version](docs/wiki/Publier-une-version.md).
- **Sur un PC Windows** :

```bash
pip install pyinstaller
python scripts/build_exe.py
```

Le script place l'éphéméride dans `data/`, dessine l'icône depuis `assets/astraeos-icone.svg`, lance PyInstaller
(`celeste.spec`), vérifie que l'application démarre (`--self-test`) et crée l'archive dans `dist/`. Si
[Inno Setup 6](https://jrsoftware.org/isinfo.php) est installé, il construit aussi le programme d'installation
(`installer/celeste.iss`, à l'icône de Céleste). Ni l'un ni l'autre n'est signé : au premier lancement, SmartScreen
affiche « Windows a protégé votre ordinateur » (*Informations complémentaires*, puis *Exécuter quand même*). Les
préférences et les favoris (`%USERPROFILE%\.celeste`) survivent à une désinstallation.

[PyInstaller]: https://pyinstaller.org/

---

## Dépendances

| Paquet | Version min. | Rôle |
|--------|-------------|------|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | 6.5 | Interface graphique (Qt 6) |
| [matplotlib](https://matplotlib.org/) | 3.10.8 | Graphiques astronomiques interactifs |
| [Skyfield](https://rhodesmill.org/skyfield/) | 1.47 | Éphéméride JPL DE440, temps (TU1, ΔT), levers et couchers (installe NumPy) |
| [timezonefinder](https://github.com/jannikmi/timezonefinder) | 6.5 | Fuseau IANA d'un lieu, hors ligne (mode « Automatique ») |
| [tzdata](https://pypi.org/project/tzdata/) | — | Base des fuseaux IANA pour `zoneinfo` (indispensable sous Windows) |

`urllib`, `json` et `argparse` font partie de la bibliothèque standard de Python. Les polices et les icônes sont fournies
avec le projet (`fonts/`, `assets/`) : rien à installer.

---

## Feuille de route

### Données et calculs

- [x] Crépuscules nautique (−12°) et astronomique (−18°)
- [x] **Système solaire** — positions de Vénus, Mars, Jupiter et Saturne
- [x] **Éclipses de Soleil** — type, magnitude, durée de la phase centrale
- [x] **Conjonctions et oppositions** — prochains événements planétaires, à la minute, avec leur carte
- [x] **Planètes mineures** — Cérès, Pallas, Junon, Vesta, Pluton, Éris, Haumea, Makemake, Sedna (JPL Horizons)
- [x] **Évènements vus d'ici** — visibilité, occultations, Lune, saisons, circonstances locales des éclipses, export .ics
- [x] **Précision** — éphéméride JPL DE440 (Skyfield) à la place des séries de Meeus ; levers et couchers à la seconde
- [x] **Équation du temps**
- [ ] **Planétaire 2D** — orbites animées
- [x] **Éclipses de Lune** — type (totale, partielle, pénombrale), magnitudes, durée des phases, heure du maximum

### Interface et visualisation

- [x] Étoiles principales sur la carte (32+, taille selon la magnitude)
- [x] Tracés des constellations sur la carte polaire
- [x] Planètes sur la carte du ciel (info-bulle et fiche au clic)
- [x] **Couleurs des crépuscules** — fond du graphique de trajectoire coloré selon le moment de la journée
- [x] **Carte du ciel interactive** — fiche complète d'une étoile au clic
- [x] **Design Astræos** — thèmes Nuit, Jour et Observation sans redémarrer, polices IBM Plex, icônes vectorielles

### Confort d'utilisation

- [x] Favoris — enregistrement des lieux (`~/.celeste/favorites.json`)
- [x] Fuseaux horaires IANA, heure d'été comprise ; « Automatique » prend celui du lieu (timezonefinder)
- [x] Altitude de l'observateur (abaissement de l'horizon), positions topocentriques, phase exacte de la Lune
- [x] **Interface multilingue** — FR / EN / ES / DE
- [x] **Réglages persistants** — langue, thème, lieu, intervalle temps réel (`~/.celeste/settings.json`)
- [ ] **Historique des calculs** — derniers calculs rechargeables en un clic
- [ ] **Recherche de lieu** — géocodage par nom de ville
- [ ] **Calendrier lunaire mensuel** — vue du mois avec la phase de chaque jour

### Technique et qualité

- [x] **Tests unitaires** — pytest sur le moteur, les graphiques, l'interface (hors écran), les thèmes, `utils.py` et
  `i18n.py` (7 fichiers, ~290 cas)
- [x] **Exécutable Windows** — `Celeste.exe` autonome (PyInstaller), éphéméride incluse

---

## Licence

Projet distribué sous licence MIT : voir le fichier `LICENSE`. Les polices de `fonts/` sont sous licence SIL Open Font
License 1.1 et les icônes Material Design Icons sous licence Apache 2.0 (voir `fonts/README.md` et `assets/README.md`).
