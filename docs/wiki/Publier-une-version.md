# Publier une version

## 1. Le numéro

Le numéro de version est à **un seul endroit** : `APP_VERSION` dans
[`config.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/config.py). La fenêtre, Paramètres › À propos,
l'exécutable, le programme d'installation et les formulaires GitHub le lisent là.

- Fonctionnalité nouvelle : `4.2` → `4.3`. Correction seule : `4.2` → `4.2.1`.
- Notez les nouveautés du moteur en tête d'[`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py)
  (paragraphe `v4.3:`), et mettez le README à jour.

## 2. Fusionner, puis le tag

Une fois la PR fusionnée dans `master` :

```bash
git switch master
```
```bash
git pull
```
```bash
git tag v4.3
```
```bash
git push origin v4.3
```

Le tag lance le workflow **Build — application Windows**. Il **refuse** un tag qui ne correspond pas à
`APP_VERSION` (`v4.3` pour `4.3`) : changez d'abord le numéro, puis taguez.

On peut aussi lancer le build sans tag : onglet *Actions*, workflow « Build — application Windows »,
*Run workflow*.

## 3. Récupérer l'application

Dans le run du workflow, rubrique *Artifacts* :

- **Celeste-Windows-Setup** : le programme d'installation `Celeste-4.3-Setup.exe` (icône de Céleste, raccourcis,
  désinstallation dans les paramètres de Windows) ;
- **Celeste-Windows** : le dossier de l'application, à lancer sans installer (`Celeste.exe`).

Les artefacts sont gardés 90 jours. L'application n'est pas signée : SmartScreen demande une confirmation au
premier lancement (*Informations complémentaires*, puis *Exécuter quand même*).

## Construire sur son PC

```bash
pip install pyinstaller
```
```bash
python scripts/build_exe.py
```

Le script construit `dist/Celeste/`, vérifie qu'il démarre, crée l'archive et, si
[Inno Setup 6](https://jrsoftware.org/isinfo.php) est installé, le programme d'installation dans `dist/`.
