"""``threading`` dans le navigateur, où il n'y a qu'un fil : ``Thread``, ``Timer``, ``Lock``, ``RLock``, ``Event``,
``Condition``, ``Semaphore``, ``BoundedSemaphore``, ``Barrier`` et ``local`` y sont remplacés dans le module
``threading`` RÉEL (celui que tout le monde a déjà importé) par des doublures COOPÉRATIVES :
``Thread.start()`` ne lance rien tout de suite, ``run()`` tourne à la tâche suivante de la boucle d'événements, et
chaque attente (``join``, ``Lock.acquire``,
``Event.wait``…) passe par le crochet ``attendre`` que fournit l'hôte (JSPI) au lieu de bloquer.

Ce module porte aussi les trois crochets partagés avec ``zmq_web`` (``attendre``, ``plus_tard``, ``poster``) : il est le
plus bas des deux, et une seule file par défaut, un seul ``pomper``, y servent les deux. Python pur : aucun import
de Qt, de ``js`` ni de ``pyodide``, le module tourne aussi dans le Web Worker (Pyodide sans Qt).

Hors navigateur (tests natifs), sans crochets, ``plus_tard`` range les rappels dans une file que ``pomper()`` vide, et
``attendre`` pompe cette file en boucle : un fil lancé avec ``start()`` tourne donc dès que quelqu'un attend.
Une attente qui ne finit qu'à la fin d'un autre rappel (un ``join`` sur un fil lui-même bloqué dans ``attendre``) ne
peut pas
aboutir sur ce fil unique, c'est la limite de la coopération."""

from __future__ import annotations

import collections
import itertools
import sys
import threading as _threading
import time
from typing import Any, Callable

# --- Crochets de l'hôte -------------------------------------------------------------------------------------------

_attendre_hote: Callable[[Callable[[], bool], int | None], bool] | None = None
_plus_tard_hote: Callable[[Callable[[], Any], int], None] | None = None
_poster_hote: Callable[[str | None, dict[str, Any]], None] | None = None
_file: collections.deque[tuple[float, Callable[[], Any]]] = collections.deque()


def poser_crochets(attendre=None, plus_tard=None, poster=None) -> None:
    """Pose les crochets fournis ; un crochet absent laisse le précédent (``zmq_web.installer`` et
    ``threading_web.installer`` se suivent sans s'effacer)."""
    global _attendre_hote, _plus_tard_hote, _poster_hote
    _attendre_hote = attendre or _attendre_hote
    _plus_tard_hote = plus_tard or _plus_tard_hote
    _poster_hote = poster or _poster_hote


def reinitialiser_crochets() -> None:
    """Retire les crochets de l'hôte et vide la file par défaut (pour les tests)."""
    global _attendre_hote, _plus_tard_hote, _poster_hote
    _attendre_hote = _plus_tard_hote = _poster_hote = None
    _file.clear()


def pomper() -> None:
    """Exécute les rappels échus de la file par défaut (vide si l'hôte fournit ``plus_tard``). Un rappel peut lui-même
    attendre, donc repomper : on ne retire qu'un élément à la fois."""
    maintenant = time.monotonic()
    for _ in range(len(_file)):
        if not _file:
            break
        echeance, fonction = _file.popleft()
        if echeance <= maintenant:
            fonction()
        else:
            _file.append((echeance, fonction))


def plus_tard(fonction: Callable[[], Any], delai_ms: int = 0) -> None:
    """Exécute ``fonction`` à une tâche suivante, jamais synchrone."""
    if _plus_tard_hote is not None:
        _plus_tard_hote(fonction, delai_ms)
    else:
        _file.append((time.monotonic() + delai_ms / 1000, fonction))


def attendre(condition: Callable[[], bool], delai_ms: int | None) -> bool:
    """Bloque jusqu'à ``condition()`` vraie ou ``delai_ms`` écoulé (``None`` = sans limite) ; rend la condition. Le fil
    qui attend cesse d'être le fil courant pendant l'attente (sous JSPI, le reste tourne : script principal, slots,
    autres fils) et le redevient à la reprise."""
    global _courant
    courant, _courant = _courant, None
    try:
        if _attendre_hote is not None:
            return _attendre_hote(condition, delai_ms)
        fin = None if delai_ms is None else time.monotonic() + delai_ms / 1000
        while True:
            pomper()
            if condition():
                return True
            if fin is not None and time.monotonic() >= fin:
                return False
            time.sleep(0.001)
    finally:
        _courant = courant


def poster(destination: str | None, message: dict[str, Any]) -> None:
    """Envoie ``message`` à un autre interpréteur (``None`` = la page)."""
    if _poster_hote is None:
        raise RuntimeError("aucun transport")
    _poster_hote(destination, message)


def _ms(timeout: float | None) -> int | None:
    """Un délai en secondes (``None`` ou négatif = pour toujours) en millisecondes."""
    return None if timeout is None or timeout < 0 else int(timeout * 1000)


# --- Fils ---------------------------------------------------------------------------------------------------------

_idents = itertools.count(1000)
_numeros = itertools.count(1)
_courant: Thread | None = None  # le fil dont ``run`` tourne en ce moment (None : le principal) ; ``attendre`` le met de
# côté pendant la suspension, ``_executer`` le rétablit en finissant
_vivants: list[Thread] = []


class Event:
    def __init__(self) -> None:
        self._drapeau = False

    def is_set(self) -> bool:
        return self._drapeau

    def set(self) -> None:
        self._drapeau = True

    def clear(self) -> None:
        self._drapeau = False

    def wait(self, timeout: float | None = None) -> bool:
        return attendre(lambda: self._drapeau, _ms(timeout))


class Thread:
    """Un « fil » : ``run()`` tourne sur l'unique fil réel, à la tâche suivante."""

    _delai_ms = 0  # ``Timer`` y met son intervalle

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None) -> None:
        self._target, self._args, self._kwargs = target, args, kwargs or {}
        self._name = name or f"Thread-{next(_numeros)}"
        self._daemon = bool(_courant and _courant._daemon) if daemon is None else daemon
        self._ident: int | None = None
        self._demarre = False
        self._fini = Event()

    def start(self) -> None:
        if self._demarre:
            raise RuntimeError("threads can only be started once")
        self._demarre, self._ident = True, next(_idents)
        _vivants.append(self)
        plus_tard(self._executer, self._delai_ms)

    def _executer(self) -> None:
        global _courant
        precedent, _courant = _courant, self  # un ``run`` peut en exécuter un autre (pompe native dans ``attendre``)
        try:
            self.run()
        except SystemExit:
            pass
        except BaseException:
            _threading.excepthook(_threading.ExceptHookArgs((*sys.exc_info(), self)))
        finally:
            _courant = precedent
            _vivants.remove(self)
            self._fini.set()

    def run(self) -> None:
        if self._target is not None:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout: float | None = None) -> None:
        if not self._demarre:
            raise RuntimeError("cannot join thread before it is started")
        if self is current_thread():
            raise RuntimeError("cannot join current thread")
        attendre(self._fini.is_set, _ms(timeout))

    def is_alive(self) -> bool:
        return self._demarre and not self._fini.is_set()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, valeur: str) -> None:
        self._name = str(valeur)

    @property
    def ident(self) -> int | None:
        return self._ident

    native_id = ident

    @property
    def daemon(self) -> bool:
        return self._daemon

    @daemon.setter
    def daemon(self, valeur: bool) -> None:
        self._daemon = bool(valeur)

    def isDaemon(self) -> bool:  # noqa: N802
        return self._daemon

    def setDaemon(self, valeur: bool) -> None:  # noqa: N802
        self._daemon = bool(valeur)

    def getName(self) -> str:  # noqa: N802
        return self._name

    def setName(self, valeur: str) -> None:  # noqa: N802
        self._name = str(valeur)


class Timer(Thread):
    def __init__(self, interval: float, function, args=None, kwargs=None) -> None:
        super().__init__()
        self.interval, self.function = interval, function
        self.args, self.kwargs = args if args is not None else [], kwargs if kwargs is not None else {}
        self.finished = Event()
        self._delai_ms = int(interval * 1000)

    def run(self) -> None:
        if not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
        self.finished.set()

    def cancel(self) -> None:
        self.finished.set()


_principal = Thread(name="MainThread")
_principal._demarre, _principal._ident = True, next(_idents)


def current_thread() -> Thread:
    return _courant or _principal


def main_thread() -> Thread:
    return _principal


def get_ident() -> int:
    return current_thread()._ident


def _enumerer() -> list[Thread]:
    return [_principal, *_vivants]


def active_count() -> int:
    return len(_vivants) + 1


def _shutdown() -> None:
    """Le interpréteur attend les fils non démons en sortant ; ici, rien ne tourne en dehors de la boucle de l'hôte."""


# --- Verrous ------------------------------------------------------------------------------------------------------

class Lock:
    """Verrou non réentrant, relâchable par un autre fil comme un vrai. Pris deux fois par le même fil sans délai, il
    gèlerait pour toujours le seul fil réel : ``RuntimeError`` à la place."""

    def __init__(self) -> None:
        self._proprietaire: Thread | None = None

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        courant = current_thread()
        if self._proprietaire is not None:
            if not blocking:
                return False
            if self._proprietaire is courant and timeout < 0:
                raise RuntimeError("interblocage coopératif")
            if not attendre(lambda: self._proprietaire is None, _ms(timeout)):
                return False
        self._proprietaire = courant
        return True

    def release(self) -> None:
        if self._proprietaire is None:
            raise RuntimeError("release unlocked lock")
        self._proprietaire = None

    def locked(self) -> bool:
        return self._proprietaire is not None

    def _is_owned(self) -> bool:
        return self._proprietaire is current_thread()

    def _release_save(self) -> None:  # pour ``Condition.wait``
        self.release()

    def _acquire_restore(self, _etat: None) -> None:
        self.acquire()

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *_) -> None:
        self.release()


class RLock:
    def __init__(self) -> None:
        self._proprietaire: Thread | None = None
        self._compte = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        courant = current_thread()
        if self._proprietaire is courant:
            self._compte += 1
            return True
        if self._proprietaire is not None:
            if not blocking:
                return False
            if not attendre(lambda: self._proprietaire is None, _ms(timeout)):
                return False
        self._proprietaire, self._compte = courant, 1
        return True

    def release(self) -> None:
        if self._proprietaire is not current_thread():
            raise RuntimeError("cannot release un-acquired lock")
        self._compte -= 1
        if not self._compte:
            self._proprietaire = None

    def _is_owned(self) -> bool:
        return self._proprietaire is current_thread()

    def _release_save(self) -> tuple[int, Thread | None]:  # pour ``Condition.wait`` : lâche tous les niveaux
        etat = (self._compte, self._proprietaire)
        self._compte, self._proprietaire = 0, None
        return etat

    def _acquire_restore(self, etat: tuple[int, Thread | None]) -> None:
        attendre(lambda: self._proprietaire is None, None)
        self._compte, self._proprietaire = etat

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *_) -> None:
        self.release()


class Condition:
    def __init__(self, lock=None) -> None:
        self._lock = lock if lock is not None else RLock()
        self.acquire, self.release = self._lock.acquire, self._lock.release
        self._attendants: list[Event] = []

    def __enter__(self) -> Any:
        return self._lock.__enter__()

    def __exit__(self, *args) -> None:
        self._lock.__exit__(*args)

    def wait(self, timeout: float | None = None) -> bool:
        if not self._lock._is_owned():
            raise RuntimeError("cannot wait on un-acquired lock")
        jeton = Event()
        self._attendants.append(jeton)
        etat = self._lock._release_save()
        try:
            return jeton.wait(timeout)
        finally:
            self._lock._acquire_restore(etat)
            if jeton in self._attendants:  # le délai a expiré sans notify
                self._attendants.remove(jeton)

    def wait_for(self, predicate: Callable[[], Any], timeout: float | None = None) -> Any:
        fin = None if timeout is None else time.monotonic() + timeout
        resultat = predicate()
        while not resultat:
            restant = None if fin is None else fin - time.monotonic()
            if restant is not None and restant <= 0:
                break
            self.wait(restant)
            resultat = predicate()
        return resultat

    def notify(self, n: int = 1) -> None:
        if not self._lock._is_owned():
            raise RuntimeError("cannot notify on un-acquired lock")
        for jeton in self._attendants[:n]:
            jeton.set()
        del self._attendants[:n]

    def notify_all(self) -> None:
        self.notify(len(self._attendants))


class Semaphore:
    def __init__(self, value: int = 1) -> None:
        if value < 0:
            raise ValueError("semaphore initial value must be >= 0")
        self._valeur = value

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        if self._valeur == 0:
            if not blocking:
                return False
            if not attendre(lambda: self._valeur > 0, _ms(timeout)):
                return False
        self._valeur -= 1
        return True

    def release(self, n: int = 1) -> None:
        self._valeur += n

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *_) -> None:
        self.release()


class BoundedSemaphore(Semaphore):
    def __init__(self, value: int = 1) -> None:
        super().__init__(value)
        self._initiale = value

    def release(self, n: int = 1) -> None:
        if self._valeur + n > self._initiale:
            raise ValueError("Semaphore released too many times")
        super().release(n)


class Barrier:
    def __init__(self, parties: int, action: Callable[[], Any] | None = None, timeout: float | None = None) -> None:
        self.parties, self._action, self._timeout = parties, action, timeout
        self._arrives, self._generation, self._brisee = 0, 0, False

    @property
    def n_waiting(self) -> int:
        return self._arrives

    @property
    def broken(self) -> bool:
        return self._brisee

    def wait(self, timeout: float | None = None) -> int:
        if self._brisee:
            raise _threading.BrokenBarrierError
        generation, indice = self._generation, self._arrives
        self._arrives += 1
        if self._arrives == self.parties:
            if self._action is not None:
                self._action()
            self._arrives, self._generation = 0, generation + 1
            return indice
        delai = self._timeout if timeout is None else timeout
        attendre(lambda: self._generation != generation or self._brisee, _ms(delai))
        if self._generation != generation:
            return indice
        self.abort()
        raise _threading.BrokenBarrierError

    def abort(self) -> None:
        self._brisee = True

    def reset(self) -> None:
        self._arrives, self._generation, self._brisee = 0, self._generation + 1, False


class local:  # noqa: N801
    """Attributs propres à chaque fil, repérés par le fil courant."""

    def __new__(cls, *_args, **_kwargs):
        self = object.__new__(cls)
        object.__setattr__(self, "_valeurs", {})
        return self

    def _dict(self) -> dict[str, Any]:
        return self._valeurs.setdefault(current_thread().ident, {})

    def __getattr__(self, nom: str) -> Any:
        try:
            return self._dict()[nom]
        except KeyError:
            raise AttributeError(nom) from None

    def __setattr__(self, nom: str, valeur: Any) -> None:
        self._dict()[nom] = valeur

    def __delattr__(self, nom: str) -> None:
        try:
            del self._dict()[nom]
        except KeyError:
            raise AttributeError(nom) from None


# --- Installation -------------------------------------------------------------------------------------------------

_ABSENT = object()
_originaux: dict[str, Any] = {}


def installer(attendre=None, plus_tard=None) -> None:
    """Remplace dans ``threading`` les noms ci-dessus ; ``desinstaller()`` remet les originaux."""
    poser_crochets(attendre, plus_tard)
    doublures = {
        "Thread": Thread, "Timer": Timer, "Lock": Lock, "RLock": RLock, "Event": Event, "Condition": Condition,
        "Semaphore": Semaphore, "BoundedSemaphore": BoundedSemaphore, "Barrier": Barrier, "local": local,
        "current_thread": current_thread, "main_thread": main_thread, "get_ident": get_ident,
        "get_native_id": get_ident, "active_count": active_count, "enumerate": _enumerer, "_shutdown": _shutdown,
        "_allocate_lock": Lock, "allocate_lock": Lock,
    }
    for nom, doublure in doublures.items():
        _originaux.setdefault(nom, getattr(_threading, nom, _ABSENT))
        setattr(_threading, nom, doublure)


def desinstaller() -> None:
    for nom, original in _originaux.items():
        if original is _ABSENT:
            delattr(_threading, nom)
        else:
            setattr(_threading, nom, original)
    _originaux.clear()


# --- Boucle asyncio ----------------------------------------------------------------------------------------------

def partager_boucle(commune: Any) -> None:
    """Dans le navigateur une seule boucle asyncio tourne (la WebLoop de Pyodide, qui est la boucle « en cours » partout) :
    un fil qui se crée la sienne (jupyter_client : ``IOLoopThread``, ``HBChannel`` ; ipykernel) y verrait ses Futures
    rattachés à l'autre (« attached to a different loop »). ``asyncio.new_event_loop()`` rend donc une vue de
    ``commune`` : tout lui est délégué, sauf ``close()``, sans effet."""
    import asyncio  # noqa: PLC0415

    class _Vue(asyncio.AbstractEventLoop):
        def __getattribute__(self, nom: str) -> Any:
            if nom in ("close", "__class__"):
                return object.__getattribute__(self, nom)
            return getattr(commune, nom)

        def close(self) -> None:
            pass

    asyncio.new_event_loop = _Vue
    asyncio.get_event_loop_policy().new_event_loop = _Vue


# --- concurrent.futures ------------------------------------------------------------------------------------------

def doubler_futures(attendre: Callable[[Callable[[], bool], int | None], bool],
                    plus_tard: Callable[[Callable[[], Any]], None]) -> None:
    """``concurrent.futures.ThreadPoolExecutor`` (absent de Pyodide) sur des tâches coopératives : chaque tâche démarre
    par ``plus_tard`` et les tâches se relaient à chacune de leurs attentes. ``result()``, ``wait``, ``as_completed`` et la
    sortie du ``with`` passent par ``attendre(condition, délai en ms ou None)`` au lieu de bloquer. ``initializer`` est
    appelé avant chaque tâche (il n'y a pas de fil à initialiser une fois). Crochets en paramètres : la page (``fils``)
    et le Worker (``preambule``) ont chacun les leurs."""
    import concurrent.futures as cf  # noqa: PLC0415
    import concurrent.futures._base as base  # noqa: PLC0415
    import os  # noqa: PLC0415

    class Future(cf.Future):
        def result(self, timeout=None):
            attendre(self.done, _ms(timeout))
            return super().result(0 if not self.done() else None)

        def exception(self, timeout=None):
            attendre(self.done, _ms(timeout))
            return super().exception(0 if not self.done() else None)

    class ThreadPoolExecutor(cf.Executor):
        def __init__(self, max_workers=None, thread_name_prefix="", initializer=None, initargs=()):
            self._max = max_workers or min(32, (os.cpu_count() or 1) + 4)
            self._initializer, self._initargs = initializer, initargs
            self._en_cours, self._file, self._ferme = 0, [], False

        def submit(self, fn, /, *args, **kwargs):
            if self._ferme:
                raise RuntimeError("cannot schedule new futures after shutdown")
            f = Future()
            self._file.append((f, fn, args, kwargs))
            self._suivant()
            return f

        def _suivant(self):
            while self._file and self._en_cours < self._max:
                self._en_cours += 1
                tache = self._file.pop(0)
                plus_tard(lambda tache=tache: self._executer(*tache))

        def _executer(self, f, fn, args, kwargs):
            try:
                if f.set_running_or_notify_cancel():
                    if self._initializer is not None:
                        self._initializer(*self._initargs)
                    try:
                        f.set_result(fn(*args, **kwargs))
                    except BaseException as e:  # noqa: BLE001
                        f.set_exception(e)
            finally:
                self._en_cours -= 1
                self._suivant()

        def shutdown(self, wait=True, *, cancel_futures=False):
            self._ferme = True
            if cancel_futures:
                for f, *_ in self._file:
                    f.cancel()
                self._file.clear()
            if wait:
                attendre(lambda: not self._en_cours and not self._file, None)

    attendre_futures = cf.wait

    def wait(fs, timeout=None, return_when=cf.ALL_COMPLETED):
        fs = list(fs)
        voulu = {cf.FIRST_COMPLETED: lambda: any(f.done() for f in fs),
                 cf.FIRST_EXCEPTION: lambda: all(f.done() for f in fs) or any(f.done() and not f.cancelled() and f.exception(0)
                                                                              for f in fs),
                 cf.ALL_COMPLETED: lambda: all(f.done() for f in fs)}[return_when]
        attendre(voulu, _ms(timeout))
        return attendre_futures(fs, 0, return_when)

    def as_completed(fs, timeout=None):
        restants, fin = set(fs), None if timeout is None else time.monotonic() + timeout
        while restants:
            attendre(lambda: any(f.done() for f in restants), None if fin is None else _ms(max(0, fin - time.monotonic())))
            finis = {f for f in restants if f.done()}
            if not finis:
                raise cf.TimeoutError(f"{len(restants)} (of {len(fs)}) futures unfinished")
            restants -= finis
            yield from finis

    cf.ThreadPoolExecutor, cf.Future, cf.wait, cf.as_completed = ThreadPoolExecutor, Future, wait, as_completed
    base.wait, base.as_completed = wait, as_completed  # Executor.map passe par Future.result : déjà doublé
