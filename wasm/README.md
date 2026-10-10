# PySide6 en WebAssembly

Cette recette produit un Pyodide 0.29.3 (Python 3.13.2) dans lequel Qt 6.10.2 et PySide6 6.10.2 sont liés
statiquement. C'est le pendant, sous LGPL, de Pyodide-Qt (PyQt6), sur lequel il est calqué. `qtpy6.web` le charge
comme Pyodide-Qt : le dossier `dist/` se met à la place de `pyodide-qt/`, et `QT_API` en mode `auto` y trouve PySide6.

Le récit, les choix argumentés et les niveaux de preuve sont dans
`notes/2026-09-30 - PySide6 en WebAssembly.md`.

## Construire

1. **Les sources, une fois, avec le réseau.** L'utilisateur lance la commande ci-dessous. Elle écrit les empreintes
   dans `versions.txt`.

       wasm/telecharger_sources.sh

2. **La construction, sans réseau.** Les phases sont rejouables, chacune saute ce qui est déjà fait.

       wasm/construire.sh emsdk qthote qt shiboken cpython pyside pyodide paquet

   Arbre de travail : `$RACINE`, par défaut `/DATA/Python/outils_wasm/pyside6` (hors dépôt, environ 40 Go).
   Les journaux de chaque phase vont dans `$RACINE/journaux/`. Le résultat se trouve dans
   `$RACINE/sources/pyodide/dist/`.

3. **Le test de fumée sous node.** Il importe les cinq modules, puis émet et reçoit un `Signal` Python.

       node wasm/fumee.mjs [dist]

## Les phases

| Phase | Ce qu'elle fait |
|---|---|
| `emsdk` | Copie privée d'emscripten 4.0.9, corrigée comme Pyodide l'attend |
| `qthote` | Qt 6.10.2 natif : moc, rcc, uic et QtCore pour le générateur |
| `qt` | qtbase et qtsvg statiques pour WebAssembly, sans fils, exceptions wasm |
| `shiboken` | Le générateur shiboken6 natif, corrigé pour le lien statique (`patches/shiboken-*`) |
| `cpython` | Le CPython de Pyodide : en-têtes et `libpython3.13.a` |
| `pyside` | libshiboken, libpyside et les 13 liaisons (QtCore, QtGui, QtWidgets, QtSvg, QtSvgWidgets, puis PrintSupport, Network, Sql, Xml, Concurrent, OpenGL, OpenGLWidgets, Test), compilées en croisé |
| `pyodide` | Archive les objets PySide, compile `qt_statique.cpp`, corrige et relie Pyodide (`patches/pyodide-*`, avec `-sFETCH` pour QNetworkAccessManager), écrit un `pyodide-lock.json` vide |
| `dynamique` | `pyside_agrege.so` (les cinq liaisons de base et Qt, chargé au démarrage) et un `pyside_Qt<M>.so` par module à la demande (liaison, `libQt6<M>.a`, greffons) ; `symboles.py --verifier` échoue si un import d'un `.so` n'est fourni ni par l'agrégat, ni par le module principal, ni par un `.so` chargé avant |
| `paquet` | `$RACINE/pyodide-pyside6-0.29.3.1.zip` : les fichiers de `dist/` qu'une page charge, sous `pyodide-qt/`, avec la licence (`hebergement/LICENSE-Pyodide-PySide6.txt`, nommée `LICENSE.txt`), à dates fixes ; son sha256 va dans `qtpy6/web/versions.json` (`pyodide_pyside6`), et le zip dans la release du même nom, que télécharge `hebergement/telecharger.sh` |

## Les fichiers

- `patches/` : les correctifs, appliqués par `git apply` une seule fois (un patch déjà appliqué est reconnu à son
  inverse). Le préfixe dit l'arbre visé : `pyside-` et `shiboken-` pour pyside-setup, `pyodide-` pour Pyodide.
- `qt_statique.cpp` : l'import des greffons Qt statiques, et les bouchons de fils et d'IndexedDB. Il est repris de la
  recette de Pyodide-Qt (JarrettSJohnson/pyodide-with-pyqt6, sous licence MIT).
- `metatypes_qtcore.cpp` : les huit `QMetaTypeInterfaceWrapper<T>::metaType` de QtCore qu'un objet compilé en visibilité
  cachée référence par relocation directe, donc à instancier dans chaque module (le commentaire du fichier détaille).
- `symboles.py` : les sections import/export des `.so`, la liste des exports à forcer sur l'agrégat, la vérification.
- `pyodide-qt.mjs` : le `pyodide.mjs` du paquet ; charge l'agrégat au démarrage et, au PREMIER `import PySide6.QtXxx`
  (finder Python, `run_sync` sur JSPI : depuis le script lancé par `qtpy6.web.lancer` ou un slot), le `.so` du module.
- `fumee.mjs` : le test de fumée, les huit modules à la demande compris.
- `versions.txt` : les empreintes des sources.

## Limites connues

- Les modules à la demande : `QNetworkAccessManager` passe par `fetch` (même origine ou CORS, pas de sockets), pas de
  TLS natif (greffon `certonly`), QtConcurrent sans fils (ni `QThreadPool`), `QPrinterInfo` sans imprimante (`QPrinter`
  écrit un PDF dans le système de fichiers de la page). Un import depuis un contexte non suspendable lève `ImportError`.

- Pas de QtPdf : pdfium n'a pas de cible WebAssembly. La doublure pdf.js de `qtpy6.web.pdf` reste en place.
- Le lien est statique. Sous LGPL v3, il faut donc fournir de quoi re-lier, et cette recette en fait partie (étape 7
  du plan).
