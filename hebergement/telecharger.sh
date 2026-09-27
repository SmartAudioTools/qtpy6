#!/bin/sh
# Pyodide-Qt (Qt 6.10.2 + PyQt6 6.10.2 + Python 3.13 en WebAssembly), la release épinglée dans qtpy6/web/versions.json :
# téléchargée si elle n'est pas déjà là, empreinte vérifiée, dépaquetée dans exemple/pyodide-qt/ (ce que sert l'exemple en
# local, et ce que l'action Pages publie).
#   hebergement/telecharger.sh                     télécharge l'archive dans hebergement/
#   hebergement/telecharger.sh /chemin/du/meme.zip une archive déjà téléchargée (sans réseau) : même vérification
# Pour changer de version : versions.json seul (archive, sha256 = sha256sum du zip, version, abi).
set -eu
[ $# -eq 0 ] || set -- "$(realpath "$1")"  # un chemin relatif survit au cd
cd "$(dirname "$0")/.."
eval "$(python3 -c "import json; a = json.load(open('qtpy6/web/versions.json'))['pyodide_qt']; print('URL=' + a['archive']); print('SHA256=' + a['sha256'])")"
ZIP="${1:-hebergement/${URL##*/}}"
[ -f "$ZIP" ] || curl -fL -o "$ZIP" "$URL"
echo "$SHA256  $ZIP" | sha256sum -c -
rm -rf exemple/pyodide-qt
unzip -q "$ZIP" -d exemple  # le zip contient le dossier pyodide-qt/
ls -l exemple/pyodide-qt
