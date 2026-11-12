# Ajouter une langue

Exemple : l'italien (`it`).

1. **Copiez** `locales/fr.json` en `locales/it.json` et traduisez **les valeurs**, jamais les clés. Gardez les
   trous `{…}` tels quels : `"Séparation {value}°"` devient `"Separazione {value}°"`.
2. **Déclarez** la langue dans `_LANG_META` de
   [`i18n.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/i18n.py), avec son nom dans sa langue :

   ```python
   _LANG_META = {"fr": "Français", "en": "English", "es": "Español", "de": "Deutsch", "it": "Italiano"}
   ```

   Elle apparaît alors dans Paramètres › Langue ; « Automatique » la choisit si le système est en italien.
3. **Tests** : dans `tests/test_i18n.py`, ajoutez `"it"` aux listes `@pytest.mark.parametrize("code", ["es", "de"])`
   (mêmes clés que le français, mêmes trous).
4. **Formulaires et installateur** (facultatif) : le programme d'installation a ses langues dans la section
   `[Languages]` de [`installer/celeste.iss`](https://github.com/astraeos-dev/Celeste_App/blob/master/installer/celeste.iss)
   (`compiler:Languages\Italian.isl`).
5. **Lieux favoris préchargés** (facultatif) : dans
   [`favorites_default.json`](https://github.com/astraeos-dev/Celeste_App/blob/master/favorites_default.json), la clé
   d'un lieu est son nom français et `"names"` donne les autres (`"en"`, `"es"`, `"de"`). Ajoutez `"it": "Londra"` là
   où le nom italien diffère ; sans cela, la langue reçoit le nom anglais.
6. **Vérifiez à l'écran** : les tableaux des onglets Planètes et Coordonnées doivent tenir dans la largeur ; un
   en-tête trop long se raccourcit (« Dist. (UA) », « Asc. droite α »). La barre de la carte du ciel (magnitude
   limite, objets de Messier, recherche) doit tenir dans la fenêtre à sa largeur minimale.

Les dates restent au format `jj/mm/aaaa` dans toutes les langues ; les nombres suivent la langue (virgule ou
point décimal) grâce à `_num()` dans `ui/common.py`.
