# Publier une version

## 1. Le numéro

Le numéro de version est à **un seul endroit** : `APP_VERSION` dans
[`config.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/config.py). La fenêtre, Paramètres › À propos,
l'exécutable, le programme d'installation et les formulaires GitHub le lisent là.

- Fonctionnalité nouvelle : `4.3` → `4.4`. Correction seule : `4.3` → `4.3.1` (le moteur ne change pas : pas de
  nouveau paragraphe dans `engine.py`).
- Notez les nouveautés du moteur en tête d'[`engine.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/engine.py)
  (paragraphe `v4.5:`, que le test `test_version_is_single_sourced` réclame), et mettez le README à jour.

## 2. La note de version : `CHANGELOG.md`

Ajoutez en tête de [`CHANGELOG.md`](https://github.com/astraeos-dev/Celeste_App/blob/master/CHANGELOG.md) une
section au numéro de la version :

```markdown
## 4.6

- Ce qui change pour l'utilisateur, en une phrase.
- Une ligne par nouveauté ou correction.
```

Cette section devient **la note de la Release** sur GitHub et le texte de la **fenêtre de mise à jour** : écrivez
pour les utilisateurs, en français, en tirets, sans gras ni code (les versions 4.4 et antérieures afficheraient les
balises), en 800 caractères au plus (la fenêtre coupe la suite). `scripts/release_notes.py 4.6` montre ce qui sera
publié. Les tests (`tests/test_release_notes.py`) refusent une version sans section, et le workflow s'arrête avant
de construire plutôt que de publier une Release sans note.

## 3. Fusionner : la version se publie toute seule

Quand une PR qui change `APP_VERSION` est fusionnée dans `master`, le workflow **Build — Windows application**
construit l'application et publie la **Release** `v4.3` : le programme d'installation `Celeste-4.3-Setup.exe` et
son empreinte `Celeste-4.3-Setup.exe.sha256`, avec la note de la version tirée de `CHANGELOG.md`. Rien ne se passe si la
version est déjà publiée : modifier `config.py` sans changer le numéro ne publie pas deux fois.

On peut encore pousser un tag à la main (`git tag v4.3` puis `git push origin v4.3`) : le workflow vérifie qu'il
correspond à `APP_VERSION`. Depuis l'onglet *Actions* (*Run workflow*), il construit sans publier.

## 4. La mise à jour chez l'utilisateur

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
`%TEMP%\Celeste-update\install.log` (dans l'Explorateur : `%TEMP%` dans la barre d'adresse). Si elle ne se
télécharge pas, `update.log`, dans le même dossier, garde chaque tentative et son erreur (depuis la 4.7.1) : la
dernière version et ses fichiers sont demandés à l'API GitHub, puis à github.com, en trois tentatives. Lors d'un
incident GitHub, les applications sans compte, comme Céleste, peuvent recevoir des erreurs 503 ou 504 pendant un moment.
Une version 4.7 ou antérieure fermait la fenêtre de progression sans rien dire en cas d'échec : il faut alors installer
la nouvelle version à la main, depuis la page de la Release.

La case « Vérifier au démarrage » coupe la recherche automatique. Depuis les sources (`python main.py`), la
fenêtre rappelle de mettre à jour avec `git pull`.

Le code est dans [`updater.py`](https://github.com/astraeos-dev/Celeste_App/blob/master/updater.py) (sans Qt) et
dans `check_updates()` de `ui/settings_tab.py` ; l'installation silencieuse rouvre Céleste grâce à la ligne `skipifnotsilent`
de `installer/celeste.iss`.

> La première version qui sait se mettre à jour (4.3) s'installe encore à la main ; les suivantes se mettent à
> jour seules.

## 5. Les artefacts du workflow

Dans chaque run du workflow, rubrique *Artifacts* :

- **Celeste-Windows-Setup** : le programme d'installation ;
- **Celeste-Windows** : le dossier de l'application, à lancer sans installer (`Celeste.exe`).

Les artefacts sont gardés 90 jours, les Releases pour toujours. L'application n'est pas signée : SmartScreen
demande une confirmation au premier lancement d'un installateur téléchargé à la main (*Informations
complémentaires*, puis *Exécuter quand même*).

## 6. Les versions bêta : tester avant la pull request

Chaque push sur une branche de travail (`claude/…` ou `beta/…`) lance le workflow **Beta — test build for Windows**
([`.github/workflows/beta.yml`](https://github.com/astraeos-dev/Celeste_App/blob/master/.github/workflows/beta.yml)) :

1. les tests (Python 3.12) ;
2. la construction de Céleste en bêta : le panneau latéral affiche « 4.12 bêta 7 » (7 = le numéro du run) ;
3. une **pré-version** GitHub `v4.12-beta.7` avec son programme d'installation, dans la page
   [Releases](https://github.com/astraeos-dev/Celeste_App/releases), marquée *Pre-release*.

Pour tester : ouvrez la page Releases, prenez la pré-version la plus récente, téléchargez
`Celeste-4.12-beta.7-Setup.exe` et installez-le par-dessus la version en place (les réglages et les favoris sont
gardés). On peut aussi lancer le workflow à la main sur n'importe quelle branche : onglet *Actions*, *Beta*,
*Run workflow*.

- Les pré-versions ne sont **jamais proposées** par la mise à jour automatique : elle demande à GitHub la dernière
  version publiée, qui les exclut. Seul qui télécharge une bêta l'installe.
- Une bêta se met à jour d'elle-même vers la version définitive de son numéro (4.12 bêta 7 → 4.12) dès sa
  publication.
- Seules les trois bêtas les plus récentes sont gardées ; les plus anciennes et leurs tags sont supprimés.
- Un push qui ne touche que la documentation (`*.md`, `docs/`) ne construit pas de bêta.

Le cycle : on travaille sur la branche, chaque push donne une bêta à essayer ; quand elle convient, on ouvre la pull
request ; sa fusion publie la version (étape 3).

## 7. Signer l'application (fin de l'avertissement SmartScreen)

Sans signature, Windows affiche « Windows a protégé votre ordinateur » et « éditeur inconnu » au premier lancement
du programme d'installation. Une signature de code nomme l'éditeur ; SmartScreen se tait ensuite à mesure que la
réputation du certificat grandit (quelques centaines d'installations, ou tout de suite avec un certificat EV).

Depuis juin 2023, les clés de signature de code restent sur un matériel (clé USB, ou service en ligne) : on ne
reçoit plus de fichier `.pfx`. D'où deux voies, que le dépôt sait déjà utiliser :

| Voie | Coût | Où se fait la signature |
|---|---|---|
| **SignPath Foundation** (signpath.org), gratuit pour les projets libres (Céleste est sous licence MIT) | gratuit, sur dossier | dans le workflow *Build*, à chaque version publiée |
| **Certificat « Open Source Code Signing » de Certum**, avec SimplySign (clé dans le nuage) | quelques dizaines d'euros par an | sur ton PC, avec `python scripts/build_exe.py` |

**SignPath : la demande.** Le formulaire est sur [signpath.org/apply](https://signpath.org/apply). Les
conditions ([signpath.org/terms](https://signpath.org/terms)) : licence libre approuvée par l'OSI pour tout le
projet (MIT : oui), aucun composant propriétaire, projet maintenu et déjà publié sous la forme à signer (les
Releases GitHub), fonctionnement décrit sur la page de téléchargement (le README), double authentification (2FA)
sur GitHub et sur SignPath pour toute l'équipe, chaque signature approuvée à la main. Ce qu'on renseigne :

| Information | Pour Céleste |
|---|---|
| Nom du projet | Céleste |
| Dépôt | https://github.com/astraeos-dev/Celeste_App |
| Page d'accueil / de téléchargement | https://github.com/astraeos-dev/Celeste_App (README) et https://github.com/astraeos-dev/Celeste_App/releases |
| Licence | MIT |
| Description | Application de bureau d'astronomie : positions du Soleil, de la Lune, des planètes et des étoiles, évènements, carte du ciel, instruments à imprimer (Python, Qt) |
| Fichiers à signer | le programme d'installation Windows `Celeste-<version>-Setup.exe` (Inno Setup), construit par GitHub Actions |
| Système de construction | GitHub Actions (workflow `build.yml`), sur les runners hébergés par GitHub |
| Politique de signature | la section « Code signing policy » du README |
| Confidentialité | la section « Privacy » du README (Céleste se connecte à quelques services : la section les liste) |
| Rôles | auteur, relecteur et approbateur : le compte astraeos-dev |

**SignPath : après l'acceptation.**

1. Dans SignPath, *Trusted Build Systems* : ajouter le système prédéfini **GitHub.com** à l'organisation, puis le
   lier au projet.
2. Installer l'application GitHub [SignPath](https://github.com/apps/signpath) sur le dépôt `Celeste_App`.
3. Dans le projet SignPath : une configuration d'artefact qui signe le programme d'installation à l'intérieur de
   l'archive que GitHub Actions envoie (un zip) :

   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <pe-file path="Celeste-*-Setup.exe">
         <authenticode-sign/>
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

   SignPath Foundation peut demander d'y ajouter des contraintes sur les métadonnées du fichier (nom du produit
   « Céleste », éditeur « Astræos » : le programme d'installation les porte).
4. Créer un utilisateur CI dans SignPath, avec le droit de soumettre des demandes sur la politique
   `release-signing`, et copier son jeton d'API.
5. Dans GitHub, *Settings › Secrets and variables › Actions* :
   - variable `SIGNPATH_ORGANIZATION_ID` : l'identifiant de l'organisation SignPath ;
   - secret `SIGNPATH_API_TOKEN` : le jeton de l'utilisateur CI ;
   - facultatif : variables `SIGNPATH_PROJECT_SLUG` (par défaut `Celeste_App`) et `SIGNPATH_POLICY_SLUG` (par
     défaut `release-signing`) si les noms diffèrent.

Le workflow *Build* envoie alors le programme d'installation à SignPath, attend la signature (approuvée à la main
dans SignPath à chaque version) et publie le fichier signé. Sans ces réglages, il publie comme avant, sans
signature. Les bêtas ne sont pas signées.

**Sur son PC** (certificat installé dans Windows, par exemple Certum SimplySign connecté) :

```bash
set CELESTE_SIGN_THUMBPRINT=<empreinte SHA-1 du certificat>
```
```bash
python scripts/build_exe.py
```

`Celeste.exe` puis le programme d'installation sont signés avec `signtool` (Windows SDK) et horodatés. Un ancien
certificat en fichier `.pfx` reste possible : `CELESTE_SIGN_PFX` (chemin) et `CELESTE_SIGN_PASSWORD`.

## Construire sur son PC

```bash
pip install pyinstaller
```
```bash
python scripts/build_exe.py
```

Avec `CELESTE_BETA=7` dans l'environnement, il construit une bêta (fichiers `Celeste-4.12-beta.7-…`).
Le script construit `dist/Celeste/`, vérifie qu'il démarre, crée l'archive et, si
[Inno Setup 6](https://jrsoftware.org/isinfo.php) est installé, le programme d'installation dans `dist/`.
