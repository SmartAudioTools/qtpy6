"""Le navigateur doublé pour un test natif : importer hors de Pyodide un module écrit pour la page.

Un module de l'application qui ne tourne que dans la page (le pont entre la page et l'application, par exemple) importe
``js`` et ``pyodide.ffi`` au niveau du module : hors du navigateur, son import échoue. ``navigateur_double()`` pose ces
modules dans ``sys.modules`` le temps d'un bloc ``with`` et rend ensuite ``sys.modules`` tel qu'il était pour ces noms :

    from qtpy6.doublures import navigateur_double
    with navigateur_double():
        import pont
        ...

C'est qtpy6 qui nomme les modules du navigateur, pour que le test de l'application ne les cite pas (règle de
``CLAUDE.md`` : le code de l'application ne sait pas où il tourne). Ce module est hors de ``qtpy6.web`` pour la même
raison : un test de l'application n'a pas à importer le paquet du navigateur.

Les doublures sont inertes : ``document`` et ``window`` acceptent ``addEventListener`` sans rien brancher,
``create_proxy`` rend la fonction telle quelle, ``jsnull`` est un objet distinct de None (le ``null`` de JS). Ce que le
test veut de plus sur ``js`` se donne en argument : ``navigateur_double(localStorage=...)``. Un module importé dans le
bloc garde ses références aux doublures : au test de le retirer de ``sys.modules`` s'il ne doit pas servir après."""

from __future__ import annotations

import contextlib
import sys
import types
from collections.abc import Iterator
from typing import Any

MODULES = ("js", "pyodide", "pyodide.ffi")  # les noms posés, puis rendus à la sortie
_ABSENT = object()  # un nom absent de sys.modules (None y est une valeur : l'import refusé)


def _rien(*args: Any, **kwargs: Any) -> None:
    return None


def _cible() -> types.SimpleNamespace:
    """Un ``document`` ou une ``window`` qui écoute sans rien entendre."""
    return types.SimpleNamespace(addEventListener=_rien, removeEventListener=_rien)


@contextlib.contextmanager
def navigateur_double(**js: Any) -> Iterator[types.ModuleType]:
    """Pose ``js``, ``pyodide`` et ``pyodide.ffi`` doublés dans ``sys.modules`` et rend le ``js`` doublé ; à la sortie,
    ces trois noms retrouvent ce qu'ils désignaient avant (ou disparaissent s'ils n'existaient pas), même sur exception.
    ``js`` porte ``document`` et ``window``, remplacés ou complétés par les arguments nommés."""
    module_js = types.ModuleType("js")
    module_js.document, module_js.window = _cible(), _cible()
    for nom, valeur in js.items():
        setattr(module_js, nom, valeur)
    ffi = types.ModuleType("pyodide.ffi")
    ffi.create_proxy = ffi.create_once_callable = ffi.to_js = lambda objet, *args, **kwargs: objet
    ffi.jsnull = type("JsNull", (), {"__repr__": lambda self: "jsnull", "__bool__": lambda self: False})()
    pyodide = types.ModuleType("pyodide")
    pyodide.ffi = ffi
    avant = {nom: sys.modules.get(nom, _ABSENT) for nom in MODULES}
    sys.modules.update({"js": module_js, "pyodide": pyodide, "pyodide.ffi": ffi})
    try:
        yield module_js
    finally:
        for nom, module in avant.items():
            if module is _ABSENT:
                sys.modules.pop(nom, None)
            else:
                sys.modules[nom] = module
