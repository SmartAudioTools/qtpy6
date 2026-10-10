"""Construit ``site/`` (index.html, app.zip, pyodide-qt en lien) pour les essais du dossier (``?script=`` choisit lequel,
editeur.py sans), puis le mesure avec la sonde :

    $P construire_site.py            # construit
    $P -m qtpy6.web.sonde site/index.html capture_web.png --racine site --delai 600
    $P -m qtpy6.web.sonde 'site/index.html?script=jalon2.py' capture_jalon2.png --racine site --delai 600 --pilote
    $P -m qtpy6.web.sonde 'site/index.html?script=jalon4.py' capture_jalon4.png --racine site --delai 600 --pilote

Même mécanisme que ``python -m qtpy6.web.construire``, avec en plus : le fork Spyder et les roues pures sur sys.path (d'où
``--paquet spyder`` prend le fork), les paquets purs que l'import de CodeEditor tire (relevé par audit de sys.modules sur le
bureau), les dossiers de Spyder inutiles ici laissés dehors (MathJax de l'aide : 29 Mo, traductions : 6 Mo, tests : 4 Mo),
les polices DejaVu, et deux mesures imprimées dans le journal de la page : durée totale et tas WebAssembly."""

import json
import os
import sys
from pathlib import Path

sys.path[:0] = ["/DATA/Python/FORKS/SmartPythonEditor", "/DATA/Python/qtpy6/essais/roues/lib"]
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("SPYDER_QT_SKIP_VERSION_CHECK", "1")

from qtpy6.web import assembler as _assembler, construire as _construire  # noqa: E402

ICI = Path(__file__).resolve().parent
SITE = ICI / "site"
PYODIDE_QT = Path("/DATA/Python/qtpy6/exemple/pyodide-qt")
PAQUETS = ("spyder qtpy IPython asttokens chardet colorama decorator diff_match_patch executing intervaltree jedi packaging parso "
           "prompt_toolkit pure_eval pygments qdarkstyle qtawesome qtconsole sortedcontainers spyder_kernels textdistance "
           "stack_data superqt tinycss2 traitlets wcwidth webencodings "
           "dateutil jupyter_client jupyter_core msgpack platformdirs pyuca tornado watchdog").split()  # jalon 6 : mainwindow + 33 plugins
DISTRIBUTIONS = ["qstylizer", "ipython_pygments_lexers", "typing_extensions", "six"]  # modules d'un seul fichier : --paquet prendrait site-packages
EXCLURE = ["spyder/plugins/help/utils/js/", "spyder/locale/", "qtpy6/web/js/pdfjs/",
           "jedi/third_party/typeshed/stubs/"]  # stubs tiers (12 Mo) : jamais consultés ici, voir roues_jedi.py
EXCLURE_TESTS = "/tests/"
POLICES = [f"/usr/share/fonts/TTF/DejaVu{n}.ttf" for n in ("Sans", "Sans-Bold", "SansMono", "SansMono-Bold")]
ROUES = sorted(str(r) for m in ("jedi-*.whl", "parso-*.whl")  # jalon 4 : jedi dans la page (moteur A) et dans le
              for r in (ICI.parent / "roues").glob(m))  # Worker (B, travailleur.configurer) ; roues_jedi.py

MESURE = ('  await rendu();\n'
          '  print("durée totale : " + (performance.now() / 1000).toFixed(1) + " s ; tas wasm : "'
          ' + (py._module.HEAPU8.length / 1048576).toFixed(0) + " Mio");\n')


def assembler(archive, fichiers=(), **k):
    """L'assembleur de qtpy6, avec les exclusions d'ici en plus (dont tout dossier tests/)."""
    k["exclure"] = [*k.get("exclure", ()), *EXCLURE]
    original = _assembler.zipfile.ZipFile

    class Zip(original):
        def write(self, chemin, nom=None, *a, **kk):
            if nom and EXCLURE_TESTS in f"/{nom}":
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
page.write_text(texte, encoding="utf-8")
print(f"site/app.zip : {taille // 1024} Kio")
