# Ajouter un instrument à l'atelier

L'atelier (bouton **Atelier** du panneau latéral) imprime des instruments calculés pour le lieu : carte tournante,
cadran solaire équatorial, cadran solaire horizontal. Cette fiche explique comment en ajouter un, par exemple le
nocturlabe ou le quadrant horaire prévus dans [docs/INSTRUMENTS.md](https://github.com/astraeos-dev/Celeste_App/blob/master/docs/INSTRUMENTS.md).

## Les trois couches

| Fichier | Ce qu'on y met |
|---|---|
| `instruments.py` | La **géométrie** seule : des fonctions qui prennent la latitude, la longitude, le décalage du fuseau et rendent des coordonnées en millimètres. Pas de Qt, pas de texte traduit. |
| `workshop.py` | Les **pages** : une fonction `_build_<instrument>(place, paper)` qui dessine chaque page avec matplotlib (un axe en millimètres, la règle de 100 mm et le pied de page sont ajoutés par `_Pages.new`), puis les fiches avec `_Pages.text_pages`. |
| `locales/*.json` | Les **textes**, dans la section `workshop` des quatre langues : nom, description, titres des pages, fiches. |

## Étapes

1. **La géométrie.** Écrivez la fonction dans `instruments.py`, avec ses conventions dans la docstring (origine,
   sens des axes, hémisphère sud). Réutilisez ce qui existe : `equatorial()` (hauteur et azimut vers déclinaison
   et angle horaire), `sun_vector()`, `dial_hour_angle()`, `dial_reading()`.
2. **Les tests d'abord.** Dans `tests/test_workshop.py`, deux sortes de tests :
   - une **formule fermée** connue (comme `tan θ = sin φ · tan H` pour le cadran horizontal) ;
   - le **ciel du moteur** : la lecture faite sur l'instrument doit correspondre à `AstroEngine` au même instant
     (l'ombre du vrai Soleil, la position d'une étoile…). Testez aussi l'hémisphère sud.
3. **Les pages.** Ajoutez `_build_<instrument>` dans `workshop.py`, puis son nom dans `INSTRUMENTS` et dans
   `instrument_pages()`. Traits de découpe avec `_cut()` (plus épais), traits dessinés en 0,3 à 0,6 pt, gris pour
   les aides. Les fiches suivent l'ordre des autres instruments : l'instrument, matériel et montage, utilisation,
   l'astronomie derrière, un exemple calculé par Céleste pour la date du panneau.
4. **Les textes.** Ajoutez les clés `workshop.<instrument>`, `workshop.desc_<instrument>` et celles des pages et des
   fiches dans `fr.json`, puis dans `en.json`, `es.json` et `de.json` (même ensemble de clés : le test des
   traductions le vérifie). Les listes numérotées s'écrivent `1. …` sur des lignes séparées par `\n`.
5. **Vérifier à l'œil.** Générez le PDF et regardez chaque page, au nord et au sud :

   ```bash
   python -c "import workshop, i18n; from datetime import datetime; from zoneinfo import ZoneInfo; i18n.switch_lang('fr'); workshop.print_instrument('planisphere', 'essai.pdf', workshop.Place('Cherbourg', 49.63, -1.62, ZoneInfo('Europe/Paris'), datetime(2026, 11, 12, 20)))"
   ```

   Imprimez une page : la règle doit mesurer 100 mm.
6. **Documenter.** Une ligne dans le CHANGELOG, le README (section Atelier) et `docs/INSTRUMENTS.md`.

## Bon à savoir

- Le lieu est un `workshop.Place` : `lat`, `lon`, `zone` (tzinfo), `when` (TU), `std_offset` (heure d'hiver du
  fuseau) et `has_dst`. `place.dst_hours(ut)` donne l'heure d'été d'un instant.
- L'atelier refuse les latitudes de moins de 10° et de plus de 80° (`_workshop_place` dans `gui.py`) : la carte
  tournante et le cadran horizontal y dégénèrent. Un nouvel instrument qui va plus loin peut assouplir cette règle.
- L'aperçu de la fenêtre appelle `preview_png()` : gardez la construction des pages rapide (une à deux secondes).
