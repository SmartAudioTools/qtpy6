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
classes de PyQt6 elles-mêmes (``PyQt6.QtWidgets.QDialog.exec`` compris)."""

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


_pompe = []


def _pyodide_pomper(periode=10):
    """Fait tourner la boucle d'événements de Qt : compilé avec JSPI, Qt-WASM n'envoie ni minuteries ni événements postés
    de lui-même, il attend qu'on reprenne SA boucle ``exec()`` suspendue (``onTimer`` : ``if (useAsyncify()) return;``,
    qeventdispatcher_wasm.cpp) — celle qu'on ne peut pas lancer, imbriquée elle arrête tout. Mesuré : sans pompe, un
    ``QTimer`` s'arrête dès que la page cesse de redessiner. Un appel de la page, non promettant : les slots y sont
    reportés (``connect``), rien n'y suspend au milieu de ``processEvents``."""
    if _pompe:
        return
    try:
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy  # noqa: PLC0415
    except ImportError:  # tests/test_web.py, qui simule le navigateur sans Pyodide : sa boucle native fait tourner Qt
        return
    from PyQt6.QtCore import QCoreApplication  # noqa: PLC0415

    def tour():
        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()

    _pompe.append(js.setInterval(create_proxy(tour), periode))


# ``can_run_sync()`` ment pendant qu'une entrée est suspendue : un slot que Qt appelle alors y voit True, mais un
# ``run_sync`` n'y reprend jamais (mesuré : ni retour ni erreur). D'où la comptabilité : ``_actif`` dit que le code en
# cours est une entrée promettante connue (tâche de ``_plus_tard``, ou reprise après ``_suspendre``), ``_suspendus``
# combien de piles attendent. Sans pile suspendue, ``can_run_sync()`` dit vrai (le script principal de runPythonAsync).
_actif = False
_suspendus = 0


def _peut_suspendre():
    return _pyodide_peut() and (_actif or _suspendus == 0)


def _suspendre(brancher):
    global _actif, _suspendus
    avant, _actif = _actif, False
    _suspendus += 1
    try:
        return _pyodide_suspendre(brancher)
    finally:
        _suspendus -= 1
        _actif = avant or _suspendus > 0  # repris : promettant, et le seul à pouvoir le dire tant qu'un autre attend


def _plus_tard(f, *args):
    """``f(*args)`` à la tâche suivante de la boucle asyncio, une entrée où il peut suspendre."""
    def tache():
        global _actif
        avant, _actif = _actif, True
        try:
            f(*args)
        finally:
            _actif = avant

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

_connect_qt = []  # le connect de PyQt, avant la doublure
_expediteur = []  # l'expéditeur d'un slot reporté, que ``QObject.sender()`` rend pendant son exécution


def _nb_arguments(slot):
    """Combien d'arguments positionnels ``slot`` accepte (None : autant qu'on veut). PyQt tronque ceux du signal à ce
    nombre ; le relais doit faire de même."""
    try:
        parametres = inspect.signature(slot).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_POSITIONAL for p in parametres):
        return None
    return sum(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in parametres)


def doubler_qtcore(ns):
    """Pose les doublures dans l'espace de noms de ``qtpy6.QtCore`` (PyQt6 ; ses noms PySide6 y sont déjà)."""
    import weakref  # noqa: PLC0415

    from PyQt6 import sip  # noqa: PLC0415

    QObject, QCoreApplication, QEventLoop = ns["QObject"], ns["QCoreApplication"], ns["QEventLoop"]
    signal_lie = ns["SignalInstance"]
    connect, disconnect, sender = signal_lie.connect, signal_lie.disconnect, QObject.sender
    relais = {}  # clé du slot -> relais connectés, pour disconnect(slot)

    def cle(slot):
        return (id(slot.__self__), slot.__func__) if isinstance(slot, types.MethodType) else slot

    def relayer(slot, direct):
        n = _nb_arguments(slot)
        if isinstance(slot, types.MethodType):  # PyQt ne garde pas le receveur en vie : le relais non plus
            ref, fonction = weakref.ref(slot.__self__), slot.__func__

            def cible():
                objet = ref()
                if objet is None or (isinstance(objet, sip.simplewrapper) and sip.isdeleted(objet)):
                    return None
                return types.MethodType(fonction, objet)
        else:
            def cible():
                return slot

        def executer(exp, args):
            f = cible()
            if f is not None:
                _expediteur.append(exp)
                try:
                    f(*args[:n] if n is not None else args)
                finally:
                    _expediteur.pop()

        def relais_(*args):
            if direct or _peut_suspendre():
                f = cible()
                return f(*args[:n] if n is not None else args) if f is not None else None
            app = QCoreApplication.instance()
            _plus_tard(executer, sender(app) if app is not None else None, args)
            return None

        relais_.cible = cible
        return relais_

    def connect_(self, slot, *args, **kwargs):
        if isinstance(slot, (signal_lie, types.BuiltinFunctionType, types.BuiltinMethodType)) or not callable(slot):
            return connect(self, slot, *args, **kwargs)
        r = relayer(slot, direct=self.signal.startswith("2destroyed("))  # l'objet meurt : après, il serait trop tard
        relais.setdefault(cle(slot), []).append(r)
        return connect(self, r, *args, **kwargs)

    def disconnect_(self, *args):
        if len(args) == 1 and callable(args[0]) and not isinstance(args[0], signal_lie):
            vivants = [r for r in relais.get(cle(args[0]), []) if r.cible() is not None]
            for r in vivants:
                try:
                    disconnect(self, r)
                except TypeError:  # connecté à un autre signal que celui-ci
                    continue
                vivants.remove(r)
                relais[cle(args[0])] = vivants
                return None
        return disconnect(self, *args)

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

    # Pas de fils dans le navigateur : un objet reste où il est.
    if not hasattr(QObject, "moveToThread"):
        QObject.moveToThread = lambda self, thread: None
    if not hasattr(QObject, "thread"):
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

    doubler_exec_application(QCoreApplication)
    QCoreApplication.quit = staticmethod(lambda: _quitter(0))
    QCoreApplication.exit = staticmethod(lambda code=0: _quitter(code))
    _pyodide_pomper()  # dès le chargement de QtCore : avec ou sans exec(), c'est elle qui fait tourner Qt


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
    from PyQt6.QtCore import QTimer, Qt, pyqtBoundSignal  # noqa: PLC0415
    from PyQt6.QtGui import QColor, QCursor, QFont  # noqa: PLC0415

    QDialog, QMenu, QMessageBox, QInputDialog = ns["QDialog"], ns["QMenu"], ns["QMessageBox"], ns["QInputDialog"]
    QFileDialog, QColorDialog, QFontDialog = ns["QFileDialog"], ns["QColorDialog"], ns["QFontDialog"]
    connect = _connect_qt[0] if _connect_qt else pyqtBoundSignal.connect  # l'original : ``resoudre`` pose une valeur

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
        choisie = []
        connect(self.triggered, choisie.append)

        def brancher(resoudre):  # triggered part APRÈS aboutToHide, dans le même appel : attendre un tour
            connect(self.aboutToHide, lambda: QTimer.singleShot(0, resoudre))
        self.popup(pos, at)
        _suspendre(brancher)
        self.triggered.disconnect(choisie.append)
        return choisie[-1] if choisie else None

    for nom, classe in list(ns.items()):
        if isinstance(classe, type) and "exec" in vars(classe):
            if issubclass(classe, QDialog):
                classe.exec = dialogue_exec
            elif issubclass(classe, QMenu):
                classe.exec = menu_exec

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
        from PyQt6.QtCore import QT_VERSION_STR  # noqa: PLC0415
        about(parent, title or "À propos de Qt", f"Qt {QT_VERSION_STR}")

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
