"""``zmq`` (pyzmq) dans le navigateur, où il n'y a ni socket ni processus : Spyder y lance un noyau Jupyter dans un Web
Worker (second Pyodide), et jupyter_client (la page) comme ipykernel (le Worker) parlent pyzmq. Ce module fournit un
``zmq`` de même API dont le transport est ``postMessage`` entre interpréteurs ; le code de l'application n'est jamais
modifié. ``installer()`` l'enregistre sous le nom ``zmq`` (et ses sous-modules) quand pyzmq n'est pas importable.

Ce que l'hôte fournit : les crochets ``attendre``, ``plus_tard`` et ``poster`` (définis, avec leurs défauts natifs pour
les tests, dans ``threading_web`` : une seule file, un seul ``pomper``), ``recevoir`` pour ce qui arrive de l'autre
interpréteur et ``declarer_distant`` pour apprendre quel interpréteur a lié un port. Python pur, sans Qt.

Le modèle : une socket LIÉE (``bind``) connaît ses pairs par leur identité (``_pairs``) ; une socket CONNECTÉE
(``connect``) connaît une cible (``_cible``) : une socket liée locale, ou un interpréteur distant. Les deux sens se
décrivent par la même classe ``_Pair`` ; les types de socket ne décident que du préfixe d'identité (ROUTER, REP) et du
filtrage (PUB, SUB). Les messages entre interpréteurs sont des dictionnaires ``{"op": …}`` (l'hôte les enveloppe sous la clé
``"zmq"`` en les postant, et passe le contenu à ``recevoir``) :

- ``connect``    {port, type, pair, abonnements}   une socket se connecte à un port lié chez le destinataire ;
- ``vers_lie``   {port, pair, frames}              de la socket connectée ``pair`` vers la socket liée au port ;
- ``vers_pair``  {port, pair, frames}              de la socket liée au port vers la socket connectée d'identité ``pair``
                                                   (une identité peut servir à plusieurs ports : shell et control) ;
- ``subscribe`` / ``unsubscribe`` {port, pair, topic} ;  ``disconnect`` {port, pair} ;
- ``bind``       {port}                            un Worker annonce à la page un port qu'il vient de lier ;
- ``echo``       {port}                            un Worker annonce que ce port lié n'est qu'un écho (le battement de
                                                   cœur d'ipykernel) : la page répond à sa place tant qu'il vit, même
                                                   pendant un calcul qui ne rend jamais la main."""

from __future__ import annotations

import asyncio as _asyncio
import enum
import errno as _errno
import importlib.machinery
import importlib.util
import itertools
import json
import logging
import os
import pickle
import random
import sys
import types
import weakref
from collections import deque
from typing import Any, Callable

from . import threading_web as _fils
from .threading_web import attendre, plus_tard, poster

pomper = _fils.pomper  # le même que celui de threading_web : une seule file

__version__ = "26.0.0"
en_travailleur = False  # posé par l'hôte dans le Worker : un port ni lié ni déclaré y est supposé à la page


def zmq_version() -> str:
    return "4.3.5"


def pyzmq_version() -> str:
    return __version__


def zmq_version_info() -> tuple[int, int, int]:
    return (4, 3, 5)


def pyzmq_version_info() -> tuple[int, int, int]:
    return (26, 0, 0)


def has(_nom: str) -> bool:
    return False


def curve_keypair() -> tuple[bytes, bytes]:
    raise ZMQError(ENOTSUP)


# --- Constantes ---------------------------------------------------------------------------------------------------

class SocketType(enum.IntEnum):
    PAIR = 0
    PUB = 1
    SUB = 2
    REQ = 3
    REP = 4
    DEALER = 5
    ROUTER = 6
    PULL = 7
    PUSH = 8
    XPUB = 9
    XSUB = 10
    STREAM = 11


class Flag(enum.IntEnum):
    DONTWAIT = 1
    NOBLOCK = 1
    SNDMORE = 2


class PollEvent(enum.IntEnum):
    POLLIN = 1
    POLLOUT = 2
    POLLERR = 4


class SocketOption(enum.IntEnum):
    AFFINITY = 4
    IDENTITY = 5
    ROUTING_ID = 5
    SUBSCRIBE = 6
    UNSUBSCRIBE = 7
    RCVMORE = 13
    FD = 14
    EVENTS = 15
    TYPE = 16
    LINGER = 17
    RECONNECT_IVL = 18
    BACKLOG = 19
    SNDHWM = 23
    RCVHWM = 24
    RCVTIMEO = 27
    SNDTIMEO = 28
    LAST_ENDPOINT = 32
    TCP_KEEPALIVE = 34
    TCP_KEEPALIVE_CNT = 35
    TCP_KEEPALIVE_IDLE = 36
    TCP_KEEPALIVE_INTVL = 37
    IPV6 = 42
    ROUTER_HANDOVER = 56


PAIR, PUB, SUB, REQ, REP, DEALER, ROUTER, PULL, PUSH, XPUB, XSUB, STREAM = SocketType
DONTWAIT, NOBLOCK, SNDMORE = Flag.DONTWAIT, Flag.NOBLOCK, Flag.SNDMORE
POLLIN, POLLOUT, POLLERR = PollEvent
IDENTITY, SUBSCRIBE, UNSUBSCRIBE, RCVMORE = (SocketOption.IDENTITY, SocketOption.SUBSCRIBE,
                                             SocketOption.UNSUBSCRIBE, SocketOption.RCVMORE)
FD, EVENTS, TYPE, LINGER = SocketOption.FD, SocketOption.EVENTS, SocketOption.TYPE, SocketOption.LINGER
RCVTIMEO, SNDTIMEO, LAST_ENDPOINT = SocketOption.RCVTIMEO, SocketOption.SNDTIMEO, SocketOption.LAST_ENDPOINT
STREAMER, FORWARDER, QUEUE = 1, 2, 3
EAGAIN, ENOTSOCK, EADDRINUSE = _errno.EAGAIN, _errno.ENOTSOCK, _errno.EADDRINUSE
EINVAL, ENOTSUP, EINTR = _errno.EINVAL, _errno.ENOTSUP, _errno.EINTR
ETERM, EFSM = 156384765, 156384763
globals().update(SocketType.__members__, **Flag.__members__, **PollEvent.__members__, **SocketOption.__members__)

_DEFAUTS = {LINGER: -1, RCVTIMEO: -1, SNDTIMEO: -1, SocketOption.SNDHWM: 1000, SocketOption.RCVHWM: 1000}


def _constantes() -> dict[str, Any]:
    """Les constantes nues de ``zmq`` et de ``zmq.constants`` : les membres des énumérations (alias compris), et les
    entiers qui n'en font pas partie."""
    constantes: dict[str, Any] = {}
    for enumeration in (SocketType, Flag, PollEvent, SocketOption):
        constantes.update(enumeration.__members__)
    for nom in ("STREAMER", "FORWARDER", "QUEUE", "EAGAIN", "ENOTSOCK", "EADDRINUSE", "EINVAL", "ENOTSUP", "EINTR",
                "ETERM", "EFSM"):
        constantes[nom] = globals()[nom]
    return constantes


# --- Erreurs ------------------------------------------------------------------------------------------------------

_MESSAGES = {ETERM: "Context was terminated", EFSM: "Operation cannot be accomplished in current state"}


class ZMQError(Exception):
    errno_defaut: int | None = None

    def __init__(self, errno: int | None = None, msg: str | None = None) -> None:
        self.errno = self.errno_defaut if errno is None else errno
        self.strerror = msg if msg is not None else _MESSAGES.get(self.errno) or os.strerror(self.errno or 0)
        super().__init__(self.strerror)

    def __str__(self) -> str:
        return self.strerror


class Again(ZMQError):
    errno_defaut = EAGAIN


class ContextTerminated(ZMQError):
    errno_defaut = ETERM


class ZMQBindError(ZMQError):
    pass


class NotDone(ZMQError):
    pass


class InterruptedSystemCall(ZMQError):
    errno_defaut = EINTR


# --- Registres ----------------------------------------------------------------------------------------------------

_lies: dict[int | str, Socket] = {}  # port (tcp) ou endpoint (ipc, inproc) → socket liée
_distants: dict[int, str | None] = {}  # port → interpréteur qui l'a lié (côté page)
_connectees: dict[tuple[int | str, bytes], Socket] = {}  # (port, identité) → socket connectée à un interpréteur distant
_echos: dict[int, Any] = {}  # port → interpréteur qui l'a annoncé ``echo`` (côté page)
_attentes: list[tuple[Socket, int | str]] = []  # connect() vers un port ni lié ni déclaré : libzmq l'accepte aussi
_numeros_fd = itertools.count(1000)
_sockets_connues: weakref.WeakValueDictionary[int, Socket] = weakref.WeakValueDictionary()  # underlying → socket


def reinitialiser() -> None:
    """Vide registres et crochets (pour les tests)."""
    global en_travailleur
    _lies.clear()
    _distants.clear()
    _echos.clear()
    _connectees.clear()
    _attentes.clear()
    en_travailleur = False
    _fils.reinitialiser_crochets()
    for classe in (Context, ContextAsync):
        classe._instance = None


def _op(**champs: Any) -> dict[str, Any]:
    return champs


def _analyser(endpoint: str | bytes) -> tuple[int | str, str]:
    """``tcp://hôte:port`` → (port, hôte), le port valant 0 pour ``*`` ; ipc et inproc → (endpoint, endpoint). En octets
    aussi, comme pyzmq (``getsockopt(LAST_ENDPOINT)``)."""
    if isinstance(endpoint, bytes):
        endpoint = endpoint.decode()
    protocole, _, reste = endpoint.partition("://")
    if protocole != "tcp":
        return endpoint, endpoint
    hote, _, port = reste.rpartition(":")
    return (int(port) if port.isdigit() else 0), hote


def _destination(cle: int | str) -> tuple[bool, str | None]:
    """(connu, interpréteur) d'un port non lié ici : déclaré, ou, dans le Worker, supposé à la page."""
    if cle in _distants:
        return True, _distants[cle]
    return en_travailleur and isinstance(cle, int), None


def _reprendre(cle: int | str) -> None:
    """Un port vient d'être lié ou déclaré : attache les connect() qui l'attendaient."""
    for socket, c in [e for e in _attentes if e[1] == cle]:
        _attentes.remove((socket, c))
        socket._attacher(cle)


def declarer_distant(port: int, destination: str | None) -> None:
    """La page apprend que ``port`` est (ou sera) lié dans l'interpréteur ``destination``. S'il l'était ailleurs (un
    noyau redémarré dans un nouveau Worker), les sockets qui y étaient connectées s'y reconnectent, comme libzmq."""
    _distants[port] = destination
    for (cle, identite), socket in list(_connectees.items()):
        if cle == port and socket._cible.destination is not destination:
            del _connectees[(cle, identite)]  # sans « disconnect » : l'ancien interpréteur est mort
            socket._attacher(port)
    _reprendre(port)


def oublier(destination: Any) -> None:
    """L'interpréteur ``destination`` est mort : la page cesse de répondre à sa place aux battements de cœur."""
    for port in [p for p, d in _echos.items() if d == destination]:
        del _echos[port]


def recevoir(origine: str | None, message: dict[str, Any]) -> None:
    """Un message ``{"zmq": …}`` arrive de ``origine`` (``message`` est le contenu de la clé). Un port ou un pair
    inconnu est ignoré sans erreur, comme libzmq jette ce qui n'a pas de destinataire."""
    operation = message["op"]
    if operation == "bind":
        declarer_distant(message["port"], origine)
        return
    if operation == "echo":
        _echos[message["port"]] = origine
        return
    if operation == "vers_pair":
        socket = _connectees.get((message["port"], message["pair"]))
        if socket is not None:
            socket._deposer(message["frames"], None)
        return
    lie = _lies.get(message["port"])
    pair = message["pair"]
    if lie is None:
        return
    if operation == "connect":
        lie._pairs[pair] = _Pair(destination=origine, port=message["port"], identite=pair, abonnements=set(message["abonnements"]))
        lie._vider_attente()
    elif pair in lie._pairs:
        if operation == "vers_lie":
            lie._deposer(message["frames"], pair)
        elif operation == "subscribe":
            lie._pairs[pair].abonnements.add(message["topic"])
        elif operation == "unsubscribe":
            lie._pairs[pair].abonnements.discard(message["topic"])
        elif operation == "disconnect":
            del lie._pairs[pair]


# --- Messages -----------------------------------------------------------------------------------------------------

class Frame:
    def __init__(self, data: Any = b"", track: bool = False, copy: bool | None = None,
                 copy_threshold: int | None = None) -> None:
        self._octets = bytes(data)

    @property
    def bytes(self) -> bytes:
        return self._octets

    @property
    def buffer(self) -> memoryview:
        return memoryview(self._octets)

    def __bytes__(self) -> bytes:
        return self._octets

    def __len__(self) -> int:
        return len(self._octets)

    def __eq__(self, autre: object) -> bool:
        return self._octets == (autre._octets if isinstance(autre, Frame) else autre)

    def __hash__(self) -> int:
        return hash(self._octets)


Message = Frame


class MessageTracker:
    """Un envoi est fini dès que ``send`` rend la main : il n'y a rien à suivre."""

    done = True

    def wait(self, timeout: float | None = None) -> None:
        pass


# --- Pairs et sockets ---------------------------------------------------------------------------------------------

class _Pair:
    """L'autre bout d'une liaison, vu d'une socket : une socket locale, ou une socket d'un autre interpréteur.
    ``lie`` : ce bout est la socket LIÉE (on lui envoie ``vers_lie`` au port ``port``) ; sinon c'est une socket
    connectée d'identité ``identite`` (on lui envoie ``vers_pair``). ``abonnements`` : ce qu'un SUB demande
    (``{b""}`` = tout)."""

    def __init__(self, local: Socket | None = None, destination: str | None = None, port: int | str | None = None,
                 identite: bytes = b"", lie: bool = False, abonnements: set[bytes] | None = None) -> None:
        self.local, self.destination, self.port, self.identite, self.lie = local, destination, port, identite, lie
        self.abonnements = {b""} if abonnements is None else abonnements

    def envoyer(self, frames: list[bytes], moi: Socket) -> None:
        if self.local is not None:
            self.local._deposer(frames, moi.identity if self.lie else None)
        elif self.lie and self.port in _echos and _echos[self.port] == self.destination:
            moi._deposer(list(frames), None)  # battement de cœur : la page répond pour le Worker vivant
        elif self.lie:
            poster(self.destination, _op(op="vers_lie", port=self.port, pair=moi.identity, frames=frames))
        else:
            poster(self.destination, _op(op="vers_pair", port=self.port, pair=self.identite, frames=frames))


def _accepte(abonnements: set[bytes], frames: list[bytes]) -> bool:
    return any(frames[0].startswith(a) for a in abonnements)


def _option(code: int) -> property:
    return property(lambda self: self.getsockopt(code), lambda self, valeur: self.setsockopt(code, valeur))


class Socket:
    linger = _option(LINGER)
    rcvtimeo = _option(RCVTIMEO)
    sndtimeo = _option(SNDTIMEO)

    def __init__(self, context: Context, socket_type: int) -> None:
        self.context, self.type, self.closed = context, int(socket_type), False
        self._options: dict[int, Any] = {}
        self._identite: bytes | None = None
        self._abonnements: set[bytes] = set()
        self._inbox: deque[list[bytes]] = deque()
        self._pairs: dict[bytes, _Pair] = {}  # côté lié : identité du pair → pair
        self._cible: _Pair | None = None  # côté connecté
        self._en_attente: list[list[bytes]] = []  # envois faits avant qu'un pair soit attaché
        self._sortant: list[bytes] = []  # frames d'un message en cours (SNDMORE)
        self._restes: list[bytes] = []  # frames du message reçu que recv() n'a pas encore rendues
        self._enveloppe: list[bytes] = []  # REP : [identité, b""] de la requête en cours
        self._cles: list[int | str] = []
        self._dernier = b""
        self._relais: Callable[[], Any] | None = None  # device/proxy : appelé à chaque arrivée
        self._stream: ZMQStream | None = None
        self._fd = next(_numeros_fd)
        self._attentes_async: list[Callable[[], bool]] = []  # utilisé par SocketAsync et PollerAsync
        context._sockets.append(self)
        self._numero = id(self)  # stable aussi pour une ombre, qui partage le __dict__
        _sockets_connues[self._numero] = self

    # Options

    @property
    def identity(self) -> bytes:
        if self._identite is None:
            self._identite = b"\x00" + os.urandom(4)  # comme libzmq : 5 octets dont un premier nul
        return self._identite

    @identity.setter
    def identity(self, valeur: bytes) -> None:
        self._identite = bytes(valeur)

    def getsockopt(self, option: int) -> Any:
        if option == TYPE:
            return self.type
        if option == IDENTITY:
            return self.identity
        if option == LAST_ENDPOINT:
            return self._dernier
        if option == FD:
            return self._fd
        if option == EVENTS:
            return self._evenements(POLLIN | POLLOUT)
        if option == RCVMORE:
            return int(bool(self._restes))
        return self._options.get(option, _DEFAUTS.get(option, 0))

    def setsockopt(self, option: int, valeur: Any) -> None:
        if option == SUBSCRIBE:
            self.subscribe(valeur)
        elif option == UNSUBSCRIBE:
            self.unsubscribe(valeur)
        elif option == IDENTITY:
            self.identity = valeur
        else:
            self._options[int(option)] = valeur

    get, set = getsockopt, setsockopt

    def getsockopt_string(self, option: int, encoding: str = "utf-8") -> str:
        return self.getsockopt(option).decode(encoding)

    def setsockopt_string(self, option: int, valeur: str, encoding: str = "utf-8") -> None:
        self.setsockopt(option, valeur.encode(encoding))

    get_string, set_string = getsockopt_string, setsockopt_string

    def get_hwm(self) -> int:
        return self.getsockopt(SocketOption.SNDHWM)

    def set_hwm(self, valeur: int) -> None:
        """Comme pyzmq : fixe les deux seuils (le client LSP de Spyder fait ``set_hwm(0)``) ; sans effet ici."""
        self.setsockopt(SocketOption.SNDHWM, valeur)
        self.setsockopt(SocketOption.RCVHWM, valeur)

    hwm = property(get_hwm, set_hwm)

    def subscribe(self, topic: bytes | str) -> None:
        topic = topic.encode() if isinstance(topic, str) else bytes(topic)
        self._abonnements.add(topic)
        self._signaler_abonnement("subscribe", topic)

    def unsubscribe(self, topic: bytes | str) -> None:
        topic = topic.encode() if isinstance(topic, str) else bytes(topic)
        self._abonnements.discard(topic)
        self._signaler_abonnement("unsubscribe", topic)

    def _signaler_abonnement(self, operation: str, topic: bytes) -> None:
        """Un pair local partage notre ensemble d'abonnements ; un pair distant l'apprend par un message."""
        if self._cible is not None and self._cible.local is None:
            poster(self._cible.destination, _op(op=operation, port=self._cible.port, pair=self.identity, topic=topic))

    def fileno(self) -> int:
        return self._fd

    @property
    def underlying(self) -> int:
        return self._numero

    @classmethod
    def shadow(cls, address: int | Socket) -> Socket:
        """Comme pyzmq : une socket de la classe ``cls`` sur la même socket (ici, l'état est partagé)."""
        socket = address if isinstance(address, Socket) else _sockets_connues[address]
        if isinstance(socket, cls):
            return socket
        ombre = cls.__new__(cls)
        ombre.__dict__ = socket.__dict__
        return ombre

    # Liaison

    def bind(self, endpoint: str) -> None:
        self._verifier()
        cle, hote = _analyser(endpoint)
        if cle == 0:
            self.bind_to_random_port(f"tcp://{hote}")
            return
        if cle in _lies:
            raise ZMQError(EADDRINUSE)
        _lies[cle] = self
        self._cles.append(cle)
        self._dernier = (f"tcp://{hote}:{cle}" if isinstance(cle, int) else cle).encode()
        if en_travailleur and isinstance(cle, int):
            poster(None, _op(op="bind", port=cle))
        _reprendre(cle)

    def bind_to_random_port(self, addr: str, min_port: int = 49152, max_port: int = 65536, max_tries: int = 100) -> int:
        for _ in range(max_tries):
            port = random.randrange(min_port, max_port)
            try:
                self.bind(f"{addr}:{port}")
            except ZMQError as erreur:
                if erreur.errno != EADDRINUSE:
                    raise
                continue
            return port
        raise ZMQBindError(msg="Could not bind socket to random port.")

    def unbind(self, endpoint: str) -> None:
        cle, _ = _analyser(endpoint)
        if _lies.get(cle) is self:
            del _lies[cle]
            self._cles.remove(cle)

    def connect(self, endpoint: str) -> None:
        self._verifier()
        self._attacher(_analyser(endpoint)[0])

    def disconnect(self, _endpoint: str) -> None:
        self._detacher()

    def _attacher(self, cle: int | str) -> None:
        """Branche cette socket sur ``cle`` : la socket liée locale, l'interpréteur distant, ou l'attente."""
        lie = _lies.get(cle)
        if lie is not None:
            lie._pairs[self.identity] = _Pair(local=self, abonnements=self._abonnements)
            self._cible = _Pair(local=lie, lie=True)
        else:
            connu, destination = _destination(cle)
            if not connu:
                _attentes.append((self, cle))
                return
            self._cible = _Pair(destination=destination, port=cle, lie=True)
            _connectees[(cle, self.identity)] = self
            poster(destination, _op(op="connect", port=cle, type=self.type, pair=self.identity,
                                    abonnements=sorted(self._abonnements)))
        self._vider_attente()
        if lie is not None:
            lie._vider_attente()

    def _detacher(self) -> None:
        _attentes[:] = [e for e in _attentes if e[0] is not self]
        cible, self._cible = self._cible, None
        if cible is None:
            return
        if cible.local is not None:
            cible.local._pairs.pop(self.identity, None)
        else:
            del _connectees[(cible.port, self.identity)]
            poster(cible.destination, _op(op="disconnect", port=cible.port, pair=self.identity))

    def close(self, linger: int | None = None) -> None:
        if self.closed:
            return
        self.closed = True
        for cle in self._cles:
            if _lies.get(cle) is self:
                del _lies[cle]
        self._detacher()
        self.context._sockets.remove(self)

    def __enter__(self) -> Socket:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # Émission

    def _verifier(self) -> None:
        if self.context.closed:
            raise ContextTerminated()
        if self.closed:
            raise ZMQError(ENOTSOCK)

    def _ajouter(self, data: Any, flags: int) -> None:
        self._verifier()
        self._sortant.append(bytes(data))
        if not flags & SNDMORE:
            frames, self._sortant = self._sortant, []
            self._envoyer(frames)

    def send(self, data: Any, flags: int = 0, copy: bool = True, track: bool = False) -> MessageTracker | None:
        self._ajouter(data, flags)
        return MessageTracker() if track else None

    def send_multipart(self, parts: list[Any], flags: int = 0, copy: bool = True,
                       track: bool = False) -> MessageTracker | None:
        *debut, dernier = parts
        for partie in debut:
            self._ajouter(partie, flags | SNDMORE)
        self._ajouter(dernier, flags)
        return MessageTracker() if track else None

    def send_string(self, u: str, flags: int = 0, copy: bool = True, encoding: str = "utf-8") -> None:
        self.send(u.encode(encoding), flags, copy)

    def send_json(self, obj: Any, flags: int = 0, **kwargs: Any) -> None:
        self.send(_dumps(obj, **kwargs), flags)

    def send_pyobj(self, obj: Any, flags: int = 0, protocol: int = pickle.DEFAULT_PROTOCOL) -> None:
        self.send(pickle.dumps(obj, protocol), flags)

    def _envoyer(self, frames: list[bytes]) -> None:
        if self.type == REQ:
            frames = [b"", *frames]
        elif self.type == REP:
            if not self._enveloppe:
                raise ZMQError(EFSM)
            frames, self._enveloppe = [*self._enveloppe, *frames], []
        self._emettre(frames)

    def _emettre(self, frames: list[bytes]) -> None:
        if self.type in (ROUTER, REP):  # le premier frame désigne le pair
            pair = self._pairs.get(frames[0])
            if pair is not None:
                pair.envoyer(frames[1:], self)
            return
        pairs = [*self._pairs.values(), *([self._cible] if self._cible else [])]
        if self.type in (PUB, XPUB):
            for pair in pairs:
                if _accepte(pair.abonnements, frames):
                    pair.envoyer(frames, self)
        elif pairs:
            pairs[0].envoyer(frames, self)
        else:
            self._en_attente.append(frames)

    def _vider_attente(self) -> None:
        attente, self._en_attente = self._en_attente, []
        for frames in attente:
            self._emettre(frames)

    # Réception

    def _deposer(self, frames: list[bytes], de: bytes | None) -> None:
        """Un message arrive. ``de`` : identité de l'expéditeur si cette socket est la liée (ROUTER et REP la placent en
        tête), ``None`` si elle est la connectée (REQ retire la frame vide de l'enveloppe)."""
        if self.closed:
            return
        if de is not None and self.type in (ROUTER, REP):
            frames = [de, *frames]
        elif de is None and self.type == REQ:
            frames = frames[1:]
        else:
            frames = list(frames)
        self._inbox.append(frames)
        self._apres_depot()

    def _apres_depot(self) -> None:
        if self._relais is not None:
            self._relais()
        if self._stream is not None:
            plus_tard(self._stream._livrer)

    def _prendre(self, flags: int) -> list[bytes]:
        """Le message suivant, en attendant s'il le faut ; ``Again`` si le délai échoit ou si ``NOBLOCK``."""
        self._verifier()
        if not self._inbox:
            if flags & NOBLOCK:
                raise Again()
            delai = self.rcvtimeo
            attendre(lambda: bool(self._inbox) or self.closed or self.context.closed, delai if delai >= 0 else None)
            self._verifier()
            if not self._inbox:
                raise Again()
        frames = self._inbox.popleft()
        if self.type == REP:
            self._enveloppe, frames = frames[:2], frames[2:]
        return frames

    def recv(self, flags: int = 0, copy: bool = True, track: bool = False) -> bytes | Frame:
        """Une frame du message courant (``recv`` rend les messages multi-frames frame à frame, comme pyzmq)."""
        if not self._restes:
            self._restes = self._prendre(flags)
        frame = self._restes.pop(0)
        return frame if copy else Frame(frame)

    def recv_multipart(self, flags: int = 0, copy: bool = True, track: bool = False) -> list[bytes] | list[Frame]:
        frames, self._restes = (self._restes or self._prendre(flags)), []
        return frames if copy else [Frame(f) for f in frames]

    def recv_string(self, flags: int = 0, encoding: str = "utf-8") -> str:
        return self.recv(flags).decode(encoding)

    def recv_json(self, flags: int = 0, **kwargs: Any) -> Any:
        return _loads(self.recv(flags), **kwargs)

    def recv_pyobj(self, flags: int = 0) -> Any:
        return pickle.loads(self.recv(flags))

    def _evenements(self, flags: int) -> int:
        return (POLLIN if flags & POLLIN and self._inbox else 0) | (POLLOUT if flags & POLLOUT else 0)

    def poll(self, timeout: int | None = None, flags: int = POLLIN) -> int:
        self._verifier()
        attendre(lambda: bool(self._evenements(flags)), None if timeout is None or timeout < 0 else timeout)
        return self._evenements(flags)


class Context:
    _instance: Context | None = None
    _socket_class = Socket

    def __init__(self, io_threads: int = 1) -> None:
        self.closed = False
        self._sockets: list[Socket] = []

    @classmethod
    def instance(cls, io_threads: int = 1) -> Context:
        if cls.__dict__.get("_instance") is None or cls._instance.closed:
            cls._instance = cls(io_threads)
        return cls._instance

    @property
    def underlying(self) -> int:
        return id(self)

    def socket(self, socket_type: int, **_) -> Socket:
        return self._socket_class(self, socket_type)

    def term(self) -> None:
        """Ferme toutes les sockets ; les ``recv`` bloqués se réveillent en ``ContextTerminated``."""
        self.closed = True
        for socket in list(self._sockets):
            socket.close()

    destroy = lambda self, linger=None: self.term()  # noqa: E731

    def __del__(self) -> None:
        """Sans effet : pyzmq termine le contexte ramassé, ici une socket oubliée ne doit rien casser."""

    def __enter__(self) -> Context:
        return self

    def __exit__(self, *_) -> None:
        self.term()


# --- Poller, dispositifs ------------------------------------------------------------------------------------------

class Poller:
    def __init__(self) -> None:
        self.sockets: list[tuple[Socket, int]] = []

    def register(self, socket: Socket, flags: int = POLLIN | POLLOUT) -> None:
        self.unregister(socket, ignorer=True)
        self.sockets.append((socket, flags))

    modify = register

    def unregister(self, socket: Socket, ignorer: bool = False) -> None:
        restant = [e for e in self.sockets if e[0] is not socket]
        if len(restant) == len(self.sockets) and not ignorer:
            raise KeyError(socket)
        self.sockets = restant

    def _prets(self) -> list[tuple[Socket, int]]:
        return [(s, ev) for s, flags in self.sockets if (ev := s._evenements(flags))]

    def poll(self, timeout: int | None = None) -> list[tuple[Socket, int]]:
        attendre(lambda: bool(self._prets()), None if timeout is None or timeout < 0 else timeout)
        return self._prets()


def select(rlist: list[Socket], wlist: list[Socket], xlist: list[Socket], timeout: float | None = None
           ) -> tuple[list[Socket], list[Socket], list[Socket]]:
    """Comme ``zmq.select`` : ``timeout`` en secondes."""
    poller = Poller()
    for socket in rlist:
        poller.register(socket, POLLIN)
    for socket in wlist:
        poller.register(socket, POLLOUT) if socket not in rlist else poller.register(socket, POLLIN | POLLOUT)
    prets = dict(poller.poll(None if timeout is None else int(timeout * 1000)))
    return ([s for s in rlist if prets.get(s, 0) & POLLIN], [s for s in wlist if prets.get(s, 0) & POLLOUT], [])


Poller.select = staticmethod(select)


def _relier(source: Socket, destination: Socket) -> None:
    """Chaque message reçu par ``source`` repart par ``destination`` (immédiatement, à l'arrivée)."""
    def transferer() -> None:
        while source._inbox and not destination.closed:
            destination.send_multipart(source._inbox.popleft())
    source._relais = transferer
    transferer()


def device(device_type: int, frontend: Socket, backend: Socket) -> None:
    """Relais bloquant : tant que le contexte vit, ce que reçoit une socket repart par l'autre. Les arrivées sont
    traitées à leur dépôt, il ne reste ici qu'à attendre la fin ; comme libzmq, ``ETERM`` en sortie."""
    _relier(frontend, backend)
    if backend is not frontend:
        _relier(backend, frontend)
    elif en_travailleur:  # un écho : la page répondra à sa place (``echo``), même quand ce Worker calcule
        for cle in frontend._cles:
            if isinstance(cle, int):
                poster(None, _op(op="echo", port=cle))
    attendre(lambda: frontend.context.closed or frontend.closed or backend.closed, None)
    raise ZMQError(ETERM)


def proxy(frontend: Socket, backend: Socket, capture: Socket | None = None) -> None:
    device(QUEUE, frontend, backend)


# --- JSON ---------------------------------------------------------------------------------------------------------

def _dumps(obj: Any, **kwargs: Any) -> bytes:
    return json.dumps(obj, **{"ensure_ascii": False, "separators": (",", ":"), **kwargs}).encode("utf8")


def _loads(donnees: bytes | str, **kwargs: Any) -> Any:
    return json.loads(donnees, **kwargs)


# --- ZMQStream ----------------------------------------------------------------------------------------------------

def _boucle_tornado() -> Any:
    try:
        from tornado.ioloop import IOLoop  # noqa: PLC0415
    except ImportError:
        return None
    return IOLoop.current()


class ZMQStream:
    """Les rappels ``on_recv`` d'une socket, livrés à la tâche suivante (``plus_tard``) à chaque arrivée."""

    def __init__(self, socket: Socket, io_loop: Any = None) -> None:
        self.socket = socket
        self.io_loop = io_loop if io_loop is not None else _boucle_tornado()
        self._rappel: Callable[[Any], Any] | None = None
        self._copie = True
        self._rappel_envoi: Callable[[Any, Any], Any] | None = None
        self._rappel_fermeture: Callable[[], Any] | None = None
        socket._stream = self

    def on_recv(self, callback: Callable[[Any], Any] | None, copy: bool = True) -> None:
        self._rappel, self._copie = callback, copy
        if callback is not None and self.socket._inbox:  # déjà arrivé avant le rappel
            plus_tard(self._livrer)

    def on_recv_stream(self, callback: Callable[[ZMQStream, Any], Any] | None) -> None:
        self.on_recv(None if callback is None else lambda frames: callback(self, frames))

    def stop_on_recv(self) -> None:
        self.on_recv(None)

    def on_send(self, callback: Callable[[Any, Any], Any] | None) -> None:
        self._rappel_envoi = callback

    def on_send_stream(self, callback: Callable[[ZMQStream, Any, Any], Any] | None) -> None:
        self.on_send(None if callback is None else lambda frames, status: callback(self, frames, status))

    def stop_on_send(self) -> None:
        self.on_send(None)

    def receiving(self) -> bool:
        return self._rappel is not None

    def sending(self) -> bool:
        return self._rappel_envoi is not None

    def _livrer(self, limite: int | None = None) -> int:
        """Vide la file de réception vers le rappel, un appel par message ; rend le nombre livré."""
        livres = 0
        while self._rappel is not None and self.socket._inbox and (limite is None or livres < limite):
            frames = self.socket.recv_multipart(NOBLOCK, self._copie)
            livres += 1
            resultat = self._rappel(frames)
            if _asyncio.iscoroutine(resultat):  # ipykernel : dispatch_control ; pyzmq la planifie de même
                _asyncio.ensure_future(resultat)
        return livres

    def flush(self, flag: int = POLLIN | POLLOUT, limit: int | None = None) -> int:
        return self._livrer(limit) if flag & POLLIN else 0

    def send_multipart(self, msg: list[Any], flags: int = 0, copy: bool = True, track: bool = False,
                       callback: Callable[[Any, Any], Any] | None = None, **_) -> None:
        self.socket.send_multipart(msg, flags, copy, track)
        for rappel in (callback, self._rappel_envoi):
            if rappel is not None:
                plus_tard(lambda rappel=rappel: rappel(msg, None))

    def send(self, msg: Any, flags: int = 0, copy: bool = True, track: bool = False,
             callback: Callable[[Any, Any], Any] | None = None, **_) -> None:
        self.send_multipart([msg], flags, copy, track, callback)

    def send_string(self, u: str, flags: int = 0, encoding: str = "utf-8", callback=None, **_) -> None:
        self.send(u.encode(encoding), flags, callback=callback)

    def send_json(self, obj: Any, flags: int = 0, callback=None, **_) -> None:
        self.send(_dumps(obj), flags, callback=callback)

    def send_pyobj(self, obj: Any, flags: int = 0, protocol: int = pickle.DEFAULT_PROTOCOL, callback=None, **_) -> None:
        self.send(pickle.dumps(obj, protocol), flags, callback=callback)

    def set_close_callback(self, callback: Callable[[], Any] | None) -> None:
        self._rappel_fermeture = callback

    def close(self, linger: int | None = None) -> None:
        self.socket.close(linger)
        if self._rappel_fermeture is not None:
            self._rappel_fermeture()

    def closed(self) -> bool:
        return self.socket.closed

    def __getattr__(self, nom: str) -> Any:
        return getattr(self.socket, nom)


# --- asyncio ------------------------------------------------------------------------------------------------------

def _futur() -> _asyncio.Future:
    """Un futur de la boucle courante, qu'on crée et qu'on pose s'il n'y en a pas."""
    try:
        boucle = _asyncio.get_event_loop()
    except RuntimeError:
        boucle = _asyncio.new_event_loop()
        _asyncio.set_event_loop(boucle)
    return boucle.create_future()


class SocketAsync(Socket):
    """``recv``/``send`` rendent un futur : déjà résolu si le résultat est là, sinon résolu à l'arrivée."""

    def _asynchrone(self, operation: Callable[[], Any]) -> _asyncio.Future:
        futur = _futur()

        def essayer() -> bool:
            """Résout le futur si l'opération aboutit ; rend vrai quand il n'y a plus rien à attendre."""
            if futur.done():
                return True
            try:
                resultat = operation()
            except Again:
                return False
            except ZMQError as erreur:
                futur.set_exception(erreur)
            else:
                futur.set_result(resultat)
            return True

        if not essayer():
            self._attentes_async.append(essayer)
        return futur

    def _reveiller(self) -> None:
        self._attentes_async = [essayer for essayer in self._attentes_async if not essayer()]

    def _apres_depot(self) -> None:
        super()._apres_depot()
        if self._attentes_async:
            plus_tard(self._reveiller)

    def close(self, linger: int | None = None) -> None:
        super().close(linger)
        if self._attentes_async:  # les recv en attente apprennent que la socket est fermée
            plus_tard(self._reveiller)

    def recv(self, flags: int = 0, copy: bool = True, track: bool = False) -> _asyncio.Future:
        return self._asynchrone(lambda: Socket.recv(self, flags | NOBLOCK, copy))

    def recv_multipart(self, flags: int = 0, copy: bool = True, track: bool = False) -> _asyncio.Future:
        return self._asynchrone(lambda: Socket.recv_multipart(self, flags | NOBLOCK, copy))

    def send(self, data: Any, flags: int = 0, copy: bool = True, track: bool = False) -> _asyncio.Future:
        return self._asynchrone(lambda: Socket.send(self, data, flags, copy, track))

    def send_multipart(self, parts: list[Any], flags: int = 0, copy: bool = True, track: bool = False
                       ) -> _asyncio.Future:
        return self._asynchrone(lambda: Socket.send_multipart(self, parts, flags, copy, track))


class ContextAsync(Context):
    _socket_class = SocketAsync


class PollerAsync(Poller):
    def poll(self, timeout: int | None = None) -> _asyncio.Future:
        futur = _futur()

        def essayer() -> bool:
            if futur.done():
                return True
            prets = self._prets()
            if prets:
                futur.set_result(prets)
            return bool(prets)

        def expirer() -> None:
            if not futur.done():
                futur.set_result([])

        if not essayer():
            for socket, _ in self.sockets:
                socket._attentes_async.append(essayer)
            if timeout is not None and timeout >= 0:
                plus_tard(expirer, timeout)
        return futur


asyncio = types.SimpleNamespace(Context=ContextAsync, Socket=SocketAsync, Poller=PollerAsync)  # ``zmq.asyncio``


# --- Journalisation -----------------------------------------------------------------------------------------------

class PUBHandler(logging.Handler):
    """``zmq.log.handlers.PUBHandler`` : chaque enregistrement part en [sujet, message] sur une socket PUB, le sujet
    étant le niveau (préfixé par ``root_topic``)."""

    def __init__(self, interface_or_socket: str | Socket, context: Context | None = None,
                 root_topic: str = "") -> None:
        super().__init__()
        if isinstance(interface_or_socket, str):
            socket = (context or Context.instance()).socket(PUB)
            socket.bind(interface_or_socket)
        else:
            socket = interface_or_socket
        self.socket, self.root_topic = socket, root_topic

    def setRootTopic(self, root_topic: str) -> None:
        self.root_topic = root_topic

    def emit(self, record: logging.LogRecord) -> None:
        sujet = f"{self.root_topic}.{record.levelname}" if self.root_topic else record.levelname
        self.socket.send_multipart([sujet.encode(), self.format(record).encode()])


# --- Installation -------------------------------------------------------------------------------------------------

def _construire() -> dict[str, types.ModuleType]:
    """Les modules ``zmq`` et ses sous-modules, tels que les importent jupyter_client et ipykernel."""
    constantes = _constantes()
    erreurs = {"ZMQError": ZMQError, "Again": Again, "ContextTerminated": ContextTerminated,
               "ZMQBindError": ZMQBindError, "NotDone": NotDone, "InterruptedSystemCall": InterruptedSystemCall}
    try:
        from tornado.ioloop import IOLoop  # noqa: PLC0415
    except ImportError:
        ioloop = {}
    else:
        ioloop = {"IOLoop": IOLoop}
    gc = types.SimpleNamespace(context=None, thread=None, stop=lambda: None)

    def recv_monitor_message(*_, **__):
        raise NotImplementedError("zmq.utils.monitor n'existe pas dans le navigateur")

    zmq_api = {
        **constantes, **erreurs, "Context": Context, "Socket": Socket, "Frame": Frame, "Message": Message,
        "Poller": Poller, "MessageTracker": MessageTracker, "device": device, "proxy": proxy, "select": select,
        "SocketType": SocketType, "Flag": Flag, "PollEvent": PollEvent, "SocketOption": SocketOption, "has": has,
        "curve_keypair": curve_keypair, "zmq_version": zmq_version, "pyzmq_version": pyzmq_version,
        "zmq_version_info": zmq_version_info, "pyzmq_version_info": pyzmq_version_info, "__version__": __version__,
    }
    # nom → (est un paquet, attributs)
    specs = {
        "zmq": (True, zmq_api),
        "zmq.error": (False, erreurs),
        "zmq.constants": (False, {**constantes, "SocketType": SocketType, "Flag": Flag, "PollEvent": PollEvent,
                                  "SocketOption": SocketOption}),
        "zmq.eventloop": (True, {}),
        "zmq.eventloop.zmqstream": (False, {"ZMQStream": ZMQStream}),
        "zmq.eventloop.ioloop": (False, ioloop),
        "zmq.utils": (True, {}),
        "zmq.utils.jsonapi": (False, {"dumps": _dumps, "loads": _loads}),
        "zmq.utils.garbage": (False, {"gc": gc}),
        "zmq.utils.monitor": (False, {"recv_monitor_message": recv_monitor_message}),
        "zmq.asyncio": (False, vars(asyncio)),
        "zmq.log": (True, {}),
        "zmq.log.handlers": (False, {"PUBHandler": PUBHandler}),
        "zmq.sugar": (True, {"Context": Context, "Socket": Socket, "Frame": Frame}),
        "zmq.sugar.context": (False, {"Context": Context}),
        "zmq.sugar.socket": (False, {"Socket": Socket}),
        "zmq.sugar.frame": (False, {"Frame": Frame}),
    }
    modules = {}
    for nom, (paquet, attributs) in specs.items():
        module = types.ModuleType(nom)
        module.__dict__.update(attributs)
        module.__spec__ = importlib.machinery.ModuleSpec(nom, None, is_package=paquet)
        if paquet:
            module.__path__ = []  # sans cela ``import zmq.eventloop.zmqstream`` chercherait le sous-module sur disque
        modules[nom] = module
    for nom, module in modules.items():  # ``zmq.eventloop.zmqstream`` doit aussi se lire en attribut du parent
        parent, _, enfant = nom.rpartition(".")
        if parent:
            setattr(modules[parent], enfant, module)
    return modules


def installer(attendre=None, plus_tard=None, poster=None) -> None:
    """Pose les crochets de l'hôte et, si pyzmq n'est pas là, enregistre ce ``zmq`` et ses sous-modules."""
    _fils.poser_crochets(attendre, plus_tard, poster)
    if "zmq" not in sys.modules and importlib.util.find_spec("zmq") is None:
        sys.modules.update(_construire())
