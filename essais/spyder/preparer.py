"""Préambule commun des essais Spyder (editeur.py, jalon2.py) : chemins du fork et des roues pures sur le bureau,
doublures des modules absents du navigateur, et `etape` (chronomètre
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


class PickleShareDB(dict):
    """Ce que module_completion en fait : un dict persistant ; ici en mémoire."""
    def __init__(self, root):
        super().__init__()


doublure("pickleshare", PickleShareDB=PickleShareDB)        # en attendant la roue pure
doublure("three_merge", merge=lambda a, b, c: a)             # idem
# jellyfish et bcrypt : plus de doublure (W559, 12/11/2026) : déclarés par setup.py du fork, importés par aucun module.
doublure("keyring", __path__=[], get_password=lambda *a: None, set_password=lambda *a: None)
doublure("keyring.errors", NoKeyringError=type("NoKeyringError", (Exception,), {}))
# zmq et psutil (extensions C, sans roue Pyodide) : plus de doublure ici depuis le jalon 8a (11/10/2026), celles de qtpy6
# (qtpy6/web/zmq_web.py, psutil_web.py) sont posées par l'import de qtpy6.QtCore dans la page, plus bas.
# pylint : absent de SmartPython comme de la page ; le plugin Pylint lit sa version dès l'import (main_widget.py,
# importlib.metadata.version), et find_internal_plugins importe tous les plugins (jalon 7) : des métadonnées seules.
try:
    import importlib.metadata
    importlib.metadata.version("pylint")
except importlib.metadata.PackageNotFoundError:
    import tempfile
    _meta = os.path.join(tempfile.mkdtemp(prefix="doublures-"), "pylint-3.3.0.dist-info")
    os.makedirs(_meta)
    with open(os.path.join(_meta, "METADATA"), "w") as _f:
        _f.write("Metadata-Version: 2.1\nName: pylint\nVersion: 3.3.0\n")
    sys.path.append(os.path.dirname(_meta))
    print("doublure : métadonnées de pylint")
# PySide6.QtPrintSupport : plus de doublure depuis le 10/10/2026, le module est chargé à la demande (wasm/pyodide-qt.mjs).
doublure("inflection",                                       # pour qstylizer ; les deux seules fonctions qu'il appelle
         underscore=lambda m: re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", m)).lower(),
         camelize=lambda m, maj=True: "".join(x.title() if i or maj else x for i, x in enumerate(m.split("_"))))


def etape(nom):
    print(f"{nom} : {time.monotonic() - T0:.2f} s")


# Spyder importe qtpy : dans la page, le lanceur de qtpy6 le sert lui-même (qtpy6/_qtpy.py, 12/11/2026), doublures
# comprises (QProcess, fils, QWebEngineView) ; plus rien à poser ici sur PySide6.
