"""``qtpy6.doublures`` : le navigateur doublé le temps d'un bloc, puis ``sys.modules`` rendu tel quel."""

import sys

import pytest

from qtpy6.doublures import MODULES, navigateur_double


def test_modules_rendus_tels_quels():
    """Un nom absent le redevient, un nom présent retrouve son module, même quand le bloc lève."""
    sentinelle = object()
    sys.modules.pop("js", None)
    sys.modules["pyodide"] = sentinelle
    avant = {nom: sys.modules.get(nom, "absent") for nom in MODULES}
    try:
        with pytest.raises(RuntimeError), navigateur_double(titre="essai") as js:
            from js import document, titre
            from pyodide.ffi import create_proxy, jsnull
            assert sys.modules["js"] is js and titre == "essai"
            assert document.addEventListener("visibilitychange", create_proxy(print)) is None
            assert create_proxy(print) is print and jsnull is not None and not jsnull
            raise RuntimeError
        assert {nom: sys.modules.get(nom, "absent") for nom in MODULES} == avant
    finally:
        sys.modules.pop("pyodide")


# --- W556 : application(persistant=…, disque=True), le dossier autorisé de Chrome --------------------------------------
def test_disque_sans_effet_en_natif(tmp_path):
    """En natif, ``disque`` ne change rien : le dossier persistant est un dossier du disque, créé au besoin, et aucun
    montage n'est noté (``stockage`` n'importe ``js`` qu'à l'appel)."""
    from qtpy6.web import application, stockage

    dossier = tmp_path / "eleve"
    application(persistant=dossier, disque=True)
    assert dossier.is_dir() and not stockage._montes and not stockage._natifs


# --- W558 : renderProcessTerminated de la doublure QWebEngine (greffon spyder_python_tutor, main_widget.py:385) ----------
def test_moteur_web_render_process_terminated(app):
    """Le tuteur branche ``page.renderProcessTerminated`` (statut, code de sortie) : le signal existe sous le nom et la
    signature Qt sur la page et sur la vue, qui le relaie comme les autres ; jamais émis par la doublure (l'iframe meurt
    avec la page)."""
    from unittest.mock import MagicMock

    with navigateur_double(document=MagicMock(), window=MagicMock()):
        from qtpy6.web.moteur_web import QWebEnginePage, QWebEngineView

        vue = QWebEngineView()
        page = QWebEnginePage(vue)
        vue.setPage(page)
        recus = []
        page.renderProcessTerminated.connect(lambda statut, code: recus.append(("page", statut, code)))
        vue.renderProcessTerminated.connect(lambda statut, code: recus.append(("vue", statut, code)))
        crash = QWebEnginePage.RenderProcessTerminationStatus.CrashedTerminationStatus
        page.renderProcessTerminated.emit(crash, 11)
        assert sorted(recus) == [("page", crash, 11), ("vue", crash, 11)]


# --- W560 : alert() et console.* de l'iframe vers javaScriptAlert / javaScriptConsoleMessage (tuteur, _DebugPage) --------
def _page_relais(app, classe_page=None):
    from qtpy6.web.moteur_web import QWebEnginePage, QWebEngineView

    vue = QWebEngineView()
    page = (classe_page or QWebEnginePage)(vue)
    vue.setPage(page)
    return vue, page


def test_moteur_web_relais_alert_console(app):
    """Le tuteur surcharge ``javaScriptAlert`` et ``javaScriptConsoleMessage`` (``main_widget.py:372-380``) : la page
    posée par ``setHtml`` porte, avant tout autre script et après le doctype, le relais qui remplace ``alert`` et
    ``console.*`` de l'iframe ; le relais appelle les méthodes surchargées avec la signature Qt."""
    from unittest.mock import MagicMock

    with navigateur_double(document=MagicMock(), window=MagicMock()):
        from qtpy6.web.moteur_web import QWebEnginePage

        recus = []

        class _DebugPage(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, line, source):
                recus.append((level.name, message, line, source))

            def javaScriptAlert(self, origin, msg):
                recus.append(("alert", origin.toString(), msg))

        vue, page = _page_relais(app, _DebugPage)
        page.setHtml("<!DOCTYPE html><html><head><script>alert(1)</script></head></html>")
        srcdoc = str(page._cadre.srcdoc)
        assert srcdoc.startswith("<!DOCTYPE html><html><head><script>")
        assert srcdoc.index("qtpy6_relais") < srcdoc.index("alert(1)")
        relais = page._cadre.qtpy6_relais
        relais("alert", "Assertion Failure", 0, "")
        relais("error", "boum", 12, "viz.js")
        relais("warn", "attention", 3, "viz.js")
        relais("log", "info", 0, "")
        assert recus == [("alert", page.url().toString(), "Assertion Failure"),
                         ("ErrorMessageLevel", "boum", 12, "viz.js"),
                         ("WarningMessageLevel", "attention", 3, "viz.js"),
                         ("InfoMessageLevel", "info", 0, "")]


def test_moteur_web_alert_par_defaut(app):
    """Sans surcharge, ``javaScriptAlert`` ouvre une QMessageBox comme Qt, sans ``exec()`` (le relais est appelé par
    le navigateur, entrée non suspendable : ``open()`` ne bloque pas) ; ``javaScriptConsoleMessage`` ne fait rien."""
    from unittest.mock import MagicMock

    from qtpy6.QtWidgets import QMessageBox

    with navigateur_double(document=MagicMock(), window=MagicMock()):
        vue, page = _page_relais(app)
        page.setHtml("<p>x</p>")
        page._cadre.qtpy6_relais("error", "boum", 1, "")
        page._cadre.qtpy6_relais("alert", "Bonjour", 0, "")
        boites = [b for b in vue.findChildren(QMessageBox) if b.text() == "Bonjour"]
        assert len(boites) == 1 and boites[0].isVisible()
        boites[0].close()


# --- W562 : l'alias snake_case d'un SIGNAL cède au nom de l'application (Spyder, TextEditBaseWidget) ---------------------
def test_alias_signal_cede_au_mixin(app):
    """``class TextEditBaseWidget(QPlainTextEdit, BaseEditMixin)`` : la méthode ``BaseEditMixin.cursor_position_changed``
    vient après Qt dans la MRO ; un alias-attribut du signal ``cursorPositionChanged`` la masquait, et
    ``cursorPositionChanged.connect(self.cursor_position_changed)`` (spyder/plugins/editor/widgets/base.py:76) connectait
    le signal à lui-même : ``setPlainText`` récursait sans fin (jalon 5, « too much recursion » dans la page)."""
    from qtpy6.QtWidgets import QPlainTextEdit

    class Mixin:
        def cursor_position_changed(self):
            self.appels += 1

    class Editeur(QPlainTextEdit, Mixin):
        appels = 0

    e = Editeur()
    assert e.cursor_position_changed.__func__ is Mixin.cursor_position_changed
    e.cursorPositionChanged.connect(e.cursor_position_changed)
    e.setPlainText("a\nb\n")
    e.moveCursor(e.textCursor().MoveOperation.End)
    assert e.appels >= 1
    nu = QPlainTextEdit()  # sans nom de l'application, l'alias reste le signal
    vus = []
    nu.cursor_position_changed.connect(lambda: vus.append(1))
    nu.setPlainText("x\n")
    nu.moveCursor(nu.textCursor().MoveOperation.End)
    assert vus


# --- W547 : alias snake_case des signaux (D1, item 3 du TODO Portage) -----------------------------------------------------
def test_alias_signal_et_slot_homonyme(app):
    """L'alias ``text_changed`` est le signal ``textChanged`` (objet et classe) ; une méthode homonyme d'une sous-classe,
    connectée au signal, le masque sans planter (avant D1 : code 139, ``essais/alias_signal_slot.py``) et qtpy6 le dit
    à la définition de la classe."""
    import warnings

    from qtpy6._binding import SignalAliasMasked
    from qtpy6.QtWidgets import QLineEdit

    assert QLineEdit.text_changed is QLineEdit.textChanged
    recus = []
    with warnings.catch_warnings(record=True) as avertis:
        warnings.simplefilter("always")

        class Champ(QLineEdit):
            def __init__(self):
                super().__init__()
                self.textChanged.connect(self.text_changed)

            def text_changed(self, texte):
                recus.append(("slot", texte))

    from qtpy6 import PYSIDE6
    assert [a.category for a in avertis] == ([SignalAliasMasked] if PYSIDE6 else [])  # PyQt6 : pas d'avertissement
    champ, autre = Champ(), QLineEdit()
    autre.text_changed.connect(lambda t: recus.append(("alias", t)))
    champ.setText("abc")
    autre.setText("xyz")
    assert recus == [("slot", "abc"), ("alias", "xyz")]


# --- W563 : QtNetwork dans la page, QTcpServer / QTcpSocket / QNetworkInterface (greffon spyder_collab, network.py:43) --
@pytest.fixture
def boucle_locale(monkeypatch):
    """La boucle locale de socket_web (vraie sous emscripten), posée pour un test natif, registres de ports vidés."""
    from qtpy6.web import socket_web, zmq_web

    zmq_web.reinitialiser()
    monkeypatch.setattr(socket_web, "boucle_locale", True)
    yield
    zmq_web.reinitialiser()


def _pomper(condition, n=50):
    from qtpy6.web import threading_web

    for _ in range(n):
        if condition():
            return True
        threading_web.pomper()
    return condition()


def test_qtnetwork_natif_vraie_classe():
    """En natif, ``qtpy6.QtNetwork`` (et ``qtpy.QtNetwork``) rend les classes de la liaison."""
    import importlib

    from qtpy6 import API_NAME, QtNetwork
    vrai = importlib.import_module(f"{API_NAME}.QtNetwork")
    assert QtNetwork.QTcpServer is vrai.QTcpServer and QtNetwork.QNetworkInterface is vrai.QNetworkInterface


def test_reseau_web_un_octet(app, boucle_locale):
    """Ce que fait spyder_collab dans la page : le serveur écoute sur ``QHostAddress.Any``, le client s'y connecte,
    un octet passe dans chaque sens par les signaux Qt (connected, newConnection, readyRead), puis la déconnexion."""
    from qtpy6.QtNetwork import QAbstractSocket, QHostAddress
    from qtpy6.web.reseau_web import QTcpServer, QTcpSocket

    serveur = QTcpServer()
    assert serveur.listen(QHostAddress.SpecialAddress.Any, 47820) and serveur.isListening()
    assert serveur.serverPort() == 47820
    arrivees, evenements = [], []
    serveur.newConnection.connect(lambda: arrivees.append(serveur.nextPendingConnection()))
    client = QTcpSocket()
    client.connected.connect(lambda: evenements.append("connected"))
    client.disconnected.connect(lambda: evenements.append("disconnected"))
    client.connectToHost("127.0.0.1", 47820)
    assert _pomper(lambda: arrivees and evenements)
    assert evenements == ["connected"] and client.state() == QAbstractSocket.SocketState.ConnectedState
    cote_serveur = arrivees[0]
    assert cote_serveur.peerAddress().toString() == "127.0.0.1" and not serveur.hasPendingConnections()

    lus = []
    cote_serveur.readyRead.connect(lambda: lus.append(("serveur", bytes(cote_serveur.readAll()))))
    client.readyRead.connect(lambda: lus.append(("client", bytes(client.readAll()))))
    assert client.write(b"x") == 1
    assert _pomper(lambda: lus)
    assert cote_serveur.write(b"y") == 1
    assert _pomper(lambda: len(lus) == 2)
    assert lus == [("serveur", b"x"), ("client", b"y")]

    fins = []
    cote_serveur.disconnected.connect(lambda: fins.append("serveur"))
    client.disconnectFromHost()
    assert _pomper(lambda: fins)
    assert evenements == ["connected", "disconnected"] and client.state() == QAbstractSocket.SocketState.UnconnectedState
    serveur.close()
    assert not serveur.isListening()


def test_reseau_web_refus_et_port_pris(app, boucle_locale):
    """Personne n'écoute : ``errorOccurred(ConnectionRefusedError)`` à une tâche suivante (spyder_collab réessaie) ;
    un second ``listen`` sur le même port échoue avec un ``errorString``."""
    from qtpy6.QtNetwork import QAbstractSocket, QHostAddress
    from qtpy6.web.reseau_web import QTcpServer, QTcpSocket

    client, erreurs = QTcpSocket(), []
    client.errorOccurred.connect(erreurs.append)
    client.connectToHost("localhost", 47821)
    assert erreurs == []  # jamais synchrone, comme Qt
    assert _pomper(lambda: erreurs)
    assert erreurs == [QAbstractSocket.SocketError.ConnectionRefusedError] and client.error() == erreurs[0]
    assert client.state() == QAbstractSocket.SocketState.UnconnectedState and client.errorString()

    premier, second = QTcpServer(), QTcpServer()
    assert premier.listen(QHostAddress.SpecialAddress.Any, 47822)
    assert not second.listen(QHostAddress.SpecialAddress.Any, 47822) and second.errorString()


def test_reseau_web_interfaces():
    """``local_addresses`` de spyder_collab : interfaces actives hors boucle locale, IPv4. La page n'a que la boucle
    locale (aucune adresse joignable : le collab le dit) ; noms à plat et dans l'énumération, comme Qt."""
    from qtpy6.web.reseau_web import QNetworkInterface

    assert QNetworkInterface.IsUp is QNetworkInterface.InterfaceFlag.IsUp
    (interface,) = QNetworkInterface.allInterfaces()
    assert interface.flags() & QNetworkInterface.IsUp and interface.flags() & QNetworkInterface.IsLoopBack
    assert [e.ip().toString() for e in interface.addressEntries()] == ["127.0.0.1"]


def test_reseau_web_fermetures(app, boucle_locale):
    """Écarts à Qt relevés à la relecture : un second ``listen`` est refusé ; ``close`` du serveur ferme les connexions
    jamais reprises (le client voit ``disconnected``) ; « localhost » donne une adresse ; un refus programmé puis
    ``abort`` n'émet rien."""
    from qtpy6.QtNetwork import QHostAddress
    from qtpy6.web.reseau_web import QTcpServer, QTcpSocket

    serveur = QTcpServer()
    assert serveur.listen(QHostAddress.SpecialAddress.Any, 47823)
    assert not serveur.listen(QHostAddress.SpecialAddress.Any, 47824) and serveur.serverPort() == 47823
    client, fins = QTcpSocket(), []
    client.disconnected.connect(lambda: fins.append("client"))
    client.connectToHost("localhost", 47823)
    assert _pomper(serveur.hasPendingConnections)
    assert client.peerAddress().toString() == "127.0.0.1"
    serveur.close()
    assert _pomper(lambda: fins) and not serveur.hasPendingConnections()

    perdu, erreurs = QTcpSocket(), []
    perdu.errorOccurred.connect(erreurs.append)
    perdu.connectToHost("127.0.0.1", 47825)
    perdu.abort()
    _pomper(lambda: False, n=5)
    assert erreurs == []
