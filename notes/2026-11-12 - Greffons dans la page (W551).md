# Greffons de SmartPythonEditor dans la page (W551, 12/11/2026)

Demande : item 14 du TODO Portage (« Les treize greffons ») et tiret `EN_RETARD` de l'item 13, ordre du professeur du
12/11 14:04 (« mets des workers sur tous les items qui peuvent être traités indépendamment »). Ajouts en cours de route,
demandés par le Superviseur : défaut de `construire_site.py` relevé par W552 (archive corrompue), et paquets pylsp de W548.

## FAIT

- **Règle du `CLAUDE.md` sur `/DATA/Python/FORKS/SmartPythonEditorPlugins/`** (hors tests) : 0 ligne, 0 fichier.
- **`EN_RETARD` retiré** : les six fichiers sont identiques (`cmp`) entre le fork du 01/11 et l'environnement installé.
- **Quatre greffons embarqués** (`essais/spyder/construire_site.py`, `GREFFONS`) : `spyder_code_analysis`,
  `spyder_smartteacher`, `spyder_collab`, `spyder_python_tutor` ; pylint, astroid, isort, tomlkit, dill, mccabe pris dans
  l'environnement installé de SmartPythonEditor (ajouté en FIN de `sys.path` : le Python de construction ne les a pas).
  Leurs `PKG-INFO` et `entry_points.txt` sont écrits depuis le `pyproject.toml` de chaque greffon (`_greffons()`) :
  `spyder_smartteacher` n'a pas d'egg-info dans le dépôt. Existant : aucun lecteur de pyproject dans le dépôt (grep
  `tomllib`) ; l'egg-info des autres greffons, écarté parce qu'absent pour l'un et construit à la main pour les autres.
- **Défaut de l'archive (W552)** : le constructeur de qtpy6 prend tout le dossier du script ; il y avait 22 Mio de
  captures et journaux, et un dossier `chrome/` (43 Mio) d'un autre worker écrit PENDANT l'assemblage → 6 719 membres sur
  7 088 illisibles (« Bad magic number », décalage d'un octet mesuré à `capture_auto.png`). Correctifs : (a) de la racine
  du dossier, les `.py` seuls ; `chrome/`, tout dossier de site (porteur d'un `index.html`) et les `.log` exclus ;
  (b) archive écrite en `app.zip.<pid>.provisoire` puis `os.replace`, effacée en cas d'échec ; (c) `--sortie <dossier>`
  (argparse, forme `--sortie=` comprise, dossiers parents créés). Archive : 44 114 → 36 953 Kio, pylsp compris.
  Relecteur : quatre points corrigés (forme `--sortie=`, `mkdir` sans parents, `.log` des sous-dossiers, nom provisoire
  partagé). Mesuré après : `--sortie=$TMPDIR/a/b` → 0, `--sortie` sans valeur → 2, site commun → 0 ; `testzip` sain,
  aucun `.log`, `chrome/` ni `site` dans l'archive, aucun provisoire restant.
- **pylsp (W548, jalon 8d)** : `pylsp pylsp_jsonrpc pluggy docstring_to_markdown pyflakes`, `pycodestyle`, et le
  dist-info `python_lsp_server-1.14.0` (METADATA, entry_points.txt), même dossier installé (le chemin donné par W548 est
  un lien vers lui, `readlink -f`). Vérifié : présents dans l'archive ; le 5/5 de `jalon8d.py` reste à W548.
- **Essai** `essais/spyder/greffons.py` (fichier neuf) : spe.py avec le volet pylint gardé actif, puis un relevé par
  greffon (inscrit ou non) et son action. Fichier hors brief, neuf, propre à cet essai.

## VÉRIFIÉ (sonde Firefox, `site/index.html?script=greffons.py`, mesuré)

| Greffon | Verdict | Cause |
|---|---|---|
| spyder_code_analysis | inscrit ; action non mesurée | — |
| spyder_python_tutor | inscrit ; action non mesurée | voir ci-dessous |
| spyder_stop_toolbar, interpreter_toolbar, pyxel | inscrits (inchangé) | — |
| spyder_collab | **casse** à l'import | `cannot import name 'QNetworkInterface' from 'qtpy.QtNetwork'` (network.py:43) |
| spyder_smartteacher | **absent**, aucune erreur au journal | non mesuré |

Les 34 greffons internes passent toujours (« 34 passe, 0 casse »), page en 25 s, tas 215 Mio. Les actions (bouton
Docteur, « Lancer » du tuteur) n'ont rien imprimé : la page ne rend plus rien après la liste des greffons (sonde arrêtée
à 300 s). Piste non suivie : `editor.load` ou le `QTimer` de `SUITE_GREFFONS`.

## Lu dans les sources (pas mesuré)

- **spyder_collab** : QtNetwork est compilé (`pyside_QtNetwork.so`) mais sans `QNetworkInterface`, et un navigateur
  n'écoute pas (`QTcpServer`). Doublure qtpy6 à écrire : `QTcpServer`/`QTcpSocket`/`QNetworkInterface` sur un relais
  WebSocket (QtWebSockets est compilé) hors navigateur. Pas petite : non écrite.
- **spyder_smartteacher** : `client.py:35` lance `pont.py` par `subprocess.Popen` avec le Python de SmartTeacher et le
  dossier `/DATA/Python/SmartTeacher/QCM` (`pont.py:16`, `from modele import …`) : la doublure `subprocess.Popen` de
  qtpy6 lance un Python, mais le dossier QCM n'est pas dans la page. Réglage à donner (dossier QCM), pas une branche.
- **spyder_python_tutor** : la doublure `moteur_web.py` n'a pas `renderProcessTerminated` (`main_widget.py:385`,
  `page.renderProcessTerminated.connect`) → AttributeError à la 1re trace ; W546 étant fermé, signalé au Superviseur. Le traçage passe par
  `QProcess(sys.executable, run_trace.py)` → `ProcessusWeb`.
- **spyder_code_analysis** : passe par le volet pylint de Spyder (`QProcess(sys.executable, -m pylint)`), que spe.py
  désactive ; il faut l'activer dans la configuration pour que le bouton Docteur serve.

Modification de greffon à noter pour le professeur : aucune nécessaire (les causes sont des manques de qtpy6).

Alternative écartée pour (a) : modifier `qtpy6/web/construire.py` pour ne prendre que les sources (hors de mes
fichiers) ; le filtre est dans l'assembleur local de l'essai.

Écart de méthode : un `find /` lancé pour trouver `viz.html` (interdit : jamais récursif sur `/`) ; relevés faits
moi-même (une dizaine de commandes groupées) plutôt que par `releve`, pour suivre le diagnostic de l'archive.
