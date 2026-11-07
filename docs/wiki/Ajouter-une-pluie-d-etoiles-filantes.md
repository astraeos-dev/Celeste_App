# Ajouter une pluie d'étoiles filantes

L'onglet Évènements montre les maxima des treize grandes pluies de la liste de travail de l'**International Meteor
Organization** (IMO) : Quadrantides, Lyrides, η-Aquarides, δ-Aquarides du Sud, α-Capricornides, Perséides,
Draconides, Orionides, Taurides du Sud et du Nord, Léonides, Géminides et Ursides. Les autres pluies de la liste
donnent trois à six météores par heure : ajoutez-en une si elle compte pour vous (les α-Centaurides ou les
Puppides-Vélides vues de l'hémisphère sud, par exemple).

## 1. Les données : le calendrier de l'IMO

Le [Meteor Shower Calendar](https://www.imo.net/resources/calendar/) de l'année, **table 5** (*Working List of Visual
Meteor Showers*), donne pour chaque pluie :

| Colonne | Exemple (Perséides) |
|---|---|
| Activité | Jul 17–Aug 24 |
| Longitude du Soleil au maximum λ☉ (J2000) | 140,0° |
| Radiant α, δ au maximum | 48°, +58° |
| V∞ (vitesse d'entrée) | 59 km/s |
| r (indice de population) | 2,2 |
| ZHR (taux horaire zénithal) | 100 |

La date du maximum change d'une année à l'autre, pas sa longitude du Soleil : Céleste calcule l'instant où le
Soleil l'atteint, pour n'importe quelle année. Le numéro et le code de l'IAU (`007 PER`) sont entre parenthèses
après le nom.

## 2. Le moteur : `METEOR_SHOWERS`

Dans [`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py), ajoutez une ligne à
`AstroEngine.METEOR_SHOWERS`, avec le code de l'IAU pour clé :

```python
"ACE": (102, (1, 31), (2, 20), 319.4, 211.0, -58.0, 58, 2.0, 6),
#      n° IAU, début, fin (mois, jour), λ☉, α, δ, V∞, r, ZHR
```

Une pluie active autour du 1er janvier (les Quadrantides : du 28 décembre au 12 janvier) s'écrit telle quelle :
la fin est simplement avant le début dans l'année.

## 3. Le nom, dans les quatre langues

Dans chaque `locales/*.json`, section `meteors`, ajoutez `name_` + le code :

```json
"name_ACE": "α-Centaurides"
```

(en anglais α-Centaurids, en espagnol α-Centáuridas, en allemand α-Centauriden). Le titre de la carte vient de
`meteors.title` : « Maximum des {name} ».

## 4. Tester

`tests/test_engine.py`, classe `TestMeteorShowers` : ajoutez la date du maximum de la table 5 à
`test_dates_of_the_imo_calendar`, ou son heure si le texte du calendrier la donne
(`test_times_of_the_imo_calendar`). Le test de l'interface compte les cartes : mettez à jour `13` dans
`TestEvents.test_meteor_showers` (`tests/test_gui.py`) et dans `test_over_the_new_year`.

## Ce que Céleste en tire

Pour la nuit du maximum, vue du lieu choisi (`meteor_visibility`) :

- le **meilleur moment** : le radiant au plus haut pendant que le Soleil est 12° sous l'horizon ;
- le **taux attendu** sous un ciel noir : ZHR × sin(hauteur du radiant) ;
- la **Lune** : couchée ou presque nouvelle (pas de gêne), sinon gêne faible, moyenne ou forte selon sa fraction
  éclairée (moins de 40 %, moins de 75 %, au-delà).

Le radiant est celui du maximum : il se déplace d'environ un degré par jour, ce qui ne change rien à une nuit.
