# Ajouter une comète

Céleste suit les comètes qui deviennent faciles à voir de 2027 à 2029 : **C/2026 O1 (PANSTARRS)** (magnitude 8,6
en juin 2027), **45P/Honda-Mrkos-Pajdušáková** (8,2 fin août 2027), **C/2026 C1 (Tsuchinshan)** (6,6 en novembre
2028, très au sud) et **19P/Borrelly** (9,6 en décembre 2028). Elles ont leur groupe dans l'onglet Planètes,
leur fiche, leur place sur la carte du ciel quand elles passent la magnitude limite, leurs évènements (périhélie,
plus près de la Terre, plus brillante) et une ligne dans « Ce soir » sous la magnitude 10.

Une comète se traite presque comme une [planète mineure](Ajouter-une-planete-mineure.md) : JPL Horizons donne ses
positions, une table les garde, le moteur les interpole. Deux différences :

| | Planète mineure | Comète |
|---|---|---|
| Durée de la table | 1850–2149 | les années de son passage seulement (2025–2031 aujourd'hui) : son orbite change à chaque passage près du Soleil |
| Pas de la table | 10 ou 60 jours | 2 jours (rapide près du Soleil) |
| Commande Horizons | `"10;"` (numéro) | `"DES=45P;CAP;NOFRAG;"` (périodique : solution du passage le plus proche, sans fragments) ou `"DES=C/2026 C1;"` |
| Magnitude | H, G (astéroïde) | totale M1, K1 : `m = M1 + 5 log10(Δ) + K1 log10(r)`, comme la `T-mag` d'Horizons |

Hors de sa table, une comète n'apparaît nulle part.

## 1. Choisir la comète

La [base de données des petits corps](https://ssd.jpl.nasa.gov/tools/sbdb_query.html) du JPL liste les comètes
par date de périhélie ; demandez ensuite à Horizons sa magnitude prévue (`QUANTITIES='9'`, colonne `T-mag`) : une
comète qui ne passe pas sous la magnitude 11 intéressera peu. Écartez celles qui restent près du Soleil
(élongation, colonne `S-O-T`, inférieure à 20°).

## 2. La table : `scripts/make_comets.py`

Ajoutez une ligne à `COMETS` : le **nom dans Céleste** (un seul mot, une majuscule puis des minuscules, à cause
de `AstroEngine._target`), la commande Horizons et la désignation de la base de données :

```python
COMETS = {
    ...
    "Encke": ("DES=2P;CAP;NOFRAG;", "2P"),
}
```

Ajustez au besoin `START` et `STOP` pour couvrir son passage, puis lancez `python scripts/make_comets.py`
(quelques secondes, réseau). Relancez-le aussi de temps en temps : l'orbite d'une comète découverte depuis peu
repose sur quelques mois d'observations, et JPL l'affine.

## 3. Le moteur : `engine.py`

```python
COMETS = ("Panstarrs", "Honda", "Tsuchinshan", "Borrelly", "Encke")
COMET_DESIGNATIONS = {..., "Encke": "2P/Encke"}
```

Rien d'autre : `_target`, la magnitude (`observations`), `comets_at()`, `find_comet_events()` et `tonight()`
suivent la liste.

## 4. L'interface : `gui.py`

Ajoutez sa désignation courte à `_COMET_SHORT` (`"Encke": "2P/Encke"`), affichée dans les tableaux et « Ce soir » ;
la désignation complète sert dans la fiche et les évènements. Le symbole ☄ et le groupe « Comètes » suivent
`COMETS`, et le message « aucune comète suivie » se construit tout seul.

## 5. Tester

Dans `tests/test_engine.py`, `TestComets.test_position_and_magnitude` compare à JPL Horizons (quantités 1 et 9,
astrométrique, `EXTRA_PREC=YES`) : ajoutez une ou deux dates de la nouvelle comète, dont son périhélie. Les
comètes actuelles y sont à moins de 0,01″, la magnitude à 0,001 près. Mettez à jour les ensembles de noms de
`TestComets` dans `tests/test_gui.py`.

Voir [Tester ses modifications](Tester-ses-modifications.md).

## Limites à connaître

- La magnitude d'une comète est une **prévision** : les comètes s'éclairent ou s'éteignent souvent autrement.
- La queue n'est pas dessinée ; seule la position du noyau est calculée.
- Le tableau de l'onglet Coordonnées ne montre pas les comètes.
