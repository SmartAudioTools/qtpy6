# PySide6 en WebAssembly : journal du projet

Plan d'ensemble (étapes 0 à 8) : `~/.claude/plans/prancy-frolicking-dongarra.md` au moment de l'écriture ; son
contenu sera recopié dans `wasm/README` à l'étape 0. Ce journal se complète à la fin de chaque étape.

Demandes de l'utilisateur, 30/09 et 01/10/2026 :
- « peux tu faire un plan pour passer la version web de qtpy6 à une compilation WASM de PySide6 ? »
- « qu'est ce qui te permettra d'itérer le plus vite ? » → compilation en local, lancée par moi ; PyQt6 reste en repli.
- « PySide6 sera compilé avec le lecteur de pdf ? » → non, QtPdf (pdfium, chaîne gn) n'a pas de cible WASM ; la
  doublure pdf.js reste.
- « ok peut-on commencer par ce qui nécessite fable, puis on passera sur opus pour le reste pour la nuit » → l'étape 6
  (ci-dessous) d'abord, les étapes mécaniques de compilation ensuite.
- « un autre session travaille en parallèle sur le fluidification des animations. fait attention ça pourrait fausser
  certains tests » → `qtpy6/animation.py`, `tests/test_animation.py`, `CHANGELOG.md`, `README.md` et les lignes
  `animation.doubler(globals())` de `qtpy6/QtCore.py` sont à cette autre session, pas à celle-ci.

## Étape 6 — `qtpy6.web` indépendant de la liaison (01/10/2026)

**But** : que les doublures du navigateur (`bloquant`, `fils`, les `exec` suspendus par JSPI) se posent sous PySide6
comme sous PyQt6, avant même qu'un PySide6-WASM existe, pour que l'étape 5 ne teste que le build.

**Niveau de preuve** : `tests/test_web.py` vert sous `QT_API=pyqt6` ET `QT_API=pyside6` en natif (SmartPython,
PySide6 6.11.1, PyQt6, greenlet ; 27 tests, 5 s et 9 s). Sous le Pyodide-Qt local, par node (`site/pyodide-qt`,
dépôt monté en NODEFS) : `qtpy6.API == "pyqt6"` sans forçage, Qt 6.10.2, `QMenu.exec` doublé. **Rien n'est testé
dans un navigateur ni sous un PySide6-WASM** (il n'existe pas encore).

### Livré

- `qtpy6/web/bloquant.py` : doublures posées quelle que soit la liaison. `_mort()` rend `sip.isdeleted` ou
  `not shiboken6.isValid` ; `_est_destroyed(signal)` lit `signal.signal` (PyQt6) ou le `str()` du SignalInstance
  (PySide6 : `<... SignalInstance destroyed() at ...>`, seul endroit où le nom est lisible). `_pyodide_pomper(ns)`
  prend l'espace de noms de QtCore (plus d'import PyQt6). Les relais de slots sont deux classes : `Relais(QObject)`,
  enfant du receveur, pour une méthode d'un QObject ; `RelaisFonction` pour le reste. `disconnect_` passe par le
  relais existant. Les `exec` de QMenu sous PySide6 passent par `__getattribute__` (`par_instance`).
- `qtpy6/web/fils.py` : `QTimer` importé de `..QtCore`.
- `qtpy6/QtCore.py`, `QtGui.py`, `QtWidgets.py` : les gardes `and PYQT6` / `if not PYSIDE6` retirées.
- `qtpy6/web/js/qtpy6web.js` : plus de `QT_API=pyqt6` forcé ; `auto` prend ce que le Pyodide chargé contient
  (vérifié sous node, ci-dessus). Commentaires d'en-tête corrigés.
- `tests/test_web.py` : `pyqt6_seul` devient `greenlet_seul` ; la simulation du navigateur (`SIMULATION`) est
  réécrite sur la liaison des tests ; `en_navigateur` transmet `QT_API` au sous-processus ; le test de police
  complète son `js` factice (`setInterval`, `Function.new`) que la pompe et `_dessiner_aussitot` touchent désormais.

### Choix, et alternatives écartées

- **Deux classes de relais plutôt qu'une fonction par connexion (l'ancien code).** Sous PySide6, `sender()` ne vaut
  que sur le receveur Qt lui-même, et une connexion à une fonction n'est pas déconnectable par le slot d'origine :
  il faut un objet retrouvable (`relais`, WeakValueDictionary par `(id(receveur), fonction, direct)`) et, pour les
  méthodes de QObject, un QObject enfant qui meurt avec le receveur comme la connexion native. Écarté : un seul
  `Relais(QObject)` pour tout (une lambda aurait gardé un QObject sans parent, jamais libéré : le test « vivant puis
  libéré » l'attrape) ; un relais `__call__` sur le QObject lui-même au lieu de la méthode liée `relais` (non mesuré,
  écarté par lecture : c'est la méthode liée d'un QObject que les deux liaisons attachent à la durée de vie du
  receveur, un appelable quelconque est un mandataire sans receveur).
- **`disconnect_` par le relais existant.** Sous PySide6, déconnecter un appelable inconnu n'est qu'un
  RuntimeWarning, donc un slot relayé jamais déconnecté passerait inaperçu. Testé : le menu qui resert n'empile pas
  ses connexions, `receivers("2aboutToHide()")` compté.
- **`UniqueConnection` : le sort natif de chaque liaison, pas une règle commune.** PyQt6 lève TypeError au doublon ;
  PySide6 déduplique en silence une méthode liée et refuse, avec un avertissement, une fonction. Le test compare
  connexion relayée et connexion native (`_connect_qt[0]`) plutôt que d'attendre une valeur fixe.
- **`par_instance` : `__getattribute__` sur les classes dont `exec` a une forme statique (QMenu).** Mesuré sous
  PySide6 6.11 : `vars(QMenu)["exec"]` est un `staticmethod`, et le getattro généré par shiboken pour ces méthodes
  à deux formes rend la native sur une instance quoi que porte le dictionnaire de classe (descripteur de données
  et `del` sans effet ; un sous-type Python n'est pas touché ; `object.__getattribute__` voit bien la fonction
  Python). Écarté : remplacer la méthode dans le dictionnaire seul (inopérant), sous-classer QMenu (les QMenu
  créés par Qt ou par l'application n'en seraient pas). `QDialog.exec` n'a pas de forme statique : doublé normalement.
- **Le banc d'essai imite la pompe du navigateur, pas une boucle `exec()`.** `_vivre` fait `processEvents`, puis
  `sendPostedEvents(None, DeferredDelete)` quand aucune pile n'est suspendue, puis reprend les tâches en attente
  entre deux tours de Qt — comme `_pyodide_pomper`. Mesuré : sans le `sendPostedEvents`, un `deleteLater` posté
  depuis `processEvents` au niveau 0 n'est jamais livré (règle Qt : il faut une boucle exec ou cet appel explicite),
  et le mandataire de slot de PyQt6 n'était pas libéré (« vivant puis libéré False »).
- **Diagnostic corrigé en cours de route.** Le SIGSEGV dans `QMenu::hideEvent` / `QEventLoop::exit` sous PySide6
  avait d'abord été attribué aux bascules greenlet dans un rappel Qt ; la cause était l'`exec` natif de QMenu (boucle
  imbriquée) tournant dans un greenlet parce que la doublure n'atteignait pas les instances (point précédent).
  Les anciens scénarios du banc passent une fois `par_instance` en place.
- **Le forçage `QT_API=pyqt6` du chargeur JS est retiré plutôt que rendu paramétrable.** `_select_api` en `auto`
  prend la première liaison dont `find_spec` répond : vérifié sous Pyodide-Qt, PySide6 absent, PyQt6 trouvé. Un
  Pyodide-PySide6 fera l'inverse sans rien changer au chargeur.

### Passe de simplification (par fichier du changement)

- `bloquant.py` : la clé du dictionnaire de relais, calculée deux fois (`existant`, `relayer`), factorisée en
  `cle()` ; `appel` gardé sur les deux classes (voir ci-dessus). Suites relancées après : vertes.
- `fils.py`, `QtCore.py`, `QtGui.py`, `QtWidgets.py`, `qtpy6web.js` : regardés, rien à enlever.
- `test_web.py` : `SIMULATION` n'a plus `_exec/_quit/_un_coup` (la page vit par `_vivre`) ; regardé, rien d'autre.

### Points ouverts, à regarder en premier

- `web.md` et le README mentionnent encore PyQt6 pour le navigateur : à l'étape 7 avec `versions.json` et la licence.
- Le dépôt contient des fichiers non suivis (`.bashrc`, `.zshrc`, `.idea`, `rapport_bug_qt_qpdfview.md`…) qui ne
  viennent pas de cette session : à ne pas commiter avec l'étape.
- `_est_destroyed` sous PySide6 repose sur le `str()` du SignalInstance : fragile si une version le change ; un test
  le couvre (le relais d'un `destroyed` est appelé directement, sans report).

## Étapes 0 et 1 — sources, puis chaîne de construction (01/10/2026, nuit, Opus 5.5)

Demande : *« ok opus , commence, je suis encore là pour ecrire des commande pour le telechargement »*.

### Livré

- `wasm/telecharger_sources.sh`, lancé par l'utilisateur (le shell de Claude n'a aucun réseau) : archives Qt et
  pyside-setup 6.10.2 contrôlées par md5, Pyodide 0.29.3 avec ses sous-modules, le tarball CPython contrôlé par
  sha256, libffi et hiwire aux commits exacts que demande `cpython/Makefile`, `npm ci` de `src/js`, la recette
  Pyodide-Qt, emdawnwebgpu, et les ports emscripten zlib et bzip2. Empreintes dans `wasm/versions.txt`.
- `wasm/construire.sh <phase>...`, hors réseau, chaque phase rejouable, journal par phase dans
  `/DATA/Python/outils_wasm/pyside6/journaux/`. Arbre de travail : `/DATA/Python/outils_wasm/pyside6/`.

### Choix, et alternatives écartées

- **Copie privée de l'emsdk, corrigée, plutôt que l'emsdk partagé d'`outils_wasm`.** Pyodide applique quatre patchs
  à emscripten 4.0.9 (`emsdk/patches/`) ; l'emsdk partagé ne les a pas (vérifié : ils s'y appliquent tous à blanc).
  Les appliquer au partagé aurait changé l'outil dont dépend la roue serializejson. Copie : 1,4 Go, 6 s.
  `struct_info_generated.json` vérifié identique à celui de Pyodide (même contrôle que `emsdk/Makefile`).
- **Le cache emscripten de la copie est vidé** : ses bibliothèques système avaient été construites sans les patchs.
- **Qt hôte 6.10.2 construit depuis l'archive qtbase**, le Qt système étant en 6.11 : `-qt-host-path` exige la même
  version, et le générateur shiboken doit lire les en-têtes de la version cible.
- **libffi et hiwire : `make LIBFFIREPO=<clone local>`** plutôt qu'un patch du Makefile de CPython. Le `git fetch`
  du Makefile accepte un chemin local ; il faut seulement `uploadpack.allowAnySHA1InWant` et `safe.directory`
  (clones faits par un autre compte), passés par `GIT_CONFIG_*` dans l'environnement.

### Pièges du bac à sable rencontrés (testés)

- `/DATA/Python/outils_wasm` est setgid, d'un groupe non mappé dans le bac à sable : `cp -a`, `sed -i` et `patch`
  y échouent en « Argument invalide » en voulant recopier groupe ou droits (la donnée, elle, est écrite).
  Parade : les dossiers de construction sont créés par `dossier()`, avec le groupe `claude` et sans setgid (testé :
  `patch` y passe, l'ACL par défaut qui donne l'accès au compte principal reste) ; `sed -i` remplacé par
  `remplacer()` (réécriture sur place) ; les patchs de l'emsdk par `git apply`.
- **L'environnement de session exporte `CFLAGS=CXXFLAGS=FFLAGS=-march=native`** (réglage CachyOS). Les phases hôte
  s'en accommodent, mais emscripten le refuse (« unsupported option '-march=' for target wasm32 ») : le premier
  essai de Qt-WASM a échoué au test d'architecture, et celui de CPython à la compilation de `Parser/`. Les deux
  scripts n'avaient pourtant rendu aucun code d'erreur visible, car le `tee` était en fin de pipeline. Parade :
  `emsdk_env()` et `pyodide_env()` vident ces quatre variables. Alternative écartée : passer `-march=` à vide
  ou filtrer la variable, ce qui serait plus fragile qu'un `unset` pour des drapeaux qui ne visent que l'hôte.

### Résultats (01/10/2026, nuit)

- **emsdk** : `emcc 4.0.9` répond, patchs appliqués. Testé.
- **qthote** : Qt 6.10.2 natif installé dans `qt-hote/` (qmake6, moc, rcc, uic, QtCore/Gui/Widgets). Testé.
- **shiboken** : `shiboken6 --version` répond « shiboken v6.10.2 » (libclang système 22.1.8, Qt hôte 6.10.2). Testé.
- **qt** : Qt 6.10.2 statique pour WASM installé dans `qt-wasm/` (`libQt6Core/Gui/Widgets/Svg/SvgWidgets.a`,
  greffon `libqwasm.a`, imageformats, iconengines), environ 6 min. Testé (archives présentes).
- **cpython** : `libpython3.13.a` et ses en-têtes dans `sources/pyodide/cpython/installs/python-3.13.2/`. Testé.

### Étape 3 : PySide6 en compilation croisée

Trois corrections de configuration, toutes dans `phase_pyside` :
- **`CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`.** La chaîne emscripten restreint `find_package` à sa racine, et
  rendait introuvables la config Clang de l'hôte puis le `Shiboken6Config` de l'arbre de construction. La chaîne ne
  pose ce réglage que s'il n'est pas déjà fixé. Écarté : donner `Clang_DIR`, puis `LLVM_DIR` et zstd un par un,
  essayé sans succès, chaque dépendance en appelant une autre.
- **`SHIBOKEN_WRAPPER_HOST_CLANG_LIB_PATH=/usr/lib`**, qui donne libclang hôte sans passer par `find_package(Clang)`.
- **Générateur : `--compiler=clang --clang-option=--target=wasm32-unknown-emscripten`.** Le générateur ne connaît
  pas la plateforme « Emscripten ». Il retombait sur i586-linux et, en mode g++, plaçait les en-têtes intégrés du
  clang système avant la libc++ d'emscripten (« <cstddef> tried including <stddef.h> »). Le mode clang reprend
  l'ordre d'inclusion d'em++, et la vraie cible définit `__EMSCRIPTEN__` comme à la compilation. Testé : les six
  passes du générateur aboutissent.

**Patch `wasm/patches/pyside-qtcore-fonctions-absentes.patch`.** Qt-WASM désactive les fonctions `systemsemaphore`
et `timezone` (`qtcore-config.h`), si bien que le générateur ne produit ni `QSystemSemaphore` ni
`QTimeZone::OffsetData`. Le `CMakeLists.txt` de QtCore les listait sans condition, et AutoGen échouait (« source
file … does not exist »). Le patch les conditionne à la fonction, sur le modèle exact de `QSharedMemory` juste en
dessous. `phase_pyside` applique tous les `pyside-*.patch` par `git apply`, et les saute si l'inverse s'applique
(idempotent). Écarté : un `sed` sur le CMakeLists, qui ne dirait pas en clair ce qui change. Le patch a été trouvé
par une construction `ninja -k 0` : QtCore bloquait tout le reste, c'était le seul échec.

**Patch `wasm/patches/shiboken-clang22.patch` (générateur hôte).** Avec la libclang 22 du système, les wrappers
compilés se trompaient de type : `QDirListing::IteratorFlags` devenait `QFlags<QDirIterator::IteratorFlag>`
(« no type named 'Default' »). La cause : depuis clang 22, `clang_getTypeSpelling()` ne rend plus le nom qualifié, et
la recherche de flags de shiboken tombe alors, par suffixe, sur la première énumération du même nom. Corrigé en
amont dans shiboken 6.11.1 (PYSIDE-3286, commit 27cb9ca, lu sur GitHub). Le patch en reprend le fond : utiliser
`clang_getFullyQualifiedName()` avec la politique d'affichage de l'unité de traduction. Il le fait en plus court
que l'amont : une politique globale posée par `parse()`, au lieu de la passer en argument à chaque appel. Appliqué
par `patcher shiboken` dans `phase_shiboken`.
Alternatives écartées :
- une libclang 21 : il n'y en a pas d'autre sur la machine, et il aurait fallu la télécharger ;
- passer à pyside-setup 6.11.1 : le Qt cible est en 6.10.2, et l'objectif est de ne changer qu'une variable par
  rapport à Pyodide-Qt.
Le second correctif amont lié (« typedatabase: Fix flag search », 732608) n'a pas été repris : il durcit la
recherche par nom non qualifié, que le premier rend inutile ici.

**Deuxième défaut clang 22, absent du correctif amont : les types déclarés DANS un modèle de classe.** Le correctif
précédent laissait deux échecs, trouvés par `ninja -k 0` : `qitemselection_wrapper.cpp` et
`qxmlstreamattributes_wrapper.cpp`. Les deux classes dérivent de `QList<T>`, et `at()` y était généré avec le type
`QItemSelectionRange<QString>`. Une sonde C sur libclang 22.1.8 (un petit modèle `L<T>` et une classe dérivée de
`L<N::R>`) en a montré la cause. Pour un `typedef` ou une classe imbriquée dans le modèle, `clang_getFullyQualifiedName()`
qualifie avec la DERNIÈRE instanciation rencontrée : `L<N::R>::const_reference` au lieu de `L::const_reference`.
Le type canonique, lui, garde la forme sans arguments (`L::iterator`). Le patch reconstruit donc ce nom par la chaîne
des parents sémantiques quand la déclaration est dans un `ClassTemplate`. Il retire aussi un « struct » de tête,
comme l'amont 6.11. Ce cas est vraisemblablement présent tel quel dans shiboken 6.11.1 : son `getTypeName` est le
même que le nôtre sans ce traitement. Ce point a été vérifié par lecture du diff de Gerrit 726134 seulement.
Alternatives écartées :
- revenir à `clang_getTypeSpelling()` dans les modèles : sous clang 22, il rend le nom nu, `const_reference`, donc
  sans portée ;
- supprimer `at()`, `data()` et `constData()` dans le typesystem : cela masque le symptôme pour deux classes
  seulement.

**Résultat de l'étape 3 (01/10/2026, nuit) : tout compile.** Après ce second correctif, une construction complète
finit avec `rc=0` et aucun FAILED. libshiboken, libpyside, le module Shiboken et les modules QtCore, QtGui,
QtWidgets, QtSvg et QtSvgWidgets sont installés sous `$RACINE/pyside-wasm`. Le paquet `signature` est embarqué dans
libshiboken (`libshiboken/embed/signature.zip`). `llvm-nm` voit, dans les objets, `PyInit_Shiboken`, `PyInit_QtCore`,
`PyInit_QtGui`, `PyInit_QtWidgets`, `PyInit_QtSvg` et `PyInit_QtSvgWidgets`.
Écart avec le plan : les cibles produisent des modules latéraux `.so`, pas des `.a`. On ne force pas le statique
dans CMake. L'étape 4 archive directement les objets de chaque cible (`CMakeFiles/<cible>.dir/**/*.o`) avec `emar`.
Alternative écartée : patcher les `CMakeLists` de pyside-setup pour produire des `STATIC`. Ce serait un patch de
plus à porter, pour un résultat identique à l'archivage des mêmes objets.

### Étape 4 : édition de liens dans Pyodide (01/10/2026, nuit)

**Livré.**
- `wasm/construire.sh`, phase `pyodide` :
  - elle archive, avec `emar`, les objets des cibles PySide ;
  - elle compile `wasm/qt_statique.cpp` ;
  - elle exporte `PYSIDE6_LDFLAGS`, qui contient les archives PySide, Qt, Bundled*, les greffons et les objets rcc ;
  - elle applique `patches/pyodide-pyside6.patch` à Pyodide ;
  - elle copie les paquets purs `PySide6/` et `shiboken6/`, sans les `.pyi`, dans la bibliothèque standard ;
  - elle lance `make all-but-packages`, puis écrit un `pyodide-lock.json` vide.
- `wasm/patches/pyodide-pyside6.patch` :
  - dans `main.c`, `PyImport_AppendInittab` sous les noms complets (`PySide6.QtCore`, `shiboken6.Shiboken`…) ;
  - dans `Makefile.envs`, `-lembind $(PYSIDE6_LDFLAGS)` à la fin du premier `MAIN_MODULE_LDFLAGS`.
- `wasm/qt_statique.cpp` réunit en un seul fichier deux fichiers de la recette Pyodide-Qt, sous licence MIT, cités
  en tête : l'import des greffons statiques et les bouchons de fils et d'IndexedDB.
- `wasm/fumee.mjs` est le test de fumée sous node.

**Choix, et alternatives écartées.**
- **Pas de crochet d'import ni de paquet-espace de noms en C**, contrairement à la recette PyQt6.
  - Sous Python 3.13, `BuiltinImporter.find_spec` ne regarde que `_imp.is_builtin(nom complet)`, et ignore le chemin.
  - `PySide6` et `shiboken6` restent donc les vrais paquets Python purs, copiés dans la bibliothèque standard.
  - Leurs sous-modules intégrés sont trouvés sans aide.
  - La preuve est attendue du test de fumée.
- **Pas de port emdawnwebgpu ni de QtXml**, contrairement à la recette.
  - `llvm-nm` ne voit aucun symbole `wgpu` non résolu dans `libqwasm`, `libQt6Gui` ou `libQt6Core`.
  - En revanche, `-lembind` est nécessaire : il y a 195 références `_emval` dans `libqwasm`.
- **Les drapeaux passent par une variable d'environnement** (`PYSIDE6_LDFLAGS`), lue par `Makefile.envs`.
  - La recette, elle, utilise un fichier de drapeaux lu par `$(shell grep …)`.
  - La variable évite un fichier intermédiaire et un chemin absolu figé dans le patch.
- **Un patch `git apply`** sur le dépôt pyodide (un vrai dépôt git), au lieu du script Python de la recette.
  - C'est le même mécanisme `patcher` que pour pyside-setup, avec un argument « arbre » en plus.
  - Le patch est idempotent, par la vérification inverse.
- **`npm ci` n'est pas rejoué.** La phase pose le témoin `node_modules/.installed` que make attend, car l'installation
  a déjà été faite par `telecharger_sources.sh`, avec le réseau.
- **`shasum`** est exigé par `tools/dependency-check.sh`. Sous Arch, il est dans `/usr/bin/core_perl`, ajouté au
  PATH par `pyodide_env`.

**Défaut trouvé à la première édition de liens : des symboles en double entre modules.** Le générateur shiboken
suppose un module par bibliothèque partagée. Lié statiquement, il produit 30 symboles forts en double entre archives,
relevés par `llvm-nm`. Ils forment trois familles :
1. Les fonctions des conteneurs opaques, comme `createQPointList`, `QPointList_Check` ou `PythonToCppQPointList`.
   - Chaque module qui déclare le même conteneur, QtCore comme QtGui, a les siennes.
   - Chacune vise le type Python propre à son module.
   - Elles étaient en `extern "C"`.
2. `cleanTypesAttributes()`, propre à chaque module.
3. Les pointeurs vers les tableaux des modules requis, comme `SbkPySide6_QtCoreTypeStructs` défini aussi dans QtGui,
   QtWidgets et les autres.

Le correctif est `patches/shiboken-lien-statique.patch`, appliqué au générateur hôte :
- les familles 1 et 2 deviennent `static` ;
- la famille 3 devient `__attribute__((weak))` dans les modules qui la requièrent. Lié statiquement, le pointeur est
  partagé avec celui du module propriétaire, et il reçoit de toute façon la même valeur (`getTypeStructs` sur ce
  module).
- Limite connue : `createX` peut, en principe, être appelé depuis un autre fichier du même module, par un accesseur
  qui renvoie un conteneur opaque. Devenue `static`, la fonction ferait alors échouer l'édition de liens
  bruyamment (symbole indéfini), pas silencieusement. Ce cas n'existe pas dans ce build : le nom n'apparaît que dans
  les `*_module_wrapper.cpp`.

Alternatives écartées :
- `-Wl,--allow-multiple-definition` garderait une seule copie des fonctions de la famille 1. Le convertisseur de
  QtGui vérifierait alors le type opaque de QtCore, ce qui est faux et silencieux. Seul `cleanTypesAttributes` d'un
  module serait appelé. Cette option masquerait aussi tout doublon futur.
- Renommer les fonctions par module : la modification serait plus large dans le générateur, pour le même effet.

`phase_shiboken` est devenue rejouable : elle applique les patchs, reconstruit de façon incrémentale, puis efface les
témoins `mjb_rejected_classes.log` de PySide quand le générateur a changé. Sans cela, ninja ne régénère pas les
wrappers, car la règle de génération ne dépend pas du binaire hôte.

**Résultat de l'étape 4 (testé sous node, 01/10/2026 à 21:59).**
- La chaîne `construire.sh shiboken pyside pyodide` rend 0.
- `pyodide.asm.wasm` pèse 35 Mo, et `python_stdlib.zip` 29 Mo.
- `node wasm/fumee.mjs` affiche `PySide6 6.10.2 Qt 6.10.2 signal=[42] valide=True`. L'import des paquets purs et des
  sous-modules intégrés fonctionne donc sans crochet d'import, et un `Signal` Python est émis puis reçu.
- Deux avertissements restent à l'édition de liens : `create_sentinel` et `is_sentinel` indéfinis. Ce sont des
  fonctions JS de Pyodide, sans effet visible sur le test.
- Le `sed: conservation des permissions` de la fin du make vient des ACL du bac à sable. Il est sans effet, la page
  est écrite.

### Étape 5 : rendu dans le navigateur (01/10/2026, 22:00)

**Sortie 1, page minimale (testé dans Firefox sans interface, par `qtpy6.web.sonde`).**
- La page crée une `QApplication`, puis un `QWidget` qui contient un `QLabel` et un `QPushButton`.
- `button.click()` met le label à « 1 clic ».
- La capture de la page et le `grab()` de la fenêtre ont été relus : la fenêtre est dessinée dans le conteneur, sans
  artefact.
- La page est jetable (`$TMPDIR/rendu/index.html`) et n'est pas versionnée. Le cas réel est couvert par la sortie 2.

**Sortie 2, `exemple/` à travers `qtpy6.web` (testé dans Firefox sans interface).**
- `exemple/index.html?auto` est servi, avec le dist PySide6 à la place de `pyodide-qt/`.
- Le compteur passe à 1 après un clic, et la fenêtre fait 1000 x 814.
- Le travailleur Pyodide 3.14 renvoie l'écho de l'appel 1.
- **Le `grab()` est identique au pixel près à celui de Pyodide-Qt (PyQt6)** sur la même page (`ImageChops.difference`
  sans boîte).
- La liaison était bien PySide6 : la bibliothèque standard de ce build ne contient aucun `PyQt6/`.

| | PySide6 (ce build) | Pyodide-Qt (PyQt6) |
|---|---|---|
| `pyodide.asm.wasm` | 35,4 Mo (11,4 Mo gzip) | 33,7 Mo (10,4 Mo gzip) |
| `python_stdlib.zip` | 2,4 Mo | 2,4 Mo |
| tas wasm après l'exemple | 42 Mio | 35 Mio |
| fenêtre montrée après | 470 ms | 309 ms |

Les temps viennent d'un seul essai chacun, sur une machine chargée par d'autres instances : ce n'est pas une mesure.

**Défaut trouvé et corrigé pendant l'étape.** La première copie des paquets dans la bibliothèque standard emportait
les modules latéraux `.so` de PySide, alors qu'ils sont déjà liés statiquement. Le zip pesait 29 Mo au lieu de
2,4 Mo, pour des fichiers que rien ne charge : `BuiltinImporter` passe avant le chercheur de chemins.
- `phase_pyodide` les efface désormais, avec les `.pyi`.
- Après la correction, le test de fumée et l'exemple ont été rejoués, avec le même résultat.

**Points ouverts.**
- `telecharger_sources.sh` télécharge encore emdawnwebgpu, que la construction n'utilise pas : Qt n'a aucun symbole
  wgpu. Le retirer est possible, mais ce n'est pas urgent.
- Le message de chargement de `qtpy6web.js` dit « Pyodide-Qt » quel que soit le build.
- `PySide6/QtAsyncio` et `PySide6/support` sont copiés. `support` sert aux signatures ; `QtAsyncio` n'est pas testé.
- Étape 7 : l'hébergement du dist (`versions.json`, `hebergement/`), et la licence LGPL du lien statique, à faire
  valider par l'utilisateur.
- `wasm/README.md` a été écrit.

## Relecture des étapes 1 à 5, et mesures pour un plan d'optimisation (01/10/2026, 22:30, Fable 5.1)

Demande de l'utilisateur : « tout checker de ce qu'a fait opus, voir s'il y a des choses à retester ou modifier et
propose un plan pour optimiser qtpy6 pour le web ». Rien n'a été modifié dans le dépôt pendant cette relecture, hors
cette entrée ; tous les artefacts de mesure sont sous `$TMPDIR` (jetables).

### Relecture (par lecture, et par rejeu de la mesure quand elle était possible)

- `wasm/construire.sh`, les quatre patches, `qt_statique.cpp`, `fumee.mjs`, `README.md` : relus. Aucun défaut de
  fond trouvé. Les deux risques déjà consignés tiennent toujours (fonctions `create*` rendues `static` dans les
  conteneurs opaques, pointeurs faibles des modules requis) : ils ne se verront qu'au premier module qui en dépend.
- **Erreur de lecture dans mes premières conclusions, corrigée** : PySide n'est pas compilé en `-O3` mais en **`-Oz`**
  — `PySideHelpers.cmake:272` (`override_release_flags_for_size_optimization`) remplace les drapeaux Release de
  CMake pour Clang. Qt est en `-O2` (son défaut, pas d'`-optimize-size`), Pyodide en `-O2`. Les trois sont en
  `-fwasm-exceptions`, cohérents.
- Les avertissements `create_sentinel`/`is_sentinel` à l'édition de liens viennent de `src/core/jslib.c` de Pyodide
  lui-même (imports du module JS `sentinel`) : propres à Pyodide 0.29, pas à notre build.
- Le `.pyc` de `shibokensupport` : en compilation croisée, `libshiboken/CMakeLists.txt:31` force `use_pyc_in_embedding
  FALSE` ; l'archive de signatures embarquée contient donc des `.py`, recompilés à chaque démarrage (voir mesures).

### Mesures

**Taille.** Édition de liens rejouée avec `-Wl,-Map` (même binaire, 35 398 464 octets). Code avant `wasm-opt` :
33,6 Mo, dont enveloppes PySide 11,0 Mo (QtWidgets.a 4,4 ; QtGui.a 3,4 ; QtCore.a 2,8), bibliothèques Qt 12,2 Mo
(Gui 4,8 ; Widgets 4,4 ; Core 3,0), bibliothèques tierces de Qt 1,9 Mo (Harfbuzz 0,8 ; Freetype 0,55 ; libjpeg 0,4),
libpython 4,0 Mo, relocations internes 2,4 Mo. Binaire final : code 26,45 Mo, données 8,08 Mo (dont libpython 2,7,
`libqwasm` 1,0 — les polices DejaVu embarquées, `qrc_wasmfonts` —, Qt6Core 0,9 ; `qt_resource_data` 1,37 Mo au total).
Par famille, dans le code : la vue graphique (`QGraphics*`) pèse 0,69 Mo dans Qt plus 0,77 Mo d'enveloppes ; QRhi,
shaders et OpenGL environ 0,86 Mo cumulés ; les styles 0,57 Mo.

**Niveau d'optimisation des enveloppes, mesuré sur `qpushbutton_wrapper.cpp` :** `-Oz` 67 809 octets, `-Os` 67 460,
`-O2` 71 523, `-O3` 71 536. Écart de 5 % entre les deux extrêmes : le niveau d'optimisation n'est pas un levier de
taille sur PySide (≈ 0,5 Mo sur 11), et `-Oz` est déjà le réglage.

**Compression :** `pyodide.asm.wasm` 35,4 Mo → gzip -9 11,33 Mo → brotli -q 9 **9,14 Mo** (−19 % sur gzip).

**Démarrage (node, `cProfile`) :** `import shiboken6` 110 à 173 ms selon la charge, dont **68 ms dans
`builtins.compile`** (31 appels : les sources `.py` de l'archive de signatures embarquée) et ≈ 60 ms dans `re`
(compilation d'expressions régulières de `shibokensupport.signature.mapping`/`parser`). `import PySide6.QtCore`
46 ms, dominé par la création des `enum` Python (19 énumérations, 886 membres). Les types sont **déjà paresseux**
(`PYSIDE6_OPTION_LAZY` vaut 1 par défaut, `sbkmodule.cpp:376`) : matérialiser tous les types de QtWidgets coûte 53 ms,
ceux de QtGui 65 ms, payés seulement à l'usage.

**Démarrage (Firefox, 3 essais, page de chronométrage) :** PySide6 1 446–1 489 ms contre PyQt6 1 246–1 329 ms, de
`loadPyodide` à deux images rendues. `loadPyodide` est identique (≈ 1,25 s, c'est le coût du wasm) ; l'écart tient
dans `import QtCore` (+130 ms, soit shiboken6 et les énumérations) et `QApplication([])` (+60 à 75 ms, non élucidé).

**Usage réel des gros composants :** `grep` sur `qtpy6/`, `exemple/` et `SmartTeacher/QCM` : qtpy6 nomme `QGraphicsView`,
`QGraphicsScene`, `QMdiArea`, `QWizard`, `QDockWidget`, `QOpenGLContext` dans ses doublures ; le QCM utilise
`QGraphicsOpacityEffect` (qui dépend de la fonctionnalité `graphicsview`), `QTextDocument`, `QTextBrowser`,
`QListWidget`, `QTableWidget`.

### Plan d'optimisation proposé, dans l'ordre du rapport gain / risque

1. **Brotli à l'hébergement** — gain 2,2 Mo par chargement (11,3 → 9,1 Mo), zéro risque, zéro reconstruction. À
   régler dans `hebergement/` (étape 7) : servir `.wasm.br` avec `Content-Encoding: br`, repli gzip.
2. **Embarquer `shibokensupport` en `.pyc`** — gain mesuré 68 ms par démarrage. Patch d'une ligne dans
   `libshiboken/CMakeLists.txt` (`use_pyc_in_embedding TRUE` en croisé) : l'hôte est Python 3.13.14, la cible 3.13.2,
   même nombre magique de `.pyc`. À tester par `fumee.mjs` puis par le profil node.
3. **Les expressions régulières de `shibokensupport`** (≈ 60 ms) et **la création des énumérations de QtCore**
   (46 ms) : à regarder ensemble, car ce sont les deux tiers de l'écart avec PyQt6 à l'import. Pistes : différer
   `mapping`/`parser` jusqu'au premier `__signature__` demandé (modifie shiboken, patch à entretenir), et pour les
   énumérations une mesure fine avant toute action (sont-elles créées par le code C ou par `enum.py` ?).
4. **`QApplication([])` +60 ms** — à élucider avant d'agir : mesure à faire en isolant la création de la plateforme
   `wasm` (identique à PyQt6) de la matérialisation paresseuse des types QtWidgets qu'elle déclenche.
5. **Taille du wasm** — pas de levier simple : `-Oz` est déjà là côté PySide ; `-optimize-size` côté Qt (passer Gui,
   Widgets, Core de `-O2` à `-Os`) demande 25 min de reconstruction de Qt pour un gain non mesuré, et un coût en
   vitesse de rendu à mesurer ensuite ; `-no-feature-graphicsview` gagnerait ≈ 1,1 Mo après `wasm-opt` mais casse
   `QGraphicsOpacityEffect` du QCM et plusieurs doublures de qtpy6 — écarté. Retirer `QtSvgWidgets` (0,06 Mo) et
   réduire les polices DejaVu (1 Mo de données, 0,3 Mo compressé) sont des gains marginaux, à ne faire que groupés
   avec une reconstruction qui a une autre raison.
6. **Cosmétique, sans mesure** : libellé « Pyodide-Qt » de `qtpy6web.js` ; téléchargement d'emdawnwebgpu dans
   `telecharger_sources.sh` (inutilisé) ; `QtAsyncio` copié dans la bibliothèque standard sans être testé.

### Ce qui mérite d'être retesté ou modifié

- **Rien à refaire sur les étapes 1 à 5** : les résultats de l'étape 5 ont été rejoués aujourd'hui (fumée, exemple).
- **La note disait les enveloppes en `-O3`** dans mes propres conclusions de séance : c'est `-Oz`, corrigé ci-dessus.
- **Les temps de l'étape 5 (470 vs 309 ms)** venaient d'un essai unique sur machine chargée ; les trois essais de la
  page de chronométrage les ramènent à +200 ms de bout en bout, localisés à l'import et à `QApplication`.

Niveau de preuve : tailles et profils mesurés (fichier de carte, `cProfile`, compilation isolée) ; usage des classes par
`grep` seulement ; les gains des points 3 à 5 sont des estimations, non mesurées.

## Complément : mesures sans profileur, et le vrai levier (01/10/2026, 23:30, Fable 5.1)

Demande de l'utilisateur : « tu peux commencer par les points qui te concernent ». Points 3 et 4 du plan ci-dessus,
instruits ; rien de modifié dans le dépôt hors cette entrée. Artefacts sous `$TMPDIR` (`pyc/`, `chrono/`, `prof*.mjs`).

### Correction des chiffres de 22:30

`cProfile` gonfle environ trois fois le code Python dense (compilation d'expressions régulières, création d'`enum`).
Remesuré par `time.perf_counter` sans profileur, sous node :

- `import shiboken6` : 105 à 121 ms, dont `compile()` 81–83 ms au total (les 23 modules `.py` de l'archive de
  signatures embarquée plus les modules de la bibliothèque standard qu'ils tirent : `typing`, `inspect`,
  `argparse`, `dataclasses`, `traceback`, `logging`, `pathlib`…), expressions régulières **15 ms** (pas 60),
  `ZipFile` 4 ms. Remplacer `pyi_generator` par un stub : aucun gain mesurable, écarté.
- `import PySide6.QtCore` : **13 à 16 ms** (pas 46). Les énumérations ne sont pas un sujet : le point 3 du plan
  tombe, sauf sa moitié « `.pyc` de shibokensupport » (point 2, inchangé).
- Matérialisation de tous les types paresseux, mesurée en processus neufs : QtCore 226 noms 50–55 ms, QtGui 284 noms
  43–48 ms, QtWidgets 200 noms 42–46 ms.

### Point 4 élucidé : les +60 ms de « QApplication »

Page de chronométrage découpée en huit jalons, trois essais Firefox par liaison. `QApplication([])` coûte 4–5 ms
sous les deux liaisons. Les 60–64 ms sont dans `from PySide6.QtWidgets import *` (0–1 ms sous PyQt6) : c'est la
matérialisation de tous les types paresseux de QtWidgets, déclenchée par le `*`. Rien à corriger dans PySide ; c'est
la même mécanique que `qtpy6._binding.load`, ci-dessous.

### Le levier principal : la bibliothèque standard de Pyodide n'est pas précompilée

`dist/python_stdlib.zip` contient **544 `.py` et aucun `.pyc`** (`tools/create_zipfile.py`, cible `make` par
défaut). Chaque import de la bibliothèque standard est donc recompilé à chaque chargement de la page, et
`loadPyodide` en importe **233 modules** avant de rendre la main. C'est vrai aussi de Pyodide-Qt
(`exemple/pyodide-qt/python_stdlib.zip`, 533 `.py`, 0 `.pyc`) et du Pyodide officiel que qtpy6 télécharge
(`exemple/pyodide/`, 559 `.py`, 0 `.pyc`). Pyodide fournit l'outil et publie lui-même une variante précompilée
(journal des changements 0.23 : « A py-compiled build which has smaller and faster-to-load packages is now deployed
under `cdn.jsdelivr.net/pyodide/v…/pyc/` » ; l'outil est `pyodide py-compile`, cible `make py-compile`, que seule
la CI appelle).

Mesure, archive reconstruite avec `pyodide py-compile --compression-level 6 python_stdlib.zip` (venv-pyodide, 1,4 s ;
2,45 Mo → 4,24 Mo, 544 `.pyc`, même nombre magique `3.13`) :

| | bibliothèque en `.py` | en `.pyc` |
|---|---|---|
| node, `loadPyodide` (3 essais, machine chargée) | 1 540–1 823 ms | 475–570 ms |
| Firefox, `loadPyodide` | 1 610–2 268 ms | 540–615 ms |
| Firefox, de `loadPyodide` à deux images rendues (QApplication, widget) | 1 876–2 532 ms | **739–812 ms** |

Soit **plus d'une seconde gagnée au démarrage, pour les deux liaisons**, sans reconstruction : l'archive se
précompile à l'hébergement. Le reste de la chaîne (QtCore, matérialisation, affichage) est inchangé, à 20 ms près.
Coût connu, documenté par Pyodide : les traces d'erreur n'affichent plus la ligne de code des modules de la
bibliothèque standard (celles de l'application et de qtpy6, livrées en `.py`, restent entières). Non testé : la suite
`test_web.py` et l'exemple complet sur l'archive précompilée (seule la page de chronométrage a tourné, et elle rend).

Où le faire : pas dans `wasm/construire.sh` seulement, puisque le gain vaut autant pour Pyodide-Qt et le Pyodide
nu — plutôt dans `hebergement/telecharger.sh` ou `construire_site.py`, après téléchargement, pour toute
distribution servie. Le même traitement vaut pour `shibokensupport` (point 2), qui ne dépend pas de l'hébergement
mais du build (`use_pyc_in_embedding`), et pour les sources de qtpy6 copiées sans `__pycache__` (20–25 ms mesurés).

### Second levier, qui est une décision de conception : `qtpy6._binding`

`import qtpy6` suivi de `qtpy6.QtCore`, `QtGui`, `QtWidgets` coûte **237 à 287 ms** sous node (PySide6) : ≈ 140 ms
dans `_binding.load` (le `dir(source)` matérialise tous les types paresseux des trois modules) et ≈ 100 ms dans
`finish`/`_pyside6_class` (alias snake_case et énumérations non étendues sur chaque classe), compilation des
sources 5 ms. C'est aujourd'hui le premier poste après `loadPyodide`, devant tout ce qui est propre à PySide6.
Un chargement paresseux (`__getattr__` de module résolvant et finissant une classe à la première demande) en
effacerait l'essentiel, sous les deux liaisons — mais il change le contrat de `finish` (aujourd'hui, toute classe
est complète dès l'import, y compris pour `from qtpy6.QtWidgets import *`). Non engagé : c'est un choix d'API, à
trancher par l'utilisateur, pas une optimisation locale.

### Plan révisé, par gain mesuré

1. **Bibliothèque standard en `.pyc` à l'hébergement** — −1,1 s par chargement, toutes liaisons, mesuré. Opus.
2. **Brotli** — −2,2 Mo par chargement, mesuré. Opus (étape 7).
3. **`shibokensupport` en `.pyc`** (`use_pyc_in_embedding TRUE` en croisé) — de l'ordre de 50 ms, estimé sur la part
   `compile()` de shiboken6. Opus, à mesurer après.
4. **Chargement paresseux de `qtpy6._binding`** — jusqu'à ≈ 250 ms, mesuré ; décision d'API de l'utilisateur.
5. Points 5 (taille du wasm) et 6 (cosmétique) inchangés. Le point 3 d'origine (regex, énumérations) est retiré.

Niveau de preuve : tous les temps ci-dessus sont mesurés (`perf_counter`, page de chronométrage, 3 essais) sur une
machine chargée (charge moyenne 4), donc à ±100 ms sur `loadPyodide` — l'ordre de grandeur du gain est hors de ce bruit.

### Aparté (02/10/2026, 00:45) : pourquoi ne pas s'appuyer sur le snake_case natif de PySide6

Question de l'utilisateur : les alias n'existent-ils pas déjà côté PySide ? Si, mais sous une autre forme :
`from __feature__ import snake_case` (PYSIDE-1019, `libpyside/feature_select.cpp`) remplace le `__dict__` de chaque
classe par un anneau de dictionnaires et détourne chaque accès d'attribut (`SelectFeatureSet`) pour choisir le
dictionnaire selon le module appelant. Mesuré en natif (PySide6 6.11.1, 100 000 paires d'appels, `is_visible()`) :

| | alias qtpy6 | `__feature__` |
|---|---|---|
| deux objets de même type | 167 ns/accès | 189 ns/accès |
| deux types alternés (QLabel, QPushButton) | 163 ns/accès | **336 ns/accès** |

À chaque changement de type ou de module appelant, le mécanisme re-parcourt la MRO, rebascule les dictionnaires et
appelle `PyType_Modified` (le cache de méthodes de CPython est invalidé). Et **mélanger les deux styles dans un même
processus casse le camelCase** : `getFeatureSelectId` rend `last_select_id` pour un module qui n'a pas choisi, donc
après un appel depuis un module en snake_case, `w.isVisible()` depuis un module ordinaire lève `AttributeError`
(reproduit, 6.11.1). Raisons de garder les alias additifs de qtpy6 : coût nul à l'appel, les deux graphies
coexistent, même mécanisme sous PyQt6. L'alias qtpy6 est le même objet descripteur sous un second nom
(`QLabel.set_text is QLabel.setText`), 220 vs 232 ns par appel, mesuré. Niveau de preuve : mesuré en natif ;
non mesuré dans le navigateur.

### Aparté (02/10/2026, 00:50) : un `finish` paresseux, et le rattrapage des classes jamais nommées

Question de l'utilisateur : quel est le problème d'un snake_case paresseux ? Le seul : une classe que le programme ne
nomme jamais (instance rendue par Qt : `sender()`, `focus_widget()`, événement reçu) n'est pas complétée. Rattrapage
testé en natif : un `__getattr__` posé sur la classe de base commune, appelé seulement quand l'accès normal échoue,
qui complète alors la classe et réessaie.
- **PySide6** : `Shiboken.Object.__getattr__` se pose et fonctionne (6.11.1). Mais CPython remplace alors le slot
  d'accès aux attributs de toutes les sous-classes par son crochet Python : **155 → 193 ns par accès réussi**
  (+25 %), payé sur chaque accès de toute l'application, pas seulement sur les manqués.
- **PyQt6** : impossible, `sip.simplewrapper` et `sip.wrapper` sont des types immuables (« cannot set '__getattr__'
  attribute of immutable type »). Il faudrait poser le crochet classe par classe, donc toucher les ≈ 700 classes à
  l'import : on perd l'intérêt du paresseux.
Conclusion : le paresseux complet exige soit d'accepter ce trou (API), soit un surcoût de 25 % à l'exécution sous
PySide6 et rien sous PyQt6. L'autre voie, non mesurée, est de rendre l'eager moins cher : `finish` (≈ 100 ms dans le
navigateur) refait `snake_case()` sur chaque nom de méthode de chaque classe alors que les noms se répètent d'une
classe à l'autre (un cache suffirait), et `load` (≈ 140 ms) est la création des types par PySide, incompressible en
eager, que PyQt6 paie de son côté à l'import.

### Exploration des solutions pour `_binding` (02/10/2026, 01:30, Fable 5.1)

Suite de « ok explore les solutions ». Tout est mesuré sous Pyodide dans node (`bench2.mjs`, `$TMPDIR`), trois
processus neufs par variante, charge machine ≈ 4 ; les écarts entre lignes d'une même variante donnent la marge
(±40 ms sur `load`, ±3 ms sur `finish`). Rien n'est modifié dans `qtpy6/`.

**Ce que coûte `_binding` aujourd'hui, décomposé.** `load` = 180–270 ms, et ce n'est pas notre code : c'est
l'incarnation par PySide des 642 classes de premier niveau que `dir()`+`getattr` force (≈ 0,3 ms par classe).
`finish` = 66–70 ms, dont `snake_case` sur 12 768 occurrences (6 490 noms distincts), `setattr` de 9 221 alias
≈ 12 ms, `vars` ≈ 4 ms.

**Voie A — garder le contrat (tout prêt à l'import), rendre `finish` moins cher.** Mesuré, `finish` seul :

| variante de `snake_case` | `finish` | commentaire |
|---|---|---|
| actuelle (`zip` + jointure) | 66–70 ms | référence |
| v2 : `str.islower()` d'abord, regex `[A-Z]{2}`, `str.translate` | 42–45 ms | même résultat sur les 6 490 noms (assert) |
| v2 + `functools.lru_cache` | 37–42 ms | les 6 490 noms distincts ne sont convertis qu'une fois |
| table précalculée livrée avec le paquet (dict) | 15–17 ms | la table se construit en 15 ms hors ligne ; à régénérer par version de PySide, avec repli calcul pour un nom absent |

Gain : 25 à 55 ms sur ≈ 250. `load` reste entier. Alternative écartée : générer les alias snake_case côté
shiboken (patch du générateur, `tp_methods` doublés) — elle ne retire que ce que la table retire déjà (≈ 15 ms
de `finish` restants), alourdit `load` d'autant de descripteurs à créer, et coûte une maintenance par version.
Non prototypée, écartée sur ces chiffres.

**Voie B — contrat paresseux (une classe n'existe qu'à sa première utilisation).** Prototype : pour les 112
classes Qt que nomment les sources de SmartTeacher (grep `Q[A-Z]\w+` sur les fichiers qui importent qtpy6 ;
`exemple/` n'en nomme que 6), `getattr` sur le module PySide puis `finish` de la classe = **91–94 ms**, soit
≈ 0,8 ms par classe (ces classes sont lourdes : QWidget et ses bases viennent avec). Pour `exemple/` : moins de
10 ms. Contre 220–300 ms aujourd'hui : gain **130 à 250 ms** à l'import, à proportion des classes inutilisées.
`from qtpy6.QtWidgets import *` reste possible (le `__getattr__` de module sert `__all__`), au prix de la charge
complète comme aujourd'hui.

Le trou des classes jamais nommées (objet rendu par Qt dont la classe n'a pas été importée : `QMouseEvent`,
`QStyleOptionViewItem`…) se ferme **côté shiboken, pas côté Python** : lecture de `sbkmodule.cpp` et
`sbkconverter.cpp:598`, toutes les créations de types passent par deux fonctions, `incarnateType` (accès
module, `import *`, et convertisseur C++→Python qui cherche un nom de type) et `incarnateHelper` (sous-types,
modules chargés d'emblée) ; les 192 types de QtWidgets s'y enregistrent par `AddTypeCreationFunction`
(générateur, `cppgenerator.cpp:6420`). Un appelable Python posé par `Shiboken.setTypeCreationHook(...)` et appelé
à ces deux endroits finit chaque classe à l'instant où PySide la crée, y compris celles qu'aucun code n'a
nommées, sans rien ajouter au chemin d'accès aux attributs (contrairement au `__getattr__` sur `Shiboken.Object`,
+25 % mesurés la veille). Ébauche : `$TMPDIR/ebauche_crochet_incarnation.diff`, ≈ 30 lignes C++ + 4 XML, à ranger
dans `wasm/patches/` — **non appliquée, non compilée** (toucher à l'arbre de construction partagé sans
autorisation serait hors périmètre ce soir). Le coût du crochet par classe est celui de `finish` : ≈ 0,07 ms.

Limites de la voie B : elle est propre à notre PySide6 wasm (le crochet n'existe ni dans PySide6 natif ni sous
PyQt6) ; en natif et sous PyQt6 (sip immuable) qtpy6 garderait le mode d'aujourd'hui, donc **deux régimes à
tester** dans `test_web.py` ; et c'est un changement du contrat d'API de qtpy6, que seul l'utilisateur tranche.

**Recommandation.** Faire la voie A tout de suite, elle est sans risque : `snake_case` v2 + `lru_cache` (30 ms
gagnés, dix lignes, aucun fichier à livrer). La table précalculée gagne 25 ms de plus mais ajoute un artefact à
tenir par version : à ne faire que si la voie B est refusée. La voie B vaut 130–250 ms de plus, et il faut dire
dans quel ordre : stdlib `.pyc` (−1,1 s, Opus) d'abord, puis Brotli, puis seulement ceci.

Niveaux de preuve : voie A mesurée (node, 3 runs) ; voie B mesurée côté Python, crochet shiboken vérifié par
lecture du code seulement, patch non compilé ; égalité v2/actuel vérifiée par assert sur les 6 490 noms réels.

### Voies A et B implémentées (02/10/2026, 01:25, Fable 5.1)

Demande de l'utilisateur : « implémente A et B » (après « on peut combiner les deux voies ? »). L'entrée
précédente disait le patch « non appliqué, non compilé » et recommandait A seule : c'est dépassé, les deux sont
faites et combinées. A sert partout ; B s'ajoute seulement quand la liaison a le crochet.

**Ce qui a été livré.**
- `wasm/patches/pyside-shiboken-crochet-type.patch` (nouveau) : `Shiboken.setTypeCreationHook(callable)`, appelé
  à la fin de `incarnateHelper` et de `incarnateType` (`sbkmodule.cpp`) ; `None` retire le crochet ; une exception
  du crochet passe par `PyErr_WriteUnraisable` (elle n'interrompt pas la création du type). Appliqué par
  `construire.sh pyside pyodide` (le mécanisme `patcher` existant), reconstruit, relié.
- `qtpy6/_binding.py` :
  - **A** : `snake_case` passe par `islower()` d'abord, une regex `[A-Z]{2}`, `str.translate`, et `lru_cache`.
  - **B** : `LAZY` vaut vrai si `Shiboken` a `setTypeCreationHook` (donc notre build wasm seulement). Alors
    `load(namespace, name, *needed)` ne copie plus le module : il pose un `__getattr__`/`__dir__` de module
    (PEP 562) qui sert un nom à sa première demande, et ne charge d'avance que `needed`. Le crochet est posé sur
    `_pyside6_class`, qu'un ensemble `_prepared` rend idempotent (les classes créées avant le crochet passent par
    `__getattr__` ou `finish`, celles créées après par le crochet).
  - `__all__` paresseux = ce qu'aurait contenu l'espace de noms impatient, pour `import *`.
- `qtpy6/QtCore.py`, `QtGui.py`, `QtWidgets.py` : la liste `needed` = les noms que leur propre code et les
  doublures (`animation`, `fils`, `bloquant`) lisent par `ns["…"]` avant que le module existe. Relevé par grep de
  tous les `ns["` : il en manquait deux au premier essai (`QTimer`, `QLineEdit`), trouvés par le test sous Pyodide
  (KeyError), ajoutés.
- `qtpy6/web/fils.py` : avant de poser sa doublure d'un nom (`QThread`, `QMutex`…), demande d'abord le nom au
  chargeur paresseux. Sans cela, en paresseux, `QReadWriteLock` et `QProcessEnvironment`, **que le QtCore wasm
  possède**, étaient remplacés par les doublures, contrairement au mode impatient (mesuré : les deux existent
  dans `PySide6.QtCore` du build).

**Choix, et alternatives écartées.**
- *Liste `needed` explicite* plutôt qu'un dictionnaire d'espace de noms qui chargerait à la lecture : les
  globales d'un module sont un vrai `dict`, `LOAD_GLOBAL` ignore `__missing__`. La liste est fragile (un `ns["X"]`
  ajouté sans elle casse l'import sous wasm, et seulement là) : c'est le prix, et `test_web.py` ne le voit pas
  (natif = impatient). À surveiller.
- *Le crochet dans shiboken* plutôt qu'un `__getattr__` sur `Shiboken.Object` : celui-ci coûtait +25 % sur chaque
  accès d'attribut (mesure de la veille), le crochet ne coûte qu'à la création d'un type.
- *Table snake_case précalculée* : écartée, comme proposé, puisque B est en place (25 ms de plus pour un artefact
  à régénérer par version).
- *Noms pointés* : un module shiboken paresseux liste dans `dir()` ses sous-types pas encore créés
  (`'QCalendar.YearMonthDay'`), sur lesquels `getattr` échoue. `_names` ne garde que les identifiants. Le mode
  impatient les recopiait dans l'espace de noms (inaccessibles, inoffensifs) : c'est la seule différence.

**Vérifications.**
- Pyodide/node, build d'avant (impatient) contre build avec crochet (paresseux), même harnais :
  `LAZY` False/True ; `import *` de QtCore, QtGui, QtWidgets : **mêmes noms, mêmes modules d'origine**, aux noms
  pointés près ; `QMetaObject` jamais nommé, obtenu par `meta_object()` : alias présents (c'est le crochet) ;
  `QLabel.set_text is QLabel.setText` ; nom absent → `AttributeError` au nom du module qtpy6 ; `__version__` et
  enums intacts. Tests natifs : `test_qtpy6`, `test_process`, `test_web` = 80 verts sous `QT_API=pyside6` et
  `pyqt6`. Fumée wasm verte. `exemple/` dans Firefox sans interface : compteur, travailleur, grab relu, correct.
- Temps d'import `qtpy6` + QtCore + QtGui + QtWidgets, node, trois processus chacun :

| build | import |
|---|---|
| avant (impatient, A seule ne compte pas : `snake_case` d'avant) | 222–253 ms |
| avec crochet (paresseux + A) | 90–121 ms |

- Dans Firefox, sur `exemple/` (un essai, pas une mesure) : fenêtre montrée en 323 ms (470 ms à l'étape 5), tas
  wasm 35 Mio (42 Mio à l'étape 5).

**Points ouverts.**
- Un `ns["X"]` nouveau dans une doublure doit aller dans `needed` ; aucun test natif ne l'attrape. **Fermé
  en partie** : `wasm/fumee.mjs` importe maintenant qtpy6 sur le build (`paresseux=True`, `import *` des trois
  modules, alias d'une classe jamais nommée). Vérifié qu'il échoue (`KeyError: 'QLineEdit'`) quand on retire
  `QLineEdit` de la liste. Il ne couvre que les lectures faites à l'import, pas celles faites à l'appel.
- Le gain réel sur le lecteur QCM de SmartTeacher (112 classes nommées) n'est pas mesuré.

## Le lecteur QCM de SmartTeacher sous PySide6 (02/10/2026, nuit, Fable 5.1)

Demande : « 2) tester le player de qcm de SmartTeacher avec ce nouveau backent ».

**Banc.** Copie jetable de `SmartTeacher/QCM/web/pyqt6` sous `$TMPDIR/qcmweb` (rien n'est modifié dans
SmartTeacher), `pyodide-qt` lié au dist PySide6, archive assemblée par le `construire.py` de SmartTeacher avec le
qtpy6 de travail. Sonde : `sonde_lecteur.html`, sujet `essais_types`.

**Défaut trouvé : `AttributeError: module 'PySide6.QtCore' has no attribute 'QThread'`** à l'ouverture du sujet,
présent aussi sur le dist d'avant (crochet B absent) : B n'y est pour rien.
- Cause, dans shiboken : `qtcore_module_wrapper.cpp` garde la création de `QThread`, `QThreadPool`,
  `QWaitCondition` sous `#if QT_CONFIG(thread)`, mais `initInheritance` inscrit `QObject → QThread` sans garde.
  `Graph::identifyType` (`bindingmanager.cpp`) crée chaque sous-type pour identifier le type dynamique d'un
  `QObject*` converti en Python (ici l'objet du filtre d'évènements) : `Module::get` rend `nullptr` en laissant
  l'`AttributeError` posée, puis `PepType_SOTP(nullptr)` est lu. Le symptôme sort à l'appel Python suivant.
- Correctif : `wasm/patches/pyside-shiboken-type-absent.patch` — un type absent est ignoré (`PyErr_Clear`, pas
  ce type-là). Reconstruit (phases pyside puis pyodide).
- Alternative écartée : contourner côté Python seulement. Essayé d'abord (`bloquant.py`, ci-dessous) : sans effet
  sur le lecteur, l'erreur naît dans la conversion C++, avant tout code Python. Autre alternative écartée :
  retirer l'arête du graphe dans le code généré — patch du générateur plus large, pour le même effet.

**Changement conservé dans `qtpy6/web/bloquant.py`** : `QObject.thread` et `moveToThread` sont remplacés même quand
la liaison les a. Sous PySide6-WASM, `thread()` échoue toujours (pas de convertisseur pour `QThread*`), en
laissant son erreur posée (« returned a result with an exception set »). Vérifié sous node : `thread()` rend notre
`QThread`, `moveToThread` rend `None`. La raison « moveToThread refuse notre QThread » est déduite, non mesurée.

**Preuves.**
- Dist d'avant : échec reproduit (capture `avant.png`). Dist corrigé : « état : fini », capture relue (bandeau,
  titre « ESSAIS DES TYPES SQL, TABLEAU ET DESSIN », éditeur SQL, table de vérité).
- Tests natifs : 80/80 sous `QT_API=pyside6` et `pyqt6` après le changement de `bloquant.py`.
- Limite : la reproduction minimale sous node (QEvent, filtre d'évènements) n'a pas été obtenue — elle passe sur
  les deux builds. Le patch est donc prouvé par le lecteur seul.

**Démarrage, PyQt6 (Pyodide-Qt d'origine) contre PySide6, même archive, alternés, machine chargée (charge 11) :**

| essai | Pyodide chargé | lecteur importé (durée) | ouverture .qcm | tas wasm |
|---|---|---|---|---|
| PyQt6 1 | 2,76 s | 4,76 s (1,55 s) | 447 ms | 50 Mio |
| PySide6 1 | 1,95 s | 3,91 s (1,59 s) | 498 ms | 60 Mio |
| PyQt6 2 | 2,43 s | 4,43 s (1,54 s) | 594 ms | 50 Mio |
| PySide6 2 | 2,66 s | 4,58 s (1,43 s) | 543 ms | 60 Mio |

Lecture : à égalité dans le bruit ; PySide6 prend 10 Mio de tas de plus. Non mesuré au repos.

## Fluidité (animation, molette) sous PySide6 (02/10/2026, nuit, Fable 5.1)

Demande : « voir tout ce qui a été mis en place pour améliorer le scrooling et les animation sous PyQt6 et porter
et tester sous PySide6 ». Ce qui a été mis en place (`qtpy6/animation.py`, `par_image`, `UpdateRequest`) est dans
qtpy6, indépendant de la liaison : **rien à porter**, seulement à mesurer. Même banc que l'étape précédente.

| scénario (sonde_lecteur.html) | PyQt6 | PySide6 |
|---|---|---|
| animation `par_image`, 3 essais | — (référence : 0 image sans envoi) | 0 image sans envoi, 0 hors image, période 17–20 ms |
| animation `minuterie` (témoin) | — | 35 à 45 images sans envoi : l'écart que `par_image` corrige |
| molette, `essais_types` | 3 crans utiles, 37 « perdus » | identique : la page fait 306 px, la barre est au bout |
| molette, `bac_nsi_2026_j1_metropole` | 35/35 synchrones, 0 perdu | 34/34 synchrones, 0 perdu, retard 0 image |
| ouverture `python_tp` (218 questions) | 26,1 s | 25,3 s puis 33,2 s (charge 7 à 11) |
| `?accueil` | — | ouvert en 309 ms, capture correcte |

Captures relues : accueil, sujet du bac défilé jusqu'à la partie C. Niveau de preuve : mesuré dans Firefox sans
interface, machine chargée, un ou deux essais par cas.

**Point ouvert, hors liaison** : l'ouverture de `python_tp` coûte 25 s sous les deux liaisons. C'est le lecteur
(SmartTeacher) qui construit 218 questions d'un coup ; à regarder avec le point 4 (démarrage).

## PySide6 par défaut sur le web (02/10/2026, nuit, Fable 5.1)

Demande : « 1) passer qpyt6 à PySide6 en backend par defaut ». Côté Python, c'était déjà fait : `QT_API=auto`
prend la liaison présente, et `qtpy6web.js` ne force plus rien. Restait **le moteur que sert l'hébergement**.

**Livré (rien de publié, rien de commité) :**
- `wasm/construire.sh`, phase `paquet` : `$RACINE/pyodide-pyside6-0.29.3.0.zip`, 14,2 Mo. Il contient les mêmes
  fichiers que la release de Pyodide-Qt, sous `pyodide-qt/`, avec la licence en `LICENSE.txt`. Les dates sont
  fixées : deux constructions donnent la même empreinte (vérifié). `wasm/README.md` documente la phase.
- `qtpy6/web/versions.json` : entrée `pyodide_pyside6`, sha256 du zip, URL d'une release
  `pyodide-pyside6-0.29.3.0` de smartaudiotools/qtpy6 **qui n'existe pas encore**.
- `hebergement/telecharger.sh [pyside6|pyqt6] [zip]` : pyside6 par défaut, pyqt6 en repli. La licence est
  toujours dans `pyodide-qt/LICENSE.txt` (pour Pyodide-Qt, recopiée du dépôt, sa release n'en a pas).
- `hebergement/construire_site.py` ne copie plus la licence à part, elle vient avec `pyodide-qt/`.
- `hebergement/index.html` : le paragraphe « Moteur » nomme PySide6 et renvoie à `pyodide-qt/LICENSE.txt`.
- `hebergement/LICENSE-Pyodide-PySide6.txt` : **brouillon**, à faire valider. Il couvre la LGPL v3 avec un lien
  statique : la section 4 est satisfaite en fournissant la recette rejouable, les sources épinglées par sha256 et
  les correctifs. Il ne recopie pas les textes LGPL et GPL mais renvoie à ceux de la FSF ; les recopier est
  l'alternative la plus sûre, à trancher.

**Choix.**
- Le dossier garde le nom `pyodide-qt/`. Écarté : `pyodide-pyside6/`. Ce nom est écrit dans `construire.py`
  (`--pyodide ./pyodide-qt/`), dans `lecteur_qt.js` de SmartTeacher et dans l'adresse publiée. Il désigne
  « Pyodide avec Qt », quelle que soit la liaison.
- Le repli PyQt6 se fait par un argument du script. Écarté : une clé « défaut » dans `versions.json`, qui
  ajoutait un niveau d'indirection pour un seul lecteur.
- `qtpy6/web/construire.py` est inchangé. Son défaut est l'adresse du site, donc la liaison bascule quand le site
  est reconstruit (et ses hunks `--roue` sont à une autre session).

**Preuves.** Dans une copie du dépôt sous `$TMPDIR` :
- `telecharger.sh` a été essayé avec les deux liaisons, à partir de zips locaux, avec leur licence.
- Le site a été assemblé par `construire_site.py`, puis sondé avec `index.html?script=compteur.py`. L'application
  s'affiche sous PySide6 (capture relue).
- L'erreur du worker (`/pyodide/pyodide.mjs` introuvable) est identique sous PyQt6. Elle est propre au site local,
  qui ne sert pas de Pyodide ordinaire.

**À faire par l'utilisateur, avant de pousser :**
- ~~valider la licence~~ : fait le 02/10/2026, voir ci-dessous ;
- publier la release avec le zip ;
- sans cela, l'action Pages (`telecharger.sh` sans argument) échouera sur l'adresse de la release. Pour garder
  PyQt6 en attendant, il suffit d'écrire `telecharger.sh pyqt6` dans `.github/workflows/pages.yml`.
- ~~`web.md`, en cours de modification par une autre session, décrit encore la licence GPL de Pyodide-Qt (§
  hébergement et § Licence). Il est à mettre à jour après validation.~~ Fait le 02/10/2026 (dernière section).
- Le zip embarque la licence du dépôt : la modifier impose de relancer `paquet`, puis de reporter la nouvelle
  empreinte dans `versions.json` (elle change à chaque construction, voir la section suivante).

**Licence validée (02/10/2026, 8 h 35).** Question de l'utilisateur : « quel décision dois-je prendre sur la
licence ? ». Réponse : la LGPL v3 §4 b) demande de JOINDRE une copie de la GPL et de la LGPL à l'ouvrage combiné, et le
brouillon y renvoyait par lien. Proposé : y joindre les textes, puis commiter tout le travail PySide6 ; réponse « oui ».
- `hebergement/LICENSE-Pyodide-PySide6.txt` : le texte SPDX `/usr/share/licenses/spdx/LGPL-3.0-only.txt` ajouté à la
  fin. Il contient déjà la GPL v3 à la suite de la LGPL : une première version qui ajoutait aussi `GPL-3.0-only.txt`
  la donnait en double, retirée. Pris sur le disque et non sur gnu.org : le shell n'a pas de réseau, et ce sont les
  textes de la FSF à l'identique. Le marqueur « BROUILLON » de l'en-tête, d'abord gardé (fond juridique non relu par
  un juriste), a été retiré à la demande de l'utilisateur (« je veux le retirer », 9 h 07) une fois le site publié ;
  zip reconstruit, sha256 `5e7d87c7…`, release mise à jour par `gh release upload --clobber`.
- `wasm/construire.sh paquet` relancé : nouveau zip, sha256 `d0619f4f…` reporté (remplacé depuis, voir plus bas) dans `versions.json`. Vérifié :
  `telecharger.sh pyside6 <zip local>` passe la vérification d'empreinte, et `exemple/pyodide-qt/LICENSE.txt` est
  identique au fichier du dépôt. Tests : 97 verts sous `QT_API=pyqt6` et `QT_API=pyside6`.
- Reste ouvert : publier la release avec CE zip AVANT de pousser (sinon l'action Pages échoue) ; ~~`web.md` (§ Licence)~~ (fait le 02/10/2026).

## Démarrage d'un QCM en ligne (point 4 de la liste)

Demande de l'utilisateur : « optimiser au maximum le temps de démarage d'un qcm en ligne, que ce soit la première
fois ou pas : decouper le telechargement en plusieurs fichiers qui permette de commencer à lancer des chose avant
de tout avoir ? s'assure' de la mise en cash dans le navigateur de tout ce qui permetra d'accelerer la lecture du
prochain qcm ».

**1. La bibliothèque standard précompilée dans le paquet (`wasm/construire.sh`, phase `paquet`).**
`pyodide py-compile` remplace les `.py` de `python_stdlib.zip` par des `.pyc`. Mesure dans Firefox sans
interface, banc du lecteur SmartTeacher, 3 essais de chaque :

| | stdlib en `.py` | stdlib en `.pyc` |
|---|---|---|
| Pyodide chargé | 1,58–1,71 s | 0,57–0,71 s |
| .qcm ouvert | 3,6–3,87 s | 2,05–2,20 s |

Le gain vaut à chaque chargement, premier ou suivant : c'est du temps de compilation Python, pas de réseau. La
taille du zip ne bouge presque pas (4,15 Mo). Prix : les traces d'erreur n'affichent plus la ligne de source des
modules de la bibliothèque standard. C'est ce que fait déjà le Pyodide officiel.

**Reproductibilité abandonnée.** `py-compile` inscrit la date d'extraction dans l'en-tête de chaque `.pyc`, donc
le sha256 du zip change à chaque construction (`PYTHONHASHSEED=0` n'y change rien). Écarté : réécrire les
en-têtes à date fixe, du code de plus pour une propriété dont personne ne dépend, puisque l'empreinte n'est qu'un
contrôle d'intégrité du téléchargement. Conséquence : reporter l'empreinte dans `versions.json` après chaque
`paquet`, ce que dit le commentaire de la phase.

**2. Option `pyc` de `qtpy6/web/assembler.py` (désactivée par défaut).** Chaque `.py` de l'archive reçoit son
`__pycache__/<nom>.cpython-313.pyc` en mode `UNCHECKED_HASH` : l'archive est dépaquetée dans le système de
fichiers de Pyodide, Python y trouve le `.pyc` et ne recompile pas (s'il venait d'une autre version de Python, le
nombre magique diffère et il retombe sur la source, sans erreur).

| | sans | avec |
|---|---|---|
| import du lecteur | 0,81–1,02 s | 0,52–0,62 s |
| `lecteur.zip` | 5,85 Mo | 8,41 Mo |

Les 2,5 Mo de plus viennent surtout de pygments (1,8 Mo). Pourquoi pas par défaut :
- 0,3 à 0,4 s gagnés contre 2,5 Mo de plus à télécharger au premier chargement : sur une connexion à moins
  d'environ 50 Mbit/s, le premier lancement y perd ;
- `tests/test_web.py::test_assembler` (autre session) interdit tout `__pycache__` dans l'archive.

Alternatives écartées ou non tranchées :
- précompiler les seuls fichiers et paquets de l'application, sans les distributions (pygments) : la plus grande
  part du gain avec 0,5 Mo de plus seulement, mais non mesuré ;
- une archive sans les sources (`.pyc` seuls) : même taille qu'aujourd'hui, mais plus de traces lisibles dans
  l'application, ce qui gêne le débogage des élèves ;
- c'est un arbitrage qui revient à l'utilisateur ; l'option est en place pour le trancher par une mesure.

**Vérifié** : 80 tests de `test_qtpy6`, `test_process` et `test_web` verts sous `QT_API=pyside6` et sous
`QT_API=pyqt6` ; `assembler(..., pyc=True)` sur un fichier `a.py` produit `a.py` et
`__pycache__/a.cpython-313.pyc`.
Le test de fumée `node wasm/fumee.mjs` passe sur le build (signal, mode paresseux, alias).

**3. Découper le téléchargement : déjà fait, rien à ajouter.** Vérifié par lecture de `qtpy6web.js` :
- les archives de l'application sont demandées en même temps que `loadPyodide` (`Promise.all`) ;
- Pyodide compile le `.wasm` en flux (`instantiateStreaming`) : la compilation commence avant la fin du
  téléchargement ;
- découper davantage le `.wasm` est impossible : c'est un seul module lié statiquement (Qt, PySide6, CPython).

**4. Compression.** Mesuré sur le paquet :

| fichier | brut | gzip -9 | brotli -11 |
|---|---|---|---|
| `pyodide.asm.wasm` | 35,4 Mo | 11,3 Mo | 8,0 Mo |
| `pyodide.asm.js` | 1,17 Mo | 0,24 Mo | — |
| `python_stdlib.zip` | 4,15 Mo | 4,11 Mo | — |

Brotli ferait gagner 3,3 Mo au premier chargement, mais GitHub Pages ne sert que gzip. **Vérifié le 02/10/2026**
(curl lancé par l'utilisateur, `Accept-Encoding: gzip, br`, sur `pyodide-qt/pyodide.asm.wasm` publié) : Pages
répond `content-encoding: gzip`, `content-length: 10516295`, `content-type: application/wasm`,
`cache-control: max-age=600`. Le `.wasm` voyage donc compressé (10,5 Mo, le chiffre du build PyQt6 encore publié) ;
un autre hébergement pour brotli ne gagnerait que 2 à 3 Mo, pas de quoi le justifier.

**5. Cache du navigateur pour le QCM suivant.** Pages sert avec `Cache-Control: max-age=600`. Au-delà de
10 minutes, chaque fichier est revalidé (requête conditionnelle, réponse 304 sans corps) : le QCM suivant ne
retélécharge rien, il paie un aller-retour par fichier. Le code compilé du `.wasm` est en plus gardé par le
navigateur, associé à l'adresse. Rien n'est donc à faire côté qtpy6.
Proposition, non implémentée parce que la page SmartTeacher n'est pas à cette session : un service worker qui
sert `pyodide-qt/` depuis le Cache Storage, avec le numéro de version dans l'adresse, supprimerait ces
revalidations et rendrait le lancement possible hors ligne. **Non mesuré** : le gain dépend de la latence.

**Passe de simplification (02/10/2026), par fichier.** `assembler.py` : renvoi vers une note inexistante corrigé,
le fichier temporaire de `py_compile` gardé (la fonction n'écrit que vers un chemin). `construire.sh` : même
renvoi corrigé ; la réécriture des en-têtes `.pyc` retirée (reproductibilité abandonnée, voir plus haut).
`fils.py`, `bloquant.py`, `_binding.py`, `QtCore/QtGui/QtWidgets.py`, `fumee.mjs`, `telecharger.sh`,
`construire_site.py`, `index.html`, `versions.json`, la licence : relus, rien à enlever. `CHANGELOG.md` : une entrée
ajoutée pour PySide6 par défaut et l'option `pyc`.

**6. pdf.js hors de l'archive, chargé au premier PDF (02/10/2026).** Demande de l'utilisateur : « fais les 3 dans
l'ordre en autonomie » (pdf.js paresseux, service worker, serializejson sans blosc).
- `assembler(..., exclure=[...])` : des débuts de noms laissés hors du zip (les polices passent par `z.write`, pas
  par ce filtre, et ne sont pas concernées).
- `qtpy6web.js` pose `window.qtpy6Js = import.meta.url` ; `pdf.py` (`_js`, `url`) prend le fichier dans le paquet
  s'il y est (comportement inchangé pour qui n'exclut rien), sinon `new URL(nom, qtpy6Js)`.
- SmartTeacher (`QCM/web/construire.py`, `deployer.sh`) copie `pdfjs/` à côté de `qtpy6web.js` et le publie.
Écarté : retirer pdf.js du paquet qtpy6 et le servir toujours à part. Toute application devrait alors publier
`pdfjs/` ; avec `exclure`, c'est un choix de l'application, et le défaut ne casse personne.
Mesuré : `lecteur.zip` 3015 → 2516 Kio. Pour un sujet sans cours, 1,7 Mo en moins, jamais téléchargés.
Vérifié dans Firefox sans interface (sonde, scénario `cours`, sujet SNT TP01 avec son PDF) : `QPdfView`, texte
« L'ESSENTIEL DU LANGAGE PYTHON » dans la couche de texte 0,6 s après le clic, et `unzip -l` sans `pdfjs`.
97 tests verts sous `QT_API=pyqt6` et `QT_API=pyside6`.
Défaut trouvé au passage, non corrigé ici (fichier d'une autre session) : le scénario `cours` de
`sonde_lecteur.html` teste `couche is not None`. Or `querySelector` rend `jsnull` sous Pyodide 0.29, donc il
échoue avant l'affichage. Le test a été fait sur une copie corrigée (`if couche`), puis supprimée.

## Documentation passée à PySide6 (02/10/2026, 9 h 30)

Demande : « tu fais les 3 » (la documentation qui parlait encore de PyQt6 en était un).
- `web.md` : intro (anglais et français), commentaire de l'exemple de page, Installation (le terme « Pyodide-Qt »
  défini comme le Pyodide où Qt est lié, quelle que soit la liaison ; les deux builds, `pyodide_pyside6` par défaut en
  LGPL v3, `pyodide_qt` en repli GPL v3), Hébergement (`telecharger.sh [pyside6|pyqt6]`, tailles PySide6 mesurées en
  local : 41 Mo, `.wasm` 35 Mo, 11 en gzip -9 ; la construction du zip par `wasm/construire.sh paquet`), Licence.
- `README.md` : la phrase d'introduction du navigateur et la ligne du niveau de preuve (testé sous les deux liaisons).
- Choix : les autres « Pyodide-Qt » du texte sont gardés, désormais au sens générique défini une fois en Installation,
  plutôt que renommés partout (une quinzaine d'occurrences, dont des mesures faites sous PyQt6 qui restent historiques :
  « Pièges et mesures (… Pyodide-Qt 0.29.3) »). Écarté : un nouveau nom (« Pyodide-PySide6 ») partout, qui aurait
  rendu fausses les mesures faites sous PyQt6.
- Vérifié par lecture : chaque affirmation nouvelle a sa source (`telecharger.sh` l. 5-23, la notice de licence l. 23-29
  sur le moyen de re-lier, `wasm/README.md` présent). Les hunks d'une autre session dans ces deux fichiers (`--roue`,
  `stockage.monter`, `QPropertyAnimation`) ne sont pas les miens et ne sont pas commités avec.
