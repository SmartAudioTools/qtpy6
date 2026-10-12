"""Essai interactif (12/10/2026) : spe_pyxel.py sans son instrumentation, sur un vrai jeu d'élève. Le script et ses
ressources sont servis par le lien ``site/monkey`` (→ dossier Correction du Projet Monkey) ; le fichier s'ouvre dans
l'éditeur et le jeu se lance dans la console, l'image dans le panneau Pyxel, à jouer au clavier.
``index.html?script=spe_monkey.py&jeu=<fichier .py>`` (le .pyxres du même dossier suit)."""

import os

ROUE = "./roues/pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl"
_ICI = os.path.dirname(os.path.abspath(__file__))
_source = open(os.path.join(_ICI, "spe.py"), encoding="utf-8").read()
_avant = 'travailleur.configurer("./pyodide-qt/")'
_fin = "\n\nexec(compile(open(os.path.join(os.path.dirname"
assert _source.count(_avant) == 1 and _source.count(_fin) == 1
_source = _source.replace(_avant, f'travailleur.configurer("./pyodide/", roues=[{ROUE!r}])')
_source = _source.replace(_fin, '''
_SUITE_SPE = SUITE


def SUITE(main, rapport):  # noqa: N802
    import js
    js.console.log("MONKEY entrée")
    try:
        _SUITE_SPE(main, rapport)
        suite(main)
    except BaseException:
        import traceback
        js.console.log("MONKEY " + traceback.format_exc())


def suite(main):
    import js
    js.console.log("MONKEY suite")
    jeu = js.URLSearchParams.new(js.location.search).get("jeu")
    dossier = "/home/pyodide/monkey"
    chemin = dossier + "/" + jeu
    bouton = js.URLSearchParams.new(js.location.search).get("bouton") == "1"  # lancer au triangle, pas tout seul
    lancement = "" if bouton else f'exec(compile(open({chemin!r}).read(), {chemin!r}, "exec"), {{"__name__": "__main__", "__file__": {chemin!r}}})'
    os.makedirs(dossier, exist_ok=True)
    from qtpy6.QtCore import QTimer

    def ouvrir():
        try:  # côté éditeur (la page) : fetch suspendu dans un slot ; open_url (XHR synchrone) y plante
            from pyodide.ffi import run_sync
            reponse = run_sync(js.fetch("./monkey/" + jeu))
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(run_sync(reponse.text()))
            main.get_plugin("editor").load(chemin)
            js.console.log("MONKEY ouvert")
        except BaseException:
            import traceback
            js.console.log("MONKEY ouvrir " + traceback.format_exc())
    QTimer.singleShot(0, ouvrir)
    # Côté noyau (son Worker a son propre système de fichiers) : le script et le .pyxres, par XHR synchrone.
    code = f"""
import js, os
os.makedirs({dossier!r}, exist_ok=True)
for nom in ({jeu!r}, "projet_monkey.pyxres"):
    x = js.XMLHttpRequest.new(); x.open("GET", js.location.origin + "/monkey/" + nom, False)
    x.responseType = "arraybuffer"; x.send()
    open({dossier!r} + "/" + nom, "wb").write(bytes(js.Uint8Array.new(x.response).to_py()))
os.chdir({dossier!r})
{lancement}
"""
    from qtpy6.QtCore import QTimer
    console = main.get_plugin("ipython_console")

    def injecter():  # la console n'est pas toujours prête à 5 s : réessayer chaque seconde jusqu'à ce qu'elle le soit
        try:
            sw = console.get_current_shellwidget()
            if sw is None or not getattr(sw, "spyder_kernel_ready", True) or sw._executing:
                raise RuntimeError("console pas prête")
            sw.execute(code)
            js.console.log("MONKEY injecté")
        except BaseException as e:
            js.console.log("MONKEY injection en attente : " + repr(e))
            QTimer.singleShot(1000, injecter)
    QTimer.singleShot(5000, injecter)
    js.window.etat = "monkey"
''' + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
