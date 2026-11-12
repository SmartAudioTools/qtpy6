"""Essai interactif (12/10/2026) : spe_pyxel.py sans son instrumentation, sur un vrai jeu d'élève. Le script et ses
ressources sont servis par le lien ``site/monkey`` (→ dossier Correction du Projet Monkey) ; le fichier s'ouvre dans
l'éditeur et le jeu se lance dans la console, l'image dans le panneau Pyxel, à jouer au clavier.
``index.html?script=spe_monkey.py&jeu=<fichier .py>`` (le .pyxres du même dossier suit)."""

import os

ROUE = "./roues/pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl"
DIAG_JEU = """
import js, os, traceback
def _t(m): js.console.log("DIAG " + str(m))
try:
    _t(("listdir", os.listdir("/home/pyodide/monkey")))
    _t(("cwd avant init", os.getcwd()))
    import pyxel
    _t(("pyxel.init", getattr(pyxel.init, "__module__", None), getattr(pyxel.init, "__qualname__", None)))
    pyxel.init(160, 120, headless=True)
    _t(("cwd après init", os.getcwd()))
    pyxel.load("projet_monkey.pyxres")
    _t("load OK")
except BaseException:
    _t(traceback.format_exc())
"""  # instrumentation, &diag=1
DIAG_SON = """
import gc, js, sys, time, traceback
def _t(m): js.console.log("DIAG " + str(m))
gc.disable()  # le plantage de l'item 1 (GC + piles JSPI, « index out of bounds ») masquerait la mesure du son
try:
    entrees = [0]  # appels Python vus pendant que la pompe du son tourne (condition : toujours 0)
    def _prof(cadre, evenement, arg):
        son = getattr(js.self, "qtpy6_son", None)
        if son is not None and son.dans_pompe:
            entrees[0] += 1
    _t("noyau : import pyxel")
    import pyxel
    _t("noyau : init")
    pyxel.init(160, 120, headless=True)
    son = getattr(js.self, "qtpy6_son", None)
    _t(("son doublé", son is not None, "noeuds", son.noeuds.size if son else None))
    m = getattr(js.self, "qtpy6_memoires", None)
    _t(("segments du Worker", None if m is None else (m.size, m.has("qtpy6_son"))))
    if POMPE == "0":
        son.noeuds.clear()  # témoin : la pompe ne trouve plus de nœud, rien n'entre dans le mixeur
        _t("pompe coupée")
    pyxel.sounds[0].set("c3e3g3c4", "s", "7", "n", 10)
    _t("set OK")
    pyxel.play(0, 0, loop=True)
    _t("play OK")
    if PROFIL != "0":
        sys.setprofile(_prof)
    t = time.monotonic()
    for i in range(80):
        time.sleep(0.1)
    sys.setprofile(None)
    _t(("sommeil", round(time.monotonic() - t, 2), "entrées Python pendant la pompe", entrees[0]))
except BaseException:
    _t(traceback.format_exc())
"""  # instrumentation, &son=1 : un son en boucle (headless), compteurs de l'anneau relevés par la page
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
    # Instrumentation (item 8 du TODO Portage) : ``&diag=1`` remplace le jeu par la chaîne init → load en headless
    # (le Firefox du bac n'a pas de WebGL), chaque étape tracée dans la console de la page.
    diag = js.URLSearchParams.new(js.location.search).get("diag") == "1"
    son = js.URLSearchParams.new(js.location.search).get("son") == "1"
    # Le jeu réduit à init → load, lancé deux fois comme le triangle (%runfile --wdir), cwd du noyau ailleurs avant.
    diagnostic = """
open("diag_jeu.py", "w").write(@DIAG_JEU@)
os.chdir("/home/pyodide")  # cwd hors du dossier du jeu (un second init dans le noyau est fatal : un seul lancement)
exec(compile(open("/home/pyodide/monkey/diag_jeu.py").read(), "/home/pyodide/monkey/diag_jeu.py", "exec"), {"__name__": "__main__"})
"""
    pompe = js.URLSearchParams.new(js.location.search).get("pompe")
    diagnostic_son = f"""
POMPE = {pompe!r}
PROFIL = {js.URLSearchParams.new(js.location.search).get("profil")!r}
open("diag_son.py", "w").write(@DIAG_SON@)
exec(compile(open("/home/pyodide/monkey/diag_son.py").read(), "/home/pyodide/monkey/diag_son.py", "exec"), {{"__name__": "__main__", "POMPE": POMPE, "PROFIL": PROFIL}})
"""
    os.makedirs(dossier, exist_ok=True)
    from qtpy6.QtCore import QTimer
    if son:  # instrumentation : compteurs de l'anneau côté page, chaque seconde ; une vraie touche au premier son (geste)
        releves = []

        def relever():
          try:
            releve_(releves)
          except BaseException:
            import traceback
            js.console.log("SON relevé " + traceback.format_exc())
            js.window.etat = "fini"

        def releve_(releves):
            P = getattr(js.self, "qtpy6_son_page", None)
            if P is None:
                js.console.log("SON pas d'anneau dans la page")
                js.window.etat = "fini"
                return
            H, I = P.H, P.I
            v = {n: js.Atomics.load(H, getattr(I, n)) for n in ("DEMANDE", "ETAT", "POMPES", "NON_NULS", "LUES", "VIDES", "PERDUES",
                                                 "SAUTS", "NIVEAU", "CIBLE", "CANAUX")}
            ctx = P.contexte
            if ctx is not None:
                v.update(debit=ctx.sampleRate, etat_ctx=ctx.state, base_ms=round(ctx.baseLatency * 1000, 1),
                         sortie_ms=round((getattr(ctx, "outputLatency", 0) or 0) * 1000, 1))
            js.console.log("SON " + repr(v))
            if v["DEMANDE"] and js.window.etat == "monkey":
                js.window.texte = "a"
                js.window.etat = "taper"
            releves.append(v)
            if len(releves) < 300 and not (v["NON_NULS"] and v["POMPES"] and len(releves) > 25):
                QTimer.singleShot(1000, relever)
            else:
                js.window.etat = "fini"
        QTimer.singleShot(1000, relever)

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
{diagnostic_son if son else diagnostic if diag else lancement}
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
'''.replace("@DIAG_JEU@", repr(repr(DIAG_JEU))[1:-1]).replace("@DIAG_SON@", repr(repr(DIAG_SON))[1:-1]) + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
