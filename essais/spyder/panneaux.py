"""Jalon 8c (jalon8c.py) avec les seuls panneaux que l'utilisateur affiche (relevé de son état de fenêtre,
SmartOS/Commun/config_files/spyder_6.1.5/transient.ini, 12/10/2026) : éditeur, console IPython, explorateur de
variables, fichiers, projets, plan, recherche. Les panneaux qu'il n'affiche pas sont désactivés par la configuration de
Spyder (`<section>/enable`), comme le ferait sa page de préférences : Plots (suspect du gel de 8c), aide, aide en ligne,
historique, profileur, pylint. Ils reviendront un par un.

Essai INSTRUMENTÉ (bissection du gel, nuit du 12/10/2026) : chaque bloc « Bissection » est relevé, avec son résultat,
dans notes/2026-10-11 - Doublure zmq, plan.md, section « Relevé des essais »."""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="panneaux-")
import preparer  # noqa: E402, F401  (doublures avant tout import de Spyder)
from spyder.config.manager import CONF  # noqa: E402

SANS = os.environ.get("PANNEAUX_SANS", "plots help onlinehelp historylog profiler pylint completions").split()
for section in SANS:
    CONF.set(section, "enable", False)
print(f"panneaux désactivés : {', '.join(SANS)}", file=sys.__stdout__, flush=True)

# Bissection du gel (12/10/2026) : la pile du gel passe par une lecture de fichier (lseek de _io) dans une tâche asyncio.
from spyder.plugins.ipythonconsole.utils import kernel_handler  # noqa: E402
_run = kernel_handler.StdThread.run


def _run_trace(self):
    print(f"StdThread.run : {type(self._std_buffer).__name__}", file=sys.__stdout__, flush=True)
    if os.environ.get("PANNEAUX_STD", "0") == "1":
        _run(self)


kernel_handler.StdThread.run = _run_trace

if sys.platform == "emscripten":  # instrumentation : ce que le lancement du noyau zippe pour le Worker
    from qtpy6.web import travailleur  # noqa: E402
    _zipper = travailleur._zipper

    def _zipper_trace(dossiers, filtre=None, isoles=()):
        t = time.monotonic()
        print(f"ZIP> {dossiers}", file=sys.__stdout__, flush=True)
        octets = _zipper(dossiers, filtre, isoles)
        print(f"ZIP< {len(octets) / 1048576:.1f} Mio en {time.monotonic() - t:.1f} s", file=sys.__stdout__, flush=True)
        _ZIPS.append(1)
        return octets

    travailleur._zipper = _zipper_trace

if os.environ.get("PANNEAUX_SPIN", "0") != "1":  # bissection : le spinner à 3 ms d'EmptyMessageWidget
    import qtawesome  # noqa: E402
    qtawesome.Spin.start = lambda self: print("SPIN neutralisé", file=sys.__stdout__, flush=True)

if sys.platform == "emscripten":  # bissection : un widget de taille démesurée juste avant le gel
    from spyder.app.mainwindow import MainWindow as _MW  # noqa: E402
    _pvs = _MW.post_visible_setup

    def _pvs_trace(self):
        from qtpy6.QtCore import QTimer
        from qtpy6.QtWidgets import QApplication
        vus = {}

        def relever():
            from qtpy6.QtWidgets import QWidget
            for w in QApplication.allWidgets():
                g = QWidget.geometry(w)  # certaines classes de Spyder redéfinissent geometry()
                if w.isVisible() and (g.width() > 4000 or g.height() > 4000 or g.width() < 0 or g.height() < 0):
                    cle = (type(w).__name__, w.objectName(), g.width(), g.height())
                    if cle not in vus:
                        vus[cle] = 1
                        print(f"GEANT {cle} parent={type(w.parent()).__name__}", file=sys.__stdout__, flush=True)
            QTimer.singleShot(20, relever)
        relever()
        _pvs(self)

    pass  # _pvs_trace retiré : son relevé de tous les widgets toutes les 20 ms figeait la page (12/10)

# Bissection : processEvents appelé depuis Python (qtconsole._show_prompt…) s'imbrique-t-il sans fin ?
from qtpy6.QtCore import QCoreApplication as _QCA  # noqa: E402
import traceback as _tb  # noqa: E402
_pe, _pe_etat = _QCA.processEvents, {"prof": 0, "max": 0, "n": 0}


def _pe_(*a, **k):
    e = _pe_etat
    e["prof"] += 1
    e["n"] += 1
    if e["prof"] > e["max"] or e["n"] % 500 == 0:
        e["max"] = max(e["max"], e["prof"])
        appelant = " < ".join(f"{f.name}:{f.lineno}" for f in _tb.extract_stack(limit=6)[-6:-1])
        print(f"PE prof {e['prof']} n {e['n']} : {appelant}", flush=True)
    if _ZIPS:
        import asyncio as _aio
        try:
            _ct = _aio.current_task()
        except RuntimeError:
            _ct = None
        import js as _js
        _s = _js.qtpy6Suspension
        _cle = (str(_ct)[:90], _s.tache, _s.suspendu, _s.suspensions, _s.refus)
        if _cle != e.get("cle"):
            e["cle"] = _cle
            print(f"CT {_t.monotonic():.2f} {_cle}", flush=True)
    if e["prof"] == 1:  # chien de garde : pile Python imprimée une fois si ce tour dure plus de 4 s
        sys.setprofile(_cg_profil)
    try:
        return _pe(*a, **k)
    finally:
        e["prof"] -= 1


import asyncio.events as _ev  # noqa: E402
_cg = {"t": 0.0, "fait": 0}
_horloge = time.perf_counter
_run = _ev.Handle._run


def _run_(self):  # même garde pour les rappels asyncio lancés par la page (promisingApply), hors processEvents
    _cg["n"] = _cg.get("n", 0) + 1
    if _cg["n"] in (500, 5000, 50000):
        print(f"HANDLE x{_cg['n']} {_horloge() - _cg['t']:.1f} s depuis le battement : {self._callback!r}"[:300],
              file=sys.__stdout__, flush=True)
    if len(_ZIPS) >= 1 and _cg.get("h2", 0) < 400:
        _cg["h2"] = _cg.get("h2", 0) + 1
        cb = self._callback
        interne = [c.cell_contents for c in (getattr(cb, "__closure__", None) or ()) if not isinstance(
            c.cell_contents, (int, bool))]
        n = _cg["h2"]
        import asyncio as _aio, js as _js
        try:
            _ct = _aio.current_task()
        except RuntimeError:
            _ct = None
        _s = _js.qtpy6Suspension
        print(f"CT {n} {str(_ct)[:80]} tache={_s.tache} susp={_s.suspendu} n={_s.suspensions} refus={_s.refus}",
              file=sys.__stdout__, flush=True)
        if n <= 2:
            print("PILE-CT " + " < ".join(f"{f.filename.rsplit('/',2)[-1]}:{f.name}:{f.lineno}" for f in _tb.extract_stack(limit=30)[::-1]),
                  file=sys.__stdout__, flush=True)
        print(f"H2 {n} {cb!r} {interne!r}"[:500], file=sys.__stdout__, flush=True)
        for _c in interne:
            if isinstance(_c, tuple) and _c and hasattr(_c[0], "fonction"):
                _fo = _c[0].fonction
                _co = getattr(_fo, "__code__", None)
                print(f"H2F {n} {getattr(_fo, '__qualname__', '?')} {_co.co_filename if _co else ''}:{_co.co_firstlineno if _co else ''}",
                      file=sys.__stdout__, flush=True)
        try:
            return _run(self)
        finally:
            print(f"H2 fin {n}", file=sys.__stdout__, flush=True)
    sys.setprofile(_cg_profil)
    return _run(self)


def _cg_trace(frame, evenement, arg):
    frame.f_trace_lines = True
    _cg["l"] = _cg.get("l", 0) + 1
    code = frame.f_code
    change = code is not _cg.get("c")
    _cg["c"] = code
    if _cg["l"] % 2000 == 0 or (change and _cg.get("n", 0) < 1500 and not _cg.__setitem__("n", _cg.get("n", 0) + 1)):
        f, noms = frame, []
        while f is not None and len(noms) < 12:
            noms.append(f"{f.f_code.co_name}:{f.f_lineno}@{f.f_code.co_filename.rsplit('/', 3)[-3:]}")
            f = f.f_back
        print(f"LIGNE {_cg['l']} " + " < ".join(noms), file=sys.__stdout__, flush=True)
    return _cg_trace


if sys.platform == "emscripten":  # battement : une tâche JS (macrotâche) ; tant qu'un script dure, il ne bat pas
    import js as _js  # noqa: E402
    from pyodide.ffi import create_proxy as _cp  # noqa: E402

    def _battre():
        _cg["t"] = _horloge()
    _js.setInterval(_cp(_battre), 200)
    _js.eval("setInterval(() => console.log('BAT ' + Date.now() + ' ' + performance.now().toFixed(0)), 1000)")


_ev.Handle._run = _run_


def _cg_profil(frame, evenement, arg):
    if _ZIPS and len(_ZIPS) >= 1:
        _cg["e"] = _cg.get("e", 0) + 1
        if _cg["e"] % 20000 == 0:
            f, noms = frame, []
            while f is not None and len(noms) < 18:
                noms.append(f"{f.f_code.co_name}:{f.f_lineno}@{f.f_code.co_filename.rsplit('/', 2)[-2:][-1]}")
                f = f.f_back
            print(f"ECH {_cg['e']} {_horloge():.2f} " + " < ".join(noms), file=sys.__stdout__, flush=True)


_QCA.processEvents = staticmethod(_pe_)

# Bissection : la pile du gel est du Python pur dans une tâche asyncio. Chien de garde : un QTimer note que la page
# respire ; si un appel Python dure plus de 3 s sans qu'il ait tourné, on imprime la pile Python une fois.
import time as _t  # noqa: E402
from qtpy6.QtCore import QTimer as _QT  # noqa: E402
_ZIPS = []  # rempli par l'enveloppe de _zipper : le garde ne s'arme qu'après le 2e zip
_garde = {"vu": _t.monotonic(), "n": 0, "fait": 0}
_souffle = _QT()
_souffle.timeout.connect(lambda: _garde.__setitem__("vu", _t.monotonic()))
_souffle.start(100)


import asyncio.events as _ev  # noqa: E402


def _armer():
    """Crochet de profil posé DANS l'état de fil de la tâche qui gèle (une reprise JSPI rend un autre état de fil, sans
    lui) : 4 s puis 7 s après l'armement, la pile Python en cours est imprimée."""
    t0 = _t.monotonic()

    def profil(frame, evenement, arg):
        g = _garde
        g["n"] += 1
        if g["n"] % 256 == 0 and g["fait"] < 2 and _t.monotonic() - t0 > 4 + 3 * g["fait"]:
            g["fait"] += 1
            print("GARDE pile Python :\n" + "".join(_tb.format_stack(frame, limit=40)), file=sys.__stdout__, flush=True)
    sys.setprofile(profil)
    run, compte = _ev.Handle._run, [0]

    def run_(self):
        compte[0] += 1
        if compte[0] in (200, 2000, 20000):
            print(f"HANDLE x{compte[0]} {_t.monotonic() - t0:.1f} s : {self._callback!r}"[:400], file=sys.__stdout__,
                  flush=True)
        return run(self)
    _ev.Handle._run = run_


if sys.platform == "emscripten":  # bissection : une attente qui revient tout de suite, appelée en boucle ?
    from qtpy6.web import fils as _fils, zmq_web as _zw  # noqa: E402
    import asyncio as _aio  # noqa: E402

    def _compter(objet, nom):
        f = getattr(objet, nom)
        n = [0]

        def g(*a, **k):
            n[0] += 1
            if n[0] in (3000, 30000, 300000):
                print(f"COMPTE {nom} x{n[0]} :\n" + "".join(_tb.format_stack(limit=25)[:-1]), file=sys.__stdout__,
                      flush=True)
            return f(*a, **k)
        setattr(objet, nom, staticmethod(g) if isinstance(vars(objet).get(nom), staticmethod) else g)

    for _o, _n in ((_zw.Socket, "poll"), (_zw.Poller, "poll"), (_zw.Socket, "recv"), (_zw.Socket, "recv_multipart"),
                   (_zw.Socket, "send"), (_zw.Socket, "send_multipart"), (_zw.PollerAsync, "poll"), (_fils, "_attendre"),
                   (_zw, "attendre"), (_aio, "sleep"), (_t, "sleep"), (_t, "time"), (_t, "monotonic")):
        if hasattr(_o, _n):
            _compter(_o, _n)

if sys.platform == "emscripten" and os.environ.get("PANNEAUX_FILTRE", "1") == "1":  # essai : zip du noyau allégé
    from qtpy6.web import travailleur as _tr  # noqa: E402
    _LOURDS = tuple(f"/home/pyodide/app/{d}/" for d in ("spyder", "pyuca", "qtawesome", "qdarkstyle", "polices"))
    _configurer = _tr.configurer
    _tr.configurer = lambda indexURL, roues=(), filtre=None: _configurer(
        indexURL, roues, lambda chemin: not chemin.startswith(_LOURDS))

if sys.platform == "emscripten":  # bissection : qui lit stdin dans la page (window.prompt de Pyodide, bloquant) ?
    import pyodide_js  # noqa: E402
    from pyodide.ffi import to_js as _to_js  # noqa: E402

    def _stdin():
        print("STDIN lu :\n" + "".join(_tb.format_stack(limit=30)[:-1]), file=sys.__stdout__, flush=True)
        return None
    pyodide_js.setStdin(_to_js({"stdin": _stdin}, dict_converter=__import__("js").Object.fromEntries))

if sys.platform == "emscripten":  # bissection : un report qui se reporte sans fin ?
    from qtpy6.web import bloquant as _bq  # noqa: E402
    from qtpy6.QtCore import QTimer as _QT2  # noqa: E402

    def _compteur(nom, f, cle):
        n = {}

        def g(*a, **k):
            c = cle(a)
            n[c] = n.get(c, 0) + 1
            if n[c] in (500, 5000, 50000):
                print(f"REPORT {nom} {c!r:.120} x{n[c]} :\n" + "".join(_tb.format_stack(limit=12)[:-1]),
                      file=sys.__stdout__, flush=True)
            return f(*a, **k)
        return g
    _bq._plus_tard = _compteur("_plus_tard", _bq._plus_tard,
                               lambda a: getattr(a[0], "__qualname__", repr(a[0])))
    _QT2.singleShot = staticmethod(_compteur("singleShot", _QT2.singleShot,
                                             lambda a: (a[0], getattr(a[-1], "__qualname__", repr(a[-1])))))

if os.environ.get("PANNEAUX_RAYON", "0") == "0":  # bissection : la peinture arrondie d'EmptyMessageWidget gèle-t-elle ?
    from spyder.utils.palette import SpyderPalette as _SP  # noqa: E402
    _SP.SIZE_BORDER_RADIUS = "0px"

if sys.platform == "emscripten":  # bissection : quel widget peint sans fin après le 2e zip ?
    from qtpy6.QtCore import QObject as _QO, QEvent as _QE  # noqa: E402
    from qtpy6.QtWidgets import QApplication as _QA, QWidget as _QW  # noqa: E402

    class _Peintres(_QO):
        n = 0

        def eventFilter(self, objet, evenement):
            if evenement.type() == _QE.Type.Paint and isinstance(objet, _QW) and len(_ZIPS) >= 1 and _Peintres.n < 5000:
                _Peintres.n += 1
                g = _QW.geometry(objet)
                print(f"PAINT {type(objet).__name__} '{objet.objectName()}' {g.width()}x{g.height()} "
                      f"{evenement.rect().width()}x{evenement.rect().height()}", file=sys.__stdout__, flush=True)
            return False
    _peintres = _Peintres()
    _ancien_zip = travailleur._zipper

    def _zip_puis_filtre(*a, **k):
        octets = _ancien_zip(*a, **k)
        if len(_ZIPS) == 1:
            _QA.instance().installEventFilter(_peintres)
        else:
          try:
            _mon = sys.monitoring
            _mon.use_tool_id(4, "boucle")
            _sauts = {}

            def _saut(code, depart, arrivee):
                if arrivee >= depart:
                    return
                cle = (code, depart)
                n = _sauts[cle] = _sauts.get(cle, 0) + 1
                if n in (20000, 200000, 2000000):
                    f, noms = sys._getframe(1), []
                    while f is not None and len(noms) < 16:
                        noms.append(f"{f.f_code.co_name}:{f.f_lineno}@{f.f_code.co_filename.rsplit('/', 2)[-2:]}")
                        f = f.f_back
                    print(f"BOUCLE {n} {code.co_qualname} " + " < ".join(noms), file=sys.__stdout__, flush=True)
            def _debut(code, decalage):
                _cg["ps"] = n = _cg.get("ps", 0) + 1
                if n % 500 == 0:
                    f, noms = sys._getframe(1), []
                    while f is not None and len(noms) < 22:
                        noms.append(f"{f.f_code.co_name}:{f.f_lineno}@{f.f_code.co_filename.rsplit('/', 2)[-2:]}")
                        f = f.f_back
                    print(f"DEBUT {n} {_horloge():.2f} " + " < ".join(noms), file=sys.__stdout__, flush=True)
            _mon.register_callback(4, _mon.events.JUMP, _saut)
            _mon.register_callback(4, _mon.events.PY_START, _debut)
            pass  # sys.monitoring retiré : set_events sur des piles suspendues corrompt le tas
            print(f"MON actif {_mon.get_tool(4)} {_mon.get_events(4)}", file=sys.__stdout__, flush=True)
            pass  # traçage ligne à ligne retiré
          except Exception as e:  # noqa: BLE001
            print(f"MON échec {e!r}", file=sys.__stdout__, flush=True)
        return octets
    travailleur._zipper = _zip_puis_filtre

if sys.platform == "emscripten":  # bissection : qui ouvre un dialogue modal (alert/confirm/prompt) ?
    import js as _js2  # noqa: E402
    _js2.eval("""for (const n of ['alert', 'confirm', 'prompt']) { const f = window[n];
        window[n] = function (...a) { console.log('DIALOGUE ' + n + ' ' + String(a[0]).slice(0, 300) + '\\n' +
            new Error().stack.split('\\n').slice(0, 30).join('\\n')); return f.apply(window, a); }; }""")

from spyder.plugins.console.widgets import main_widget as _cmw  # noqa: E402
_he = _cmw.ConsoleWidget.handle_exception


def _he_(self, error_data, *a, **k):
    print("EXCEPTION " + repr(error_data)[:3000], file=sys.__stdout__, flush=True)
    return _he(self, error_data, *a, **k)


_cmw.ConsoleWidget.handle_exception = _he_

import _suggestions as _sg


def _pile(f, n=14):
    while f is not None and n:
        yield f
        f, n = f.f_back, n - 1
_gen = _sg._generate_suggestions


def _gen_(candidats, nom):
    t = _horloge()
    print(f"SUGG> {len(candidats)} candidats nom={nom[:80]!r} long={len(nom)} max={max(map(len, candidats), default=0)} "
          f"types={sorted({type(c).__name__ for c in candidats})} | " + " < ".join(
              f"{f.f_code.co_name}:{f.f_lineno}" for f in _pile(sys._getframe(1))), file=sys.__stdout__, flush=True)
    try:
        return _gen(candidats, nom)
    finally:
        d = _horloge() - t
        _cg["sg"] = _cg.get("sg", 0) + 1
        if _cg["sg"] < 30 or d > 0.05:
            f, noms = sys._getframe(1), []
            while f is not None and len(noms) < 14:
                noms.append(f"{f.f_code.co_name}:{f.f_lineno}@{f.f_code.co_filename.rsplit('/', 2)[-2:]}")
                f = f.f_back
            print(f"SUGG {_cg['sg']} {d:.3f} s {len(candidats)} candidats nom={nom[:80]!r} long={len(nom)} | "
                  + " < ".join(noms), file=sys.__stdout__, flush=True)


_sg._generate_suggestions = _gen_
from qtpy6.web import travailleur as _tw, zmq_web as _zw  # noqa: E402


def _marquer(cls_ou_mod, nom, etiquette):
    ancien = getattr(cls_ou_mod, nom)

    def enveloppe(*a, **k):
        if len(_ZIPS) < 2:
            return ancien(*a, **k)
        _cg["m"] = n = _cg.get("m", 0) + 1
        if n < 3000:
            print(f"E> {n} {etiquette}", file=sys.__stdout__, flush=True)
        try:
            return ancien(*a, **k)
        finally:
            if n < 3000:
                print(f"E< {n} {etiquette}", file=sys.__stdout__, flush=True)
    setattr(cls_ou_mod, nom, enveloppe)


_marquer(_tw.ProcessusWeb, "_recevoir", "ProcessusWeb._recevoir")
_marquer(_zw, "recevoir", "zmq_web.recevoir")
for _nom in dir(_tw):
    _o = getattr(_tw, _nom)
    if isinstance(_o, type) and "_recevoir" in vars(_o) and _o is not _tw.ProcessusWeb:
        _marquer(_o, "_recevoir", f"{_nom}._recevoir")
import os as _os  # noqa: E402
_ul = {"n": 0}
for _nom in ("unlink", "remove", "rmdir"):
    def _fab(f0, nom):
        def f_(chemin, *a, **k):
            _ul["n"] += 1
            n = _ul["n"]
            if n <= 5 or n % 1000 == 0:
                print(f"UL {nom} {n} {chemin!r} < " + " < ".join(
                    f"{f.filename.rsplit('/', 2)[-1]}:{f.name}:{f.lineno}" for f in _tb.extract_stack(limit=12)[-2::-1]),
                    file=sys.__stdout__, flush=True)
            return f0(chemin, *a, **k)
        return f_
    setattr(_os, _nom, _fab(getattr(_os, _nom), _nom))
# Bissection (12/10) : qui lance le second noyau ? (relance automatique de jupyter_client, ou Spyder)
import traceback as _tb  # noqa: E402
from jupyter_client import manager as _jcm  # noqa: E402
from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler as _KH  # noqa: E402
for _cls, _nom in ((_jcm.KernelManager, "_async_restart_kernel"), (_jcm.KernelManager, "_async_start_kernel")):
    _orig = getattr(_cls, _nom)
    def _f(self, *a, _orig=_orig, _nom=_nom, **k):
        print(f"KM {_nom}", "".join(_tb.format_stack(limit=8)).replace("\n", " | "), file=sys.__stdout__, flush=True)
        return _orig(self, *a, **k)
    setattr(_cls, _nom, _f)
_nfs = _KH.new_from_spec.__func__
_KH.new_from_spec = classmethod(lambda cls, *a, **k: (print("KH new_from_spec", "".join(_tb.format_stack(limit=10)).replace("\n", " | "), file=sys.__stdout__, flush=True), _nfs(cls, *a, **k))[1])
from jupyter_client import restarter as _rs  # noqa: E402
_poll = _rs.KernelRestarter.poll
def _poll_(self):
    print(f"RESTARTER poll alive={self.kernel_manager.is_alive()}", file=sys.__stdout__, flush=True)
    return _poll(self)
_rs.KernelRestarter.poll = _poll_
# Bissection (12/10) : sans le noyau de réserve que Spyder démarre pour la console suivante (mixins.get_cached_kernel)
from spyder.plugins.ipythonconsole.widgets import mixins as _mx  # noqa: E402
_gck = _mx.CachedKernelMixin.get_cached_kernel
_mx.CachedKernelMixin.get_cached_kernel = lambda self, spec, cache=True: _gck(self, spec, cache=False)
# Bissection (12/10) : le gel suit les StdThread ; où exactement ? (connect_std_pipes, start_channels)
from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler as _KH3  # noqa: E402
for _n3 in ("connect_std_pipes", "connect_"):
    if hasattr(_KH3, _n3):
        def _w3(self, *a, _o=getattr(_KH3, _n3), _n=_n3, **k):
            print(f"KH3 {_n} >", file=sys.__stdout__, flush=True)
            r = _o(self, *a, **k)
            print(f"KH3 {_n} <", file=sys.__stdout__, flush=True)
            return r
        setattr(_KH3, _n3, _w3)
from qtconsole import client as _qcl  # noqa: E402
_sc = _qcl.QtKernelClient.start_channels
def _sc_(self, *a, **k):
    print("KC start_channels >", file=sys.__stdout__, flush=True)
    r = _sc(self, *a, **k)
    print("KC start_channels <", file=sys.__stdout__, flush=True)
    return r
_qcl.QtKernelClient.start_channels = _sc_
# Bissection (12/10) : après KernelHandler.connect_, quel appel du widget console ne rend pas la main ?
import functools as _ft4  # noqa: E402
_TR4 = {"n": 0, "on": False}
def _trace4(cls):
    for _nom, _v in list(vars(cls).items()):
        if callable(_v) and not isinstance(_v, type) and not _nom.startswith("__") and _nom != "eventFilter" and type(_v).__name__ == "function":
            def _w(*a, _v=_v, _q=f"{cls.__name__}.{_nom}", **k):
                if not _TR4["on"] or _TR4["n"] > 3000:
                    return _v(*a, **k)
                _TR4["n"] += 1
                print(f"W> {_q}", file=sys.__stdout__, flush=True)
                r = _v(*a, **k)
                print(f"W< {_q}", file=sys.__stdout__, flush=True)
                return r
            setattr(cls, _nom, _ft4.wraps(_v)(_w))
from spyder.plugins.ipythonconsole.widgets import shell as _sh4, client as _cl4  # noqa: E402
for _c4 in _sh4.ShellWidget.__mro__ + (_cl4.ClientWidget,):
    if _c4.__module__.split(".")[0] in ("spyder", "qtconsole"):
        _trace4(_c4)
_cx4 = _KH3.connect_
def _cx4_(self, *a, **k):
    _TR4["on"] = True
    return _cx4(self, *a, **k)
_KH3.connect_ = _cx4_
# Bissection (12/10) : les messages du Worker (onmessage, hors WebLoop : invisibles des traces H2)
if sys.platform == "emscripten":
    from qtpy6.web import travailleur as _tv5  # noqa: E402
    _rc5 = _tv5.ProcessusWeb._recevoir
    _N5 = [0]
    def _rc5_(self, ev):
        _N5[0] += 1
        t = time.monotonic()
        try:
            cles = list(ev.data.to_py())
        except Exception:  # noqa: BLE001
            cles = "?"
        if _N5[0] <= 40:
            print(f"RM> {_N5[0]} {cles}", file=sys.__stdout__, flush=True)
        r = _rc5(self, ev)
        d = time.monotonic() - t
        if _N5[0] <= 40 or d > 0.05:
            print(f"RM< {_N5[0]} {d * 1000:.0f} ms", file=sys.__stdout__, flush=True)
        return r
    _tv5.ProcessusWeb._recevoir = _rc5_
# Bissection (12/10) : ce que la console interne reçoit juste avant le gel
from spyder.plugins.console.widgets import internalshell as _is6  # noqa: E402
_w6 = _is6.InternalShell.write
def _w6_(self, text, *a, **k):
    print(f"IS write {len(str(text))} {str(text)[:300]!r}", file=sys.__stdout__, flush=True)
    t = time.monotonic()
    r = _w6(self, text, *a, **k)
    print(f"IS write fin {(time.monotonic() - t) * 1000:.0f} ms", file=sys.__stdout__, flush=True)
    return r
_is6.InternalShell.write = _w6_
# Bissection (12/10) : l'erreur que la console affiche (l'explorateur de variables montre _ErroredMessageWidget)
import traceback as _tb7  # noqa: E402
from spyder.plugins.ipythonconsole.widgets import client as _cl7  # noqa: E402
_ske7 = _cl7.ClientWidget.show_kernel_error
def _ske7_(self, error, *a, **k):
    print(f"ERREUR NOYAU {str(error)[:1500]!r}", file=sys.__stdout__, flush=True)
    print("".join(_tb7.format_stack(limit=12)).replace("\n", " | ")[:2000], file=sys.__stdout__, flush=True)
    return _ske7(self, error, *a, **k)
_cl7.ClientWidget.show_kernel_error = _ske7_
# Bissection (12/10) : le gel dépend-il du Worker du noyau ? On le termine dès son lancement.
if sys.platform == "emscripten":
    _st8 = _tv5.ProcessusWeb.start
    def _st8_(self, *a, **k):
        r = _st8(self, *a, **k)
        pass  # self.worker.terminate() : essai fait, le gel persiste sans Worker
        print("WORKER termine", file=sys.__stdout__, flush=True)
        return r
    _tv5.ProcessusWeb.start = _st8_
# Bissection (12/10) : sans les widgets web (option de Spyder --no-web-widgets : page de chargement de la console, aide)
if os.environ.get("PANNEAUX_WEB", "0") == "0":
    from spyder.app import cli_options as _co9  # noqa: E402
    _go9 = _co9.get_options
    _co9.get_options = lambda argv=None: _go9(list(argv or []) + ["--no-web-widgets"])
exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon8c.py")).read(), "jalon8c.py", "exec"))
