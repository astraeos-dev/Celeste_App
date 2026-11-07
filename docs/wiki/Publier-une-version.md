# Publier une version

## 1. Le numéro

Le numéro de version est à **un seul endroit** : `APP_VERSION` dans
[`config.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/config.py). La fenêtre, Paramètres › À propos,
l'exécutable, le programme d'installation et les formulaires GitHub le lisent là.

- Fonctionnalité nouvelle : `4.3` → `4.4`. Correction seule : `4.3` → `4.3.1` (le moteur ne change pas : pas de
  nouveau paragraphe dans `engine.py`).
- Notez les nouveautés du moteur en tête d'[`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py)
  (paragraphe `v4.3:`, que le test `test_version_is_single_sourced` réclame), et mettez le README à jour.

## 2. Fusionner : la version se publie toute seule

Quand une PR qui change `APP_VERSION` est fusionnée dans `master`, le workflow **Build — application Windows**
construit l'application et publie la **Release** `v4.3` : le programme d'installation `Celeste-4.3-Setup.exe` et
son empreinte `Celeste-4.3-Setup.exe.sha256`, avec des notes tirées des PR fusionnées. Rien ne se passe si la
version est déjà publiée : modifier `config.py` sans changer le numéro ne publie pas deux fois.

On peut encore pousser un tag à la main (`git tag v4.3` puis `git push origin v4.3`) : le workflow vérifie qu'il
correspond à `APP_VERSION`. Depuis l'onglet *Actions* (*Run workflow*), il construit sans publier.

## 3. La mise à jour chez l'utilisateur

Céleste installé cherche une version plus récente au démarrage (après quelques secondes, sans bloquer la fenêtre)
et quand on clique sur **Paramètres › À propos › Vérifier les mises à jour**. S'il en trouve une, une fenêtre la
propose :

- **Mettre à jour** : le programme d'installation est téléchargé, son empreinte SHA-256 vérifiée, puis il
  s'installe par-dessus l'ancienne version en mode silencieux (fenêtre de progression seule) ; Céleste se ferme
  et se rouvre. Réglages, favoris et éphéméride (`%USERPROFILE%\.celeste`) sont conservés.
- **Voir la version** : la page de la Release sur GitHub.
- **Ignorer cette version** : elle n'est plus proposée au démarrage (le bouton de vérification la montre encore).
- **Plus tard**.

L'éphéméride JPL (32 Mo) n'est pas dans le programme d'installation : Céleste la télécharge une fois, à son premier
lancement, dans `%USERPROFILE%\.celeste`, et une mise à jour ne pèse donc qu'environ 80 Mo. Une installation antérieure
à la 4.4 garde la sienne dans le dossier du programme, où Céleste la trouve encore : rien n'est retéléchargé.
`scripts/build_exe.py` vérifie qu'elle n'est pas dans l'application construite.

Si une mise à jour ne s'installe pas, le journal du programme d'installation est dans
`%TEMP%\Celeste-update\install.log` (dans l'Explorateur : `%TEMP%` dans la barre d'adresse).

La case « Vérifier au démarrage » coupe la recherche automatique. Depuis les sources (`python main.py`), la
fenêtre rappelle de mettre à jour avec `git pull`.

Le code est dans [`updater.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/updater.py) (sans Qt) et
dans `check_updates()` de `gui.py` ; l'installation silencieuse rouvre Céleste grâce à la ligne `skipifnotsilent`
de `installer/celeste.iss`.

> La première version qui sait se mettre à jour (4.3) s'installe encore à la main ; les suivantes se mettent à
> jour seules.

## 4. Les artefacts du workflow

Dans chaque run du workflow, rubrique *Artifacts* :

- **Celeste-Windows-Setup** : le programme d'installation ;
- **Celeste-Windows** : le dossier de l'application, à lancer sans installer (`Celeste.exe`).

Les artefacts sont gardés 90 jours, les Releases pour toujours. L'application n'est pas signée : SmartScreen
demande une confirmation au premier lancement d'un installateur téléchargé à la main (*Informations
complémentaires*, puis *Exécuter quand même*).

## Construire sur son PC

```bash
pip install pyinstaller
```
```bash
python scripts/build_exe.py
```

Le script construit `dist/Celeste/`, vérifie qu'il démarre, crée l'archive et, si
[Inno Setup 6](https://jrsoftware.org/isinfo.php) est installé, le programme d'installation dans `dist/`.
