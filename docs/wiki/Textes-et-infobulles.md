# Textes et infobulles

Tout texte de l'interface — libellé, bouton, infobulle, message, titre de graphique — vient des fichiers de
traduction [`locales/`](https://github.com/astraeos-dev/Celeste_App/tree/master/locales) : `fr.json` (la
référence), `en.json`, `es.json` et `de.json`. Le code n'écrit jamais de texte en dur ; il demande une **clé**.

```python
from i18n import t, tf

t("side.geoloc_tip")                        # texte simple
tf("events.separation", value="0,37")      # texte à trous : "Séparation {value}°"
```

Une clé `section.nom` désigne l'entrée `"nom"` de la section `"section"` du JSON :

```json
"side": {
  "geoloc_tip": "Détecter ma position (service de localisation de l'appareil, sinon adresse IP)"
}
```

## Changer un texte existant

1. **Trouver la clé** : cherchez le texte affiché dans `locales/fr.json` (Ctrl+F dans l'éditeur, ou
   `git grep "Détecter ma position" locales/fr.json`).
2. **Voir où il sert**, si besoin : `git grep "side.geoloc_tip"` — ici, le bouton de géolocalisation dans
   `gui.py` (`_icon_button("geolocate", t("side.geoloc_tip"))`).
3. **Modifier la valeur dans les quatre fichiers** `fr`, `en`, `es`, `de`.
4. **Vérifier** : `python -m pytest -q tests/test_i18n.py`, puis lancer l'application.

## Ajouter une infobulle (ou un texte)

1. Choisissez une section qui correspond à l'endroit (`planets`, `events`, `settings`, `detail`, `side`…) et
   un nom en anglais, en minuscules, avec des `_` : par exemple `planets.mag_tip`.
2. Ajoutez la clé **dans les quatre fichiers**, à la même place :

   ```json
   "mag_tip": "Magnitude visuelle : plus elle est petite, plus l'astre est brillant",
   ```

3. Dans `gui.py`, donnez-la au widget :

   ```python
   item.setToolTip(t("planets.mag_tip"))          # une cellule de tableau
   bouton.setToolTip(t("planets.mag_tip"))        # un bouton, une case, un menu…
   ```

## Où sont les infobulles actuelles

| Infobulle | Clé ou code |
|---|---|
| Boutons de la barre latérale | `side.*_tip` (création dans `_build_sidebar`) |
| Nom d'un astre dans l'onglet Planètes (visible, numéro d'une planète mineure) | `_update_planet_table` dans `gui.py` |
| « Cliquez sur un astre… » des tableaux | `detail.click_tip` |
| Choix « Tous / Planètes / Planètes mineures » | `planets.group_*_tip` |
| Bouton « Carte » des évènements et des éclipses | `event_map.button_tip`, `eclipse_map.button_tip` |
| Liens de Paramètres › À propos | `links.*_tip` |
| Survol de la carte du ciel | titre de la fiche (`_object_details` dans `gui.py`), dessiné par `charts._tooltip` |

## Règles vérifiées par les tests

- **Mêmes clés dans les quatre langues** : une clé absente ou en trop fait échouer `tests/test_i18n.py`.
- **Mêmes trous** `{…}` dans chaque traduction d'une clé (`{value}` en français → `{value}` partout).
- **Pas de valeur vide**, **pas d'emoji** (`tests/test_gui.py` : « pas d'emoji dans l'interface »). Pour un
  symbole astronomique, utilisez `SYMBOL["Venus"]` (dans `gui.py`), jamais le caractère seul.
- Le JSON reste en UTF-8, indenté de deux espaces.

## Conseils

- Restez **court** dans les tableaux et les en-têtes : ils sont calculés pour tenir dans une fenêtre de 1350 px
  (onglets Planètes et Coordonnées). Un en-tête plus long peut couper la dernière colonne.
- Une infobulle peut être plus longue : elle s'affiche au survol.
- Un texte qui contient une valeur (« Séparation 0,37° ») se fait avec `tf()` et un trou, jamais en collant des
  morceaux : l'ordre des mots change selon les langues.
- En français, `gui.py` élide « de » devant une voyelle dans les phrases « au nord de … »
  (`_elide`) : « au sud d'Antarès ».
