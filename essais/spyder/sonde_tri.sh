#!/bin/sh
# Essai du triangle (12/10/2026) : SmartPythonEditor web dans un Firefox visible, le jeu Monkey ouvert ; cliquer le triangle.
cd /DATA/Python/qtpy6/essais/spyder || exit 1
timeout 1300 /DATA/Python/SmartPython/CachyOS/versions/SmartPython/bin/python -m qtpy6.web.sonde \
    'site/index.html?script=spe_monkey.py&jeu=projet_monkey_correction_exercice_33_tilemaps_images.py&bouton=1' \
    capture_tri2.png --racine site --delai 1200 --etat jamais --visible > sonde_tri2.log 2>&1
