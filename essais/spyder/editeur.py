"""Jalon 1 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) :
le CodeEditor de Spyder (coloration, numéros, pliage, indentation) dans une fenêtre qtpy6, le même script sur le bureau
et dans la page (qtpy6.web.construire). Mesure : durée de chaque étape (import de spyder, import du CodeEditor,
fenêtre montrée) et, dans la page, le tas WebAssembly (index.html). Rien d'autre que l'éditeur : ni plugin, ni LSP, ni
console. Le fork est pris tel quel ; les modules absents du navigateur (psutil…) reçoivent une doublure minimale."""

import os
import re
import sys
import time
import types

T0 = time.monotonic()
ICI = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("SPYDER_QT_SKIP_VERSION_CHECK", "1")   # le fork accepte PySide6 6.8-6.9 ; ici 6.10/6.11

# Sur le bureau : le fork et les roues pures dépaquetées ; dans la page, tout est dans app.zip (--paquet).
if sys.platform != "emscripten":
    sys.path[:0] = ["/DATA/Python/FORKS/SmartPythonEditor", "/DATA/Python/qtpy6/essais/roues/lib"]


def doublure(nom, **attrs):
    """Un module vide portant `attrs`, posé dans sys.modules si `nom` n'est pas importable."""
    try:
        __import__(nom)
    except ImportError:
        m = types.ModuleType(nom)
        m.__dict__.update(attrs)
        sys.modules[nom] = m
        print(f"doublure : {nom}")


class _Mem:
    total = 2 << 30
    available = 1 << 30
    percent = 50.0


class PickleShareDB(dict):
    """Ce que module_completion en fait : un dict persistant ; ici en mémoire."""
    def __init__(self, root):
        super().__init__()


doublure("psutil", cpu_percent=lambda *a, **k: 0.0, pid_exists=lambda pid: False, virtual_memory=lambda: _Mem(),
         Process=lambda *a, **k: None)
doublure("pickleshare", PickleShareDB=PickleShareDB)        # en attendant la roue pure
doublure("three_merge", merge=lambda a, b, c: a)             # idem
doublure("jellyfish", levenshtein_distance=lambda a, b: 0)   # extension C, sans roue Pyodide
doublure("bcrypt")                                           # extension C, remoteclient seulement
doublure("keyring", __path__=[], get_password=lambda *a: None, set_password=lambda *a: None)
doublure("keyring.errors", NoKeyringError=type("NoKeyringError", (Exception,), {}))
doublure("inflection",                                       # pour qstylizer ; les deux seules fonctions qu'il appelle
         underscore=lambda m: re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", m)).lower(),
         camelize=lambda m, maj=True: "".join(x.title() if i or maj else x for i, x in enumerate(m.split("_"))))


def etape(nom):
    print(f"{nom} : {time.monotonic() - T0:.2f} s")


if sys.platform == "emscripten":
    # Spyder importe qtpy, qui lit PySide6 directement : ce que qtpy6 double pour le navigateur (QThread, QProcess, verrous…
    # dans son propre espace de noms, QtCore de qtpy6) est posé ici sur PySide6.QtCore, pour les classes qui y manquent.
    import qtpy6.QtCore
    from PySide6 import QtCore
    poses = [n for n, v in vars(qtpy6.QtCore).items() if isinstance(v, type) and n.startswith("Q") and not hasattr(QtCore, n)]
    for n in poses:
        setattr(QtCore, n, getattr(qtpy6.QtCore, n))
    print(f"PySide6.QtCore complété par qtpy6 : {' '.join(poses)}")  # QtGui et QtWidgets : rien n'y manque (vérifié)


if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister (base.py, get_available_translations)
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
import spyder  # noqa: E402
etape("import spyder")
from qtpy.QtGui import QFont  # noqa: E402
from qtpy.QtWidgets import QMainWindow  # noqa: E402
etape("import qtpy")
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
etape("import CodeEditor")


def retirer_alias_signaux():
    """qtpy6 pose sur chaque classe PySide6 un alias snake_case de chaque méthode et signal (_binding._pyside6_class, une
    fois par classe, mémorisé dans _prepared). Une classe fille qui définit une MÉTHODE du nom d'un alias de SIGNAL et la
    connecte à ce signal fait planter PySide6 (segfault au premier setPlainText) : Spyder le fait dans
    plugins/editor/widgets/base.py avec cursor_position_changed (bissection des 98 alias de QPlainTextEdit, repro en dix
    lignes). Premier contournement (09/10/2026, 20 h) : retirer tous les alias de signaux - reconnaissables au même objet
    Signal sous deux noms - après les imports de Spyder (toutes ses classes de base existent alors, mode paresseux de la
    page compris) et avant le premier widget ; les alias de méthodes restent, une redéfinition les masque sans planter.
    Depuis 22 h le fork est corrigé (trois slots renommés on_…, relevé dans la note) et ce retrait n'est plus appelé que
    sur --retirer-alias, pour mesurer l'un sans l'autre."""
    import qtpy6._binding
    from qtpy.QtCore import Signal
    retires = 0
    for cls in list(qtpy6._binding._prepared):
        membres = vars(cls)
        camel = {id(v) for n, v in membres.items() if isinstance(v, Signal) and "_" not in n}
        for n in [n for n, v in membres.items() if isinstance(v, Signal) and "_" in n and id(v) in camel]:
            delattr(cls, n)
            retires += 1
    etape(f"{retires} alias de signaux retirés")


if "--retirer-alias" in sys.argv:
    retirer_alias_signaux()

import qtpy6.web  # noqa: E402

# La QApplication de qtpy6 : dans la page, elle charge les polices de app.zip (Qt n'en a aucune) ; en natif, rien de plus.
app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))
fenetre = QMainWindow()
editeur = CodeEditor(fenetre)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename=__file__)
editeur.set_text_from_file(os.path.abspath(__file__))
fenetre.setCentralWidget(editeur)
fenetre.setWindowTitle("CodeEditor de Spyder dans qtpy6")
etape("CodeEditor créé")
if sys.platform == "emscripten":
    fenetre.showFullScreen()
else:
    fenetre.resize(900, 700)
    fenetre.show()
etape("fenêtre montrée")
if "--capture" in sys.argv:  # bureau : une image, pour comparer au rendu de la page
    from qtpy.QtCore import QTimer
    def capturer():
        fenetre.grab().save(os.path.join(ICI, "capture_bureau.png"))
        etape("capture faite")
        app.quit()
    QTimer.singleShot(500, capturer)
sys.exit(app.exec())
