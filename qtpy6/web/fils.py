"""Les fils d'exécution de Qt dans le navigateur, où il n'y en a qu'un : Qt-WASM n'a ni ``QThread``, ni ``QThreadPool``,
ni verrous, et ``threading.Thread.start`` y lève ``RuntimeError``. Ces doublures en gardent la surface et font tourner
le travail sur le fil unique, de façon COOPÉRATIVE : ``QThread.start()`` lance ``run()`` à la tâche suivante de la
boucle asyncio de Pyodide, et chaque attente (``QThread.msleep``, ``wait``, ``QWaitCondition.wait``, ``QSemaphore.acquire``,
``time.sleep``) y suspend l'appel (JSPI, comme ``exec()`` : ``bloquant``) au lieu de bloquer : la page, Qt et les autres
« fils » continuent pendant ce temps. Un calcul qui ne s'arrête jamais de lui-même garde la main jusqu'à sa fin :
l'interface ne se redessine qu'entre deux attentes.

Le schéma ``worker.moveToThread(thread)`` marche tel quel (``moveToThread`` ne fait rien : il n'y a qu'un fil), les
signaux inter-fils deviennent des appels directs. Posé par ``qtpy6.QtCore`` sous Pyodide."""

import enum
import os
import time

from . import bloquant


def _pause(ms):
    """Rend la main ``ms`` millisecondes si l'appel peut suspendre ; sinon, rien (jamais d'attente active sur le fil de
    la page)."""
    if bloquant._peut_suspendre():
        from ..QtCore import QTimer  # noqa: PLC0415
        bloquant._suspendre(lambda resoudre: QTimer.singleShot(max(0, int(ms)), resoudre))


def _attendre(condition, delai_ms=-1):
    """Suspend, par pas de 10 ms, jusqu'à ``condition()`` ou l'échéance ; rend ``condition()``. Hors entrée suspendable,
    un seul examen : attendre y bloquerait la page pour de bon."""
    fin = None if delai_ms is None or delai_ms < 0 else time.monotonic() + delai_ms / 1000
    while not condition() and bloquant._peut_suspendre() and (fin is None or time.monotonic() < fin):
        _pause(10)
    return condition()


def _obtenir(condition, quoi):
    """Attend ``condition()`` sans échéance ; hors entrée suspendable, rien ne pourrait la rendre vraie : ``RuntimeError``
    plutôt qu'un verrou pris deux fois en silence."""
    if not _attendre(condition):
        raise RuntimeError(f"{quoi} : rien ne pourra le libérer (un seul fil, hors entrée suspendable)")


def _delai(deadline):
    """Le délai de ``wait(deadline)`` en ms : un entier, un QDeadlineTimer, ou rien (pour toujours)."""
    if deadline is None:
        return -1
    if isinstance(deadline, int):
        return deadline if deadline < 2**31 - 1 else -1  # ULONG_MAX de Qt 5 : pour toujours
    return -1 if deadline.isForever() else deadline.remainingTime()


def doubler(ns):
    QObject, Signal = ns["QObject"], ns["Signal"]

    class QThread(QObject):
        """Un « fil » : ``run()`` tourne sur le fil de la page, lancé à la tâche asyncio suivante."""

        class Priority(enum.IntEnum):
            IdlePriority, LowestPriority, LowPriority, NormalPriority = 0, 1, 2, 3
            HighPriority, HighestPriority, TimeCriticalPriority, InheritPriority = 4, 5, 6, 7

        started = Signal()
        finished = Signal()
        _principal = None

        def __init__(self, parent=None):
            super().__init__(parent)
            self._etat, self._interruption, self._priorite, self._boucle = "neuf", False, QThread.Priority.NormalPriority, []

        def start(self, priority=None):
            if self._etat == "en cours":
                return
            if priority is not None:
                self._priorite = priority
            self._etat, self._interruption = "en cours", False
            bloquant._plus_tard(self._executer)

        def _executer(self):
            try:
                bloquant._plus_tard(self.started.emit)  # comme les slots d'un autre fil en Qt : à la tâche suivante, une
                self.run()  # fois ``exec()`` entré, sans quoi le ``quit()`` d'un travailleur rapide le précéderait
            finally:
                self._etat = "fini"
                self.finished.emit()

        def run(self):
            self.exec()

        def exec(self):
            """La boucle d'événements du fil : il n'y a que celle de la page, on attend donc ``quit()``/``exit()``."""
            if not bloquant._peut_suspendre():
                return 0
            return bloquant._suspendre(self._boucle.append)

        def exit(self, returnCode=0):
            while self._boucle:
                self._boucle.pop()(returnCode)

        def quit(self):
            self.exit(0)

        def terminate(self):  # rien ne peut interrompre un appel en cours : on le lui demande
            self._interruption = True
            self.quit()

        def wait(self, deadline=None):
            return _attendre(lambda: self._etat != "en cours", _delai(deadline))

        def isRunning(self):
            return self._etat == "en cours"

        def isFinished(self):
            return self._etat == "fini"

        def requestInterruption(self):
            self._interruption = True

        def isInterruptionRequested(self):
            return self._interruption

        def priority(self):
            return self._priorite

        def setPriority(self, priority):
            self._priorite = priority

        def setStackSize(self, stackSize):
            pass

        def stackSize(self):
            return 0

        def loopLevel(self):
            return len(self._boucle)

        def isCurrentThread(self):
            return self is QThread.currentThread()

        @staticmethod
        def currentThread():
            if QThread._principal is None:
                QThread._principal = QThread()
                QThread._principal._etat = "en cours"
            return QThread._principal

        @staticmethod
        def isMainThread():
            return True

        @staticmethod
        def idealThreadCount():
            return 1

        @staticmethod
        def sleep(secs):
            _pause(secs * 1000)

        @staticmethod
        def msleep(msecs):
            _pause(msecs)

        @staticmethod
        def usleep(usecs):
            _pause(usecs / 1000)

        @staticmethod
        def yieldCurrentThread():
            _pause(0)

    class QRunnable:
        def __init__(self):
            self._auto = True

        def run(self):
            raise NotImplementedError

        def autoDelete(self):
            return self._auto

        def setAutoDelete(self, autoDelete):
            self._auto = autoDelete

        @staticmethod
        def create(functionToRun):
            r = QRunnable()
            r.run = functionToRun
            return r

    class QThreadPool(QObject):
        """Chaque tâche démarre à la tâche asyncio suivante ; elles se relaient à chacune de leurs attentes."""
        _global = None

        def __init__(self, parent=None):
            super().__init__(parent)
            self._actives, self._max, self._expiration = 0, 1, 30000

        @staticmethod
        def globalInstance():
            if QThreadPool._global is None:
                QThreadPool._global = QThreadPool()
            return QThreadPool._global

        def start(self, runnable, priority=0):
            tache = runnable.run if isinstance(runnable, QRunnable) else runnable
            self._actives += 1

            def executer():
                try:
                    tache()
                finally:
                    self._actives -= 1
            bloquant._plus_tard(executer)

        def tryStart(self, runnable):
            self.start(runnable)
            return True

        def startOnReservedThread(self, runnable):
            self.start(runnable)

        def activeThreadCount(self):
            return self._actives

        def maxThreadCount(self):
            return self._max

        def setMaxThreadCount(self, maxThreadCount):
            self._max = maxThreadCount

        def expiryTimeout(self):
            return self._expiration

        def setExpiryTimeout(self, expiryTimeout):
            self._expiration = expiryTimeout

        def reserveThread(self):
            pass

        def releaseThread(self):
            pass

        def clear(self):
            pass

        def waitForDone(self, msecs=-1):
            return _attendre(lambda: self._actives == 0, _delai(msecs))

    # Verrous : un seul fil ne se dispute rien avec lui-même ; les attentes, elles, suspendent.
    class QMutex:
        def __init__(self):
            self._pris = 0

        def lock(self):
            _obtenir(lambda: not self._pris, "QMutex.lock")
            self._pris += 1

        def tryLock(self, timeout=0):
            if not _attendre(lambda: not self._pris, timeout):
                return False
            self._pris += 1
            return True

        def try_lock(self):
            return self.tryLock()

        def unlock(self):
            self._pris = max(0, self._pris - 1)

    class QRecursiveMutex(QMutex):  # un seul fil : il est toujours le détenteur
        def lock(self):
            self._pris += 1

        def tryLock(self, timeout=0):
            self._pris += 1
            return True

    class QMutexLocker:
        def __init__(self, mutex):
            self._mutex, self._pris = mutex, False
            self.relock()

        def mutex(self):
            return self._mutex

        def relock(self):
            if not self._pris:
                self._mutex.lock()
                self._pris = True

        def unlock(self):
            if self._pris:
                self._mutex.unlock()
                self._pris = False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.unlock()

    class QReadWriteLock:
        class RecursionMode(enum.IntEnum):
            NonRecursive, Recursive = 0, 1

        def __init__(self, recursionMode=None):
            self._lecteurs, self._ecrivain = 0, False

        def lockForRead(self):
            _obtenir(lambda: not self._ecrivain, "QReadWriteLock.lockForRead")
            self._lecteurs += 1

        def lockForWrite(self):
            _obtenir(lambda: not self._ecrivain and not self._lecteurs, "QReadWriteLock.lockForWrite")
            self._ecrivain = True

        def tryLockForRead(self, timeout=0):
            if not _attendre(lambda: not self._ecrivain, timeout):
                return False
            self._lecteurs += 1
            return True

        def tryLockForWrite(self, timeout=0):
            if not _attendre(lambda: not self._ecrivain and not self._lecteurs, timeout):
                return False
            self._ecrivain = True
            return True

        def unlock(self):
            if self._ecrivain:
                self._ecrivain = False
            else:
                self._lecteurs = max(0, self._lecteurs - 1)

    def verrou(prendre):
        class Verrou:
            def __init__(self, lock):
                self._lock = lock
                self.relock()

            def readWriteLock(self):
                return self._lock

            def relock(self):
                getattr(self._lock, prendre)()

            def unlock(self):
                self._lock.unlock()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.unlock()
        return Verrou

    QReadLocker, QWriteLocker = verrou("lockForRead"), verrou("lockForWrite")
    QReadLocker.__name__, QWriteLocker.__name__ = "QReadLocker", "QWriteLocker"

    class QSemaphore:
        def __init__(self, n=0):
            self._n = n

        def acquire(self, n=1):
            _obtenir(lambda: self._n >= n, "QSemaphore.acquire")
            self._n -= n

        def tryAcquire(self, n=1, timeout=0):
            if not _attendre(lambda: self._n >= n, timeout):
                return False
            self._n -= n
            return True

        def release(self, n=1):
            self._n += n

        def available(self):
            return self._n

    class QSemaphoreReleaser:
        def __init__(self, sem=None, n=1):
            self._sem, self._n = sem, n

        def semaphore(self):
            return self._sem

        def cancel(self):
            sem, self._sem = self._sem, None
            return sem

        def __del__(self):
            if self._sem is not None:
                self._sem.release(self._n)

    class QWaitCondition:
        def __init__(self):
            self._reveils = []

        def wait(self, lockedMutex, deadline=None):
            jeton = [False]
            self._reveils.append(jeton)
            lockedMutex.unlock()
            try:
                return _attendre(lambda: jeton[0], _delai(deadline))
            finally:
                if jeton in self._reveils:
                    self._reveils.remove(jeton)
                lockedMutex.lock() if hasattr(lockedMutex, "lock") else lockedMutex.lockForRead()

        def wakeOne(self):
            if self._reveils:
                self._reveils.pop(0)[0] = True

        def wakeAll(self):
            while self._reveils:
                self.wakeOne()

        def notify_one(self):
            self.wakeOne()

        def notify_all(self):
            self.wakeAll()

    class QProcessEnvironment:
        """L'environnement d'un processus : un dictionnaire (le « processus » du navigateur est un Worker Pyodide)."""

        class Initialization(enum.IntEnum):
            InheritFromParent = 0

        def __init__(self, other=None):
            self._env = dict(other._env) if isinstance(other, QProcessEnvironment) else {}

        @staticmethod
        def systemEnvironment():
            e = QProcessEnvironment()
            e._env = dict(os.environ)
            return e

        def insert(self, name, value=None):
            if isinstance(name, QProcessEnvironment):
                self._env.update(name._env)
            else:
                self._env[name] = value

        def remove(self, name):
            self._env.pop(name, None)

        def value(self, name, defaultValue=""):
            return self._env.get(name, defaultValue)

        def contains(self, name):
            return name in self._env

        def keys(self):
            return list(self._env)

        def isEmpty(self):
            return not self._env

        def clear(self):
            self._env.clear()

        def toStringList(self):
            return [f"{k}={v}" for k, v in self._env.items()]

        def inheritsFromParent(self):
            return False

        def swap(self, other):
            self._env, other._env = other._env, self._env

        def __eq__(self, other):
            return isinstance(other, QProcessEnvironment) and self._env == other._env

    for classe in (QThread, QRunnable, QThreadPool, QMutex, QRecursiveMutex, QMutexLocker, QReadWriteLock, QReadLocker,
                   QWriteLocker, QSemaphore, QSemaphoreReleaser, QWaitCondition, QProcessEnvironment):
        if classe.__name__ not in ns:
            ns[classe.__name__] = classe


def doubler_sleep():
    """``time.sleep`` rend la main à la page quand l'appel peut suspendre (le ``sleep`` de Pyodide gèle la page : il n'y a
    pas d'attente passive sur son fil)."""
    sleep = time.sleep

    def sleep_(secs):
        if bloquant._peut_suspendre():
            _pause(secs * 1000)
        else:
            sleep(secs)

    time.sleep = sleep_
