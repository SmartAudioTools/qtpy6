"""Essai Pyxel (12/10/2026), notes/2026-10-12 - Pyxel dans la page.md : spe.py avec le noyau de la console sur le Pyodide
ordinaire (3.14, emscripten 5.0.3, celui de versions.json) au lieu du Pyodide-Qt du site (3.13), et la roue wasm
officielle de Pyxel 2.9.9 (même ABI 2026_0 que pyxel.js) chargée au premier ``import pyxel`` du noyau. Liens posés à la
main pour l'essai : ``site/pyodide`` → qtpy6/exemple/pyodide, ``site/roues`` → essais/spyder/roues.
Instrumentation : ESSAI_CODE, exécuté dans la console 5 s après l'affichage de la fenêtre ; il écrit un vrai fichier
(pyxel.init fait un chdir dans le dossier du script appelant) et pose dans le Worker ce que SDL y attend du DOM :
OffscreenCanvas avec style, screen, navigator.getGamepads, document factice ; window posé avant loadPyodide."""

import os
import time

ROUE = "./roues/pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl"
ESSAI_CODE = """
import builtins, os, sys
# Essai 23 : l'ordre du greffon (bridge/kernel.py) : __import__ enveloppé, flip capturé dès que pyxel, encore
# partiellement initialisé, a init/run/flip ; la doublure doit être déjà en place à cet instant.
_capte = {}
_imp = builtins.__import__
def _guet(*a, **k):
    m = _imp(*a, **k)
    p = sys.modules.get("pyxel")
    if p is not None and not _capte and all(hasattr(p, n) for n in ("init", "run", "flip")):
        _capte["flip"] = p.flip.__module__
    return m
builtins.__import__ = _guet
import pyxel
builtins.__import__ = _imp
print("RES" "ULTAT capture", _capte, "attendu qtpy6.web.pyxel_web")
print("pyxel", pyxel.__file__)
JEU = '''
import os, pyxel
import time
try:
    # Essai 22 : le code du bureau tel quel, servi par la doublure qtpy6/web/pyxel_web.py (installée par le préambule).
    os.environ["SDL_VIDEODRIVER"] = "offscreen"  # ce que pose le greffon : la doublure doit le retirer
    pyxel.init(64, 48)
    print("RES" "ULTAT init OK", pyxel.width, pyxel.height, pyxel.flip.__module__)
    journal = []
    t0 = time.monotonic()
    for k in range(60):  # la boucle de patched_run : entrées (pump), update, draw, flip
        if k in (30, 45):
            pyxel.set_btn(pyxel.KEY_SPACE, k == 30)
        if k < 3 or k % 10 == 0 or 29 <= k <= 31 or 44 <= k <= 46:
            journal.append(f"k={k} fc={pyxel.frame_count} t={time.monotonic() - t0:.2f} btn={pyxel.btn(pyxel.KEY_SPACE)} btnp={pyxel.btnp(pyxel.KEY_SPACE)}")
        pyxel.cls(k % 16)
        pyxel.flip()
    m = bytes(memoryview(pyxel.screen.data_ptr()))
    print("RES" "ULTAT flip", journal, "frame_count", pyxel.frame_count, "duree", round(time.monotonic() - t0, 2), "attendu ~2.0", "pixel", m[0], "attendu 11")
except BaseException as e:
    import traceback; traceback.print_exc(); print("RES" "ULTAT KO", type(e).__name__, e)
'''
os.makedirs("/home/pyodide/jeux", exist_ok=True)
open("/home/pyodide/jeux/jeu.py", "w").write(JEU)
exec(compile(JEU, "/home/pyodide/jeux/jeu.py", "exec"), {"__name__": "__main__"})
"""

# Essai 12 ter : l'état de la boucle principale d'emscripten (Module.MainLoop), et un compteur requestAnimationFrame en
# JS pur, pour séparer « rAF ne bat pas dans ce Worker » de « la boucle bat mais n'entre pas dans Python ».
CELLULE_2 = """import pyxel, js, pyodide_js
M = pyodide_js._module.MainLoop
print('RES' 'ULTAT mainloop', 'running', M.running, 'image', M.currentFrameNumber, 'frame_count', pyxel.frame_count, 'setTimeout JS', js.self.__s, 'journal', list(js.self.__log), ' f' 'in')
"""
CELLULE_3 = ""

_ICI = os.path.dirname(os.path.abspath(__file__))
_source = open(os.path.join(_ICI, "spe.py"), encoding="utf-8").read()
_avant = 'travailleur.configurer("./pyodide-qt/")'
_fin = "\n\nexec(compile(open(os.path.join(os.path.dirname"
assert _source.count(_avant) == 1 and _source.count(_fin) == 1
# window = le Worker avant loadPyodide : posé désormais par qtpy6/web/js/travailleur.js lui-même.
_source = _source.replace(_avant, f'travailleur.configurer("./pyodide/", roues=[{ROUE!r}])')
_source = _source.replace(_fin, """
_SUITE_SPE = SUITE


def SUITE(main, rapport):  # noqa: N802
    import js
    js.console.log("SUITE pyxel : entrée")
    js.console.log("WEBGL page " + str([str(js.document.createElement("canvas").getContext(k)) for k in ("webgl2", "webgl")]) + " offscreen " + str(js.OffscreenCanvas.new(8, 8).getContext("webgl2")))
    try:
        _SUITE_SPE(main, rapport)
    except BaseException:
        import traceback
        js.console.log("SUITE spe " + traceback.format_exc())
    js.console.log("SUITE pyxel : minuterie armée")
    from qtpy6.QtCore import QTimer
    import js
    js.window.etat = "pyxel"
    console = main.get_plugin("ipython_console")
    debut = []

    def relever():
        try:
            relever_()
        except BaseException:
            import traceback
            js.console.log("RELEVER " + traceback.format_exc())
            js.window.etat = "pyxel-fini"

    def relever_():  # instrumentation : le texte de la console, jusqu'au verdict ou 90 s
        texte = console.get_current_shellwidget()._control.toPlainText()
        if not debut:
            debut.append(time.monotonic())
            console.get_current_shellwidget().execute(ESSAI_CODE)
        if False:  # essai 12 : la cellule est rendue ; les images avancent-elles ?
            debut.append(time.monotonic())
            QTimer.singleShot(3000, lambda: console.get_current_shellwidget().execute(CELLULE_2))
        if "RESULTAT mainloop" in texte and len(debut) == 2:
            debut.append(time.monotonic())
            QTimer.singleShot(2000, lambda: console.get_current_shellwidget().execute(CELLULE_3))
        if ("RESULTAT flip" in texte or "RESULTAT run leve" in texte or "RESULTAT KO" in texte or "Error" in texte) or time.monotonic() - debut[0] > 90:
            js.console.log("CONSOLE >>> " + texte[:8000])
            js.window.etat = "pyxel-fini"
        else:
            QTimer.singleShot(2000, relever)

    QTimer.singleShot(5000, relever)
""" + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
