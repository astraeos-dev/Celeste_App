# Tester ses modifications

## Les tests

```bash
pip install -r requirements-dev.txt
```
```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/
```

Sous Windows (PowerShell), la variable s'écrit autrement :

```bash
$env:QT_QPA_PLATFORM="offscreen"; python -m pytest -q tests/
```

La suite complète prend une vingtaine de minutes, surtout à cause des tests d'interface. Pendant le travail,
lancez seulement ce qui vous concerne :

| Changement | Tests |
|---|---|
| Textes, traductions | `python -m pytest -q tests/test_i18n.py` |
| Calculs (`engine.py`) | `python -m pytest -q tests/test_engine.py -k "MinorPlanets"` (un nom de classe ou de test) |
| Graphiques, symboles | `python -m pytest -q tests/test_charts.py` |
| Interface | `QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_gui.py -k "planet_table"` |

La CI de GitHub relance tout à chaque push, sous Python 3.10 à 3.13.

## L'auto-test

```bash
python main.py --self-test
```

Il ouvre la fenêtre, calcule, cherche une éclipse et quitte en affichant une ligne de résumé : le nombre d'étoiles
visibles, de planètes mineures et les services de localisation disponibles. Le build Windows le lance aussi sur
l'exécutable.

## Une valeur de référence de JPL Horizons

Chaque calcul nouveau se compare à une référence. Pour une position, l'API d'Horizons répond en quelques
secondes ; ouvrez cette adresse dans le navigateur (le tableau est entre `$$SOE` et `$$EOE`) :

```
https://ssd.jpl.nasa.gov/api/horizons.api?format=text&COMMAND='10%3B'&CENTER='500@399'&EPHEM_TYPE=OBSERVER&QUANTITIES='1,9'&TLIST='2026-11-03%2012:00'&TLIST_TYPE=CAL&TIME_TYPE=UT&ANG_FORMAT=DEG&EXTRA_PREC=YES
```

- `COMMAND` : `'10;'` pour la planète mineure n° 10, `'499'` pour Mars, `'DES=12P;CAP;'` pour une comète. Dans
  l'adresse, chaque `;` s'écrit `%3B` (et une espace `%20`), sinon Horizons répond « query parameter was not
  recognized ».
- `CENTER='500@399'` : vu du centre de la Terre.
- `QUANTITIES` : `1` ascension droite et déclinaison astrométriques (ICRF), `9` magnitude, `10` fraction
  éclairée, `13` diamètre apparent, `20` distance, `31` longitude écliptique (pour les conjonctions).

Puis, dans le test (`tests/test_engine.py`) :

```python
astrometric = _sky()["earth"].at(AstroEngine._time_ut(t)).observe(AstroEngine._target("Hygiea"))
ra, dec, _ = astrometric.radec()
assert abs(dec.degrees - dec_horizons) * 3600 < 0.01        # à 0,01″
```

Les tests existants montrent les tolérances habituelles : 0,01″ pour une position de planète mineure, 30 s pour
l'instant d'une conjonction, 0,02 pour une magnitude.
