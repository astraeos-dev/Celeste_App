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
  Symbols, Symbols 2 et Math (30 symboles). Fichier WOFF2 du design system converti en TTF
  sans modification des glyphes. Licence SIL Open Font License 1.1 : voir
  `OFL-Astraeos-Symboles.txt`.
