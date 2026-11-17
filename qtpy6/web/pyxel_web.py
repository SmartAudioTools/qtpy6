"""Pyxel dans le Web Worker d'un processus (le noyau de la console de SmartPythonEditor) : la doublure qui laisse le code
écrit pour le bureau, et le crochet du greffon spyder_pyxel, tourner tels quels. ``installer()`` (appelé par le préambule)
pose un chercheur d'import : au premier ``import pyxel`` (la roue wasm officielle, chargée à ce moment-là), l'extension
``pyxel.pyxel_binding`` est complétée dès son exécution, donc AVANT que ``pyxel/__init__.py`` en recopie les noms et que
quiconque les capture : le greffon pose ses crochets depuis un ``__import__`` enveloppé, dès que ``pyxel`` (encore
partiellement initialisé) a ``init``, ``run`` et ``flip``.

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

import math
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


_ENVELOPPES = ("qtpy6.", "spyder_pyxel.")


def _cwd_du_jeu(avant: str) -> None:
    """Le répertoire courant que Pyxel aurait choisi sans enveloppe. ``init`` exécute
    ``os.chdir(os.path.dirname(inspect.stack()[1].filename) or ".")`` (lu dans ``pyxel_binding``) : le dossier de
    l'APPELANT, censé être le jeu, d'où ses ``load("x.pyxres")`` relatifs. Ici l'appelant est ``init_web`` (et le
    crochet du greffon) : le cwd partait dans ``qtpy6/web`` et le ``.pyxres`` du jeu n'était plus trouvé (item 8 du
    TODO Portage). On remonte donc au premier cadre hors des enveloppes, et on fait le même ``chdir`` que Pyxel, un
    dossier relatif résolu depuis ``avant``, le cwd d'avant ``init`` (Pyxel l'aurait résolu de là)."""
    cadre = sys._getframe(1)
    while cadre is not None and str(cadre.f_globals.get("__name__", "")).startswith(_ENVELOPPES):
        cadre = cadre.f_back
    if cadre is not None:
        dossier = os.path.dirname(cadre.f_code.co_filename)
        if dossier:
            dossier = os.path.join(avant, dossier)  # sans effet si absolu
        if dossier and os.path.isdir(dossier):
            os.chdir(dossier)


def _compteur_de_balayages() -> Any:
    """Le segment ``memoire_partagee.BALAYAGES`` de la page : ``lire(0)`` balayages comptés, ``lire(1)`` période en µs
    (``Atomics``), ``lire(2)`` instant absolu du dernier balayage compté, en s ; ``None`` sans lui."""
    import js  # noqa: PLC0415
    from qtpy6.web.memoire_partagee import BALAYAGES  # noqa: PLC0415
    segments = getattr(js.self, "qtpy6_memoires", None)
    if segments is None or not segments.has(BALAYAGES):
        return None
    sab = segments.get(BALAYAGES)
    a, instant = js.Int32Array.new(sab, 0, 2), js.Float64Array.new(sab, 8, 1)
    return lambda i: js.Atomics.load(a, i) if i < 2 else instant[0]


def _horloge() -> float:
    """Le temps absolu du navigateur, en s : le même dans la page et dans le Worker (``timeOrigin`` + ``now``)."""
    import js  # noqa: PLC0415
    return (js.performance.timeOrigin + js.performance.now()) / 1000


def attendre_balayages(lire: Callable[[int], float], etat: dict[str, Any], dormir: Callable[[float], None] | None = None,
                       horloge: Callable[[], float] | None = None) -> bool:
    """Synchro verticale : l'image Pyxel suivante part sur un balayage de l'écran, pas à l'heure de ``time.sleep``.
    W572 : le noyau et la page comptaient chacun leur temps ; à 60 i/s sur un écran de 60 Hz, une image sur trois
    n'était jamais montrée. W573 : caler le noyau sur le COMPTEUR des rappels ``requestAnimationFrame`` le faisait
    tourner à la vitesse de la page, qui en saute quand son fil est chargé (écran réel : 35 i/s au lieu de 60, le jeu au
    ralenti) ; il se cale donc sur la GRILLE de l'écran, l'instant du dernier balayage et la période, qui ne dépendent
    pas des sauts. Chaque image dure ``round(hz / fps)`` balayages ; en retard de plus d'une demi-période, on repart du
    balayage suivant. Un seul sommeil, sans scrutation (un sommeil de 1 ms en dure 2,6 dans le Worker, mesure W573).
    Faux si la page ne balaie plus depuis 100 ms (onglet caché, fil figé) : l'appelant cadence alors au temps."""
    dormir = dormir or time.sleep  # lu à l'appel : la doublure du préambule (réconcilie la mémoire partagée) vient après l'import
    horloge = horloge or _horloge
    compte = lire(0)
    if etat.get("fige") == compte:  # la page ne comptait déjà plus : ne pas réattendre à chaque image
        return False
    etat.pop("fige", None)
    periode = (lire(1) or 16_667) / 1e6
    n = max(1, round(1 / etat["fps"] / periode))
    dernier, maintenant = lire(2), horloge()
    if maintenant - dernier > 0.1:
        etat.pop("cible", None)
        etat["fige"] = compte
        return False
    cible = etat.get("cible")
    rang = round(((maintenant if cible is None else cible + n * periode) - dernier) / periode)
    if dernier + rang * periode < maintenant - periode / 2:  # image lourde : on repart du balayage suivant
        rang = math.ceil((maintenant - dernier) / periode)
    cible = etat["cible"] = dernier + rang * periode
    if cible > maintenant:
        dormir(cible - maintenant)  # JSPI : la page et le moteur de mémoire (qui envoie l'image) tournent pendant ce temps
    return True


def completer(pyxel: Any) -> None:
    """Remplace ``init``, ``flip`` et ``run`` du module ``pyxel.pyxel_binding`` exécuté."""
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
        avant = os.getcwd()
        init(width, height, *args, **kwargs)
        _cwd_du_jeu(avant)

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
        compteur = _compteur_de_balayages()
        if compteur is None or not attendre_balayages(compteur, etat):
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
            flip_web()

    pyxel.init, pyxel.flip, pyxel.run = init_web, flip_web, run_web


class _Chercheur:
    """``pyxel.pyxel_binding`` trouvé par les autres chercheurs (la roue est installée à l'import de ``pyxel``, juste
    avant), complété juste après son exécution."""

    def find_spec(self, nom: str, chemin: Any = None, cible: Any = None) -> Any:
        if nom != "pyxel.pyxel_binding":
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
