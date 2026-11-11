# Ajouter une comète

Céleste suit les comètes qui deviennent faciles à voir de 2027 à 2029 : **C/2025 A6 (Lemmon)** (passée près de la Terre en octobre 2025), **C/2026 O1 (PANSTARRS)** (magnitude 8,6
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

## 2. Une seule ligne : `scripts/make_comets.py`

Depuis la version 4.9, une comète se déclare **à un seul endroit**. Ajoutez une ligne à `COMETS` : le **nom dans
Céleste** (un seul mot, une majuscule puis des minuscules, à cause de `AstroEngine._target`), la commande Horizons,
la désignation de la base de données, la désignation complète (fiche, évènements) et la désignation courte
(tableaux, « Ce soir ») :

```python
COMETS = {
    ...
    "Encke": ("DES=2P;CAP;NOFRAG;", "2P", "2P/Encke", "2P/Encke"),
}
```

Ajustez au besoin `START` et `STOP` pour couvrir son passage, puis lancez `python scripts/make_comets.py`
(quelques secondes, réseau) et validez `assets/comets.npz` avec le script. La table emporte les noms : le moteur
(`COMETS`, `COMET_DESIGNATIONS`, `COMET_SHORT`), le groupe « Comètes », le symbole ☄, la carte du ciel, les
évènements et « Ce soir » suivent sans autre modification.

Relancez le script de temps en temps : l'orbite d'une comète découverte depuis peu repose sur quelques mois
d'observations, et JPL l'affine.

**Pourquoi je ne la vois pas ?** Une comète n'est dessinée sur la carte du ciel que si elle est au-dessus de
l'horizon et plus brillante que la magnitude limite ; « Ce soir » ne la cite que sous la magnitude 10. Elle est
toujours dans l'onglet Planètes, groupe « Comètes », avec sa magnitude du moment : C/2025 A6 (Lemmon), brillante
en octobre 2025, est à la magnitude 20 fin 2026. Mettez la date de son passage pour la retrouver.

## 5. Tester

Dans `tests/test_engine.py`, `TestComets.test_position_and_magnitude` compare à JPL Horizons (quantités 1 et 9,
astrométrique, `EXTRA_PREC=YES`) : ajoutez une ou deux dates de la nouvelle comète, dont son périhélie. Les
comètes actuelles y sont à moins de 0,01″, la magnitude à 0,001 près. Les tests de l'interface suivent la liste tout seuls.

Voir [Tester ses modifications](Tester-ses-modifications.md).

## Limites à connaître

- La magnitude d'une comète est une **prévision** : les comètes s'éclairent ou s'éteignent souvent autrement.
- La queue n'est pas dessinée ; seule la position du noyau est calculée.
- Le tableau de l'onglet Coordonnées ne montre pas les comètes.
