#!/bin/sh
# Le Pyodide où Qt 6.10.2 et sa liaison Python sont liés en WebAssembly (Python 3.13), la release épinglée dans
# qtpy6/web/versions.json : téléchargée si elle n'est pas déjà là, empreinte vérifiée, dépaquetée dans exemple/pyodide-qt/
# avec sa licence (pyodide-qt/LICENSE.txt) : ce que sert l'exemple en local, et ce que l'action Pages publie.
# Puis les deux gros fichiers doublés de jumeaux Brotli et gzip (NOM.br, NOM.gz), que qtpy6web.js demande d'abord : GitHub
# Pages ne sert qu'en gzip, et Brotli fait 8,0 Mo du moteur au lieu de 11,3, 2,7 Mo de la bibliothèque standard au lieu de 4,2
# (mesuré le 02/10/2026 : −0,5 s sur le seul moteur à 50 Mbit/s). La bibliothèque standard est d'abord réécrite sans
# compression (ZIP_STORED, 9,8 Mo en mémoire au lieu de 4,2) : déjà dégonflée, Brotli n'en tirait rien (4,1 Mo). Le jumeau
# gzip sert les navigateurs sans DecompressionStream("brotli") (Chromium 153, 04/10/2026) : sans lui, ils téléchargeaient
# cette bibliothèque standard non compressée (Pages ne compresse pas les .zip).
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
python3 -c "
import os, zipfile
with zipfile.ZipFile('exemple/pyodide-qt/python_stdlib.zip') as a, zipfile.ZipFile('s.zip', 'w', zipfile.ZIP_STORED) as b:
    for i in a.infolist(): b.writestr(i, a.read(i), zipfile.ZIP_STORED)
os.replace('s.zip', 'exemple/pyodide-qt/python_stdlib.zip')"
brotli -q 11 -f exemple/pyodide-qt/pyodide.asm.wasm & MOTEUR=$!  # les deux en parallèle (une minute et demie pour le moteur)
brotli -q 11 -f exemple/pyodide-qt/python_stdlib.zip
gzip -9 -k -f -n exemple/pyodide-qt/pyodide.asm.wasm exemple/pyodide-qt/python_stdlib.zip
wait $MOTEUR
ls -l exemple/pyodide-qt
