"""Essai interactif (12/10/2026) : spe_pyxel.py sans son instrumentation, sur un vrai jeu d'élève. Le script et ses
ressources sont servis par le lien ``site/monkey`` (→ dossier Correction du Projet Monkey) ; le fichier s'ouvre dans
l'éditeur et le jeu se lance dans la console, l'image dans le panneau Pyxel, à jouer au clavier.
``index.html?script=spe_monkey.py&jeu=<fichier .py>`` (le .pyxres du même dossier suit)."""

import os

ROUE = "./roues/qtpy6-vsync/pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl"  # fork qtpy6-vsync (pyxel.step), W575/W580
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
DIAG_CLAVIER = """
import js, pyxel
def _t(m): js.console.log("DIAG noyau " + str(m))
pyxel.init(64, 48, headless=True)  # le Firefox du bac n a pas de WebGL
vu = []
def update():
    if pyxel.btn(pyxel.KEY_SPACE) and not vu:
        vu.append(pyxel.frame_count)
        _t(("espace vue", pyxel.frame_count))
    if pyxel.frame_count % 60 == 0:
        _t(("image", pyxel.frame_count))
def draw():
    pyxel.cls(8 if vu else 1)
pyxel.run(update, draw)
"""  # instrumentation, &clavier=1 : un jeu minimal qui dit quand il voit Espace (item 8, clavier)
DIAG_CADENCE = """
import js, pyxel, time
def _t(m): js.console.log("CADENCE noyau " + str(m))
_init, _run, _sleep = pyxel.init, pyxel.run, time.sleep
def init_h(*a, **k):
    k["headless"] = HEADLESS  # le Firefox du bac n a pas de WebGL ; &headless=0 : le vrai rendu
    _t(("init", a, k))
    return _init(*a, **k)
M = dict(u=0.0, d=0.0, sd=0.0, sr=0.0, n=0, t=time.monotonic())
_bc, _lot = js.BroadcastChannel.new("qtpy6-vsync"), []  # horloge du noyau : (image, instant absolu) vers la page, par 30
def sleep_m(s):
    t = time.monotonic(); _sleep(s); M["sd"] += s; M["sr"] += time.monotonic() - t
    _somm.append(time.monotonic() - t)
_somm, _rev = [], []  # W573 : durée réelle de chaque sommeil ; réveils (balayage lu, instant absolu, sommeils de l attente)
import qtpy6.web.pyxel_web as _pw
_ab = _pw.attendre_balayages
def ab_m(lire, etat, *a, **k):
    n0 = len(_somm); r = _ab(lire, etat, *a, **k)
    if r:
        _rev.append([lire(0), js.performance.timeOrigin + js.performance.now(), len(_somm) - n0, etat.get("cible", 0) * 1000])
        if len(_rev) >= 30:
            js.BroadcastChannel.new("qtpy6-reveil").postMessage(js.JSON.parse(str(_rev))); _rev.clear()
    return r
_pw.attendre_balayages = ab_m
def somm_q():
    d = sorted(_somm[-600:]); return [round(d[int(p * (len(d) - 1))] * 1000, 2) for p in (.1, .5, .9)] if d else []
def run_m(update, draw):
    def u():
        t = time.monotonic(); update(); M["u"] += time.monotonic() - t
    def d():
        t = time.monotonic(); draw(); M["d"] += time.monotonic() - t
        M["n"] += 1
        _lot.append([M["n"], js.performance.timeOrigin + js.performance.now()])
        if len(_lot) >= 30:
            _bc.postMessage(js.JSON.parse(str(_lot))); _lot.clear()
        if M["n"] % 60 == 0:
            T = time.monotonic(); dt = T - M["t"]
            _t(dict(images=M["n"], ips=round(60 / dt, 1), ms_image=round(dt * 1000 / 60, 1),
                    ms_update=round(M["u"] * 1000 / 60, 1), ms_draw=round(M["d"] * 1000 / 60, 1),
                    ms_sommeil_demande=round(M["sd"] * 1000 / 60, 1), ms_sommeil_reel=round(M["sr"] * 1000 / 60, 1), sommeil_1ms_reel_q10_50_90=somm_q()))
            M.update(u=0.0, d=0.0, sd=0.0, sr=0.0, t=T)
    return _run(u, d)
pyxel.init, pyxel.run, time.sleep = init_h, run_m, sleep_m
"""  # instrumentation, &cadence=1 : le vrai jeu en headless, temps par image découpé (item 8, « le jeu rame »)
REFOCUS = """let presse = false;
window.addEventListener("pointerdown", () => { presse = true; }, true);
for (const n of ["pointerup", "pointercancel"]) window.addEventListener(n, () => { presse = false; }, true);
document.addEventListener("focusout", e => {
  const el = e.composedPath()[0];
  if (!presse || e.relatedTarget || !String(el.className).startsWith("qt-window-")) return;
  setTimeout(() => { if (!document.activeElement || document.activeElement === document.body) el.focus({preventScroll: true}); }, 0);
}, true);"""
_ICI = os.path.dirname(os.path.abspath(__file__))
_source = open(os.path.join(_ICI, "spe.py"), encoding="utf-8").read()
_fin = "\n\nexec(compile(open(os.path.join(os.path.dirname"
assert _source.count(_fin) == 1
# Le noyau sur le Pyodide ordinaire (3.14) avec la roue de Pyxel : spe.py n'appelle plus ``configurer`` depuis W559 (D4).
_source = _source.replace(_fin, f'''
from qtpy6.web import travailleur  # noqa: E402
travailleur.configurer("./pyodide/", roues=[{ROUE!r}])
''' + '''
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


VSYNC_JS = """
window.vsync = {raf: [], passes: [], presentations: [], peint: 0, ecrit: 0, ecarts: [], noyau: []};
requestAnimationFrame(function f(t) { vsync.raf.push(t); requestAnimationFrame(f); });
// W573 : chaque top de balayage (valeur du compteur BALAYAGES après TOUS les rappels de l image, instant de l image,
// instant de la lecture), les réveils du Worker, la durée et la fin (depuis le début de l image) de chaque écriture.
Object.assign(vsync, {tops: [], reveils: [], ecr_duree: [], ecr_fin: []});
requestAnimationFrame(function g(t) {
  setTimeout(() => {
    const s = self.qtpy6_memoires && self.qtpy6_memoires.get("qtpy6-balayages");
    if (s) vsync.tops.push([Atomics.load(new Int32Array(s), 0), t, performance.now()]);
  }, 0);
  requestAnimationFrame(g);
});
new BroadcastChannel("qtpy6-reveil").onmessage = e => {
  for (const [k, t, n, c] of e.data) vsync.reveils.push([k, t - performance.timeOrigin, n, c ? c - performance.timeOrigin : null]);
};
// Une écriture du canevas montre le dernier numéro peint : présenté au balayage de l image en cours (Qt-WASM n écrit
// qu au requestAnimationFrame ; l écart à l instant de l image, gardé, le vérifie).
for (const proto of [CanvasRenderingContext2D.prototype, OffscreenCanvasRenderingContext2D.prototype])
  for (const nom of ["putImageData", "drawImage"]) {
    const vrai = proto[nom];
    proto[nom] = function (...a) {
      if (vsync.peint !== vsync.ecrit) {
        const t = document.timeline.currentTime;
        vsync.presentations.push([t, vsync.peint]); vsync.ecarts.push(performance.now() - t); vsync.ecrit = vsync.peint;
      }
      const t0 = performance.now(), r = vrai.apply(this, a), t1 = performance.now();
      vsync.ecr_duree.push(t1 - t0); vsync.ecr_fin.push(t1 - document.timeline.currentTime);
      return r;
    };
  }
new BroadcastChannel("qtpy6-vsync").onmessage = e => {
  for (const [n, t] of e.data) vsync.noyau.push([n, t - performance.timeOrigin]);
};
"""


def horloges(main):
    """Instrumentation (W572, &cadence=1) : les trois horloges de Pyxel dans la page, et le nombre de balayages pendant
    lesquels chaque image Pyxel reste à l'écran. Noyau : fin de chaque draw (BroadcastChannel) ; pont : passes du moteur
    de mémoire partagée et tours de la minuterie du greffon, images reçues (sig_frame) ; page : chaque
    requestAnimationFrame, et l'image où chaque numéro Pyxel arrive au canevas. Rend la fonction qui affiche le bilan
    dans la page (cadre en haut à droite) et dans la console."""
    import js
    from collections import Counter
    from pyodide.code import run_js
    from qtpy6.QtCore import QEvent, QObject
    from qtpy6.web import memoire_partagee
    from spyder_pyxel.spyder.bridge_manager import get_bridge
    run_js(VSYNC_JS)
    memoire_partagee.ajouter_crochet(run_js("() => vsync.passes.push(performance.now())"))
    pont, H = get_bridge(), {"recus": [], "tours": [], "dernier": 0, "ecran": None}
    pont._timer.timeout.connect(lambda: H["tours"].append(js.performance.now()))
    D = {"deliver": [], "paint": [], "t0": js.performance.now()}  # W573 : ce que coûte le pont au fil principal
    vrai_deliver = pont._deliver

    def deliver_m(canal):
        t = js.performance.now()
        vrai_deliver(canal)
        D["deliver"].append(js.performance.now() - t)
    pont._deliver = deliver_m

    def mesurer_peinture(ecran):
        classe, vrai_paint = type(ecran), type(ecran).paintEvent

        def paint_m(self, e):
            t = js.performance.now()
            vrai_paint(self, e)
            D["paint"].append(js.performance.now() - t)
        classe.paintEvent = paint_m

    class Peinture(QObject):
        def eventFilter(self, objet, e):
            if e.type() == QEvent.Paint:
                js.vsync.peint = H["dernier"]
            return False
    H["filtre"] = Peinture()

    def recu(kind, frame, canal):
        H["recus"].append((frame.number, js.performance.now()))
        H["dernier"] = frame.number
        if H["ecran"] is None:
            H["ecran"] = main.get_plugin("pyxel_game").get_widget()._screens.get(canal)
            H["ecran"].installEventFilter(H["filtre"])
            mesurer_peinture(H["ecran"])
    pont.sig_frame.connect(recu)
    cadre = js.document.createElement("pre")
    cadre.style.cssText = ("position:fixed;top:4px;right:4px;z-index:2147483647;margin:0;padding:6px;font:12px monospace;"
                           "background:rgba(0,0,0,.85);color:#fff;pointer-events:none;white-space:pre")
    js.document.body.appendChild(cadre)

    def ecarts(temps):
        d = sorted(b - a for a, b in zip(temps, temps[1:]))
        if not d:
            return "—"
        q = lambda p: d[min(len(d) - 1, int(p * len(d)))]
        return f"méd {q(.5):.1f} ms, 10 % {q(.1):.1f}, 90 % {q(.9):.1f}, max {d[-1]:.1f} ({len(d) + 1})"

    def quant(d):
        d = sorted(d)
        if not d:
            return "—"
        q = lambda p: d[min(len(d) - 1, int(p * len(d)))]
        return f"méd {q(.5):.1f}, 10 % {q(.1):.1f}, 90 % {q(.9):.1f}, max {d[-1]:.1f} ({len(d)})"

    def reveil(v):
        """W573 : du top de balayage écrit par la page au réveil du Worker qui le lit, puis l'écriture du canevas."""
        import bisect
        tops = [tuple(x) for x in v.tops.to_py()]
        rev = [tuple(x) for x in v.reveils.to_py()]
        ks = [k for k, _, _ in tops]
        lat_image, lat_lu, sautes = [], [], Counter()
        visee = [tw - c for _, tw, _, c in rev if c is not None]
        for k, tw, _, _ in rev:
            i = bisect.bisect_left(ks, k)  # première image où le compteur valait k
            if i < len(tops) and tops[i][0] == k and tw >= tops[i][1]:
                lat_image.append(tw - tops[i][1]); lat_lu.append(tw - tops[i][2])
        for (k1, *_), (k2, *_) in zip(rev, rev[1:]):
            sautes[k2 - k1] += 1
        return [f"réveil Worker − début de l image du top : {quant(lat_image)} ms",
                f"réveil Worker − top lu par la page      : {quant(lat_lu)} ms",
                f"balayages entre deux réveils : {dict(sorted(sautes.items()))}",
                f"sommeils par attente : {quant([n for _, _, n, _ in rev])}",
                f"réveil Worker − balayage visé (grille, W573) : {quant(visee)} ms",
                f"écriture canevas, durée      : {quant(list(v.ecr_duree.to_py())[-3000:])} ms",
                f"écriture canevas, fin depuis le début de l image : {quant(list(v.ecr_fin.to_py())[-3000:])} ms"]

    def bilan():
        v = js.vsync
        raf, pres = list(v.raf.to_py()), [tuple(x) for x in v.presentations.to_py()]
        noyau = [t for _, t in v.noyau.to_py()]
        hz = 1000 / sorted(b - a for a, b in zip(raf, raf[1:]))[len(raf) // 2] if len(raf) > 2 else 0
        import bisect
        pres = [(bisect.bisect_left(raf, t - 1), n) for t, n in pres if n and raf and raf[0] - 1 <= t <= raf[-1] + 1]
        duree = Counter(n for n in Counter(
            n for (i, n), (j, _) in zip(pres, pres[1:]) for _ in range(j - i)).values())
        montres = {n for _, n in pres}
        nums = sorted({n for n, _ in H["recus"]})
        jamais = sum(1 for n in nums[:-1] if n not in montres)
        perdus = (nums[-1] - nums[0] + 1 - len(nums)) if nums else 0
        ecart = sorted(v.ecarts.to_py())
        lignes = [f"Pyxel : balayages par image ({hz:.0f} Hz ; attendu {hz / 60:.1f} à 60 i/s)",
                  f"  0 : {jamais + perdus:5d} {'#' * min(60, jamais + perdus)}  (reçues non montrées {jamais},"
                  f" jamais reçues {perdus})"]
        lignes += [f"  {k} : {duree[k]:5d} {'#' * min(60, duree[k])}" for k in sorted(duree)]
        lignes += [f"noyau (fin de draw) : {ecarts(noyau)}",
                   f"moteur mémoire     : {ecarts(list(v.passes.to_py())[-3000:])}",
                   f"minuterie du pont  : {ecarts(H['tours'][-3000:])} ; {pont._timer.interval()} ms",
                   f"reçues (sig_frame) : {ecarts([t for _, t in H['recus']])}",
                   f"requestAnimFrame   : {ecarts(raf)}",
                   f"écriture canevas après l image : max {ecart[-1] if ecart else 0:.1f} ms"]
        lignes += reveil(v)
        secs = (js.performance.now() - D["t0"]) / 1000
        lignes += [f"pont _deliver : {quant(D['deliver'][-3000:])} ms ; {sum(D['deliver']) / secs / 10:.1f} % du fil",
                   f"paintEvent écran : {quant(D['paint'][-3000:])} ms ; {sum(D['paint']) / secs / 10:.1f} % du fil"]
        cadre.textContent = "\\n".join(lignes)
        js.console.log("VSYNC " + " | ".join(lignes))
        return len(H["recus"])
    return bilan


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
    diagnostic_clavier = """
open("diag_clavier.py", "w").write(@DIAG_CLAVIER@)
exec(compile(open("/home/pyodide/monkey/diag_clavier.py").read(), "/home/pyodide/monkey/diag_clavier.py", "exec"), {"__name__": "__main__"})
"""
    cadence = js.URLSearchParams.new(js.location.search).get("cadence") == "1"
    diagnostic_cadence = """
open("diag_cadence.py", "w").write(@DIAG_CADENCE@)
exec(compile(open("/home/pyodide/monkey/diag_cadence.py").read(), "/home/pyodide/monkey/diag_cadence.py", "exec"), {"__name__": "diag", "HEADLESS": @HEADLESS@})
""".replace("@HEADLESS@", repr(js.URLSearchParams.new(js.location.search).get("headless") != "0")) + lancement
    os.makedirs(dossier, exist_ok=True)
    from qtpy6.QtCore import QTimer
    if cadence:  # instrumentation : images reçues par le panneau, et retard de la boucle de la page, toutes les 2 s
        from spyder_pyxel.spyder.bridge_manager import get_bridge
        page = {"images": 0, "releves": 0, "t": js.performance.now(), "retard": 0.0}

        def image_page(kind, frame, canal):
            page["images"] += 1
        get_bridge().sig_frame.connect(image_page)
        vsync = horloges(main)

        def battement():
            t = js.performance.now()
            page["retard"] = max(page["retard"], t - page["prevu"])
            page["prevu"] = t + 50
            QTimer.singleShot(50, battement)
        page["prevu"] = js.performance.now() + 50
        QTimer.singleShot(50, battement)

        def relever_page():
            from qtpy6.web import memoire_partagee
            t0 = js.performance.now()
            js.self.qtpy6_memoire.passer()  # une passe du moteur de réconciliation (tous les segments), chronométrée
            t = js.performance.now()
            tailles = [s.byteLength for s in memoire_partagee._SEGMENTS.values()]
            js.console.log(f"CADENCE page images/s {page['images'] * 1000 / (t - page['t']):.1f}"
                           f" ; pire retard minuterie 50 ms : {page['retard']:.0f} ms"
                           f" ; une passe {t - t0:.1f} ms sur segments {tailles}")
            page.update(images=0, t=t, retard=0.0)
            page["attente"] = page.get("attente", 0) + 1
            page["releves"] += 1 if vsync() else 0  # 25 relevés comptés à partir de la première image du jeu
            if page["releves"] < 25 and page["attente"] < 150:
                QTimer.singleShot(2000, relever_page)
            else:
                js.window.etat = "fini"
        QTimer.singleShot(2000, relever_page)
    clavier =js.URLSearchParams.new(js.location.search).get("clavier") == "1"
    if clavier:  # instrumentation : vrai clic sur l'écran du jeu, puis vraies touches ; focus DOM et Qt relevés
        from qtpy6.QtCore import QEvent, QObject, QPoint
        from qtpy6.QtWidgets import QApplication
        from spyder_pyxel.spyder.bridge_manager import get_bridge
        recu = {"images": 0, "evenements": [], "sig_key": []}

        def dom(quand):
            a = js.document.activeElement
            racine = getattr(a, "shadowRoot", None) if a else None
            b = racine.activeElement if racine else None
            js.console.log(f"CLAVIER {quand} : DOM actif {a.tagName if a else None} classe={getattr(a, 'className', '')!r}"
                           f" ombre {b.tagName if b else None} {getattr(b, 'className', '')!r}"
                           f" id={getattr(a, 'id', '')!r} ; Qt focus {type(QApplication.focusWidget()).__name__}"
                           f" ; événements écran {recu['evenements'][-12:]} ; sig_key {recu['sig_key'][-6:]}")

        def ecouter_dom(e):
            js.console.log(f"CLAVIER DOM {e.type} {e.key!r} cible {e.target.tagName} {getattr(e.target, 'className', '')!r}")
        from pyodide.ffi import create_proxy
        js.window.addEventListener("keydown", create_proxy(ecouter_dom), True)
        if js.URLSearchParams.new(js.location.search).get("refocus") == "1":  # essai du correctif, avant la doublure
            from pyodide.code import run_js
            run_js(REFOCUS)

        class Filtre(QObject):
            def eventFilter(self, objet, e):
                if e.type() in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.FocusIn, QEvent.FocusOut, QEvent.MouseButtonPress):
                    recu["evenements"].append(e.type().name if hasattr(e.type(), "name") else int(e.type()))
                return False
        filtre = Filtre()

        def image(kind, frame, canal):
            recu["images"] += 1
            if recu["images"] != 60:
                return
            ecran = main.get_plugin("pyxel_game").get_widget()._screens.get(canal)
            ecran.installEventFilter(filtre)
            ecran.sig_key.connect(lambda code, appui: recu["sig_key"].append((code, appui)))
            centre = ecran.mapToGlobal(QPoint(ecran.width() // 2, ecran.height() // 2))
            js.console.log(f"CLAVIER écran {ecran.width()}x{ecran.height()} centre global {centre.x()},{centre.y()}"
                           f" visible {ecran.isVisible()} focusPolicy {ecran.focusPolicy()}")
            dom("avant clic")
            js.window.clic = js.JSON.parse(f"[{centre.x()}, {centre.y()}]")
            js.window.etat = "cliquer"
            QTimer.singleShot(200, etape)

        def etape():
            if js.window.etat == "cliquer_fait" and not recu.get("temoin"):
                dom("après clic")
                js.window.texte = "   "
                js.window.etat = "taper"
            elif js.window.etat == "taper_fait":
                dom("après frappe")
                editeur = main.get_plugin("editor").get_current_editor()  # témoin : un clic sur l'éditeur
                c = editeur.viewport().mapToGlobal(QPoint(editeur.viewport().width() // 2, 40))
                js.window.clic = js.JSON.parse(f"[{c.x()}, {c.y()}]")
                js.window.etat = "cliquer"
                recu["temoin"] = True
            elif js.window.etat == "cliquer_fait" and recu.get("temoin"):
                dom(f"après clic éditeur ({type(QApplication.focusWidget()).__name__})")
                js.window.etat = "attente"
                QTimer.singleShot(4000, lambda: (dom("fin"), setattr(js.window, "etat", "fini")))
                return
            QTimer.singleShot(200, etape)
        get_bridge().sig_frame.connect(image)
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
{diagnostic_son if son else diagnostic if diag else diagnostic_clavier if clavier else diagnostic_cadence if cadence else lancement}
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
'''.replace("@DIAG_JEU@", repr(repr(DIAG_JEU))[1:-1]).replace("@DIAG_SON@", repr(repr(DIAG_SON))[1:-1]).replace("@DIAG_CLAVIER@", repr(repr(DIAG_CLAVIER))[1:-1]).replace("@DIAG_CADENCE@", repr(repr(DIAG_CADENCE))[1:-1]) + _fin)
__file__ = os.path.join(_ICI, "spe.py")
exec(compile(_source, __file__, "exec"))
