"""Construit ``site/`` (index.html, app.zip, pyodide-qt en lien) pour les essais du dossier (``?script=`` choisit lequel,
editeur.py sans), puis le mesure avec la sonde :

    $P construire_site.py            # construit
    $P -m qtpy6.web.sonde site/index.html capture_web.png --racine site --delai 600
    $P -m qtpy6.web.sonde 'site/index.html?script=jalon2.py' capture_jalon2.png --racine site --delai 600 --pilote
    $P -m qtpy6.web.sonde 'site/index.html?script=jalon4.py' capture_jalon4.png --racine site --delai 600 --pilote

Même mécanisme que ``python -m qtpy6.web.construire``, avec en plus : le fork Spyder et les roues pures sur sys.path (d'où
``--paquet spyder`` prend le fork), les paquets purs que l'import de CodeEditor tire (relevé par audit de sys.modules sur le
bureau), les dossiers de Spyder inutiles ici laissés dehors (MathJax de l'aide : 29 Mo, traductions sauf le .mo français : 6 Mo, tests : 4 Mo), les métadonnées de spyder (ses points d'entrée),
les polices DejaVu, et deux mesures imprimées dans le journal de la page : durée totale et tas WebAssembly."""

import json
import os
import sys
from pathlib import Path

GREFFONS = ("spyder_stop_toolbar", "spyder_interpreter_toolbar")  # spe.py : les greffons de SmartPythonEditor qui
# portent ses boutons Stop et Interpréteur (smartos-support/plugins-catalogue.txt), en pur Python ; window_controls dessine
# des boutons de fenêtre, sans objet dans une page, viztracer et line_profiler ont des extensions C
GREFFONS_SOURCES = Path("/DATA/Python/FORKS/SmartPythonEditorPlugins")
sys.path[:0] = ["/DATA/Python/FORKS/SmartPythonEditor", "/DATA/Python/qtpy6/essais/roues/lib",
                *(str(GREFFONS_SOURCES / g) for g in GREFFONS)]
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("SPYDER_QT_SKIP_VERSION_CHECK", "1")

from qtpy6.web import assembler as _assembler, construire as _construire  # noqa: E402

ICI = Path(__file__).resolve().parent
SITE = ICI / "site"
PYODIDE_QT = Path("/DATA/Python/qtpy6/exemple/pyodide-qt")
PAQUETS = ("spyder qtpy IPython asttokens chardet colorama decorator diff_match_patch executing intervaltree jedi packaging parso "
           "prompt_toolkit pure_eval pygments qdarkstyle qtawesome qtconsole sortedcontainers spyder_kernels textdistance "
           "stack_data superqt tinycss2 traitlets wcwidth webencodings "
           "dateutil jupyter_client jupyter_core msgpack platformdirs pyuca tornado watchdog jinja2 markupsafe "  # jalon 6 : mainwindow + 33 plugins
           "ipykernel comm cloudpickle matplotlib_inline").split() + list(GREFFONS)  # jalon 8a : le noyau (relevé de sys.modules au démarrage)
DISTRIBUTIONS = ["qstylizer", "ipython_pygments_lexers", "typing_extensions", "six"]  # modules d'un seul fichier : --paquet prendrait site-packages
FORK = Path("/DATA/Python/FORKS/SmartPythonEditor")
# Contournement d'ESSAI (12/10/2026) : le fork a été généré le 11/10 à 16 h 55, avant quatre correctifs de
# SmartPythonEditor_generator (6791937 onglets ouverts sur leur volet, c2e516e volet qui a le focus : onglet actif en bleu,
# 264f60c congé de l'onglet actif, 8367c00 croix fines) que l'environnement installé porte déjà. Ces six fichiers sont
# pris dans l'installé, celui que l'utilisateur compare ; sans objet dès que le fork sera regénéré (comparer avec diff).
INSTALLE = Path("/DATA/Python/SmartPython/CachyOS/versions/3.12.14/envs/SmartPythonEditor-6.1.5/lib/python3.12/site-packages")
EN_RETARD = ("widgets/tabs.py", "utils/stylesheet.py", "utils/icon_manager.py", "plugins/editor/widgets/base.py",
             "plugins/editor/widgets/codeeditor/codeeditor.py", "plugins/ipythonconsole/utils/style.py")
JUPYTER_CLIENT = next(Path(__import__("jupyter_client").__file__).parent.parent.glob("jupyter_client-*.dist-info"))
EXCLURE = ["spyder/plugins/help/utils/js/", "qtpy6/web/js/pdfjs/",
           "spyder/locale/spyder.pot", "spyder/locale/fr/LC_MESSAGES/spyder.po",  # jalon 7 : config/base.py liste le
           *(f"spyder/locale/{l.name}/" for l in (FORK / "spyder/locale").iterdir() if l.name != "fr"),  # dossier ; le .mo
           # français est gardé, pour une interface en français
           "jedi/third_party/typeshed/stubs/"]  # stubs tiers (12 Mo) : jamais consultés ici, voir roues_jedi.py
EXCLURE_TESTS = "/tests/"
POLICES = [f"/usr/share/fonts/TTF/DejaVu{n}.ttf" for n in ("Sans", "Sans-Bold", "SansMono", "SansMono-Bold")]
ROUES = sorted(str(r) for m in ("jedi-*.whl", "parso-*.whl")  # jalon 4 : jedi dans la page (moteur A) et dans le
              for r in (ICI.parent / "roues").glob(m))  # Worker (B, travailleur.configurer) ; roues_jedi.py

MESURE = ('  await rendu();\n'
          '  print("durée totale : " + (performance.now() / 1000).toFixed(1) + " s ; tas wasm : "'
          ' + (py._module.HEAPU8.length / 1048576).toFixed(0) + " Mio");\n')


def _metadonnees():
    """Le METADATA de chaque distribution embarquée (12/10/2026) : sans lui, importlib.metadata ne trouve pas sa version,
    et superqt annonce « unknown », que le contrôle des dépendances de Spyder ne sait pas comparer (InvalidVersion, fenêtre
    « problème interne » au démarrage de SmartPythonEditor)."""
    from importlib import metadata
    distributions = metadata.packages_distributions()
    resultat = {}
    for paquet in [*PAQUETS, *DISTRIBUTIONS]:
        for nom in distributions.get(paquet, ()):
            d = metadata.distribution(nom)
            if paquet == "spyder" or d._path.name.endswith(".egg-info"):  # spyder : son egg-info du fork, déjà ajouté
                continue
            resultat[f"{d._path.name}/METADATA"] = d._path / "METADATA"
    return resultat


METADONNEES = _metadonnees()


def assembler(archive, fichiers=(), **k):
    """L'assembleur de qtpy6, avec les exclusions d'ici en plus (dont tout dossier tests/)."""
    k["exclure"] = [*k.get("exclure", ()), *EXCLURE]
    fichiers = {**dict(fichiers), **{f"spyder.egg-info/{n}": FORK / "spyder.egg-info" / n  # jalon 7 : les points d'entrée
                                     for n in ("PKG-INFO", "entry_points.txt")},  # spyder.plugins, que MainWindow.setup lit
                 **{f"{JUPYTER_CLIENT.name}/{n}": JUPYTER_CLIENT / n  # jalon 8a : le point d'entrée local-provisioner ;
                    for n in ("METADATA", "entry_points.txt")},  # sans lui, le repli de jupyter_client rend un module
                 **METADONNEES,
                 **{f"spyder/{n}": INSTALLE / "spyder" / n for n in EN_RETARD},  # avant le paquet : gagne
                 **{f"{g}.egg-info/{n}": GREFFONS_SOURCES / g / f"{g}.egg-info" / n  # leurs points d'entrée spyder.plugins
                    for g in GREFFONS for n in ("PKG-INFO", "entry_points.txt")},
                 **{f"config-reference/{n}": FORK / "smartos-support/config-reference" / n  # spe.py : la configuration
                    for n in ("spyder.ini", "transient.ini")}}  # que l'installation de SmartPythonEditor pose
    original = _assembler.zipfile.ZipFile

    class Zip(original):
        def write(self, chemin, nom=None, *a, **kk):
            if nom and (EXCLURE_TESTS in f"/{nom}" or nom in self.NameToInfo):  # EN_RETARD : la 1re écriture gagne
                return
            super().write(chemin, nom, *a, **kk)

    compile_original = _assembler.py_compile.compile

    def compile_(chemin, cfile, dfile, *a, **kk):  # un test écrit en syntaxe fausse exprès ne se compile pas
        if EXCLURE_TESTS not in f"/{dfile}":
            compile_original(chemin, cfile, dfile, *a, **kk)

    _assembler.zipfile.ZipFile, _assembler.py_compile.compile = Zip, compile_
    try:
        return _assembler.assembler(archive, fichiers, **k)
    finally:
        _assembler.zipfile.ZipFile, _assembler.py_compile.compile = original, compile_original


_construire.assembler = assembler
SITE.mkdir(exist_ok=True)
lien = SITE / "pyodide-qt"
if not lien.exists():
    lien.symlink_to(PYODIDE_QT)
taille = _construire.construire(ICI / "editeur.py", SITE, "./pyodide-qt/", PAQUETS, DISTRIBUTIONS, POLICES, ROUES,
                                "CodeEditor de Spyder dans qtpy6")
page = SITE / "index.html"
texte = page.read_text(encoding="utf-8")
assert texte.count("  await rendu();\n") == 1
texte = texte.replace("  await rendu();\n", MESURE)
assert texte.count('"/home/pyodide/app/editeur.py"') == 1
texte = texte.replace('"/home/pyodide/app/editeur.py"',  # un seul site pour tous les essais : index.html?script=jalon2.py
                      '"/home/pyodide/app/" + (new URLSearchParams(location.search).get("script") || "editeur.py")')
assert texte.count('window.etat = "en cours";') == 1
texte = texte.replace('window.etat = "en cours";',  # les roues, pour le Worker du jalon 4 (travailleur.configurer)
                      'window.etat = "en cours"; window.roues = ' + json.dumps([f"./{Path(r).name}" for r in ROUES]) + ";")
_import = 'import { preparer, lancer, print, rendu } from "./qtpy6web.js";'
assert texte.count(_import) == 1  # la page isolée (SharedArrayBuffer : mémoire partagée du greffon Pyxel), par sw.js
texte = texte.replace(_import, _import.replace("rendu }", "rendu, service_worker }")
                      + '\nservice_worker("./sw.js", { cache: "essai_spyder", isoler: true });')
page.write_text(texte, encoding="utf-8")
print(f"site/app.zip : {taille // 1024} Kio")
