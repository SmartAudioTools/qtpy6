"""Le site GitHub Pages de qtpy6 dans ``site/`` (ou le dossier donné) : la page de lancement (``index.html``), le cadre
isolé où tourne le script (``cadre.html``), le chargeur ``qtpy6web.js``, ``qtpy6.zip`` (le paquet, que le cadre met dans
``sys.path``) et Pyodide-Qt (``exemple/pyodide-qt/``, qu'apporte ``telecharger.sh``) avec sa licence. La bibliothèque
standard seule : ni qtpy6 ni Qt n'ont à être installés pour construire (l'action Pages n'a qu'un python3 nu).

    python3 hebergement/construire_site.py [site]"""

import shutil
import sys
import zipfile
from pathlib import Path

DEPOT = Path(__file__).resolve().parent.parent


def construire(site):
    site = Path(site)
    site.mkdir(parents=True, exist_ok=True)
    for source, cible in (("hebergement/index.html", "index.html"), ("hebergement/cadre.html", "cadre.html"),
                          ("hebergement/LICENSE-Pyodide-Qt.txt", "LICENSE-Pyodide-Qt.txt"),
                          ("qtpy6/web/js/qtpy6web.js", "qtpy6web.js")):
        shutil.copyfile(DEPOT / source, site / cible)
    with zipfile.ZipFile(site / "qtpy6.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((DEPOT / "qtpy6").rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, p.relative_to(DEPOT))
    moteur = site / "pyodide-qt"
    if not moteur.exists():
        shutil.copytree(DEPOT / "exemple/pyodide-qt", moteur)


if __name__ == "__main__":
    construire(sys.argv[1] if len(sys.argv) > 1 else "site")
