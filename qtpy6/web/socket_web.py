"""Doublure de ``socket``, ``select`` et ``selectors`` dans le navigateur, où une socket TCP ne joint personne. Deux usages :

- le choix d'un port libre par jupyter_client (``LocalPortCache.find_available_port`` : ``SO_LINGER``, ``bind((ip, 0))``,
  ``getsockname``). Les sockets d'Emscripten ne savent pas le faire (« Protocol not available » sur ``SO_LINGER``,
  mesuré dans Firefox au jalon 8a) ; or ce port ne sert qu'à zmq, dont la doublure (zmq_web) tient le registre des
  ports liés : le port « libre » se tire donc dans ce registre, sans socket réelle ;
- le TCP de boucle locale (``boucle_locale``, vrai sous emscripten) : un serveur (pylsp ``--tcp`` sur
  ``socketserver``) et son client (la passerelle LSP de Spyder) dans deux interpréteurs. ``bind``/``listen``/``accept``,
  ``connect``, ``send``/``recv``, ``makefile`` passent par les opérations de flux de zmq_web (même registre de ports,
  même routage ``postMessage`` : page ↔ Worker, et Worker ↔ Worker relayé par la page) ; une attente (``recv``,
  ``accept``, ``connect``) passe par le crochet ``attendre``. ``select.select`` et ``selectors`` (que lit
  ``socketserver.serve_forever``) savent attendre ces sockets.

Tout le reste (AF_UNIX, UDP, autres hôtes) passe à la vraie socket. ``doubler_qsocketnotifier`` donne à
``QtCore.QSocketNotifier`` le même service pour le descripteur d'une socket zmq_web (``getsockopt(zmq.FD)``, lu par le
client LSP de Spyder) ou d'une socket de ce module. Python pur : Qt n'y est reçu qu'en paramètre."""

from __future__ import annotations

import errno
import os
import random
import select as _select_module
import selectors
import socket
import sys
import types
import weakref
from collections import deque
from typing import Any

from . import zmq_web
from .threading_web import attendre, plus_tard, poster

_Socket = socket.socket
_select_reel = _select_module.select
boucle_locale = sys.platform == "emscripten"  # les tests natifs le posent
_HOTES_LOCAUX = {"127.0.0.1", "localhost", "::1", "0.0.0.0", "::", ""}
_installe = False


def port_libre() -> int:
    """Un port éphémère qu'aucune socket zmq ni TCP de la page ni d'un Worker n'a lié."""
    while True:
        port = random.randrange(49152, 65536)
        if port not in zmq_web._lies and port not in zmq_web._distants and port not in zmq_web._ecoutes:
            return port


def _delai_ms(secondes: float | None) -> int | None:
    return None if secondes is None else int(secondes * 1000)


class Socket(_Socket):
    """Une vraie socket, qui devient une doublure de boucle locale au ``bind`` ou au ``connect`` (``_mode`` :
    ``"lie"`` après bind, ``"ecoute"``, ``"connexion"`` ; ``None`` : la vraie)."""

    _adresse: tuple | None = None
    _mode: str | None = None

    # Le choix du mode

    def _eligible(self, adresse: Any) -> bool:
        return (boucle_locale and self.family in (socket.AF_INET, socket.AF_INET6)
                and self.type == socket.SOCK_STREAM and isinstance(adresse, tuple) and len(adresse) >= 2
                and adresse[0] in _HOTES_LOCAUX)

    def _devenir(self, mode: str) -> None:
        if self._mode is None:
            self._fd = next(zmq_web._numeros_fd)
            zmq_web._par_fd[self._fd] = self
            self._veilleurs: list = []
            self._attente: deque[Socket] = deque()  # écoute : connexions arrivées, pas encore acceptées
            self._tampon = bytearray()
            self._fin_recue = self._fin_envoyee = False
            self._etat = ""  # connexion : "attente", "etablie", "refusee", "fermee"
            self._vers: Any = None  # connexion locale : l'autre bout ; distante : l'interpréteur (None = la page)
            self._local = False
            self._conn = ""
            self._pair: tuple | None = None
        self._mode = mode

    def setsockopt(self, niveau: int, option: int, *valeur) -> None:
        try:
            super().setsockopt(niveau, option, *valeur)
        except OSError:
            if option != socket.SO_LINGER and self._mode is None:  # sans objet : la socket n'est pas réellement liée
                raise

    def fileno(self) -> int:
        return self._fd if self._mode is not None else super().fileno()

    # Liaison et écoute

    def bind(self, adresse) -> None:
        if self._eligible(adresse):
            port = adresse[1]
            if port and (port in zmq_web._lies or port in zmq_web._ecoutes or port in zmq_web._distants):
                raise OSError(errno.EADDRINUSE, os.strerror(errno.EADDRINUSE))
            self._devenir("lie")
            self._adresse = (adresse[0], port or port_libre())
        elif isinstance(adresse, tuple) and len(adresse) >= 2 and adresse[1] == 0:
            self._adresse = (adresse[0], port_libre())
        else:
            super().bind(adresse)

    def getsockname(self):
        return self._adresse or super().getsockname()

    def listen(self, backlog: int = 0) -> None:
        if self._mode != "lie":
            return super().listen(backlog)
        if zmq_web._ecoutes.get(self._adresse[1], self) is not self:
            raise OSError(errno.EADDRINUSE, os.strerror(errno.EADDRINUSE))
        self._mode = "ecoute"
        zmq_web._ecoutes[self._adresse[1]] = self
        if zmq_web.en_travailleur:  # la page apprend où joindre ce port (l'op ``bind`` de zmq)
            poster(None, zmq_web._op(op="bind", port=self._adresse[1]))

    def _arrivee(self, conn: str, origine: Any, adresse: Any, local: Socket | None = None) -> None:
        """Une connexion arrive sur ce port (``zmq_web`` : ``flux_connect``) ; ``local`` : le client est ici."""
        serveur = Socket(self.family, self.type)
        serveur._devenir("connexion")
        serveur._adresse, serveur._pair, serveur._conn = self._adresse, tuple(adresse), conn
        serveur._etat, serveur._local = "etablie", local is not None
        serveur._vers = local if local is not None else origine
        if local is None:
            zmq_web._flux[conn] = serveur
            poster(origine, zmq_web._op(op="flux_accepte", conn=conn))
        self._attente.append(serveur)
        self._signaler()

    def accept(self):
        if self._mode != "ecoute":
            return super().accept()
        self._attendre(lambda: bool(self._attente) or self._closed)
        if self._closed:
            raise OSError(errno.EBADF, os.strerror(errno.EBADF))
        serveur = self._attente.popleft()
        return serveur, serveur._pair

    # Connexion

    def connect(self, adresse) -> None:
        if not self._eligible(adresse):
            return super().connect(adresse)
        if self._mode == "connexion" and self._etat == "etablie":
            raise OSError(errno.EISCONN, os.strerror(errno.EISCONN))
        hote, port = adresse[0], adresse[1]
        self._devenir("connexion")
        if self._adresse is None:
            self._adresse = (hote if hote not in ("", "0.0.0.0", "::") else "127.0.0.1", port_libre())
        self._pair, self._conn, self._etat = (hote, port), os.urandom(8).hex(), "attente"
        ecoute = zmq_web._ecoutes.get(port)
        if ecoute is not None:
            self._vers, self._local, self._etat = None, True, "etablie"
            ecoute._arrivee(self._conn, None, self._adresse, local=self)
            self._vers = ecoute._attente[-1]
            return
        connu, destination = zmq_web._destination(port)
        if not connu:
            self._etat = "refusee"
        else:
            self._vers = destination
            zmq_web._flux[self._conn] = self
            poster(destination, zmq_web._op(op="flux_connect", port=port, conn=self._conn, adresse=list(self._adresse)))
            try:
                self._attendre(lambda: self._etat != "attente")
            except socket.timeout:  # abandonnée : une acceptation tardive reçoit flux_fin (zmq_web._recevoir_flux)
                zmq_web._flux.pop(self._conn, None)
                self._etat = "fermee"
                raise
        if self._etat == "refusee":
            zmq_web._flux.pop(self._conn, None)
            raise ConnectionRefusedError(errno.ECONNREFUSED, os.strerror(errno.ECONNREFUSED))

    def connect_ex(self, adresse) -> int:
        try:
            self.connect(adresse)
        except OSError as erreur:
            return erreur.errno or errno.EIO
        return 0

    def getpeername(self):
        if self._mode is None:
            return super().getpeername()
        if self._mode != "connexion" or self._etat != "etablie":
            raise OSError(errno.ENOTCONN, os.strerror(errno.ENOTCONN))
        return self._pair

    def _recevoir(self, message: dict[str, Any]) -> None:
        """Une opération de flux pour ce bout (zmq_web la route ici par son identifiant de connexion)."""
        operation = message["op"]
        if operation == "flux_accepte":
            self._etat = "etablie" if self._etat == "attente" else self._etat
        elif operation == "flux_refus":
            self._etat = "refusee"
        elif operation == "flux_octets":
            self._tampon += message["octets"]
        elif operation == "flux_fin":
            if self._etat == "attente":
                self._etat = "refusee"
            self._fin_recue = True
        self._signaler()

    def _transmettre(self, message: dict[str, Any]) -> None:
        if self._local:
            if self._vers is not None:
                self._vers._recevoir(message)
        else:
            poster(self._vers, message)

    # Échanges

    def _attendre(self, condition) -> None:
        """Attend ``condition`` selon le délai de la socket : ``BlockingIOError`` en non bloquant, ``TimeoutError`` à
        l'échéance."""
        if condition():
            return
        delai = self.gettimeout()
        if delai == 0:
            raise BlockingIOError(errno.EAGAIN, os.strerror(errno.EAGAIN))
        if not attendre(condition, _delai_ms(delai)):
            raise socket.timeout("timed out")

    def send(self, donnees, flags: int = 0) -> int:
        if self._mode != "connexion":
            return super().send(donnees, flags)
        if self._closed or self._etat != "etablie" or self._fin_envoyee:
            raise BrokenPipeError(errno.EPIPE, os.strerror(errno.EPIPE))
        octets = bytes(donnees)
        if octets:
            self._transmettre(zmq_web._op(op="flux_octets", conn=self._conn, octets=octets))
        return len(octets)

    def sendall(self, donnees, flags: int = 0) -> None:
        if self._mode != "connexion":
            return super().sendall(donnees, flags)
        self.send(donnees, flags)

    def recv(self, taille: int, flags: int = 0) -> bytes:
        if self._mode != "connexion":
            return super().recv(taille, flags)
        if self._etat != "etablie":
            raise OSError(errno.ENOTCONN, os.strerror(errno.ENOTCONN))
        self._attendre(lambda: bool(self._tampon) or self._fin_recue or self._closed)
        octets = bytes(self._tampon[:taille])
        if not flags & socket.MSG_PEEK:
            del self._tampon[:len(octets)]
        return octets

    def recv_into(self, tampon, nbytes: int = 0, flags: int = 0) -> int:
        if self._mode != "connexion":
            return super().recv_into(tampon, nbytes, flags)
        vue = memoryview(tampon).cast("B")
        octets = self.recv(nbytes or len(vue), flags)
        vue[:len(octets)] = octets
        return len(octets)

    def shutdown(self, how: int) -> None:
        if self._mode != "connexion":
            return super().shutdown(how)
        if how in (socket.SHUT_WR, socket.SHUT_RDWR):
            self._finir()

    def _finir(self) -> None:
        if not self._fin_envoyee and self._etat == "etablie":
            self._fin_envoyee = True
            self._transmettre(zmq_web._op(op="flux_fin", conn=self._conn))

    def _real_close(self, _ss=_Socket) -> None:
        if self._mode == "connexion":
            self._finir()
            zmq_web._flux.pop(self._conn, None)
            self._etat = "fermee" if self._etat == "etablie" else self._etat
        elif self._mode == "ecoute":
            if zmq_web._ecoutes.get(self._adresse[1]) is self:
                del zmq_web._ecoutes[self._adresse[1]]
            while self._attente:  # les connexions arrivées, jamais acceptées : le client voit la fin
                self._attente.popleft().close()
        if self._mode is not None:
            self._signaler()
        super()._real_close()

    # Disponibilité (select, selectors, QSocketNotifier)

    def _lisible(self) -> bool:
        if self._mode == "ecoute":
            return bool(self._attente) or self._closed
        return self._mode == "connexion" and (bool(self._tampon) or self._fin_recue
                                             or self._etat not in ("etablie", "attente"))

    def _ecrivable(self) -> bool:
        return self._mode == "connexion" and self._etat != "attente"

    def _signaler(self) -> None:
        for veilleur in list(self._veilleurs):
            plus_tard(veilleur)


# --- Attente de plusieurs descripteurs ----------------------------------------------------------------------------

def _objet(fd: Any) -> Any:
    """La socket zmq_web ou de ce module dont ``fd`` (entier ou objet à ``fileno()``) est le descripteur, sinon None."""
    try:
        numero = fd if isinstance(fd, int) else fd.fileno()
    except (AttributeError, OSError, ValueError):
        return None
    return zmq_web._par_fd.get(numero)


def _pret(objet: Any, lecture: bool) -> bool:
    if isinstance(objet, zmq_web.Socket):
        return bool(objet._evenements(zmq_web.POLLIN if lecture else zmq_web.POLLOUT))
    return objet._lisible() if lecture else objet._ecrivable()


def _veiller(objet: Any, rappel) -> None:
    """``rappel`` appelé (tâche suivante) à chaque changement de ``objet`` ; gardé par référence faible s'il est une
    méthode, retiré quand son receveur meurt."""
    reference = weakref.WeakMethod(rappel) if hasattr(rappel, "__self__") else (lambda: rappel)

    def veilleur() -> None:
        fonction = reference()
        if fonction is None:
            if veilleur in objet._veilleurs:
                objet._veilleurs.remove(veilleur)
        else:
            fonction()

    objet._veilleurs.append(veilleur)


def select(rlist, wlist, xlist, timeout: float | None = None):
    """``select.select`` : les sockets de la doublure attendues par ``attendre`` ; sans elles, le vrai."""
    if not any(_objet(f) is not None for f in (*rlist, *wlist)):
        return _select_reel(rlist, wlist, xlist, timeout)

    def prets() -> tuple[list, list]:
        return ([f for f in rlist if _disponible(f, True)], [f for f in wlist if _disponible(f, False)])

    attendre(lambda: any(prets()), None if timeout is None else max(0, int(timeout * 1000)))
    lus, ecrits = prets()
    return lus, ecrits, []


def _disponible(fichier: Any, lecture: bool) -> bool:
    objet = _objet(fichier)
    if objet is not None:
        return _pret(objet, lecture)
    vrais = _select_reel([fichier], [], [], 0) if lecture else _select_reel([], [fichier], [], 0)
    return bool(vrais[0] or vrais[1])


class Selecteur(selectors._BaseSelectorImpl):
    """``selectors.DefaultSelector`` (et ``PollSelector``, ``SelectSelector``) : ``select`` attend par ``attendre``."""

    def select(self, timeout: float | None = None):
        def prets() -> list:
            resultat = []
            for cle in list(self._fd_to_key.values()):
                evenements = ((selectors.EVENT_READ if cle.events & selectors.EVENT_READ and _disponible(cle.fd, True)
                               else 0)
                              | (selectors.EVENT_WRITE if cle.events & selectors.EVENT_WRITE
                                 and _disponible(cle.fd, False) else 0))
                if evenements:
                    resultat.append((cle, evenements))
            return resultat

        if timeout is None or timeout > 0:
            attendre(lambda: bool(prets()), _delai_ms(timeout))
        return prets()


# --- QSocketNotifier ----------------------------------------------------------------------------------------------

def doubler_qsocketnotifier(ns: dict[str, Any], module: Any) -> type:
    """Pose dans ``ns`` (QtCore de qtpy6) et dans ``module`` (le QtCore de la liaison, que lit ``qtpy``) un
    ``QSocketNotifier`` qui sait veiller le descripteur d'une socket zmq_web ou de ce module : ``activated`` est émis à
    la tâche suivante d'une arrivée, et à ``setEnabled(True)`` si la socket est déjà prête. Pour tout autre descripteur,
    le constructeur rend la vraie classe."""
    Vrai, QObject, Signal = module.QSocketNotifier, ns["QObject"], ns["Signal"]
    Descripteur = getattr(module, "QSocketDescriptor", None)

    class QSocketNotifier(QObject):
        Type = Vrai.Type
        Read, Write, Exception = Vrai.Type.Read, Vrai.Type.Write, Vrai.Type.Exception
        activated = Signal(Descripteur or int, Vrai.Type)

        def __new__(cls, socket_, type_, parent=None):
            if _objet(socket_) is None:
                return Vrai(socket_, type_, parent)
            return super().__new__(cls)

        def __init__(self, socket_, type_, parent=None) -> None:
            super().__init__(parent)
            self._type, self._actif, self._prevu = type_, True, False
            self.setSocket(socket_)

        def setSocket(self, socket_) -> None:  # noqa: N802
            self._fd = socket_ if isinstance(socket_, int) else socket_.fileno()
            _veiller(_objet(self._fd), self._signaler)
            self._signaler()

        def _signaler(self) -> None:
            if not self._prevu:
                self._prevu = True
                plus_tard(self._emettre)

        def _prete(self) -> bool:
            objet = _objet(self._fd)
            return objet is not None and self._type != Vrai.Type.Exception and _pret(objet, self._type == Vrai.Type.Read)

        def _emettre(self) -> None:
            self._prevu = False
            if self._actif and self._prete():
                self.activated.emit(Descripteur(self._fd) if Descripteur else self._fd, self._type)

        def setEnabled(self, enable: bool) -> None:  # noqa: N802
            self._actif = bool(enable)
            if self._actif and self._prete():
                self._signaler()

        def isEnabled(self) -> bool:  # noqa: N802
            return self._actif

        def isValid(self) -> bool:  # noqa: N802
            return True

        def socket(self) -> int:
            return self._fd

        def type(self):
            return self._type

    QSocketNotifier.__module__, QSocketNotifier.__doc__ = Vrai.__module__, Vrai.__doc__
    ns["QSocketNotifier"] = QSocketNotifier
    module.QSocketNotifier = QSocketNotifier
    return QSocketNotifier


# --- Le descripteur lu par os (fstat, read, write, close) ---------------------------------------------------------

_os_reel = {nom: getattr(os, nom) for nom in ("fstat", "read", "write", "close")}


def _socket_de(fd: Any) -> Socket | None:
    objet = zmq_web._par_fd.get(fd) if isinstance(fd, int) else None
    return objet if isinstance(objet, Socket) else None


def _fstat(fd, *a, **k):
    s = _socket_de(fd)
    if s is None:
        return _os_reel["fstat"](fd, *a, **k)
    import stat  # noqa: PLC0415
    return os.stat_result((stat.S_IFSOCK | 0o777, 0, 0, 1, os.getuid(), os.getgid(), 0, 0, 0, 0))


def _read(fd, n):
    s = _socket_de(fd)
    return _os_reel["read"](fd, n) if s is None else s.recv(n)


def _write(fd, donnees):
    s = _socket_de(fd)
    return _os_reel["write"](fd, donnees) if s is None else s.send(donnees)


def _close(fd):
    s = _socket_de(fd)
    return _os_reel["close"](fd) if s is None else s.close()


def doubler_os() -> None:
    """``os.fstat``, ``os.read``, ``os.write`` et ``os.close`` sur le descripteur d'une socket de ce module (que le
    système ne connaît pas) : la socket, comme sur le bureau. La passerelle LSP de Spyder lit pylsp par
    ``pexpect.fdpexpect.fdspawn(socket)`` (W548)."""
    os.fstat, os.read, os.write, os.close = _fstat, _read, _write, _close


# --- Terminal (termios, fcntl, resource) --------------------------------------------------------------------------

def _refuser(*_a, **_k):
    raise OSError(errno.ENOTTY, os.strerror(errno.ENOTTY))


def doubler_terminal(noms: tuple[str, ...] | None = None) -> None:
    """Pose ``termios``, ``fcntl`` et ``resource`` là où l'interpréteur ne les a pas (Pyodide : aucun des trois), pour
    que s'importent ``pty``, ``tty`` et ``ptyprocess`` : la passerelle LSP de Spyder importe ``pexpect.fdpexpect`` sans
    s'en servir en TCP (W548). Un appel lève ``ENOTTY``, ce que rend un descripteur qui n'est pas un terminal. ``noms`` :
    ceux à doubler (les tests natifs) ; par défaut, les absents."""
    import importlib.util  # noqa: PLC0415
    if noms is None:
        noms = tuple(n for n in ("termios", "fcntl", "resource")
                     if n not in sys.modules and importlib.util.find_spec(n) is None)
    for nom in noms:
        module = types.ModuleType(nom)
        if nom == "termios":
            class error(Exception):  # noqa: N801 - le nom de termios
                pass

            def refuser(*_a, _erreur=error, **_k):
                raise _erreur(errno.ENOTTY, os.strerror(errno.ENOTTY))
            module.error = error
            module.TCSANOW, module.TCSADRAIN, module.TCSAFLUSH = 0, 1, 2  # tty : valeurs par défaut de ses fonctions
            for fonction in ("tcgetattr", "tcsetattr", "tcsendbreak", "tcdrain", "tcflush", "tcflow",
                             "tcgetwinsize", "tcsetwinsize"):
                setattr(module, fonction, refuser)
            module.__all__ = ["error", "TCSANOW", "TCSADRAIN", "TCSAFLUSH", "tcgetattr", "tcsetattr", "tcsendbreak", "tcdrain", "tcflush", "tcflow",
                              "tcgetwinsize", "tcsetwinsize"]
        elif nom == "fcntl":
            for fonction in ("fcntl", "ioctl", "flock", "lockf"):
                setattr(module, fonction, _refuser)
        else:
            module.error = OSError
            module.RLIMIT_NOFILE, module.RLIM_INFINITY = 7, -1
            module.getrlimit = lambda _ressource: (1024, 1024)
            module.setrlimit = _refuser
        sys.modules[nom] = module


# --- Installation -------------------------------------------------------------------------------------------------

def installer() -> None:
    """Pose ``socket.socket`` ; avec ``boucle_locale``, aussi ``select.select`` et les sélecteurs (et celui que
    ``socketserver`` a déjà lu s'il est importé). Une seconde fois : sans effet."""
    global _installe
    if _installe:
        return
    _installe = True
    socket.socket = Socket
    if not boucle_locale:
        return
    doubler_terminal()
    doubler_os()
    _select_module.select = select
    for nom in ("DefaultSelector", "SelectSelector", "PollSelector"):
        if hasattr(selectors, nom):
            setattr(selectors, nom, Selecteur)
    serveur = sys.modules.get("socketserver")
    if serveur is not None:
        serveur._ServerSelector = Selecteur
