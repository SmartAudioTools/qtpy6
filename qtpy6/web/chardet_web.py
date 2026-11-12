"""Doublure de ``chardet`` dans la page (D6, 12/11/2026) : ``detect`` répond utf-8 sans charger chardet quand les octets
se décodent en utf-8 — le cas des fichiers écrits par l'éditeur —, et ne charge le vrai chardet (63 Mio de tas, 51 ms :
faisabilité du 09/10, « chardet, ce que la lecture coûte ») que pour un fichier qui n'est pas en utf-8 (latin-1 venu de
Windows) : aucun fichier mal lu. Posée par ``qtpy6.web.lancer`` ; rien en natif."""

import importlib
import sys
import types

_UTF8 = {"encoding": "utf-8", "confidence": 0.99, "language": ""}


def _vrai():
    """Le chardet de l'archive, à la place de la doublure dans ``sys.modules`` (les ``import chardet`` suivants l'ont)."""
    if sys.modules.get("chardet") is _DOUBLURE:
        del sys.modules["chardet"]
    try:
        return importlib.import_module("chardet")
    except ImportError:
        sys.modules["chardet"] = _DOUBLURE
        raise


def detect(octets, *args, **kwargs):
    # Le vrai chardet pour : un non-octets (même erreur), le vide (il rend None), des NUL (utf-16/32 sans BOM, utf-8 valide
    # en apparence : encoding.py:154 les écarte déjà de « ascii »), et ce qui ne se décode pas en utf-8.
    if not isinstance(octets, (bytes, bytearray)) or not octets or b"\x00" in octets:
        return _vrai().detect(octets, *args, **kwargs)
    try:
        bytes(octets).decode("utf-8")
    except UnicodeDecodeError:
        return _vrai().detect(octets, *args, **kwargs)
    return dict(_UTF8, encoding="ascii", confidence=1.0) if bytes(octets).isascii() else dict(_UTF8)


def _getattr(nom):  # tout le reste de chardet (UniversalDetector, detect_all…) : le vrai
    return getattr(_vrai(), nom)


_DOUBLURE = types.ModuleType("chardet", __doc__)
_DOUBLURE.detect = detect
_DOUBLURE.__getattr__ = _getattr


def installer():
    """Pose la doublure si chardet n'est pas déjà importé ; idempotent."""
    sys.modules.setdefault("chardet", _DOUBLURE)
