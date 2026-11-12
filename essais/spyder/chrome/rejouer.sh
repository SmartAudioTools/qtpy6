#!/bin/bash
# Item 15 du TODO Portage (W552, 12/11/2026) : rejoue les jalons sous Blink (sonde --chromium, QtWebEngine = Chrome 140),
# ou sous Firefox pour contrôle (moteur=firefox), sur un site à part, /DATA/Python/qtpy6_essais/chrome/site (construire_chrome.py : le site
# commun, zippé avec les journaux que les sondes des autres écrivent, était corrompu à 14:11).
#   bash chrome/rejouer.sh chromium|firefox [essai ...]       (depuis essais/spyder)
# Essai = script[:état attendu[:options]] ; défaut : la liste des jalons de l'item 15.
cd "$(dirname "$0")/.." || exit 1
P=/DATA/Python/SmartPython/CachyOS/versions/SmartPython/bin/python
moteur=$1; shift
[ "$moteur" = chromium ] && opt=--chromium || opt=
essais=("$@")
[ ${#essais[@]} -eq 0 ] && essais=(jalon5.py:fini:--pilote jalon7.py jalon8a.py jalon8b.py panneaux.py jalon8c.py
                                   spe_pyxel.py:pyxel-fini)
mkdir -p /DATA/Python/qtpy6_essais/chrome/logs
for e in "${essais[@]}"; do
    IFS=: read -r script etat extra <<< "$e"
    nom=${script%.py}_$moteur
    debut=$(date +%s)
    # shellcheck disable=SC2086
    timeout 1000 "$P" -m qtpy6.web.sonde "/DATA/Python/qtpy6_essais/chrome/site/index.html?script=$script" "/DATA/Python/qtpy6_essais/chrome/logs/$nom.png" \
        --racine /DATA/Python/qtpy6_essais/chrome/site --delai 800 --etat "${etat:-fini}" $opt $extra > "/DATA/Python/qtpy6_essais/chrome/logs/$nom.log" 2>&1
    echo "$script $moteur code=$? $(( $(date +%s) - debut ))s : $(grep -E 'état :|verdicts|passe sur|Traceback' \
        "/DATA/Python/qtpy6_essais/chrome/logs/$nom.log" | tail -2 | tr '\n' ' ')" >> /DATA/Python/qtpy6_essais/chrome/logs/bilan.log
done
echo "fin $moteur" >> /DATA/Python/qtpy6_essais/chrome/logs/bilan.log
