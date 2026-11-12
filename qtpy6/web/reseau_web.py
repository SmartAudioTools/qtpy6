"""``QTcpServer``, ``QTcpSocket`` et ``QNetworkInterface`` de QtNetwork dans le navigateur, où une page n'écoute pas et ne
joint aucun hôte par TCP. Le QtNetwork de Qt-WASM a ``QTcpServer``/``QTcpSocket`` mais sans moteur qui écoute, et pas de
``QNetworkInterface`` (``wasm/patches/pyside-qtnetwork-features-absentes.patch``) : spyder_collab (``network.py:43``) ne
s'importait pas. Ces doublures portent les signaux et méthodes Qt sur la boucle locale de ``socket_web`` (même registre de
ports et même routage page ↔ Worker que pylsp ``--tcp`` et zmq) : un serveur et un client de la page, ou d'un Worker,
se joignent. Un autre hôte n'est pas joint (``NetworkError``) ; ``QNetworkInterface`` ne connaît que la boucle locale.

Comme Qt, rien n'est émis pendant l'appel : ``connected``, ``readyRead``, ``errorOccurred``, ``newConnection`` arrivent à
une tâche suivante (``socket_web._veiller``, ``threading_web.plus_tard``). ``QAbstractSocket`` et ``QHostAddress`` restent
ceux de la liaison (présents dans Qt-WASM) : leurs énumérations sont celles qu'on compare."""

from __future__ import annotations

import enum
import importlib
import socket
from typing import Any

from qtpy6 import API_NAME
from qtpy6.QtCore import QByteArray, QObject, Signal

from . import socket_web
from .threading_web import plus_tard

_reseau = importlib.import_module(f"{API_NAME}.QtNetwork")
QAbstractSocket, QHostAddress = _reseau.QAbstractSocket, _reseau.QHostAddress
_Etat, _Erreur = QAbstractSocket.SocketState, QAbstractSocket.SocketError


def _hote(adresse: Any) -> str:
    if isinstance(adresse, QHostAddress.SpecialAddress):
        adresse = QHostAddress(adresse)
    return adresse.toString() if isinstance(adresse, QHostAddress) else str(adresse)


class QTcpSocket(QObject):
    """Un bout de connexion : ``connectToHost`` côté client, ou rendu par ``QTcpServer.nextPendingConnection``."""

    connected = Signal()
    disconnected = Signal()
    readyRead = Signal()
    bytesWritten = Signal("qint64")
    stateChanged = Signal(_Etat)
    errorOccurred = Signal(_Erreur)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket: socket_web.Socket | None = None
        self._etat, self._erreur, self._message = _Etat.UnconnectedState, _Erreur.UnknownSocketError, ""
        self._annonces = 0  # octets du tampon déjà signalés par readyRead
        self._tentative = 0  # change à chaque connectToHost et fermeture : un rappel d'avant ne fait plus rien

    # Connexion

    def connectToHost(self, hote: Any, port: int, *_mode) -> None:  # noqa: N802
        self.abort()
        hote = _hote(hote)
        hote = "127.0.0.1" if hote == "localhost" else hote  # peerAddress : une adresse, pas un nom
        self._changer(_Etat.HostLookupState)
        self._changer(_Etat.ConnectingState)
        if hote not in socket_web._HOTES_LOCAUX:
            self._plus_tard(lambda: self._echouer(_Erreur.NetworkError, f"Le navigateur ne joint pas {hote} par TCP"))
            return
        self._socket = socket_web.Socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(False)
        try:
            self._socket.connect((hote, int(port)))
        except BlockingIOError:
            pass  # un Worker écoute : la réponse arrive par _evenement
        except ConnectionRefusedError:
            self._plus_tard(lambda: self._echouer(_Erreur.ConnectionRefusedError, "Connection refused"))
            return
        socket_web._veiller(self._socket, self._evenement)
        plus_tard(self._evenement)

    def _adopter(self, connexion: socket_web.Socket) -> None:
        """Le bout serveur d'une connexion acceptée par ``QTcpServer``."""
        self._socket, self._etat = connexion, _Etat.ConnectedState
        connexion.setblocking(False)
        socket_web._veiller(connexion, self._evenement)
        plus_tard(self._evenement)

    def _plus_tard(self, rappel) -> None:
        tentative = self._tentative
        plus_tard(lambda: rappel() if tentative == self._tentative else None)

    def _evenement(self) -> None:
        s = self._socket
        if s is None:
            return
        if self._etat == _Etat.ConnectingState:
            if s._etat == "etablie":
                self._changer(_Etat.ConnectedState)
                self.connected.emit()
            elif s._etat != "attente":
                self._echouer(_Erreur.ConnectionRefusedError, "Connection refused")
                return
        if self._etat != _Etat.ConnectedState:
            return
        if len(s._tampon) > self._annonces:
            self._annonces = len(s._tampon)
            self.readyRead.emit()
        if s._fin_recue and not s._tampon and self._socket is s:
            self._erreur, self._message = _Erreur.RemoteHostClosedError, "The remote host closed the connection"
            self.errorOccurred.emit(self._erreur)
            self._fermer()

    def _echouer(self, erreur, message: str) -> None:
        self._erreur, self._message = erreur, message
        self._liberer()
        self._changer(_Etat.UnconnectedState)
        self.errorOccurred.emit(erreur)

    def _liberer(self) -> None:
        self._tentative += 1
        if self._socket is not None:
            self._socket.close()
            self._socket, self._annonces = None, 0

    def _fermer(self) -> None:
        connecte = self._etat == _Etat.ConnectedState
        self._liberer()
        if self._etat != _Etat.UnconnectedState:
            if connecte:
                self._changer(_Etat.ClosingState)
            self._changer(_Etat.UnconnectedState)
            if connecte:
                self.disconnected.emit()

    def _changer(self, etat) -> None:
        if etat != self._etat:
            self._etat = etat
            self.stateChanged.emit(etat)

    def disconnectFromHost(self) -> None:  # noqa: N802
        self._fermer()

    close = abort = disconnectFromHost

    # Échanges

    def write(self, donnees: Any) -> int:
        if self._etat != _Etat.ConnectedState:
            return -1
        try:
            n = self._socket.send(bytes(donnees))
        except OSError:
            return -1
        self._plus_tard(lambda: self.bytesWritten.emit(n))
        return n

    def read(self, taille: int) -> QByteArray:
        s = self._socket
        if s is None:
            return QByteArray()
        octets = bytes(s._tampon[:taille])
        del s._tampon[:len(octets)]
        self._annonces = len(s._tampon)
        if s._fin_recue and not s._tampon:
            plus_tard(self._evenement)
        return QByteArray(octets)

    def readAll(self) -> QByteArray:  # noqa: N802
        return self.read(self.bytesAvailable())

    def bytesAvailable(self) -> int:  # noqa: N802
        return len(self._socket._tampon) if self._socket is not None else 0

    def flush(self) -> bool:
        return False  # rien n'attend : write a déjà remis les octets

    # État

    def state(self):
        return self._etat

    def error(self):
        return self._erreur

    def errorString(self) -> str:  # noqa: N802
        return self._message or "Unknown error"

    def isValid(self) -> bool:  # noqa: N802
        return self._socket is not None

    def isOpen(self) -> bool:  # noqa: N802
        return self._etat == _Etat.ConnectedState

    def peerAddress(self) -> QHostAddress:  # noqa: N802
        return QHostAddress(self._socket._pair[0]) if self.isOpen() else QHostAddress()

    def peerPort(self) -> int:  # noqa: N802
        return self._socket._pair[1] if self.isOpen() else 0

    def localAddress(self) -> QHostAddress:  # noqa: N802
        return QHostAddress(self._socket._adresse[0]) if self._socket is not None else QHostAddress()

    def localPort(self) -> int:  # noqa: N802
        return self._socket._adresse[1] if self._socket is not None else 0


class QTcpServer(QObject):
    """L'écoute d'un port de la boucle locale ; chaque connexion arrivée devient un ``QTcpSocket`` enfant."""

    newConnection = Signal()
    acceptError = Signal(_Erreur)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket: socket_web.Socket | None = None
        self._en_attente: list[QTcpSocket] = []
        self._erreur, self._message = _Erreur.UnknownSocketError, ""

    def listen(self, adresse: Any = QHostAddress.SpecialAddress.Any, port: int = 0) -> bool:
        if self._socket is not None:  # comme Qt : l'écoute en cours reste
            self._erreur, self._message = _Erreur.OperationError, "The server is already listening"
            return False
        s = socket_web.Socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((_hote(adresse), int(port)))
            s.listen()
        except OSError as erreur:
            s.close()
            self._erreur, self._message = _Erreur.AddressInUseError, erreur.strerror or str(erreur)
            return False
        s.setblocking(False)
        self._socket = s
        socket_web._veiller(s, self._evenement)
        return True

    def _evenement(self) -> None:
        while self._socket is not None:
            try:
                connexion, _pair = self._socket.accept()
            except (BlockingIOError, OSError):
                return
            bout = QTcpSocket(self)
            bout._adopter(connexion)
            self._en_attente.append(bout)
            self.newConnection.emit()

    def hasPendingConnections(self) -> bool:  # noqa: N802
        return bool(self._en_attente)

    def nextPendingConnection(self) -> QTcpSocket | None:  # noqa: N802
        return self._en_attente.pop(0) if self._en_attente else None

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        while self._en_attente:  # comme Qt : les connexions jamais reprises sont fermées
            self._en_attente.pop().abort()

    def isListening(self) -> bool:  # noqa: N802
        return self._socket is not None

    def serverPort(self) -> int:  # noqa: N802
        return self._socket.getsockname()[1] if self._socket is not None else 0

    def serverAddress(self) -> QHostAddress:  # noqa: N802
        return QHostAddress(self._socket.getsockname()[0]) if self._socket is not None else QHostAddress()

    def serverError(self):  # noqa: N802
        return self._erreur

    def errorString(self) -> str:  # noqa: N802
        return self._message

    def setMaxPendingConnections(self, _n: int) -> None:  # noqa: N802
        pass


class QNetworkAddressEntry:
    def __init__(self, ip: QHostAddress, masque: QHostAddress) -> None:
        self._ip, self._masque = ip, masque

    def ip(self) -> QHostAddress:
        return self._ip

    def netmask(self) -> QHostAddress:
        return self._masque

    def broadcast(self) -> QHostAddress:
        return QHostAddress()


class QNetworkInterface:
    """La seule interface d'une page : la boucle locale (aucune adresse joignable depuis un autre poste)."""

    class InterfaceFlag(enum.Flag):
        IsUp = 0x1
        IsRunning = 0x2
        CanBroadcast = 0x4
        IsLoopBack = 0x8
        IsPointToPoint = 0x10
        CanMulticast = 0x20

    IsUp, IsRunning, CanBroadcast = InterfaceFlag.IsUp, InterfaceFlag.IsRunning, InterfaceFlag.CanBroadcast
    IsLoopBack, IsPointToPoint, CanMulticast = InterfaceFlag.IsLoopBack, InterfaceFlag.IsPointToPoint, InterfaceFlag.CanMulticast

    def isValid(self) -> bool:  # noqa: N802
        return True

    def index(self) -> int:
        return 1

    def name(self) -> str:
        return "lo"

    humanReadableName = name

    def flags(self) -> InterfaceFlag:
        return self.IsUp | self.IsRunning | self.IsLoopBack

    def addressEntries(self) -> list[QNetworkAddressEntry]:  # noqa: N802
        return [QNetworkAddressEntry(QHostAddress("127.0.0.1"), QHostAddress("255.0.0.0"))]

    @staticmethod
    def allInterfaces() -> list[QNetworkInterface]:  # noqa: N802
        return [QNetworkInterface()]

    @staticmethod
    def allAddresses() -> list[QHostAddress]:  # noqa: N802
        return [QHostAddress("127.0.0.1")]
