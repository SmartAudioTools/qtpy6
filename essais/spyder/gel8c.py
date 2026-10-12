"""Essai provisoire (12/10/2026) : où la page gèle après la connexion de la console (jalon 8c). Compte les appels de
chaque méthode Python de qtconsole et de la console de Spyder, imprime un nom quand son compte atteint une puissance de
2 : une boucle Python s'y voit. StdThread neutralisé si GEL_SANS_STD (défaut ici : actif, la page ne lit pas l'env)."""
import functools
import inspect
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preparer  # noqa: E402, F401
T0 = time.monotonic()
SANS_STD = True
compte = {}


def compter(classe):
    for nom, f in list(vars(classe).items()):
        if not inspect.isfunction(f) or nom.startswith("__"):
            continue
        cle = f"{classe.__name__}.{nom}"

        def g(*a, _f=f, _cle=cle, **k):
            n = compte[_cle] = compte.get(_cle, 0) + 1
            if n & (n - 1) == 0 and n >= 256:
                print(f"GEL {time.monotonic() - T0:.2f} {_cle} ×{n}", file=sys.__stdout__, flush=True)
            return _f(*a, **k)
        functools.update_wrapper(g, f)
        setattr(classe, nom, g)


from qtconsole import console_widget, frontend_widget, jupyter_widget, rich_jupyter_widget  # noqa: E402
from spyder.plugins.ipythonconsole.widgets import shell, control  # noqa: E402
from spyder.plugins.ipythonconsole.utils import kernel_handler  # noqa: E402
for m in (console_widget, frontend_widget, jupyter_widget, rich_jupyter_widget, shell, control):
    for _n, c in vars(m).items():
        if inspect.isclass(c) and c.__module__ == m.__name__:
            compter(c)
import importlib  # noqa: E402
from qtpy6.web import bloquant as _bl, fils as _fi  # noqa: E402
_courant = [0, ""]
_num = [0]
_ptt = _bl._pyodide_plus_tard


def _ptt_(f):
    _num[0] += 1
    ident = _num[0]
    nom = getattr(f, "__qualname__", repr(f))
    try:
        cellules = dict(zip(f.__code__.co_freevars, (c.cell_contents for c in f.__closure__ or ())))
        cible = cellules.get("f", f)
        args = cellules.get("args", ())
        ev = cellules.get("evenement")
        if ev is not None and hasattr(ev, "func"):
            fc = dict(zip(ev.func.__code__.co_freevars, (c.cell_contents for c in ev.func.__closure__ or ())))
            cible = fc.get("fn", ev.func)
        if args and hasattr(args[0], "cible"):
            cible = args[0].cible()
        nom = getattr(cible, "__qualname__", repr(cible))[:80]
        soi = getattr(cible, "__self__", None)
        if soi is not None:
            nom += f" [{soi!r}"[:120] + "]"
            cible_fil = getattr(soi, "_target", None) or getattr(soi, "run", None)
            nom += " " + getattr(cible_fil, "__qualname__", "")
        code = getattr(getattr(cible, "__func__", cible), "__code__", None)
        if code:
            nom += f" {code.co_filename.rsplit('/', 2)[-1]}:{code.co_firstlineno}"
    except Exception as e:  # noqa: BLE001
        nom += f" ?{e}"

    def g():
        _courant[:] = [ident, nom]
        if actif[0]:
            print(f"T> {ident} {nom}", file=sys.__stdout__, flush=True)
        try:
            return f()
        finally:
            if actif[0]:
                print(f"T< {ident} {time.monotonic() - T0:.2f}", file=sys.__stdout__, flush=True)
    _ptt(g)


_bl._pyodide_plus_tard = _ptt_
_pause = _fi._pause


def _pause_(ms):
    moi = list(_courant)
    f = sys._getframe(1)
    pile = []
    for _ in range(7):
        if f is None:
            break
        pile.append(f"{f.f_code.co_filename.rsplit('/', 1)[-1]}:{f.f_lineno}:{f.f_code.co_name}")
        f = f.f_back
    r = _pause(ms)
    _courant[:] = moi
    if actif[0]:
        print(f"R {moi[0]} {moi[1][:200]} @ {' < '.join(pile)}", file=sys.__stdout__, flush=True)
    return r


_fi._pause = _pause_
_ps = _bl._peut_suspendre
_non = {}


def _ps_():
    r = _ps()
    if not r and actif[0]:
        f = sys._getframe(1)
        pile = []
        for _ in range(4):
            if f is None:
                break
            pile.append(f"{f.f_code.co_filename.rsplit('/', 1)[-1]}:{f.f_lineno}:{f.f_code.co_name}")
            f = f.f_back
        cle = " < ".join(pile)
        n = _non[cle] = _non.get(cle, 0) + 1
        if n >= 64 and n & (n - 1) == 0:
            print(f"NONSUSP ×{n} tâche {_courant[0]} {cle}", file=sys.__stdout__, flush=True)
    return r


_bl._peut_suspendre = _ps_
_psu = _bl._pyodide_suspendre


def _psu_(brancher):
    f = sys._getframe(1)
    pile = []
    for _ in range(5):
        if f is None:
            break
        pile.append(f"{f.f_code.co_filename.rsplit('/', 1)[-1]}:{f.f_lineno}:{f.f_code.co_name}")
        f = f.f_back
    moi = list(_courant)
    if actif[0] and "_pause" not in pile[1]:
        print(f"S {moi[0]} {' < '.join(pile)}", file=sys.__stdout__, flush=True)
    r = _psu(brancher)
    _courant[:] = moi
    if actif[0] and "_pause" not in pile[1]:
        print(f"RS {moi[0]} {' < '.join(pile)}", file=sys.__stdout__, flush=True)
    return r


_bl._pyodide_suspendre = _psu_
import gc  # noqa: E402
_gc_t = [0.0]


_dernier_battement = [time.monotonic()]
_rapports = [0, 0.0]


def _gc_rappel(phase, info):
    maintenant = time.monotonic()
    if (phase == "start" and actif[0] and maintenant - _dernier_battement[0] > 2 and _rapports[0] < 6
            and maintenant - _rapports[1] > 1):
        import traceback
        _rapports[0] += 1
        _rapports[1] = maintenant
        print(f"CHIEN {maintenant - T0:.2f} battement figé depuis {maintenant - _dernier_battement[0]:.1f} s, tâche "
              f"{_courant[0]} {_courant[1][:120]}\n" + "".join(traceback.format_stack(sys._getframe(1))[-25:]),
              file=sys.__stdout__, flush=True)
    if phase == "start" and info["generation"] < 2:
        return
    if phase == "start":
        _gc_t[0] = time.monotonic()
        print(f"GC start gen {info['generation']} {gc.get_count()} objets {len(gc.get_objects()) if info['generation'] == 2 else ''}",
              file=sys.__stdout__, flush=True)
    elif info["generation"] == 2:
        print(f"GC stop gen {info['generation']} collectés {info['collected']} {time.monotonic() - _gc_t[0]:.2f} s",
              file=sys.__stdout__, flush=True)


gc.callbacks.append(_gc_rappel)
_del_vus = set()


def compter_module(nom_module):
    try:
        m = importlib.import_module(nom_module)
    except Exception as e:  # noqa: BLE001
        print(f"GEL pas de {nom_module} : {e}", file=sys.__stdout__, flush=True)
        return
    for _n, c in list(vars(m).items()):
        if inspect.isclass(c) and c.__module__ == m.__name__:
            compter(c)
        elif inspect.isfunction(c) and c.__module__ == m.__name__:
            setattr(m, _n, compter_fonction(c, f"{nom_module}.{_n}"))


def compter_fonction(f, cle):
    def g(*a, **k):
        n = compte[cle] = compte.get(cle, 0) + 1
        if n & (n - 1) == 0 and n >= 256:
            print(f"GEL {time.monotonic() - T0:.2f} {cle} ×{n}", file=sys.__stdout__, flush=True)
        return f(*a, **k)
    return functools.update_wrapper(g, f)


for _m in ("qtpy6.web.zmq_web", "qtpy6.web.threading_web", "qtpy6.web.fils", "qtpy6.web.sous_processus",
           "qtpy6.web.travailleur", "jupyter_client.channels", "jupyter_client.session", "jupyter_client.client",
           "jupyter_client.threaded", "jupyter_client.manager", "jupyter_core.utils", "qtconsole.client",
           "qtconsole.util", "spyder.api.asyncdispatcher", "spyder.plugins.ipythonconsole.utils.kernel_handler",
           "spyder.plugins.ipythonconsole.comms.kernelcomm", "spyder_kernels.comms.commbase",
           "spyder_kernels.comms.frontendcomm", "spyder.plugins.ipythonconsole.widgets.client",
           "spyder.plugins.editor.panels.classfunctiondropdown",
           "spyder.plugins.editor.panels.codefolding",
           "spyder.plugins.editor.panels.edgeline",
           "spyder.plugins.editor.panels.indentationguides",
           "spyder.plugins.editor.panels.linenumber",
           "spyder.plugins.editor.panels.manager",
           "spyder.plugins.editor.panels.scrollflag",
           "spyder.plugins.editor.panels.utils",
           "spyder.plugins.editor.utils.decoration",
           "spyder.plugins.editor.utils.editor",
           "spyder.plugins.editor.utils.findtasks",
           "spyder.plugins.editor.utils.bookmarks",
           "spyder.plugins.editor.extensions.manager",
           "spyder.plugins.editor.widgets.codeeditor.codeeditor",
           "spyder.plugins.editor.widgets.base",
           "spyder.utils.syntaxhighlighters",
           "spyder.widgets.waitingspinner",
           "superqt.utils._throttler",
           "spyder.plugins.ipythonconsole.widgets.mixins",
           "spyder.plugins.ipythonconsole.widgets.main_widget",
           "spyder.plugins.editor.widgets.editorstack.editorstack",
           "spyder.plugins.statusbar.widgets.status",
           "spyder.api.widgets.status",
           "spyder.plugins.completion.providers.languageserver.provider",
           "spyder.plugins.completion.providers.languageserver.client"):
    compter_module(_m)
if SANS_STD:
    kernel_handler.StdThread.start = lambda self, *a: print("GEL StdThread neutralisé", file=sys.__stdout__, flush=True)

from qtpy6 import QtCore, QtGui, QtWidgets  # noqa: E402
actif = [False]
METHODES = {
    "QWidget": "setStyleSheet setPalette setFont ensurePolished adjustSize setVisible show resize setGeometry "
               "updateGeometry setMinimumSize setMaximumSize setFixedSize setMinimumWidth setMaximumHeight setFocus "
               "setUpdatesEnabled repaint update setLayout",
    "QApplication": "setStyleSheet setPalette setFont",
    "QTextEdit": "setHtml insertHtml setPlainText append setDocument setTabStopDistance setLineWrapMode "
                 "ensureCursorVisible setTextCursor moveCursor setReadOnly setUndoRedoEnabled",
    "QPlainTextEdit": "setPlainText insertPlainText appendPlainText setTabStopDistance ensureCursorVisible "
                      "setTextCursor moveCursor",
    "QTextCursor": "insertHtml insertText insertBlock insertFragment removeSelectedText movePosition setPosition "
                   "beginEditBlock endEditBlock insertImage",
    "QTextDocument": "setDefaultStyleSheet setHtml setPlainText setMaximumBlockCount setDocumentMargin "
                     "setDefaultFont adjustSize setTextWidth",
    "QAbstractScrollArea": "setViewportMargins",
    "QAbstractSlider": "setRange setValue setPageStep setMaximum",
    "QFontMetrics": "horizontalAdvance boundingRect",
}


def envelopper(classe, nom):
    f = getattr(classe, nom, None)
    if f is None:
        return

    def g(*a, **k):
        if not actif[0]:
            return f(*a, **k)
        t = time.monotonic()
        qui = type(a[0]).__name__ if a else ""
        print(f"QT > {qui}.{nom}", file=sys.__stdout__, flush=True)
        try:
            return f(*a, **k)
        finally:
            d = time.monotonic() - t
            print(f"QT < {qui}.{nom} {d * 1000:.0f} ms", file=sys.__stdout__, flush=True)
    setattr(classe, nom, staticmethod(g) if isinstance(inspect.getattr_static(classe, nom), staticmethod) else g)


for _c, _ms in METHODES.items():
    _classe = getattr(QtWidgets, _c, None) or getattr(QtGui, _c)
    for _m in _ms.split():
        envelopper(_classe, _m)
from spyder.plugins.ipythonconsole.widgets.main_widget import IPythonConsoleWidget  # noqa: E402
_cnc = IPythonConsoleWidget._connect_new_client_to_kernel


SURCHARGES = {"event", "eventFilter", "sizeHint", "minimumSizeHint", "paint", "data", "rowCount", "columnCount",
              "headerData", "flags", "index", "parent", "hasChildren", "canFetchMore", "fetchMore", "filterAcceptsRow",
              "lessThan", "highlightBlock", "focusInEvent", "heightForWidth", "hasHeightForWidth", "setVisible",
              "showEvent", "hideEvent", "timerEvent", "customEvent", "changeEvent", "viewportEvent", "keyPressEvent",
              "resizeEvent", "paintEvent", "moveEvent", "wheelEvent", "enterEvent", "leaveEvent", "mouseMoveEvent",
              "closeEvent", "contextMenuEvent", "focusOutEvent", "inputMethodEvent", "sizeHintForColumn",
              "sizeHintForRow", "visualRect", "scrollContentsBy", "updateGeometries", "setModel", "setGeometry"}
_prof = [0]


def suivre_surcharges():
    import types
    n = 0
    for nom_m, m in list(sys.modules.items()):
        if not nom_m.startswith(("spyder", "qtconsole", "superqt", "qtawesome", "spyder_kernels")) or m is None:
            continue
        for c in list(vars(m).values()):
            if not (inspect.isclass(c) and c.__module__ == nom_m):
                continue
            for nom, f in list(vars(c).items()):
                if nom not in SURCHARGES or not isinstance(f, types.FunctionType):
                    continue
                cle = f"{c.__name__}.{nom}"

                def g(*a, _f=f, _cle=cle, **k):
                    _prof[0] += 1
                    print(f"O> {_prof[0]} {_cle}", file=sys.__stdout__, flush=True)
                    try:
                        return _f(*a, **k)
                    finally:
                        print(f"O< {_prof[0]} {_cle}", file=sys.__stdout__, flush=True)
                        _prof[0] -= 1
                functools.update_wrapper(g, f)
                setattr(c, nom, g)
                n += 1
    print(f"GEL surcharges suivies : {n}", file=sys.__stdout__, flush=True)


from qtpy6.QtCore import QObject as _QO  # noqa: E402


class _Filtre(_QO):
    """Tous les événements de l'application, par séries : une ligne au changement, puis aux puissances de deux."""
    dernier, n = None, 0

    vu = [0]

    def eventFilter(self, o, e):
        import js
        n = js.qtpy6Suspension.suspensions
        if n != self.vu[0] and self.vu[0] < 40:
            self.vu[0] = n
            import traceback as _tb
            print(f"PILESUSP {n} " + " < ".join(f"{os.path.basename(fr.filename)}:{fr.lineno}:{fr.name}"
                                                for fr in reversed(_tb.extract_stack()[:-1])), file=sys.__stdout__, flush=True)
        cle = (int(e.type().value) if hasattr(e.type(), "value") else int(e.type()), type(o).__name__)
        js.noter(f"E {time.monotonic() - T0:.3f} {cle}")
        if cle == self.dernier:
            self.n += 1
            if self.n & (self.n - 1) == 0:
                print(f"EV {time.monotonic() - T0:.2f} {cle} x{self.n}", file=sys.__stdout__, flush=True)
        else:
            self.dernier, self.n = cle, 1
            print(f"EV {time.monotonic() - T0:.2f} {cle}", file=sys.__stdout__, flush=True)
        return False


_filtre = _Filtre()


def _cnc_(self, *a, **k):
    suivre_surcharges()
    from qtpy6.QtWidgets import QApplication as _QA
    _QA.instance().installEventFilter(_filtre)
    print("GEL connexion de la console", file=sys.__stdout__, flush=True)
    actif[0] = True
    gc.enable()  # le chien de garde vit dans les passes automatiques
    import js
    import pyodide_js
    js.Function("FS", """
        const ecrire = FS.write, n = new Map();
        FS.write = function (flux, tampon, decalage, longueur, position, canOwn) {
            const r = ecrire.apply(this, arguments);
            const cle = (flux.path || '?') + ' fd ' + flux.fd + ' rend ' + r;
            const c = (n.get(cle) || 0) + 1; n.set(cle, c);
            if (c >= 16 && (c & (c - 1)) === 0) console.log('FSW ' + cle + ' x' + c + ' long ' + longueur);
            return r;
        };""")(pyodide_js.FS)
    js.Function("p", "for (const k of ['alert', 'prompt', 'confirm']) { const f = window[k]; window[k] = (...a) => { console.log('DIALOGUE ' + k + ' ' + String(a[0]).slice(0, 300) + ' ' + new Error().stack.replace(/\\n/g, ' | ').slice(0, 2500)); return k === 'confirm' ? false : null; }; } p.setStdin({ stdin: () => { console.log('STDIN ' + new Error().stack.replace(/\\n/g, ' | ').slice(0, 1500)); return null; } });")(pyodide_js)
    js.Function("""window.addEventListener('error', e => console.log('ERREURJS ' + e.message + ' ' + e.filename + ':' + e.lineno + ' err=' + String(e.error) + ' ' + (e.error && e.error.stack)));
        (() => { const s = window.qtpy6Suspension, t0 = s.tourner; let n = 0, max = 0;
            s.tourner = () => { n++; if (n > max) max = n; if (n >= 32 && (n & (n - 1)) === 0) console.log('MICRO ' + n + ' sans macrotache ' + (performance.now() / 1000).toFixed(2)); return t0(); };
            setInterval(() => { if (n >= 8) console.log('MICRO fin de serie ' + n); n = 0; }, 5); })();
        (() => { const s = window.qtpy6Suspension; let r = s.refus, n = s.suspensions;
            Object.defineProperty(s, 'refus', { get: () => r, set: v => { r = v;
                if ((r & (r - 1)) === 0) console.log('REFUS ' + r + ' prom=' + s.promettant + ' tache=' + s.tache + ' ' + new Error().stack.replace(/\\n/g, ' | ').slice(0, 1500)); } });
            Object.defineProperty(s, 'suspensions', { get: () => n, set: v => { n = v;
                if (n <= 3) console.log('SUSPENSION ' + n + ' ' + new Error().stack.replace(/\\n/g, ' | ').slice(0, 1500)); } }); })();
        (() => { let av = ''; setInterval(() => { const s = window.qtpy6Suspension, M = s && s.M; if (!s) return;
            const e = `susp=${s.suspensions} refus=${s.refus} suspendu=${s.suspendu} qtEnTache=${s.qtEnTache} tache=${s.tache} prom=${s.promettant} gil=${M ? M._PyGILState_Check() : '?'}`;
            if (e !== av) { av = e; console.log('SUSP ' + (performance.now() / 1000).toFixed(2) + ' ' + e); } }, 5); })();
        window.addEventListener('unhandledrejection', e => console.log('REJETJS ' + String(e.reason) + ' ' + (e.reason && e.reason.stack)));""")()
    if os.environ.get("GEL_SANS_CACHE", "1") == "1":
        print("GEL sans cache de noyau", file=sys.__stdout__, flush=True)
        a = (False,) + a[1:]
    return _cnc(self, *a, **k)


IPythonConsoleWidget._connect_new_client_to_kernel = _cnc_


def marquer(classe, nom):
    """Repères bruts autour d'une méthode : le dernier « M> » sans « M< » désigne la boucle."""
    f = getattr(classe, nom)

    def g(*a, **k):
        print(f"M> {time.monotonic() - T0:.2f} {classe.__name__}.{nom}", file=sys.__stdout__, flush=True)
        if nom in ("start_kernel", "__init__") and classe.__name__ != "Comm":
            import traceback as _tb
            print("PILE " + " < ".join(f"{os.path.basename(fr.filename)}:{fr.lineno}:{fr.name}"
                                      for fr in reversed(_tb.extract_stack()[-16:-1])), file=sys.__stdout__, flush=True)
        r = f(*a, **k)
        print(f"M< {time.monotonic() - T0:.2f} {classe.__name__}.{nom}", file=sys.__stdout__, flush=True)
        return r
    setattr(classe, nom, g)


from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler  # noqa: E402
from spyder.plugins.ipythonconsole.utils.manager import SpyderKernelManager  # noqa: E402
import jupyter_client.manager as _jm  # noqa: E402
import jupyter_client.client as _jc  # noqa: E402
for _cl, _ns in ((SpyderKernelManager, "start_kernel _async_start_kernel _async_post_start_kernel _connect_control_socket client _async_launch_kernel _async_pre_start_kernel"),
                 (KernelHandler, "__init__ connect_ connect_std_pipes handle_comm_ready check_spyder_kernel_info"),
                 (_jc.KernelClient, "start_channels")) + tuple(
                    (getattr(__import__(_m, fromlist=[_c]), _c), _ns2) for _m, _c, _ns2 in (
                        ("spyder.plugins.ipythonconsole.comms.kernelcomm", "KernelComm", "open_comm _register_comm _send_call"),
                        ("spyder_kernels.comms.commbase", "CommBase", "_register_comm _send_message remote_call"),
                        ("qtconsole.comms", "CommManager", "new_comm register_comm"),
                        ("qtconsole.comms", "Comm", "__init__ open send _send_msg"),
                        ("jupyter_client.session", "Session", "send serialize msg sign"),
                        ("jupyter_client.channels", "ZMQSocketChannel", "send"),
                        ("qtpy6.web.zmq_web", "Socket", "send send_multipart"))):
    for _n in _ns.split():
        if hasattr(_cl, _n):
            marquer(_cl, _n)
from spyder.plugins.editor.panels.scrollflag import ScrollFlagArea  # noqa: E402


def _uf_(self):
    doc = self.editor.document()
    block, n = doc.firstBlock(), 0
    print(f"UF> {time.monotonic() - T0:.2f} blocs={doc.blockCount()} premier={block.blockNumber()} valide={block.isValid()}",
          file=sys.__stdout__, flush=True)
    while block.isValid():
        n += 1
        if n in (1, 2, 3, 10, 1000, 100000):
            print(f"UF {n} num={block.blockNumber()} pos={block.position()} suivant={block.next().blockNumber()} "
                  f"suivant_valide={block.next().isValid()} type={type(block).__module__}", file=sys.__stdout__, flush=True)
        if n > 200000:
            print("UF ABANDON", file=sys.__stdout__, flush=True)
            break
        block = block.next()
    print(f"UF< {n}", file=sys.__stdout__, flush=True)


ScrollFlagArea._update_flags = _uf_
import asyncio  # noqa: E402
_bc = type(asyncio.get_event_loop())
print(f"GEL boucle {_bc.__qualname__} nest={hasattr(_bc, '_nest_patched')} ruc={_bc.run_until_complete.__qualname__}",
      file=sys.__stdout__, flush=True)


from qtpy6.QtCore import QTimer  # noqa: E402
_b = [0]


def battement():
    _b[0] += 1
    _dernier_battement[0] = time.monotonic()
    if _b[0] % 10 == 0:
        print(f"GEL {time.monotonic() - T0:.2f} battement {_b[0]}", file=sys.__stdout__, flush=True)
    QTimer.singleShot(100, battement)


QTimer.singleShot(0, battement)

import qtpy6.web.calque as _cq
_sync0 = _cq.Calque._synchroniser
_sync_n = [0]
def _sync_(self):
    _sync_n[0] += 1
    n = _sync_n[0]
    t = time.monotonic()
    if n & (n - 1) == 0 or n % 50 == 0:
        print(f"SYNC> {n} {type(self).__name__} {t - T0:.2f}", file=sys.__stdout__, flush=True)
    _sync0(self)
    d = time.monotonic() - t
    if d > 0.05:
        print(f"SYNC lent {n} {d:.3f}s", file=sys.__stdout__, flush=True)
_cq.Calque._synchroniser = _sync_

import qtpy6.web.threading_web as _tw, qtpy6.web.fils as _fi, qtpy6.web.zmq_web as _zw
_att0 = _tw.attendre
_att_n = [0]
def _att_(condition, delai_ms):
    _att_n[0] += 1
    n = _att_n[0]
    t = time.monotonic()
    print(f"ATT> {n} {t - T0:.2f} delai={delai_ms} hote={getattr(_tw._attendre_hote, '__qualname__', None)} {sys._getframe(1).f_code.co_qualname}", file=sys.__stdout__, flush=True)
    r = _att0(condition, delai_ms)
    print(f"ATT< {n} {time.monotonic() - t:.3f}s -> {r}", file=sys.__stdout__, flush=True)
    return r
_tw.attendre = _att_
_zw.attendre = _att_
_pause0 = _fi._pause
_pause_n = [0, 0]
def _pause_(ms):
    t = time.monotonic()
    _pause0(ms)
    d = time.monotonic() - t
    _pause_n[0] += 1
    if d < ms / 2000:
        _pause_n[1] += 1
        k = _pause_n[1]
        if k & (k - 1) == 0:
            print(f"PAUSE courte {k}/{_pause_n[0]} {d*1000:.2f}ms peut={_fi.bloquant._peut_suspendre()} tache={_fi.bloquant._en_tache()}", file=sys.__stdout__, flush=True)
_fi._pause = _pause_

import qtconsole.console_widget as _qcw
for _nm in ("_insert_plain_text", "_insert_html", "_insert_html_fetching_plain_text", "_append_custom", "_insert_plain_text_into_buffer"):
    _f0 = getattr(_qcw.ConsoleWidget, _nm, None)
    if _f0 is None:
        continue
    def _w(self, *a, _f0=_f0, _nm=_nm, **k):
        lg = [len(x) for x in a if isinstance(x, str)]
        t = time.monotonic()
        print(f"TXT> {_nm} {lg} {t - T0:.2f}", file=sys.__stdout__, flush=True)
        r = _f0(self, *a, **k)
        print(f"TXT< {_nm} {time.monotonic() - t:.3f}s doc={self._control.document().characterCount()}", file=sys.__stdout__, flush=True)
        return r
    setattr(_qcw.ConsoleWidget, _nm, _w)

import js as _js
_js.Function("globalThis.anneau = []; globalThis.nnoter = 0; globalThis.noter = (s) => { nnoter++; anneau.push(nnoter + ' ' + s); if (anneau.length > 600) anneau.shift(); }; setInterval(() => console.log('NOTER ' + nnoter + ' ' + anneau.length + ' ' + (anneau[anneau.length-1]||'').slice(0,80)), 250);")()
class _Anneau:
    def __init__(self, f):
        self.f = f
    def write(self, t):
        if t.strip():
            _js.noter(t.rstrip()[:200])
        return self.f.write(t)
    def __getattr__(self, n):
        return getattr(self.f, n)
sys.__stdout__ = _Anneau(sys.__stdout__)
exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon8c.py")).read(), "jalon8c.py", "exec"))
