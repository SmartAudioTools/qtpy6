"""Les appels BLOQUANTS de Qt dans le navigateur : ``exec()`` des boîtes, des menus, des boucles d'événements et de
l'application, et les boîtes statiques (``QMessageBox.question``, ``QFileDialog.getOpenFileName``…). Qt-WASM ne sait pas
imbriquer une boucle d'événements : un ``exec()`` natif y arrête tout le programme (``Aborted()``).

Ce qui les rend possibles : JSPI, la suspension de pile de WebAssembly (``pyodide.ffi.run_sync``). ``exec()`` suspend
l'appel Python en cours jusqu'au signal de fin (``finished``, ``aboutToHide``, ``quit``…) pendant que la page, Qt et
les autres slots continuent ; puis il rend la valeur, comme en natif. Une suspension n'est possible que si l'appel Python
a été lancé de façon « promettante » : c'est le cas du script principal (``runPythonAsync``) et d'une tâche de la boucle
asyncio de Pyodide, pas d'un slot que Qt appelle directement. D'où ``connect`` : un slot Python que Qt appelle dans une
entrée non suspendable est reporté à la tâche suivante de la boucle asyncio (le même tour de la page, juste après), où
il peut suspendre. Appelé depuis du Python déjà suspendable (``emit`` du code, ``click()``…), il reste immédiat.

Hors slot, dans une méthode virtuelle (``contextMenuEvent``, ``mousePressEvent``…) que Qt appelle directement, rien ne
peut suspendre : ``exec()`` y ouvre sans bloquer et rend la valeur d'un abandon (``Rejected``, None), avec un
avertissement. Les doublures sont posées par ``QtCore``, ``QtGui`` et ``QtWidgets`` de qtpy6 sous Pyodide, sur les
classes de la liaison elle-même (``PyQt6.QtWidgets.QDialog.exec`` compris), PyQt6 ou PySide6 : rien ici ne dépend de
l'une ou de l'autre, hors les deux lignes de ``_mort``."""

import functools
import inspect
import os
import sys
import time
import types

# Les quatre primitives de Pyodide, remplacées par tests/test_web.py pour éprouver le reste hors navigateur.


def _pyodide_peut():
    try:
        from pyodide.ffi import can_run_sync  # noqa: PLC0415
    except ImportError:
        return False
    return can_run_sync()


def _pyodide_suspendre(brancher):
    """Suspend l'appel en cours jusqu'à ce que ``brancher(resoudre)`` ait appelé ``resoudre(valeur)`` ; rend la valeur."""
    import asyncio  # noqa: PLC0415

    from pyodide.ffi import run_sync  # noqa: PLC0415

    fut = asyncio.get_event_loop().create_future()
    brancher(lambda valeur=None: fut.done() or fut.set_result(valeur))
    return run_sync(fut)


def _pyodide_plus_tard(f):
    import asyncio  # noqa: PLC0415

    asyncio.get_event_loop().call_soon(f)


def _pyodide_signaler(actif):
    """Dit à qtpy6web.js (``boucles_qt``) si le code en cours est une tâche promettante de ``_plus_tard`` : Qt peut alors y
    suspendre ses propres boucles (QDrag.exec), comme dans la pompe. Sans boucles_qt, ou hors navigateur, rien."""
    try:
        import js  # noqa: PLC0415
    except ImportError:
        return
    s = getattr(js, "qtpy6Suspension", None)
    if s is not None:
        s.tache = actif
        if not actif:
            s.qtEnTache = False


_pompe = []


def _pyodide_pomper(ns, periode=10):
    """Fait tourner la boucle d'événements de Qt : compilé avec JSPI, Qt-WASM n'envoie ni minuteries ni événements postés
    de lui-même, il attend qu'on reprenne SA boucle ``exec()`` suspendue (``onTimer`` : ``if (useAsyncify()) return;``,
    qeventdispatcher_wasm.cpp) — celle qu'on ne peut pas lancer, imbriquée elle arrête tout. Mesuré : sans pompe, un
    ``QTimer`` s'arrête dès que la page cesse de redessiner. Un appel de la page, où les slots sont reportés (``connect``) :
    rien de Python n'y suspend au milieu de ``processEvents`` ; seul Qt peut y suspendre sa propre boucle (``qtpy6Pomper``)."""
    if _pompe:
        return
    try:
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy  # noqa: PLC0415
    except ImportError:  # tests/test_web.py, qui simule le navigateur sans Pyodide : sa boucle native fait tourner Qt
        return
    QCoreApplication, QEvent = ns["QCoreApplication"], ns["QEvent"]

    def tour():
        global _pompe_tourne
        app = QCoreApplication.instance()
        if app is not None:
            # promettante (qtpy6Pomper), elle n'est pas pour autant une entrée où Python peut suspendre : un dialogue
            # ouvert par un slot l'arrêterait, et avec elle Qt, qui doit le fermer. Les slots y restent reportés.
            _pompe_tourne = True
            try:
                app.processEvents()
            finally:
                _pompe_tourne = False
            # les deleteLater : processEvents ne les fait jamais hors d'une boucle exec() (doc de Qt), et il n'y en a pas.
            # Mesuré (01/10/2026) : sans cela, rien de ce qui est détruit par deleteLater ne l'était, et un widget
            # resté à l'écran, son objet Python libéré, s'y peignait en widget natif (la case de SmartTeacher).
            # Jamais pendant qu'une pile est suspendue (exec() d'un dialogue) : le bureau ne détruit qu'au retour dans
            # la boucle qui a appelé deleteLater, et un slot qui a fait deleteLater avant exec() retrouve son objet
            # vivant au retour. Mesuré (01/10/2026, scénario « suspendu ») : sans cette garde, RuntimeError au retour
            if _suspendus == 0:
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    # La pompe promettante de qtpy6web.js (``boucles_qt``), quand elle est là : Qt peut y suspendre ses boucles imbriquées
    # (QDrag.exec).
    pomper = getattr(js, "qtpy6Pomper", None)
    _pompe.append(pomper(create_proxy(tour), periode) if pomper else js.setInterval(create_proxy(tour), periode))


# ``can_run_sync()`` ment pendant qu'une entrée est suspendue : un slot que Qt appelle alors y voit True, mais un
# ``run_sync`` n'y reprend jamais (mesuré : ni retour ni erreur). D'où la comptabilité : ``_actif`` dit que le code en
# cours est une entrée promettante connue (tâche de ``_plus_tard``, ou reprise après ``_suspendre``), ``_suspendus``
# combien de piles attendent. Sans pile suspendue, ``can_run_sync()`` dit vrai (le script principal de runPythonAsync).
_actif = False
_suspendus = 0
_reportes = 0  # tâches de ``_plus_tard`` pas encore finies
_garde = None  # pose (True) ou retire (False) la garde des destructions différées : ``doubler_qtcore``
_pompe_tourne = False  # la pompe est dans processEvents (et Qt y a peut-être suspendu un QDrag.exec)


def _peut_suspendre():
    return _pyodide_peut() and (_actif or (_suspendus == 0 and not _pompe_tourne))


def _suspendre(brancher):
    global _actif, _suspendus
    avant, _actif = _actif, False
    _pyodide_signaler(False)
    _suspendus += 1
    try:
        return _pyodide_suspendre(brancher)
    finally:
        _suspendus -= 1
        _actif = avant or _suspendus > 0  # repris : promettant, et le seul à pouvoir le dire tant qu'un autre attend
        _pyodide_signaler(_actif)


def _plus_tard(f, *args):
    """``f(*args)`` à la tâche suivante de la boucle asyncio, une entrée où il peut suspendre. Une exception va à
    ``sys.excepthook``, comme celle d'un slot en natif (asyncio, lui, se contenterait de la journaliser)."""
    global _reportes

    def tache():
        global _actif, _reportes
        avant, _actif = _actif, True
        _pyodide_signaler(True)
        try:
            f(*args)
        except Exception:  # noqa: BLE001
            sys.excepthook(*sys.exc_info())
        finally:
            _actif = avant
            _pyodide_signaler(avant)
            _reportes -= 1
            if not _reportes and _garde:
                _garde(False)

    if not _reportes and _garde:
        _garde(True)
    _reportes += 1
    _pyodide_plus_tard(tache)



_averti = set()


def _avertir(quoi):
    if quoi not in _averti:
        _averti.add(quoi)
        print(f"qtpy6.web : {quoi} appelé hors d'un slot (méthode virtuelle ?) : rien ne peut y suspendre, il ne bloque "
              "pas et rend la valeur d'un abandon", file=sys.stderr)


def attendre_signal(signal, _connect=None):
    """Suspend jusqu'à la prochaine émission de ``signal`` ; rend ses arguments (un tuple)."""
    def brancher(resoudre):
        def une_fois(*args):
            signal.disconnect(une_fois)
            resoudre(args)
        (_connect or type(signal).connect)(signal, une_fois)
    return _suspendre(brancher)


# --- connect : les slots venus de Qt passent par la boucle asyncio ---------------------------------------------------

_connect_qt = []  # le connect de la liaison, avant la doublure
_expediteur = []  # l'expéditeur d'un slot reporté, que ``QObject.sender()`` rend pendant son exécution


def _est_destroyed(signal):
    """``signal`` est-il ``destroyed`` ? Son nom n'a pas la même porte : ``signal.signal`` sous PyQt6 (``"2destroyed(QObject*)"``),
    ``str()`` seulement sous PySide6 (``"<PySide6.QtCore.SignalInstance destroyed() at 0x…>"``)."""
    nom = getattr(signal, "signal", None) or str(signal).split(" ")[1]
    return nom.lstrip("2").startswith("destroyed(")


def _mort():
    """Rend la fonction qui dit si l'objet C++ d'un receveur a été détruit (la seule chose que chaque liaison nomme autrement)."""
    from .. import PYQT6  # noqa: PLC0415

    if PYQT6:
        from PyQt6 import sip  # noqa: PLC0415
        return lambda objet: isinstance(objet, sip.simplewrapper) and sip.isdeleted(objet)
    import shiboken6  # noqa: PLC0415
    return lambda objet: not shiboken6.isValid(objet)  # True pour un objet Python ordinaire


def _detruire():
    """Rend la fonction qui détruit l'objet C++ d'un QObject, comme le ferait son DeferredDelete."""
    from .. import PYQT6  # noqa: PLC0415

    if PYQT6:
        from PyQt6 import sip  # noqa: PLC0415
        return sip.delete
    import shiboken6  # noqa: PLC0415
    return shiboken6.delete


def _nb_arguments(slot):
    """Combien d'arguments positionnels ``slot`` accepte (None : autant qu'on veut). La liaison tronque ceux du signal à ce
    nombre ; le relais doit faire de même."""
    if type(slot) is functools.partial and not slot.keywords:  # functools.partial(self.methode, x) : un relais par question
        n = _nb_arguments(slot.func)  # d'un sujet, inspect.signature 0,12 ms chacun dans le navigateur (02/10/2026)
        return None if n is None else max(0, n - len(slot.args))
    fonction = getattr(slot, "__func__", slot)
    if type(fonction) is types.FunctionType and not hasattr(fonction, "__wrapped__"):
        # lu sur le code : inspect.signature coûtait 0,4 s sur les 3 300 connexions de l'ouverture d'un sujet (02/10/2026)
        code = fonction.__code__
        if code.co_flags & inspect.CO_VARARGS:
            return None
        return code.co_argcount - (fonction is not slot)  # une méthode liée : son premier paramètre est déjà pris
    try:
        parametres = inspect.signature(slot).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_POSITIONAL for p in parametres):
        return None
    return sum(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in parametres)


def doubler_qtcore(ns):
    """Pose les doublures dans l'espace de noms de ``qtpy6.QtCore`` (la liaison ; ses noms PySide6 y sont déjà)."""
    import weakref  # noqa: PLC0415

    QObject, QCoreApplication, QEventLoop, QEvent = ns["QObject"], ns["QCoreApplication"], ns["QEventLoop"], ns["QEvent"]
    signal_lie = ns["SignalInstance"]
    connect, disconnect, sender = signal_lie.connect, signal_lie.disconnect, QObject.sender
    mort = _mort()
    # Un seul relais par slot : la liaison reconnaît ainsi un doublon (UniqueConnection) et le retrouve (disconnect(slot)).
    # Référence faible : c'est la connexion qui le garde en vie, comme le slot qu'il remplace.
    relais = weakref.WeakValueDictionary()

    def cle(slot, direct):
        return (id(slot.__self__), slot.__func__, direct) if isinstance(slot, types.MethodType) else (slot, direct)

    def existant(slot, direct):
        """Le relais déjà posé pour ``slot`` (None sinon, ou si ``slot`` ne se hache pas)."""
        try:
            r = relais.get(cle(slot, direct))
        except TypeError:
            return None
        return r if r is not None and r.cible() is not None else None  # ``id`` réutilisé par un autre receveur, l'ancien étant mort

    def relayer(slot, direct):
        """Ce qui est connecté à la place de ``slot`` : l'appelable du relais, un par slot."""
        r = existant(slot, direct)
        if r is None:
            r = nouveau_relais(slot, direct)
            try:
                relais[cle(slot, direct)] = r
            except TypeError:  # un appelable qui ne se hache pas : un relais à chaque connexion
                pass
        return r.appel

    class Relais(QObject):
        """Le relais d'une méthode d'un QObject : lui-même un QObject, enfant du receveur. Il meurt avec lui, comme la
        connexion native (aucune liaison ne garde un receveur en vie), et c'est le seul moyen, sous PySide6, de connaître
        l'expéditeur depuis un slot Python : ``sender()`` n'y vaut que sur le receveur Qt lui-même."""

        def __init__(self, slot, direct):
            super().__init__(slot.__self__)
            self.ref, self.fonction, self.direct, self.n = weakref.ref(slot.__self__), slot.__func__, direct, _nb_arguments(slot)
            self.appel = self.relais

        def cible(self):
            objet = self.ref()
            return None if objet is None or mort(objet) else types.MethodType(self.fonction, objet)

        def relais(self, *args):
            return _relayer(self, args, self.sender())

    class RelaisFonction:
        """Le relais d'un autre appelable (fonction, lambda, méthode d'un objet qui n'est pas un QObject) : un appelable
        ordinaire, que la connexion garde en vie et libère avec l'expéditeur, comme elle le ferait du slot."""

        def __init__(self, slot, direct):
            self.direct, self.n = direct, _nb_arguments(slot)
            if isinstance(slot, types.MethodType):  # le receveur n'est pas gardé en vie par la connexion : ni par le relais
                self.ref, self.fonction = weakref.ref(slot.__self__), slot.__func__
            else:
                self.ref, self.fonction = None, slot

        def cible(self):
            if self.ref is None:
                return self.fonction
            objet = self.ref()
            return None if objet is None or mort(objet) else types.MethodType(self.fonction, objet)

        def __call__(self, *args):
            app = QCoreApplication.instance()  # PyQt6 : l'expéditeur est celui du slot en cours, quel que soit l'objet
            return _relayer(self, args, sender(app) if app is not None else None)

        appel = property(lambda self: self)

    def nouveau_relais(slot, direct):
        if isinstance(slot, types.MethodType) and isinstance(slot.__self__, QObject) and not mort(slot.__self__):
            return Relais(slot, direct)
        return RelaisFonction(slot, direct)

    def _relayer(r, args, exp):
        # Un QEvent passé en argument (Spyder : sig_key_pressed.emit(event) dans keyPressEvent) ne vit que le temps du
        # dispatch, et l'émetteur lit son accept() juste après l'emit : reporté, le slot lirait un objet C++ détruit et
        # son accept() viendrait trop tard (une touche insérée deux fois, Entrée perdue). Il s'exécute donc sur place.
        if r.direct or _peut_suspendre() or any(isinstance(a, QEvent) for a in args):
            return executer(r, exp, args)  # appelé tout de suite, mais par le relais : sender() n'y vaut que par _expediteur
        _plus_tard(executer, r, exp, args)
        return None

    def executer(r, exp, args):
        f = r.cible()
        if f is not None:
            _expediteur.append(exp)
            try:
                return f(*args[:r.n] if r.n is not None else args)
            finally:
                _expediteur.pop()
        return None

    def connect_(self, slot, *args, **kwargs):
        if isinstance(slot, (signal_lie, types.BuiltinFunctionType, types.BuiltinMethodType)) or not callable(slot):
            return connect(self, slot, *args, **kwargs)
        return connect(self, relayer(slot, _est_destroyed(self)), *args, **kwargs)  # destroyed : après, trop tard

    def disconnect_(self, *args):
        if len(args) == 1 and callable(args[0]) and not isinstance(args[0], signal_lie):
            r = existant(args[0], _est_destroyed(self))
            if r is not None:  # sinon, connecté sans relais (le connect de la liaison, ``_connect_qt``), ou pas du tout
                return disconnect(self, r.appel)
        return disconnect(self, *args)

    # La garde des destructions différées. En natif, un slot passe avant le retour à la boucle, donc avant toute
    # destruction différée, et le code le suppose : le slot de ``accepted`` d'une fenêtre ``WA_DeleteOnClose`` y lit encore
    # ses widgets. Reporté, il passe après le tour de Qt qui a détruit la fenêtre, et levait RuntimeError (les
    # signalements de SmartTeacher perdus au vrai clic, 09/10/2026). Tant qu'un slot reporté attend, un filtre de
    # l'application retient donc les DeferredDelete, et le dernier slot fini détruit ce qu'il a retenu. Posé seulement
    # pendant cette attente : un filtre Python permanent verrait passer chaque événement de Qt. Détruit directement, pas
    # par un nouveau deleteLater : Qt n'en poste qu'un par objet (``deleteLaterCalled``), le second serait sans effet.
    detruire = _detruire()
    retenus = []

    class Garde(QObject):
        def eventFilter(self, objet, evenement):
            if evenement.type() == QEvent.Type.DeferredDelete:
                retenus.append(objet)
                return True
            return False

    garde = []

    def garder(actif):
        app = QCoreApplication.instance()
        if actif:
            if app is not None and not garde:
                garde.append(Garde())
                app.installEventFilter(garde[0])
            return
        if garde:
            if app is not None:
                app.removeEventFilter(garde[0])
            garde.pop().deleteLater()  # pas dans un filtre en cours d'appel : à la boucle suivante
        while retenus:
            objet = retenus.pop(0)
            if not mort(objet):
                detruire(objet)

    global _garde
    _garde = garder

    def sender_(self):
        s = sender(self)
        return s if s is not None or not _expediteur else _expediteur[-1]

    signal_lie.connect, signal_lie.disconnect, QObject.sender = connect_, disconnect_, sender_
    _connect_qt.append(connect)

    # QTimer.singleShot(ms, fonction) : la fonction est un slot comme un autre, que Qt appelle hors entrée suspendable.
    un_coup = ns["QTimer"].singleShot

    def un_coup_(ms, *args):
        f = args[-1] if args else None
        if callable(f) and not isinstance(f, (signal_lie, types.BuiltinFunctionType, types.BuiltinMethodType)):
            args = (*args[:-1], relayer(f, direct=False))
        return un_coup(ms, *args)

    ns["QTimer"].singleShot = staticmethod(un_coup_)

    # Pas de fils dans le navigateur : un objet reste où il est. Remplacées même si la liaison les a : PyQt6-WASM n'a ni l'une
    # ni l'autre, PySide6-WASM les a mais sans le type QThread (Qt sans fils), si bien que thread() échoue en laissant son
    # erreur posée (« returned a result with an exception set » à l'appel suivant) et que moveToThread refuse notre QThread.
    QObject.moveToThread = lambda self, thread: None
    QObject.thread = lambda self: ns["QThread"].currentThread()

    # QEventLoop.exec : suspendre jusqu'à quit()/exit().
    def boucle_exec(self, flags=None):
        if not _peut_suspendre():
            _avertir("QEventLoop.exec()")
            return -1
        self._qtpy6_fin = []
        try:
            return _suspendre(self._qtpy6_fin.append)
        finally:
            del self._qtpy6_fin

    def boucle_exit(self, code=0):
        for resoudre in getattr(self, "_qtpy6_fin", ()):
            resoudre(code)

    QEventLoop.exec = boucle_exec
    QEventLoop.exit = boucle_exit
    QEventLoop.quit = lambda self: boucle_exit(self, 0)
    QEventLoop.isRunning = lambda self: bool(getattr(self, "_qtpy6_fin", None))

    # processEvents : jamais de suspension. Quand qtpy6web.js lui donne la JSPI (boucles_qt), Qt-WASM suspend dans tout
    # processEvents pour laisser passer les événements du navigateur, sauf sous EventLoopExec (sendNativeEvents,
    # qeventdispatcher_wasm.cpp) ; hors entrée promettante (runPython de la page), cette suspension tue Pyodide
    # (« No matching WebAssembly.promising », mesuré le 05/10/2026). Les événements en attente sont envoyés quand même.
    traiter = QCoreApplication.processEvents
    Drapeau = QEventLoop.ProcessEventsFlag

    def traiter_(*args, **kwargs):
        drapeaux = kwargs.pop("flags", args[0] if args else Drapeau.AllEvents)
        return traiter(drapeaux | Drapeau.EventLoopExec, *args[1:], **kwargs)

    QCoreApplication.processEvents = staticmethod(traiter_)

    doubler_exec_application(QCoreApplication)
    QCoreApplication.quit = staticmethod(lambda: _quitter(0))
    QCoreApplication.exit = staticmethod(lambda code=0: _quitter(code))
    _pyodide_pomper(ns)  # dès le chargement de QtCore : avec ou sans exec(), c'est elle qui fait tourner Qt


_fin_application = []
_au_demarrage = []  # appelés quand l'application entre dans exec() : ``lancer`` y prévient la page


def _quitter(code):
    while _fin_application:
        _fin_application.pop()(code)


def doubler_exec_application(classe):
    """``exec()`` de QCoreApplication, QGuiApplication, QApplication (chacune a le sien) : suspendre jusqu'à ``quit()`` ou
    à la fermeture de la dernière fenêtre. Hors entrée suspendable (une page qui appelle le module de façon synchrone),
    rend 0 tout de suite : la page tient l'application en vie d'elle-même."""
    def exec_(*_):
        if not _peut_suspendre():
            return 0
        app = classe.instance()
        if hasattr(app, "lastWindowClosed"):
            def derniere():
                if app.quitOnLastWindowClosed():
                    _quitter(0)
            app.lastWindowClosed.connect(derniere)
        while _au_demarrage:
            _au_demarrage.pop()()
        code = _suspendre(_fin_application.append)
        app.aboutToQuit.emit()
        return code

    classe.exec = staticmethod(exec_)


# --- QtWidgets ------------------------------------------------------------------------------------------------------

def doubler_qtwidgets(ns):
    from ..QtCore import Qt, QTimer  # noqa: PLC0415  (QtCore de qtpy6 : ses doublures d'abord, ``_connect_qt`` avec)
    from ..QtGui import QColor, QCursor, QFont  # noqa: PLC0415

    QDialog, QMenu, QMessageBox, QInputDialog = ns["QDialog"], ns["QMenu"], ns["QMessageBox"], ns["QInputDialog"]
    QFileDialog, QColorDialog, QFontDialog = ns["QFileDialog"], ns["QColorDialog"], ns["QFontDialog"]
    connect = _connect_qt[0]  # l'original : ``resoudre`` pose une valeur

    doubler_exec_application(ns["QApplication"])

    def dialogue_exec(self):
        if not _peut_suspendre():
            _avertir(f"{type(self).__name__}.exec()")
            self.open()
            return 0
        if self.windowModality() == Qt.WindowModality.NonModal:
            self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.show()
        (resultat,) = attendre_signal(self.finished, connect)
        return resultat

    def menu_exec(self, *args, **kwargs):
        if not isinstance(self, QMenu):  # QMenu.exec(actions, pos, at=None, parent=None) : la forme statique
            actions, pos, *reste = (self, *args)
            at, parent = (reste + [None, None])[:2]
            menu = QMenu(kwargs.get("parent", parent))
            menu.addActions(actions)
            return menu_exec(menu, pos, kwargs.get("at", at))
        pos = args[0] if args else kwargs.get("pos", QCursor.pos())
        at = args[1] if len(args) > 1 else kwargs.get("at")
        if not _peut_suspendre():
            _avertir("QMenu.exec()")
            self.popup(pos, at)
            return None
        choisie, fin = [], []

        def brancher(resoudre):  # triggered part APRÈS aboutToHide, dans le même appel : attendre un tour
            fin.append(lambda: QTimer.singleShot(0, resoudre))
            connect(self.aboutToHide, fin[0])
        connect(self.triggered, choisie.append)
        self.popup(pos, at)
        _suspendre(brancher)
        self.triggered.disconnect(choisie.append)
        self.aboutToHide.disconnect(fin[0])  # un menu gardé resservira : ne pas y empiler les connexions
        return choisie[-1] if choisie else None

    def par_instance(classe, remplacant):
        # PySide6 : ``exec`` a une forme statique (``QMenu.exec(actions, pos)``), et sur une instance le getattro que
        # shiboken génère pour ces méthodes à deux formes rend la native quoi que porte le dictionnaire de la classe
        # (mesuré : même posé en descripteur de données, même après ``del``). Seul ``__getattribute__`` passe devant.
        getattro = classe.__getattribute__

        def __getattribute__(self, name):
            return types.MethodType(remplacant, self) if name == "exec" else getattro(self, name)
        classe.__getattribute__ = __getattribute__

    for nom, classe in list(ns.items()):
        if isinstance(classe, type) and "exec" in vars(classe):
            remplacant = dialogue_exec if issubclass(classe, QDialog) else menu_exec if issubclass(classe, QMenu) else None
            if remplacant is None:
                continue
            if isinstance(vars(classe)["exec"], staticmethod):
                par_instance(classe, remplacant)
            classe.exec = remplacant

    # QMessageBox : les boîtes statiques, sur une instance.
    B = QMessageBox.StandardButton

    def boite(icone, boutons_defaut):
        def f(parent, title, text, buttons=boutons_defaut, defaultButton=B.NoButton):
            b = QMessageBox(icone, title, text, buttons, parent)
            b.setDefaultButton(defaultButton)
            r = b.exec()
            try:
                return B(r)
            except ValueError:
                return B.NoButton
        return staticmethod(f)

    I = QMessageBox.Icon
    QMessageBox.information = boite(I.Information, B.Ok)
    QMessageBox.warning = boite(I.Warning, B.Ok)
    QMessageBox.critical = boite(I.Critical, B.Ok)
    QMessageBox.question = boite(I.Question, B.Yes | B.No)

    def about(parent, title, text):
        b = QMessageBox(I.Information, title, text, B.Ok, parent)
        b.exec()

    def about_qt(parent, title=""):
        from .. import QT_VERSION  # noqa: PLC0415
        about(parent, title or "À propos de Qt", f"Qt {QT_VERSION}")

    QMessageBox.about, QMessageBox.aboutQt = staticmethod(about), staticmethod(about_qt)

    # QInputDialog : idem, avec ce que rend Qt sur une annulation (la valeur de départ).
    def saisie(parent, title, label, flags):
        d = QInputDialog(parent, flags or Qt.WindowType(0))
        d.setWindowTitle(title)
        d.setLabelText(label)
        return d

    def get_text(parent, title, label, echo=ns["QLineEdit"].EchoMode.Normal, text="", flags=None,
                 inputMethodHints=Qt.InputMethodHint.ImhNone):
        d = saisie(parent, title, label, flags)
        d.setTextEchoMode(echo)
        d.setTextValue(text)
        d.setInputMethodHints(inputMethodHints)
        ok = d.exec() == 1
        return (d.textValue() if ok else "", ok)

    def get_multi_line_text(parent, title, label, text="", flags=None, inputMethodHints=Qt.InputMethodHint.ImhNone):
        d = saisie(parent, title, label, flags)
        d.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput)
        d.setTextValue(text)
        d.setInputMethodHints(inputMethodHints)
        ok = d.exec() == 1
        return (d.textValue() if ok else "", ok)

    def get_int(parent, title, label, value=0, min=-2147483647, max=2147483647, step=1, flags=None):  # noqa: A002
        d = saisie(parent, title, label, flags)
        d.setIntRange(min, max)
        d.setIntValue(value)
        d.setIntStep(step)
        ok = d.exec() == 1
        return (d.intValue() if ok else value, ok)

    def get_double(parent, title, label, value=0.0, min=-2147483647.0, max=2147483647.0, decimals=1,  # noqa: A002
                   flags=None, step=1.0):
        d = saisie(parent, title, label, flags)
        d.setDoubleDecimals(decimals)
        d.setDoubleRange(min, max)
        d.setDoubleValue(value)
        d.setDoubleStep(step)
        ok = d.exec() == 1
        return (d.doubleValue() if ok else value, ok)

    def get_item(parent, title, label, items, current=0, editable=True, flags=None,
                 inputMethodHints=Qt.InputMethodHint.ImhNone):
        d = saisie(parent, title, label, flags)
        d.setComboBoxItems(items)
        d.setTextValue(items[current] if 0 <= current < len(items) else "")
        d.setComboBoxEditable(editable)
        d.setInputMethodHints(inputMethodHints)
        ok = d.exec() == 1
        return (d.textValue() if ok else (items[current] if 0 <= current < len(items) else ""), ok)

    for nom, f in (("getText", get_text), ("getMultiLineText", get_multi_line_text), ("getInt", get_int),
                   ("getDouble", get_double), ("getItem", get_item)):
        setattr(QInputDialog, nom, staticmethod(f))

    def get_color(initial=None, parent=None, title="", options=None):
        d = QColorDialog(initial if initial is not None else QColor(Qt.GlobalColor.white), parent)
        d.setWindowTitle(title)
        if options is not None:
            d.setOptions(options)
        return d.currentColor() if d.exec() == 1 else QColor()

    def get_font(*args, **kwargs):
        if args and isinstance(args[0], QFont) or "initial" in kwargs:  # (initial, parent=None, title='', options=0)
            initial, parent, title, options = (list(args) + [None] * 4)[:4]
            initial, parent = kwargs.get("initial", initial), kwargs.get("parent", parent)
            title, options = kwargs.get("title", title), kwargs.get("options", options)
        else:  # (parent=None)
            initial, parent, title, options = QFont(), (args[0] if args else kwargs.get("parent")), None, None
        d = QFontDialog(initial, parent)
        if title:
            d.setWindowTitle(title)
        if options is not None:
            d.setOptions(options)
        ok = d.exec() == 1
        return (d.selectedFont() if ok else initial, ok)

    QColorDialog.getColor, QFontDialog.getFont = staticmethod(get_color), staticmethod(get_font)

    # QFileDialog : le disque de l'utilisateur n'est joignable que par le sélecteur de fichiers de la page (ouvrir) et
    # par le téléchargement (enregistrer). Un fichier ouvert est copié dans le système de fichiers de Pyodide, dont
    # le chemin est rendu ; un fichier enregistré y est écrit par l'application, puis téléchargé.
    def get_open_file_names(parent=None, caption="", directory="", filter="", initialFilter="", options=None):  # noqa: A002
        return (_televerser(directory, filter, multiple=True), initialFilter)

    def get_open_file_name(parent=None, caption="", directory="", filter="", initialFilter="", options=None):  # noqa: A002
        chemins = _televerser(directory, filter, multiple=False)
        return (chemins[0] if chemins else "", initialFilter)

    def get_save_file_name(parent=None, caption="", directory="", filter="", initialFilter="", options=None):  # noqa: A002
        nom, ok = get_text(parent, caption or "Enregistrer sous", "Nom du fichier (il sera téléchargé) :",
                           text=os.path.basename(directory))
        nom = os.path.basename(nom.strip())
        if not ok or not nom:
            return ("", initialFilter)
        chemin = os.path.join(_dossier(directory), nom)
        _telecharger_quand_ecrit(chemin, QTimer)
        return (chemin, initialFilter)

    def get_existing_directory(parent=None, caption="", directory="", options=None):
        d = QFileDialog(parent, caption, _dossier(directory))
        d.setFileMode(QFileDialog.FileMode.Directory)
        d.setOption(QFileDialog.Option.ShowDirsOnly)
        return d.selectedFiles()[0] if d.exec() == 1 and d.selectedFiles() else ""

    for nom, f in (("getOpenFileName", get_open_file_name), ("getOpenFileNames", get_open_file_names),
                   ("getSaveFileName", get_save_file_name), ("getExistingDirectory", get_existing_directory)):
        setattr(QFileDialog, nom, staticmethod(f))


def _dossier(directory):
    """Le dossier (du système de fichiers de Pyodide) que désigne ``directory`` : lui-même, celui du fichier qu'il nomme,
    le dossier personnel sinon."""
    for d in (directory, os.path.dirname(directory or "")):
        if d and os.path.isdir(d):
            return d
    return os.path.expanduser("~")


def _accept(filtre):
    """``"Images (*.png *.jpg);;Tout (*)"`` -> ``".png,.jpg"`` pour l'attribut ``accept`` ; vide dès qu'un ``*`` seul
    ou ``*.*`` autorise tout."""
    import re  # noqa: PLC0415

    motifs = re.findall(r"\*(\.[\w.-]+|\*|(?=[\s)]|$))", filtre or "")
    if not motifs or any(m in ("", "*", ".*") for m in motifs):
        return ""
    return ",".join(dict.fromkeys(motifs))


ELEMENT_FICHIERS = "qtpy6-fichiers"  # l'id du <input type=file> de la page, le temps d'un choix (la sonde le remplit)


def _televerser(directory, filtre, multiple):
    """Le sélecteur de fichiers de la page ; les fichiers choisis sont copiés dans ``_dossier(directory)``. Rend leurs
    chemins ([] si l'utilisateur annule, ou hors entrée suspendable)."""
    if not _peut_suspendre():
        _avertir("QFileDialog.getOpenFileName()")
        return []
    import js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    champ = js.document.createElement("input")
    champ.type, champ.id, champ.multiple, champ.hidden = "file", ELEMENT_FICHIERS, multiple, True
    champ.accept = _accept(filtre)
    js.document.body.appendChild(champ)
    try:
        def brancher(resoudre):
            champ.addEventListener("change", create_once_callable(lambda _: resoudre(True)))
            champ.addEventListener("cancel", create_once_callable(lambda _: resoudre(False)))
            champ.click()
        if not _suspendre(brancher):
            return []
        chemins = []
        dossier = _dossier(directory)
        for f in champ.files:
            chemin = os.path.join(dossier, f.name)
            contenu = _suspendre(lambda resoudre, f=f: f.arrayBuffer().then(resoudre))
            with open(chemin, "wb") as sortie:
                sortie.write(js.Uint8Array.new(contenu).to_bytes())
            chemins.append(chemin)
        return chemins
    finally:
        champ.remove()


def _telecharger_quand_ecrit(chemin, QTimer, delai=120):
    """Télécharge ``chemin`` dès que l'application l'a écrit (après ``getSaveFileName``) : sa taille est relevée à
    chaque quart de seconde, le fichier part quand elle n'a pas bougé entre deux relevés. Abandon au bout de ``delai`` s."""
    from . import stockage  # noqa: PLC0415

    depart, avant = time.time(), os.stat(chemin).st_mtime if os.path.exists(chemin) else None
    minuterie = QTimer()
    releves = []

    def arreter():
        minuterie.stop()
        _minuteries.discard(minuterie)

    def relever():
        if time.time() - depart > delai:
            arreter()
        elif os.path.exists(chemin) and os.stat(chemin).st_mtime != avant:
            releves.append(os.path.getsize(chemin))
            if len(releves) >= 2 and releves[-1] == releves[-2]:
                arreter()
                with open(chemin, "rb") as f:
                    stockage.telecharger(os.path.basename(chemin), f.read())

    minuterie.timeout.connect(relever)
    minuterie.start(250)
    _minuteries.add(minuterie)  # gardée en vie jusqu'à son arrêt


_minuteries = set()
