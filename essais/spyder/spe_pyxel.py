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
run_js("self.screen ??= {width: 1280, height: 720, availWidth: 1280, availHeight: 720, colorDepth: 24}; self.navigator.getGamepads ??= () => []; self._readVirtualGamepadBitmask ??= () => 0; const _n = () => {}; self.document ??= {addEventListener: _n, removeEventListener: _n, querySelector: () => null, getElementById: () => null, title: '', body: {style: {}, addEventListener: _n, removeEventListener: _n}, documentElement: {style: {}}, fullscreenElement: null, pointerLockElement: null, hidden: false, visibilityState: 'visible', hasFocus: () => true};")
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
    # Essai 12 : drapeau posé, puis pyxel.run appelé par un trampoline JS synchrone (hors JSPI) ; l'« unwind » quitte la
    # cellule, et les images arrivent ensuite par requestAnimationFrame, sans tâche Python suspendue à côté.
    pyodide_js._api._skip_unwind_fatal_error = True
    js.self.__log = js.Array.new()
    t0 = time.monotonic()
    def u():  # essai 14 : sans set_btn (emprunt de la plateforme déjà tenu par la boucle de Pyxel, essai 13)
        n = pyxel.frame_count
        if n < 3 or n % 15 == 0 or pyxel.btnp(pyxel.KEY_SPACE):
            js.self.__log.push(f"image {n} t={time.monotonic() - t0:.2f} btn={pyxel.btn(pyxel.KEY_SPACE)} btnp={pyxel.btnp(pyxel.KEY_SPACE)} pixel={bytes(memoryview(pyxel.screen.data_ptr()))[0]} setTimeout={js.self.__s}")
        if n == 90:  # essai 16 : arrêt comme pyxel.js, pour rendre la main au noyau
            js.self.__log.push(f"arret a {time.monotonic() - t0:.2f}")
            pyodide_js._module._emscripten_cancel_main_loop()
    def d():
        pyxel.cls(pyxel.frame_count % 16)
    from pyodide.ffi import create_once_callable
    trampoline = js.Function.new("f", "f()")  # appel synchrone d'un PyProxy : l'unwind s'arrête dans maybe_fatal_error
    # Essai 17 : la touche posée depuis JS entre deux images (ce que fera le pont clavier), et un compteur setTimeout pour
    # savoir si les tâches JS (donc les messages du noyau) passent pendant la boucle.
    from pyodide.ffi import create_proxy
    js.self.__touche = create_proxy(lambda v: pyxel.set_btn(pyxel.KEY_SPACE, v))
    js.self.__module = pyodide_js._module
    from pyodide.code import run_js
    run_js("self.__s = 0; (function u(){ self.__s++; if (self.__s < 400) setTimeout(u, 16); })(); const t = (v) => { try { self.__touche(v); self.__log.push('touche ' + v + ' posee') } catch (e) { self.__log.push('touche ' + v + ' : ' + String(e).slice(0, 300)) } }; setTimeout(() => t(true), 1000); setTimeout(() => t(false), 1500); setTimeout(() => { self.__log.push('arret JS a 3 s'); self.__module._emscripten_cancel_main_loop() }, 3000);")
    try:
        trampoline(create_once_callable(lambda: pyxel.run(u, d)))
        print("RES" "ULTAT run rendu")
    except BaseException as e:
        print("RES" "ULTAT run leve", type(e).__name__, str(e)[:100])
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
        if "run rendu" in texte and len(debut) == 1:  # essai 12 : la cellule est rendue ; les images avancent-elles ?
            debut.append(time.monotonic())
            QTimer.singleShot(3000, lambda: console.get_current_shellwidget().execute(CELLULE_2))
        if "RESULTAT mainloop" in texte and len(debut) == 2:
            debut.append(time.monotonic())
            QTimer.singleShot(2000, lambda: console.get_current_shellwidget().execute(CELLULE_3))
        if (" fin" in texte or "RESULTAT run leve" in texte or "RESULTAT KO" in texte or "Error" in texte) or time.monotonic() - debut[0] > 90:
            js.console.log("CONSOLE >>> " + texte[:8000])
            js.window.etat = "pyxel-fini"
        else:
            QTimer.singleShot(2000, relever)

    QTimer.singleShot(5000, relever)
""" + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
