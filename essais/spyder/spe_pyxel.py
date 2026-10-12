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
# Essai 26 : le greffon spyder_pyxel embarqué ; son amorce (reader.kernel_bootstrap_code), injectée par le panneau dans
# ce noyau, a-t-elle installé le pont ? Puis un jeu ordinaire (pyxel.run), vu par le panneau, avec la touche Espace
# envoyée par la page à l'écran du panneau (QKeyEvent réel).
import os, sys
import spyder_pyxel.bridge.kernel as k
print("RES" "ULTAT pont", k.status(), sys.modules.get("_spyder_pyxel_error"))
JEU = '''
import pyxel
pyxel.init(64, 48)
vu = []
import time, pyodide.ffi
mesure = {"t0": time.monotonic()}
def update():
    if pyxel.frame_count == 10:
        mesure["sync"] = pyodide.ffi.can_run_sync(); mesure["sleep"] = time.sleep.__qualname__
        t = time.monotonic(); time.sleep(0.05); mesure["sleep50ms"] = round(time.monotonic() - t, 3)
    if pyxel.btn(pyxel.KEY_SPACE) and not vu:
        vu.append(pyxel.frame_count)
    if pyxel.frame_count >= 150:
        pyxel.quit()
def draw():
    pyxel.cls(1)
    pyxel.rect(8, 8, 16, 16, 7 if pyxel.btn(pyxel.KEY_SPACE) else 8)
pyxel.run(update, draw)
print("RES" "ULTAT jeu fini", pyxel.frame_count, "espace vue à l'image", vu)
print("RES" "ULTAT taille", pyxel.width, pyxel.height)
print("RES" "ULTAT mesure", mesure, "durée", round(time.monotonic() - mesure["t0"], 2))
try:
    d = pyxel.screen.data_ptr(); print("RES" "ULTAT data_ptr", type(d), len(d), bytes(memoryview(d)[:4]))
except BaseException as e:
    import traceback; print("RES" "ULTAT data_ptr KO", traceback.format_exc().replace(chr(10), " | "))
'''
os.makedirs("/home/pyodide/jeux", exist_ok=True)
open("/home/pyodide/jeux/jeu.py", "w").write(JEU)
try:
    exec(compile(JEU, "/home/pyodide/jeux/jeu.py", "exec"), {"__name__": "__main__"})
except BaseException as e:
    import traceback; traceback.print_exc(); print("RES" "ULTAT KO", type(e).__name__, e)
print("RES" "ULTAT pont après", k.status())
"""

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
    js.console.log("ISOLATION page " + str(js.self.crossOriginIsolated) + " SAB " + str(hasattr(js, "SharedArrayBuffer")))
    js.console.log("WEBGL page " + str([str(js.document.createElement("canvas").getContext(k)) for k in ("webgl2", "webgl")]) + " offscreen " + str(js.OffscreenCanvas.new(8, 8).getContext("webgl2")))
    try:
        _SUITE_SPE(main, rapport)
    except BaseException:
        import traceback
        js.console.log("SUITE spe " + traceback.format_exc())
    from spyder_pyxel.spyder.bridge_manager import get_bridge
    from qtpy6.QtCore import QEvent, Qt
    from qtpy6.QtGui import QKeyEvent
    from qtpy6.QtWidgets import QApplication
    pont, images = get_bridge(), []

    def image(kind, frame, canal):  # instrumentation : chaque image reçue par le panneau ; Espace envoyée à son écran
        images.append((frame.number, round(time.monotonic(), 2), frame.pixels[0], frame.pixels[8 * frame.width + 8]))
        ecran = main.get_plugin("pyxel_game").get_widget()._screens.get(canal)
        for n, type_ in ((40, QEvent.KeyPress), (80, QEvent.KeyRelease)):
            if len(images) == n and ecran is not None:
                QApplication.sendEvent(ecran, QKeyEvent(type_, Qt.Key_Space, Qt.NoModifier, " "))
    pont.sig_frame.connect(image)
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

    def relever_():  # instrumentation : le texte de la console, jusqu'au verdict ou 120 s
        texte = console.get_current_shellwidget()._control.toPlainText()
        if not debut:
            debut.append(time.monotonic())
            js.console.log("PONT page canaux " + repr([(c.name, c.notify_fd) for c in pont.channels().values()])
                           + " minuterie " + str(pont._timer.interval()) + " active " + str(pont._timer.isActive()))
            console.get_current_shellwidget().execute(ESSAI_CODE)
        if "RESULTAT pont après" in texte or "RESULTAT KO" in texte or "Error" in texte or time.monotonic() - debut[0] > 120:
            js.console.log("RES" "ULTAT images " + str(len(images)) + " " + repr(images[:3] + images[38:44] + images[78:84] + images[-3:]))
            if len(images) > 1:
                js.console.log("RES" "ULTAT cadence " + str(round((len(images) - 1) / (images[-1][1] - images[0][1] + 1e-9), 1)) + " images/s")
            for c in pont.channels().values():
                js.console.log("SEGMENT page " + c.name + " " + bytes(c._shm.buf[:32]).hex())
            js.console.log("CONSOLE >>> " + texte[:8000])
            js.window.etat = "pyxel-fini"
        else:
            QTimer.singleShot(2000, relever)

    QTimer.singleShot(5000, relever)
""" + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
