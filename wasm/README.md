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
| `pyside` | libshiboken, libpyside et les modules QtCore, QtGui, QtWidgets, QtSvg, QtSvgWidgets, compilés en croisé |
| `pyodide` | Archive les objets PySide, compile `qt_statique.cpp`, corrige et relie Pyodide (`patches/pyodide-*`), écrit un `pyodide-lock.json` vide |
| `paquet` | `$RACINE/pyodide-pyside6-0.29.3.0.zip` : les fichiers de `dist/` qu'une page charge, sous `pyodide-qt/`, avec la licence (`hebergement/LICENSE-Pyodide-PySide6.txt`, nommée `LICENSE.txt`), à dates fixes ; son sha256 va dans `qtpy6/web/versions.json` (`pyodide_pyside6`), et le zip dans la release du même nom, que télécharge `hebergement/telecharger.sh` |

## Les fichiers

- `patches/` : les correctifs, appliqués par `git apply` une seule fois (un patch déjà appliqué est reconnu à son
  inverse). Le préfixe dit l'arbre visé : `pyside-` et `shiboken-` pour pyside-setup, `pyodide-` pour Pyodide.
- `qt_statique.cpp` : l'import des greffons Qt statiques, et les bouchons de fils et d'IndexedDB. Il est repris de la
  recette de Pyodide-Qt (JarrettSJohnson/pyodide-with-pyqt6, sous licence MIT).
- `fumee.mjs` : le test de fumée.
- `versions.txt` : les empreintes des sources.

## Limites connues

- Pas de QtPdf : pdfium n'a pas de cible WebAssembly. La doublure pdf.js de `qtpy6.web.pdf` reste en place.
- Le lien est statique. Sous LGPL v3, il faut donc fournir de quoi re-lier, et cette recette en fait partie (étape 7
  du plan).
