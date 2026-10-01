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
