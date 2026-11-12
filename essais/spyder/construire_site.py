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

GREFFONS = ("spyder_stop_toolbar", "spyder_interpreter_toolbar", "spyder_pyxel",  # spe.py : les greffons de SmartPythonEditor
             "spyder_code_analysis", "spyder_smartteacher", "spyder_collab", "spyder_python_tutor")  # en pur Python (W551) ;
# window_controls dessine des boutons de fenêtre, sans objet dans une page, viztracer et line_profiler ont des extensions C,
# claude, konsole et tortoisehg sont des greffons du poste ; spyder_pyxel : essai 26
GREFFONS_SOURCES = Path("/DATA/Python/FORKS/SmartPythonEditorPlugins")
sys.path[:0] = ["/DATA/Python/FORKS/SmartPythonEditor", "/DATA/Python/qtpy6/essais/roues/lib",
                *(str(GREFFONS_SOURCES / g) for g in GREFFONS)]
# pylint et ses dépendances (greffon spyder_code_analysis, par le volet pylint de Spyder) : de l'environnement installé de
# SmartPythonEditor, en dernier sur sys.path (le Python de construction ne les a pas)
INSTALLE = Path("/DATA/Python/SmartPython/CachyOS/versions/3.12.14/envs/SmartPythonEditor-6.1.5/lib/python3.12/site-packages")
sys.path.append(str(INSTALLE))
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("SPYDER_QT_SKIP_VERSION_CHECK", "1")

from qtpy6.web import assembler as _assembler, construire as _construire  # noqa: E402

ICI = Path(__file__).resolve().parent
import argparse  # noqa: E402
# --sortie <dossier> : un site à part, pour un worker qui construit sans toucher site/ que les sondes des autres lisent
_options = argparse.ArgumentParser()
_options.add_argument("--sortie", default=str(ICI / "site"))
SITE = Path(_options.parse_args().sortie).resolve()
PYODIDE_QT = Path("/DATA/Python/qtpy6/exemple/pyodide-qt")
PAQUETS = ("spyder qtpy IPython asttokens chardet colorama decorator diff_match_patch executing intervaltree jedi packaging parso "
           "prompt_toolkit pure_eval pygments qdarkstyle qtawesome qtconsole sortedcontainers spyder_kernels textdistance "
           "stack_data superqt tinycss2 traitlets wcwidth webencodings "
           "dateutil jupyter_client jupyter_core msgpack platformdirs pyuca tornado watchdog jinja2 markupsafe "  # jalon 6 : mainwindow + 33 plugins
           "ipykernel comm cloudpickle matplotlib_inline "  # jalon 8a : le noyau (relevé de sys.modules au démarrage)
           "pylint astroid isort tomlkit dill "  # W551 : pylint, pour spyder_code_analysis
           "pexpect ptyprocess importlib_metadata zipp "  # jalon 8d : le transport LSP (fdpexpect), W548
           "pylsp pylsp_jsonrpc pluggy docstring_to_markdown pyflakes").split() + list(GREFFONS)  # jalon 8d : serveur pylsp, W548
DISTRIBUTIONS = ["qstylizer", "ipython_pygments_lexers", "typing_extensions", "six", "mccabe", "pycodestyle"]  # modules d'un seul fichier : --paquet prendrait site-packages
FORK = Path("/DATA/Python/FORKS/SmartPythonEditor")
PYLSP = next(INSTALLE.glob("python_lsp_server-*.dist-info"))  # jalon 8d (W548) : ses points d'entrée « pylsp », sans
# lesquels pylsp ne charge aucun greffon (pylsp/config/config.py:90) : diagnostic et complétion vides
JUPYTER_CLIENT = next(Path(__import__("jupyter_client").__file__).parent.parent.glob("jupyter_client-*.dist-info"))
EXCLURE = ["spyder/plugins/help/utils/js/", "qtpy6/web/js/pdfjs/",
           "spyder/locale/spyder.pot", "spyder/locale/fr/LC_MESSAGES/spyder.po",  # jalon 7 : config/base.py liste le
           *(f"spyder/locale/{l.name}/" for l in (FORK / "spyder/locale").iterdir() if l.name != "fr"),  # dossier ; le .mo
           # français est gardé, pour une interface en français
           "jedi/third_party/typeshed/stubs/",  # stubs tiers (12 Mo) : jamais consultés ici, voir roues_jedi.py
           # tout site construit dans ce dossier (le commun, ceux de --sortie, chrome/ : 43 Mo écrits pendant l'assemblage
           # le 12/11/2026) : construire() n'exclut que le sien
           *(f"{d.name}/" for d in ICI.iterdir() if d.is_dir() and ((d / "index.html").exists() or d.name == "chrome"))]
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


def _greffons():
    """Les métadonnées des greffons (PKG-INFO, entry_points.txt : leurs points d'entrée spyder.plugins), écrites depuis
    leur pyproject.toml (W551) : spyder_smartteacher n'a pas d'egg-info dans le dépôt, et celui des autres est une
    construction locale qui peut retarder sur le pyproject."""
    import tempfile
    import tomllib
    dossier = Path(tempfile.mkdtemp(prefix="greffons-"))
    resultat = {}
    for g in GREFFONS:
        projet = tomllib.loads((GREFFONS_SOURCES / g / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        textes = {"PKG-INFO": f"Metadata-Version: 2.1\nName: {projet['name']}\nVersion: {projet['version']}\n",
                  "entry_points.txt": "".join(f"[{groupe}]\n" + "".join(f"{n} = {v}\n" for n, v in points.items()) + "\n"
                                              for groupe, points in projet["entry-points"].items())}
        for nom, texte in textes.items():
            (dossier / f"{g}.{nom}").write_text(texte, encoding="utf-8")
            resultat[f"{g}.egg-info/{nom}"] = dossier / f"{g}.{nom}"
    return resultat


def assembler(archive, fichiers=(), **k):
    """L'assembleur de qtpy6, avec les exclusions d'ici en plus (dont tout dossier tests/)."""
    k["exclure"] = [*k.get("exclure", ()), *EXCLURE]
    fichiers = {**dict(fichiers), **{f"spyder.egg-info/{n}": FORK / "spyder.egg-info" / n  # jalon 7 : les points d'entrée
                                     for n in ("PKG-INFO", "entry_points.txt")},  # spyder.plugins, que MainWindow.setup lit
                 **{f"{JUPYTER_CLIENT.name}/{n}": JUPYTER_CLIENT / n  # jalon 8a : le point d'entrée local-provisioner ;
                    for n in ("METADATA", "entry_points.txt")},  # sans lui, le repli de jupyter_client rend un module
                 **{f"{PYLSP.name}/{n}": PYLSP / n for n in ("METADATA", "entry_points.txt")},
                 **METADONNEES,
                 **_greffons(),
                 **{f"config-reference/{n}": FORK / "smartos-support/config-reference" / n  # spe.py : la configuration
                    for n in ("spyder.ini", "transient.ini")}}  # que l'installation de SmartPythonEditor pose
    original = _assembler.zipfile.ZipFile

    class Zip(original):
        def write(self, chemin, nom=None, *a, **kk):
            if nom and (EXCLURE_TESTS in f"/{nom}" or nom in self.NameToInfo  # un doublon : la 1re écriture gagne
                        or ("/" not in nom and not nom.endswith(".py")) or nom.endswith(".log")):  # du dossier des essais,
                return  # pas les captures de sa racine ni aucun journal, que les sondes des autres workers réécrivent
            super().write(chemin, nom, *a, **kk)

    compile_original = _assembler.py_compile.compile

    def compile_(chemin, cfile, dfile, *a, **kk):  # un test écrit en syntaxe fausse exprès ne se compile pas
        if EXCLURE_TESTS not in f"/{dfile}":
            compile_original(chemin, cfile, dfile, *a, **kk)

    _assembler.zipfile.ZipFile, _assembler.py_compile.compile = Zip, compile_
    provisoire = Path(archive).with_name(Path(archive).name + f".{os.getpid()}.provisoire")  # écrit à côté puis renommé : une sonde ne
    try:  # lit jamais une archive à moitié écrite (12/11/2026 : 6 719 membres sur 7 088 illisibles, « Bad magic number »)
        taille = _assembler.assembler(provisoire, fichiers, **k)
        os.replace(provisoire, archive)
        return taille
    except BaseException:
        provisoire.unlink(missing_ok=True)
        raise
    finally:
        _assembler.zipfile.ZipFile, _assembler.py_compile.compile = original, compile_original


_construire.assembler = assembler
SITE.mkdir(parents=True, exist_ok=True)
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
