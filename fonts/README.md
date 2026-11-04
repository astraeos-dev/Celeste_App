# Polices

Les polices du design system Astræos, livrées avec Céleste pour que l'interface
ait le même rendu sur toutes les machines. `gui.py` les déclare au démarrage
(`QFontDatabase.addApplicationFont`) et `charts.py` les donne à matplotlib.

| Fichier | Famille | Rôle |
|---|---|---|
| `IBMPlexSans-Regular.ttf` | IBM Plex Sans 400 | Texte courant (`corps`, `legende`) |
| `IBMPlexSans-SemiBold.ttf` | IBM Plex Sans 600 | Titres, boutons, onglets, libellés de champ |
| `IBMPlexMono-Medium.ttf` | IBM Plex Mono 500 | Données (`donnee`, `cadran`) : chiffres à chasse fixe |
| `AstraeosSymboles-Regular.ttf` | Astraeos Symboles | Symboles astronomiques (☉ ☽ ♀ ♂ ♃ ♄ ☌ ☍ ♈ …), après Plex dans chaque pile |

## Provenance et licences

- **IBM Plex Sans et IBM Plex Mono** : fichiers TTF du dépôt
  [IBM/plex](https://github.com/IBM/plex) (`packages/plex-sans` et `packages/plex-mono`,
  `fonts/complete/ttf/`), non modifiés. Licence SIL Open Font License 1.1, nom de police
  réservé « Plex » : voir `OFL-IBM-Plex.txt`.
- **Astraeos Symboles** : police du design system Astræos, sous-ensemble de Noto Sans
  Symbols, Symbols 2 et Math (34 symboles). Fichier WOFF2 du design system converti en TTF
  sans modification des glyphes ; les symboles d'Éris (U+2BF1), de Sedna (U+2BF2), de Haumea
  (U+1F77B) et de Makemake (U+1F77C) y sont copiés, tels quels, de Noto Sans Symbols 2
  (version 2.008) par `scripts/add_font_symbols.py`. Licence SIL Open Font License 1.1 : voir
  `OFL-Astraeos-Symboles.txt`.
