#!/bin/sh
# Le Pyodide où Qt 6.10.2 et sa liaison Python sont liés en WebAssembly (Python 3.13), la release épinglée dans
# qtpy6/web/versions.json : téléchargée si elle n'est pas déjà là, empreinte vérifiée, dépaquetée dans exemple/pyodide-qt/
# avec sa licence (pyodide-qt/LICENSE.txt) : ce que sert l'exemple en local, et ce que l'action Pages publie.
#   hebergement/telecharger.sh [pyside6|pyqt6] [/chemin/du/meme.zip]
# pyside6 (défaut) : Pyodide-PySide6, construit par wasm/construire.sh (phase paquet), LGPL v3.
# pyqt6 : Pyodide-Qt de JarrettSJohnson, GPL v3, le repli.
# Le zip donné : une archive déjà téléchargée (sans réseau), même vérification.
# Pour changer de version : versions.json seul (archive, sha256 = sha256sum du zip, version, abi).
set -eu
LIAISON=pyside6
case "${1:-}" in pyside6|pyqt6) LIAISON=$1; shift ;; esac
[ $# -eq 0 ] || set -- "$(realpath "$1")"  # un chemin relatif survit au cd
cd "$(dirname "$0")/.."
CLE=$( [ "$LIAISON" = pyqt6 ] && echo pyodide_qt || echo pyodide_pyside6 )
eval "$(python3 -c "import json; a = json.load(open('qtpy6/web/versions.json'))['$CLE']; print('URL=' + a['archive']); print('SHA256=' + a['sha256'])")"
ZIP="${1:-hebergement/${URL##*/}}"
[ -f "$ZIP" ] || curl -fL -o "$ZIP" "$URL"
echo "$SHA256  $ZIP" | sha256sum -c -
rm -rf exemple/pyodide-qt
unzip -q "$ZIP" -d exemple  # le zip contient le dossier pyodide-qt/
# La release de Pyodide-Qt n'a pas sa licence : celle du dépôt, au nom qu'elle a dans le zip de Pyodide-PySide6
[ "$LIAISON" = pyside6 ] || cp hebergement/LICENSE-Pyodide-Qt.txt exemple/pyodide-qt/LICENSE.txt
ls -l exemple/pyodide-qt
