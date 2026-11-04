# Ajouter une planète mineure

Exemple : **(10) Hygie**. Comptez une demi-heure. Il faut une connexion internet (JPL Horizons) pour régénérer
la table des positions.

## 1. Les positions : la table JPL Horizons

Dans [`scripts/make_minor_planets.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/scripts/make_minor_planets.py),
ajoutez l'astre à `BODIES` : son **numéro** (ou sa désignation) et le **pas** de la table, en jours.

```python
BODIES = {
    "Ceres": ("1", 10), "Pallas": ("2", 10), "Juno": ("3", 10), "Vesta": ("4", 10),
    "Hygiea": ("10", 10),
    ...
}
```

- Pas de **10 jours** pour la ceinture principale, **60 jours** au-delà de Neptune (Éris, Sedna…) : l'astre doit
  parcourir moins de 5° de son orbite entre deux positions.
- Le **nom** est un seul mot, avec une majuscule puis des minuscules (`"Hygiea"`, pas `"hygiea"` ni
  `"10 Hygiea"`) : le moteur retrouve les astres avec `nom.capitalize()`.

Puis régénérez la table (tous les astres sont retéléchargés, avec H et G de la JPL Small-Body Database) :

```bash
python scripts/make_minor_planets.py
```

`assets/minor_planets.npz` grossit d'environ 300 Ko par astre de la ceinture principale.

## 2. Le moteur : `engine.py`

| Où | Ajout |
|---|---|
| `MINOR_PLANETS` | `"Hygiea"` : l'astre apparaît dans l'onglet Planètes, sur la carte du ciel s'il est assez brillant, et dans les oppositions |
| `MINOR_PLANET_NUMBERS` | `"Hygiea": 10` : « (10) Hygie » dans la fiche et l'infobulle |
| `_RADII_KM` | `"Hygiea": 217.0` : rayon moyen en km, pour le diamètre apparent de la fiche |
| `AstroEngine.BODIES` | `"Hygiea"` à sa place (ordre des distances au Soleil) : la ligne de l'onglet Coordonnées |

## 3. Le symbole : `charts.py`

Ajoutez une entrée à `SYMBOL`, avec **exactement le même nom** que dans `MINOR_PLANETS` :

```python
SYMBOL = {..., "Hygiea": "○"}
```

Le symbole doit exister dans la police *Astraeos Symboles* (test `test_symbols_are_in_the_symbol_font`).
Sinon :

- prenez `○`, déjà dans la police ;
- ou ajoutez-le : dans [`scripts/add_font_symbols.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/scripts/add_font_symbols.py),
  mettez son code Unicode dans `SYMBOLS`, puis lancez le script avec la police Noto qui le contient
  (*Noto Sans Symbols 2* pour la plupart des symboles d'astéroïdes et de planètes naines) :

  ```bash
  python scripts/add_font_symbols.py NotoSansSymbols2-Regular.ttf
  ```

## 4. Le nom : `locales/*.json`

Dans la section `"planets"` des **quatre** fichiers, ajoutez le nom **court** (sans numéro : il est ajouté par
`MINOR_PLANET_NUMBERS`) et complétez `group_minor_tip` :

```json
"hygiea": "Hygie",
```

(`"Hygiea"` en anglais et en allemand, `"Higía"` en espagnol.)

## 5. Les tests et le README

- `tests/test_gui.py` : ajoutez le nom à la liste de `test_minor_planets_of_the_planet_table`, augmentez le
  nombre d'astres de `test_all_bodies_and_visible_only` (16 → 17) et la liste `TestCoordinatesTab.BODIES`.
- `tests/test_engine.py` : ajoutez une position de référence à `TestMinorPlanets`
  (voir [Tester ses modifications](Tester-ses-modifications.md) pour l'obtenir de JPL Horizons).
- `README.md` : la liste des planètes mineures.

## 6. Vérifier

```bash
python main.py --self-test
```

La ligne doit annoncer un astre de plus (`… 10 minor planets …`). Ouvrez ensuite l'onglet Planètes, choisissez
« Planètes mineures » et cliquez sur la nouvelle ligne : la fiche doit afficher « (10) Hygie ».

## Cas particulier : un astre de DE440

Pluton est dans DE440 (`_PLANETS` dans `engine.py`) : il n'a pas besoin de la table Horizons. Les autres astres
de DE440 sont les planètes et la Lune ; tout nouvel astre passe par la table.
