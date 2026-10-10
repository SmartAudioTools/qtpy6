"""Préambule commun des essais Spyder (editeur.py, jalon2.py) : chemins du fork et des roues pures sur le bureau,
doublures des modules absents du navigateur, PySide6.QtCore complété par qtpy6 dans la page, et `etape` (chronomètre
depuis l'import). Importé en premier, avant spyder."""

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
# zmq (extension C, sans roue Pyodide) : ce que jupyter_client, spyder_kernels et Spyder en lisent à l'IMPORT (classes de base,
# annotations, constantes) ; aucun socket n'est jamais ouvert ici (jalon 6 : import nu). Le transport réel est l'obstacle 1 de la note.
_Classe = type("Classe", (), {"shadow": classmethod(lambda cls, *a: cls())})
doublure("zmq", __path__=[], Context=_Classe, Socket=_Classe, Message=_Classe, MessageTracker=_Classe, Poller=_Classe,
         ZMQError=type("ZMQError", (Exception,), {}), curve_keypair=lambda: (b"", b""),
         **{n: i for i, n in enumerate("DEALER REQ SUB SUBSCRIBE POLLIN NOBLOCK IDENTITY EAGAIN ROUTER PUB".split())})
for _nom, _attrs in (("zmq.asyncio", dict(Context=_Classe, Socket=_Classe, Poller=_Classe)),
                     ("zmq.eventloop", dict(__path__=[])), ("zmq.eventloop.zmqstream", dict(ZMQStream=_Classe)),
                     ("zmq.sugar", dict(__path__=[])), ("zmq.sugar.socket", dict(Socket=_Classe)),
                     ("zmq.utils", dict(__path__=[])), ("zmq.utils.garbage", dict(gc=None))):
    if "zmq" in sys.modules and not getattr(sys.modules["zmq"], "__file__", None):  # la doublure, pas le vrai
        doublure(_nom, **_attrs)
        setattr(sys.modules[_nom.rpartition(".")[0]], _nom.rpartition(".")[2], sys.modules[_nom])
# QtPrintSupport (non lié dans Pyodide-Qt, obstacle 3 de la note) : les quatre classes que Spyder importe, et ce qu'il en lit à
# l'import (printer.py : `mode=QPrinter.PrinterMode.ScreenResolution` en valeur par défaut). Imprimer n'a pas de sens dans la page.
_QPrinter = type("QPrinter", (), {
    "PrinterMode": type("PrinterMode", (), {"ScreenResolution": 0, "PrinterResolution": 1, "HighResolution": 2}),
    "ColorMode": type("ColorMode", (), {"GrayScale": 0, "Color": 1}),
    "PageOrder": type("PageOrder", (), {"FirstPageFirst": 0, "LastPageFirst": 1}),
    "HighResolution": 2, "__init__": lambda self, *a, **k: None})
doublure("PySide6.QtPrintSupport", QPrinter=_QPrinter, QPrintDialog=type("QPrintDialog", (), {"Accepted": 1}),
         QPrintPreviewDialog=type("QPrintPreviewDialog", (), {}), QPageSetupDialog=type("QPageSetupDialog", (), {}),  # qtpy l'aliasse
         QAbstractPrintDialog=type("QAbstractPrintDialog", (), {
             "PrintDialogOption": type("PrintDialogOption", (), {"PrintSelection": 2})}))
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
