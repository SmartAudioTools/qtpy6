"""Le site d'une application qtpy6 écrite pour le bureau, sans rien y changer : ``python -m qtpy6.web.construire app.py``
écrit dans ``site/`` la page (``js/gabarit.html``, qui lance le script comme ``python app.py`` : ``qtpy6.web.lancer``),
les fichiers de qtpy6 (``deposer`` : le chargeur ``qtpy6web.js``, le service worker, pdf.js) et ``app.zip`` (le dossier du script, qtpy6 et ce qu'on y ajoute). Reste à servir ``site/``
(ou le vérifier : ``python -m qtpy6.web.sonde site/index.html capture.png``).

    python -m qtpy6.web.construire app.py [site] [--pyodide URL] [--paquet nom]… [--distribution nom]… [--police f]…
                                   [--roue f.whl]… [--titre texte]

``--pyodide`` : où la page charge Pyodide-Qt (l'hébergement de qtpy6 par défaut ; ``./pyodide-qt/`` pour un dossier
servi avec la page). ``--paquet`` : un paquet pur Python importable ici, pris tel qu'installé (``assembler``) ;
``--distribution`` : idem avec ses métadonnées (points d'entrée) ; ``--police`` : un .ttf/.otf, sous ``polices/`` —
Qt-WASM embarque déjà DejaVu Sans et DejaVu Sans Mono, une application n'en a besoin que pour une autre police.
``--roue`` : une extension compilée pour Pyodide-Qt (``…-pyemscripten_2025_0_wasm32.whl``), copiée à côté de la page
sous son nom, que Pyodide lit pour savoir quel paquet il installe.
Le dossier du script est pris entier, sauf les fichiers et dossiers cachés, ``__pycache__`` et le site lui-même."""

import argparse
import importlib.resources
import json
import shutil
from pathlib import Path

from .assembler import assembler

PYODIDE_QT = "https://smartaudiotools.github.io/qtpy6/pyodide-qt/"
DOSSIER = "/home/pyodide/app"


FICHIERS_JS = ("qtpy6web.js", "sw.js", "pdfjs/pdf.min.mjs", "pdfjs/pdf.worker.min.mjs")


def deposer(site):
    """Dépose dans ``site`` (le dossier de la page) les fichiers de qtpy6 que la page charge par URL : le chargeur
    ``qtpy6web.js``, le service worker ``sw.js`` (``service_worker`` de qtpy6web.js : il ne contrôle que son dossier et ce
    qui est en dessous, d'où sa place à côté de la page) et pdf.js sous ``pdfjs/`` (hors de l'archive : ``assembler``,
    ``exclure``). Une application qui écrit sa propre page appelle ceci plutôt que de recopier une liste qui changerait
    sans elle. Le contenu seul, sans copystat (refusé sur des fichiers d'un autre compte)."""
    site = Path(site)
    js = importlib.resources.files("qtpy6.web") / "js"
    for nom in FICHIERS_JS:
        (site / nom).parent.mkdir(parents=True, exist_ok=True)
        (site / nom).write_bytes(js.joinpath(nom).read_bytes())


def construire(script, site="site", pyodide=PYODIDE_QT, paquets=(), distributions=(), polices=(), roues=(), titre=None):
    """Écrit ``site/index.html``, ``site/app.zip`` et les fichiers de ``deposer`` ; rend la taille de l'archive en octets."""
    script, site = Path(script).resolve(), Path(site).resolve()
    site.mkdir(parents=True, exist_ok=True)
    racine = script.parent
    fichiers = {str(p.relative_to(racine)): p for p in sorted(racine.rglob("*"))
                if p.is_file() and site not in p.parents and "__pycache__" not in p.parts
                and not any(part.startswith(".") for part in p.relative_to(racine).parts)}
    taille = assembler(site / "app.zip", fichiers, paquets=("qtpy6", *paquets), distributions=distributions,
                       polices=polices, exclure=["qtpy6/web/js/pdfjs/"])  # pdf.js : à côté de la page (deposer)
    for roue in roues:
        shutil.copyfile(roue, site / Path(roue).name)
    js = importlib.resources.files("qtpy6.web") / "js"
    page = (js / "gabarit.html").read_text(encoding="utf-8")
    for avant, apres in (('"./pyodide-qt/"', json.dumps(pyodide)),
                         ('"/home/pyodide/app/app.py"', json.dumps(f"{DOSSIER}/{script.name}")),
                         ("roues: [],", f"roues: {json.dumps([f'./{Path(r).name}' for r in roues])},"),
                         ("<title>Application</title>", f"<title>{titre or script.stem}</title>")):
        assert page.count(avant) == 1, avant  # le gabarit a changé sans ce module
        page = page.replace(avant, apres)
    (site / "index.html").write_text(page, encoding="utf-8")
    deposer(site)
    return taille


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("script")
    a.add_argument("site", nargs="?", default="site")
    a.add_argument("--pyodide", default=PYODIDE_QT)
    a.add_argument("--paquet", action="append", default=[])
    a.add_argument("--distribution", action="append", default=[])
    a.add_argument("--police", action="append", default=[])
    a.add_argument("--roue", action="append", default=[])
    a.add_argument("--titre")
    o = a.parse_args(argv)
    taille = construire(o.script, o.site, o.pyodide, o.paquet, o.distribution, o.police, o.roue, o.titre)
    print(f"{o.site}/ : index.html, {', '.join(FICHIERS_JS)}, app.zip ({taille // 1024} Kio)")


if __name__ == "__main__":
    main()
