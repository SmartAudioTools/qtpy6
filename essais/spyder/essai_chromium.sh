#!/bin/sh
# SmartPythonEditor (spe.py) sous Chromium : serveur local sur le site de l'essai, puis la page. Lancé par l'utilisateur.
ICI=$(dirname "$(readlink -f "$0")")
cd "$ICI/site" || exit 1
setsid python3 -m http.server 8765 --bind 127.0.0.1 > "$ICI/serveur_spe.log" 2>&1 &
setsid chromium "http://127.0.0.1:8765/index.html?script=spe.py" > "$ICI/chromium_spe.log" 2>&1 &
