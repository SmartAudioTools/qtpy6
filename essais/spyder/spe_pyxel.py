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
import os, sys, pyxel
print("pyxel", pyxel.__file__)
JEU = '''
import os, pyxel
import js, pyodide_js
_c = js.OffscreenCanvas.new(64, 48)
_c.style = js.Object.new()
print('RES' 'ULTAT webgl', [str(js.OffscreenCanvas.new(8, 8).getContext(k)) for k in ('webgl2', 'webgl', '2d')], str(js.navigator.userAgent))
_c.getBoundingClientRect = lambda: js.Object.fromEntries(js.Object.entries(js.JSON.parse('{"left":0,"top":0,"width":64,"height":48,"right":64,"bottom":48}')))
pyodide_js.canvas.setCanvas2D(_c)
from pyodide.code import run_js
run_js("self.screen ??= {width: 1280, height: 720, availWidth: 1280, availHeight: 720, colorDepth: 24}; self.navigator.getGamepads ??= () => []; const _n = () => {}; self.document ??= {addEventListener: _n, removeEventListener: _n, querySelector: () => null, getElementById: () => null, title: '', body: {style: {}, addEventListener: _n, removeEventListener: _n}, documentElement: {style: {}}, fullscreenElement: null, pointerLockElement: null, hidden: false, visibilityState: 'visible', hasFocus: () => true};")
print("canvas", pyodide_js.canvas.getCanvas2D())
try:
    pyxel.init(64, 48)
    print("RES" "ULTAT init OK", pyxel.width, pyxel.height, os.getcwd())
    import time
    vus = []
    t0 = time.monotonic()
    for i in range(10):  # images sans flip (interdit en web) : dessin seul, cadence par sleep
        pyxel.cls(i); pyxel.rect(0, 0, 8, 8, 15 - i)
        m = bytes(memoryview(pyxel.screen.data_ptr()))
        vus.append((m[0], m[63 * 47]))
        time.sleep(1 / 30)
    print("RES" "ULTAT boucle", vus, "duree", round(time.monotonic() - t0, 3), "attendu ~0.333")
    print("RES" "ULTAT frame_count", pyxel.frame_count)
    pyxel.set_btn(pyxel.KEY_SPACE, True)
    print("RES" "ULTAT btn", pyxel.btn(pyxel.KEY_SPACE), "btnp", pyxel.btnp(pyxel.KEY_SPACE))
    pyxel.set_btn(pyxel.KEY_SPACE, False)
    vus_run = []
    def update():
        vus_run.append(pyxel.frame_count)
        if len(vus_run) == 5:
            print("RES" "ULTAT run images", vus_run, "fin")
            pyxel.quit()
    def draw():
        pyxel.cls(len(vus_run))
    try:
        pyxel.run(update, draw)
        print("RES" "ULTAT run rendu", vus_run, "fin")
    except BaseException as e:
        print("RES" "ULTAT run leve", type(e).__name__, str(e)[:200], vus_run)
except BaseException as e:
    import traceback; traceback.print_exc(); print("RES" "ULTAT KO", type(e).__name__, e)
'''
os.makedirs("/home/pyodide/jeux", exist_ok=True)
open("/home/pyodide/jeux/jeu.py", "w").write(JEU)
exec(compile(JEU, "/home/pyodide/jeux/jeu.py", "exec"), {"__name__": "__main__"})
"""

_ICI = os.path.dirname(os.path.abspath(__file__))
_source = open(os.path.join(_ICI, "spe.py"), encoding="utf-8").read()
_avant = 'travailleur.configurer("./pyodide-qt/")'
_fin = "\n\nexec(compile(open(os.path.join(os.path.dirname"
assert _source.count(_avant) == 1 and _source.count(_fin) == 1
# window = le Worker, AVANT loadPyodide : SDL (emscripten) fige window/document au chargement (specialHTMLTargets), et
# sans window, SDL_Init échoue sur « Could not set gamepad connect callback ».
_source = _source.replace(_avant, f'travailleur.configurer("./pyodide/", roues=[{ROUE!r}])' + '''
    import importlib.resources, js
    _js = importlib.resources.files("qtpy6.web").joinpath("js/travailleur.js").read_text(encoding="utf-8")
    travailleur._URL_WORKER = js.URL.createObjectURL(js.Blob.new(["globalThis.window ??= globalThis;\\n" + _js],
                                                                 type="text/javascript"))''')
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
        if (" fin" in texte or "RESULTAT run leve" in texte or "RESULTAT KO" in texte or "Error" in texte) or time.monotonic() - debut[0] > 90:
            js.console.log("CONSOLE >>> " + texte[:8000])
            js.window.etat = "pyxel-fini"
        else:
            QTimer.singleShot(2000, relever)

    QTimer.singleShot(5000, relever)
""" + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
