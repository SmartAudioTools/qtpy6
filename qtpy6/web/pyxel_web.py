"""Pyxel dans le Web Worker d'un processus (le noyau de la console de SmartPythonEditor) : la doublure qui laisse le code
écrit pour le bureau, et le crochet du greffon spyder_pyxel, tourner tels quels. ``installer()`` (appelé par le préambule)
pose un chercheur d'import : au premier ``import pyxel`` (la roue wasm officielle, chargée à ce moment-là), le module est
complété AVANT que quiconque capture ses fonctions (le greffon capture ``pyxel.flip`` et ``pyxel.init`` à ``install()``).

Ce que la roue ne sait pas faire seule dans un Worker, et ce qui est doublé (mesures : notes/2026-10-12 - Pyxel dans la
page.md, essais 1 à 21) :
- ``init`` : SDL attend du DOM (canvas avec style, ``screen``, ``navigator.getGamepads``, ``document``) et la page de
  pyxel.js (``_readVirtualGamepadBitmask``) : objets factices posés ici ; le canvas est un ``OffscreenCanvas`` (WebGL y
  existe). ``SDL_VIDEODRIVER=offscreen``, que le greffon pose pour le bureau, n'a pas de sens ici : retiré.
- ``flip`` : interdit en web par Pyxel (il faudrait rendre la main au navigateur). Au premier appel, le ``run`` d'origine
  est lancé une fois avec des rappels vides (il pose la boucle principale d'emscripten puis « déroule » la pile, d'où le
  trampoline JS synchrone et ``_skip_unwind_fatal_error``), et cette boucle est aussitôt mise en pause. Chaque ``flip``
  cadence ensuite à ``fps`` par ``time.sleep`` (suspendu par JSPI : la page et le noyau restent servis) puis déroule UNE
  image en appelant la fonction d'itération d'emscripten : rendu, ``frame_count``, ``btnp`` avancent par Pyxel lui-même.
- ``run`` : la boucle du bureau (update, draw, flip) en Python, sur ce ``flip``.
Les entrées posées depuis Python entre deux ``flip`` (``set_btn``, comme le pont du greffon) sont vues normalement
(essai 21). Une touche posée par un rappel JS PENDANT le ``sleep`` ne l'est pas (essai 20 : le rappel ne peut pas entrer
dans Python pendant que la cellule est suspendue)."""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable

_DOM = """
self.screen ??= {width: 1280, height: 720, availWidth: 1280, availHeight: 720, colorDepth: 24};
self.navigator.getGamepads ??= () => [];
self._readVirtualGamepadBitmask ??= () => 0;
const _n = () => {};
self.document ??= {addEventListener: _n, removeEventListener: _n, querySelector: () => null, getElementById: () => null,
  title: '', body: {style: {}, addEventListener: _n, removeEventListener: _n}, documentElement: {style: {}},
  fullscreenElement: null, pointerLockElement: null, hidden: false, visibilityState: 'visible', hasFocus: () => true};
"""


def _canvas(largeur: int, hauteur: int) -> None:
    """Le canvas de SDL : un OffscreenCanvas, avec ce que SDL lit d'un élément du DOM."""
    import js  # noqa: PLC0415
    import pyodide_js  # noqa: PLC0415
    from pyodide.code import run_js  # noqa: PLC0415

    run_js(_DOM)
    canvas = js.OffscreenCanvas.new(largeur, hauteur)
    canvas.style = js.Object.new()
    boite = js.JSON.parse(f'{{"left":0,"top":0,"width":{largeur},"height":{hauteur},"right":{largeur},"bottom":{hauteur}}}')
    canvas.getBoundingClientRect = lambda: boite
    pyodide_js.canvas.setCanvas2D(canvas)


def completer(pyxel: Any) -> None:
    """Remplace ``init``, ``flip`` et ``run`` du module ``pyxel`` importé."""
    import js  # noqa: PLC0415
    import pyodide_js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    init, run = pyxel.init, pyxel.run
    trampoline = js.Function.new("f", "f()")
    etat: dict[str, Any] = {"fps": 30, "boucle": None, "t": 0.0}

    def init_web(width: int, height: int, *args: Any, **kwargs: Any) -> None:
        if os.environ.get("SDL_VIDEODRIVER") == "offscreen":
            del os.environ["SDL_VIDEODRIVER"]
        _canvas(width, height)
        etat["fps"] = kwargs.get("fps") or 30
        etat["boucle"] = None
        init(width, height, *args, **kwargs)

    def flip_web() -> None:
        boucle = etat["boucle"]
        if boucle is None:
            api = pyodide_js._api
            api._skip_unwind_fatal_error = True  # emscripten_set_main_loop déroule la pile par une exception
            try:
                trampoline(create_once_callable(lambda: run(lambda: None, lambda: None)))
            finally:
                api._skip_unwind_fatal_error = False
            boucle = etat["boucle"] = pyodide_js._module.MainLoop
            boucle.pause()
            etat["t"] = time.monotonic()
        etat["t"] += 1 / etat["fps"]
        attente = etat["t"] - time.monotonic()
        if attente > 0:
            time.sleep(attente)
        else:  # en retard (image lourde) : on repart d'ici plutôt que d'enchaîner les images sans attendre
            etat["t"] = time.monotonic()
        boucle.func()

    def run_web(update: Callable[[], None], draw: Callable[[], None]) -> None:
        while True:
            update()
            draw()
            pyxel.flip()

    pyxel.init, pyxel.flip, pyxel.run = init_web, flip_web, run_web


class _Chercheur:
    """Au premier ``import pyxel`` : le module trouvé par les autres chercheurs (dont celui qui charge la roue), complété
    juste après son exécution."""

    def find_spec(self, nom: str, chemin: Any = None, cible: Any = None) -> Any:
        if nom != "pyxel":
            return None
        sys.meta_path.remove(self)
        for chercheur in sys.meta_path:
            spec = getattr(chercheur, "find_spec", lambda *a: None)(nom, chemin, cible)
            if spec is not None:
                break
        else:
            return None
        executer = spec.loader.exec_module

        def exec_module(module: Any) -> None:
            executer(module)
            completer(module)

        spec.loader.exec_module = exec_module
        return spec


def installer() -> None:
    sys.meta_path.insert(0, _Chercheur())
