# Ajouter une comète

> **Pas encore pris en charge.** Cette fiche décrit le chemin le plus court, en réutilisant ce que font déjà les
> planètes mineures. Comptez une journée, tests compris.

Une comète se traite presque comme une [planète mineure](Ajouter-une-planete-mineure.md) : JPL Horizons donne ses
positions, une table les garde, le moteur les interpole. Quatre choses changent.

| | Planète mineure | Comète |
|---|---|---|
| Commande Horizons | `"10;"` (numéro) | `"DES=12P;CAP;"` : désignation et apparition la plus proche |
| Durée valable | 1850–2149 | les années autour de l'arc observé (les forces non gravitationnelles changent l'orbite) |
| Pas de la table | 10 ou 60 jours | 1 à 2 jours (rapide près du Soleil) |
| Magnitude | H, G (astéroïde) | magnitude totale M1, K1 : `m = M1 + 5 log10(Δ) + K1 log10(r)` |

## 1. Les positions : `scripts/make_minor_planets.py`

Ajoutez un dictionnaire des comètes : commande Horizons complète, pas, et années couvertes.

```python
COMETS = {
    # nom : (commande Horizons, pas en jours, début, fin)
    "Ponsbrooks": ("DES=12P;CAP;", 2, "2020-01-01", "2030-01-01"),
}
```

- `CAP` choisit la solution orbitale de l'apparition la plus proche de la date. Pour une comète non périodique,
  la désignation seule suffit : `"DES=C/2023 A3;"`.
- Le nom suit les règles du moteur : **un seul mot, une majuscule puis des minuscules** (`"Ponsbrooks"`), ou bien
  adaptez `_target` (voir plus bas) pour accepter `"Pons-Brooks"`.

Dans `states()`, la requête doit utiliser la commande telle quelle (`COMMAND=f"'{commande}'"`, sans ajouter `;`),
et le début et la fin propres à la comète. Les paramètres de magnitude viennent de la JPL Small-Body Database :

```python
phys = {p["name"]: p["value"] for p in sbdb["phys_par"] if p.get("value")}
m1, k1 = float(phys["M1"]), float(phys["K1"])        # 12P : M1 = 5, K1 = 15
table[f"{name}_m1k1"] = np.array([m1, k1])
```

La table garde `{nom}_start`, `{nom}_position` et `{nom}_velocity`, comme pour les planètes mineures :
`_TabulatedOrbit` les lit sans changement.

## 2. Le moteur : `engine.py`

1. **La liste** :

   ```python
   COMETS = ("Ponsbrooks",)
   ```

2. **Le chargement** : `_minor_planet(name)` lit `{name}_hg`. Faites-lui rendre les paramètres présents
   (`_hg` ou `_m1k1`), avec leur sorte.

3. **La magnitude**, dans `AstroEngine.observations()`, à côté du système H, G :

   ```python
   def _comet_magnitude(m1, k1, r, delta):
       """Magnitude totale d'une comète (convention de JPL Horizons, T-mag)."""
       return m1 + 5.0 * math.log10(delta) + k1 * math.log10(r)
   ```

4. **Hors de la table** : `_TabulatedOrbit._at` lève `ValueError` en dehors des années couvertes. L'interface doit
   alors ignorer la comète plutôt que planter : un `try/except ValueError` autour de son calcul dans
   `AstroApp.calculate()` et dans `_refresh_coordinates()`, avec « — » dans les cellules.

5. **Le nom** (si vous gardez des noms composés) : dans `AstroEngine._target`, cherchez le nom exact avant de
   le passer par `capitalize()` :

   ```python
   name = body if body in MINOR_PLANETS + COMETS else body.capitalize()
   ```

## 3. L'interface : `gui.py`, `charts.py`, `locales/`

- **Groupe** de l'onglet Planètes : ajoutez `("comets", COMETS)` à `_BODY_GROUPS`. Le sélecteur gagne un bouton
  « Comètes » ; ajoutez `planets.group_comets` et `planets.group_comets_tip` dans les quatre langues.
- **Calcul** : dans `calculate()`, parcourez `_PLANETS + MINOR_PLANETS + COMETS` et rangez les comètes à part
  (`self.comets`), comme `self.minor_planets` ; idem pour les levers et couchers (`self.planet_events`).
- **Carte du ciel** : ajoutez les comètes assez brillantes, comme le fait la ligne
  `bright = [m for m in self.minor_planets if m["mag"] <= self._mag_limit()]`.
- **Symbole** : `"Ponsbrooks": "☄"` dans `charts.SYMBOL` (U+2604, déjà dans la police).
- **Nom** : `"ponsbrooks": "12P/Pons-Brooks"` dans la section `planets` des quatre fichiers.
- **Évènements** : ne mettez pas les comètes dans `find_conjunctions()` (une opposition de comète a peu de
  sens) ; le passage au périhélie ferait un bon évènement à ajouter ensuite.

## 4. Tester

- Positions : quelques dates comparées à JPL Horizons, astrométriques (quantité 1), à 1″ près.
- Magnitude : comparée à la `T-mag` d'Horizons (quantité 9), à 0,05 près.
- Interface : la comète dans son groupe, sa fiche, et une date hors de la table sans plantage.

Voir [Tester ses modifications](Tester-ses-modifications.md).

## Limites à connaître

- La magnitude d'une comète est une **prévision** : les comètes s'éclairent ou s'éteignent souvent autrement.
- La queue n'est pas dessinée ; seule la position du noyau est calculée.
- L'orbite d'une comète change à chaque passage : régénérez la table quand JPL publie une nouvelle solution.
