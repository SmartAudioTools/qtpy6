"""``qtpy6.doublures`` : le navigateur doublé le temps d'un bloc, puis ``sys.modules`` rendu tel quel."""

import sys

import pytest

from qtpy6.doublures import MODULES, navigateur_double


def test_modules_rendus_tels_quels():
    """Un nom absent le redevient, un nom présent retrouve son module, même quand le bloc lève."""
    sentinelle = object()
    sys.modules.pop("js", None)
    sys.modules["pyodide"] = sentinelle
    avant = {nom: sys.modules.get(nom, "absent") for nom in MODULES}
    try:
        with pytest.raises(RuntimeError), navigateur_double(titre="essai") as js:
            from js import document, titre
            from pyodide.ffi import create_proxy, jsnull
            assert sys.modules["js"] is js and titre == "essai"
            assert document.addEventListener("visibilitychange", create_proxy(print)) is None
            assert create_proxy(print) is print and jsnull is not None and not jsnull
            raise RuntimeError
        assert {nom: sys.modules.get(nom, "absent") for nom in MODULES} == avant
    finally:
        sys.modules.pop("pyodide")
