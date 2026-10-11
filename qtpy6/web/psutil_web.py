"""``psutil`` dans le navigateur, où il n'y a ni table des processus ni /proc : ce module fournit un ``psutil`` de même
API, réduit à ce que l'écosystème de Spyder emploie réellement. ``installer()`` l'enregistre sous le nom ``psutil`` quand
psutil n'est pas importable. Python pur, sans Qt, sans js ni pyodide (il tourne aussi dans le Web Worker du noyau).

Relevé de l'usage réel (SmartPython et fork Spyder, 11/10/2026), fichier:ligne → attribut :
- ipykernel/kernelbase.py:38,90 (import, annotation Process) ; :1053 Process() ; :1054 children(recursive=True) ;
  :1035-1046 cpu_percent(), memory_full_info() (+ hasattr « pss », absent ici → rss) ; :1074 cpu_percent() ;
  :1079 cpu_count(logical=True) ; :1080 virtual_memory()._asdict() ; :1351 NoSuchProcess ; :1361 Process().children() ;
  :1325-1340 terminate(), kill(), send_signal() sur les enfants.
- spyder_kernels/console/kernelapp.py:20,47 : pid_exists(parent) — le noyau s'arrête si le parent n'existe pas.
- jupyter_client/localinterfaces.py:165-172 : net_if_addrs() (vide ici, le repli sans psutil est ensuite utilisé).
- spyder/plugins/ipythonconsole/utils/manager.py:60-82 : Process(pid), children(recursive=True), send_signal,
  AccessDenied, NoSuchProcess, wait_procs(timeout, callback).
- spyder/plugins/completion/providers/languageserver/{client.py:381-388, transport/main.py:124-148} : pid_exists,
  Process(pid).status(), STATUS_ZOMBIE, Process().ppid().
- spyder/utils/programs.py:1202-1215 : Process(pid).cmdline() ; utils/environ.py:121 : terminal() ;
  utils/system.py:51 : virtual_memory().percent ; plugins/statusbar/widgets/status.py:39 : cpu_percent(interval=0).

Le modèle : un registre de pids « vivants » : le pid courant, et des pids factices inscrits par d'autres doublures
(``inscrire`` / ``retirer`` : un Popen doublé s'en sert). ``kill`` / ``terminate`` / ``send_signal`` d'un pid factice le
retirent du registre ; le processus courant, lui, ne se tue pas (AccessDenied)."""

from __future__ import annotations

import contextlib
import os
import sys
import time
from collections import namedtuple
from typing import Any, Callable, Iterator

__version__ = "7.0.0"
version_info = tuple(int(x) for x in __version__.split("."))

STATUS_RUNNING = "running"
STATUS_SLEEPING = "sleeping"
STATUS_ZOMBIE = "zombie"

_MEMOIRE_TOTALE = 4 * 1024 ** 3  # rien à mesurer dans le navigateur : une machine de 4 Gio, entièrement disponible

_vivants: set[int] = set()


# --- Exceptions ---------------------------------------------------------------------------------------------------

class Error(Exception):
    """Racine des erreurs de psutil."""


class NoSuchProcess(Error):
    def __init__(self, pid: int, name: str | None = None, msg: str | None = None) -> None:
        super().__init__(msg or f"process no longer exists (pid={pid})")
        self.pid, self.name, self.msg = pid, name, msg


class ZombieProcess(NoSuchProcess):
    pass


class AccessDenied(Error):
    def __init__(self, pid: int | None = None, name: str | None = None, msg: str | None = None) -> None:
        super().__init__(msg or f"access denied (pid={pid})")
        self.pid, self.name, self.msg = pid, name, msg


class TimeoutExpired(Error):
    def __init__(self, seconds: float, pid: int | None = None, name: str | None = None) -> None:
        super().__init__(f"timeout after {seconds} seconds (pid={pid})")
        self.seconds, self.pid, self.name = seconds, pid, name


# --- Registre -----------------------------------------------------------------------------------------------------

def inscrire(pid: int) -> None:
    """Déclare vivant un pid factice (un processus doublé, le parent d'une page…)."""
    _vivants.add(int(pid))


def retirer(pid: int) -> None:
    """Retire un pid factice ; le pid courant reste toujours vivant."""
    _vivants.discard(int(pid))


def reinitialiser() -> None:
    _vivants.clear()


def pid_exists(pid: int) -> bool:
    return int(pid) == os.getpid() or int(pid) in _vivants


def pids() -> list[int]:
    return sorted({os.getpid(), *_vivants})


# --- Processus ----------------------------------------------------------------------------------------------------

_InfoMemoire = namedtuple("pmem", "rss vms shared text lib data dirty")
_MemoireVirtuelle = namedtuple("svmem", "total available percent used free active inactive buffers cached shared slab")


class Process:
    def __init__(self, pid: int | None = None) -> None:
        self.pid = os.getpid() if pid is None else int(pid)
        if not pid_exists(self.pid):
            raise NoSuchProcess(self.pid)

    def __repr__(self) -> str:
        return f"Process(pid={self.pid})"

    def __eq__(self, autre: object) -> bool:
        return isinstance(autre, Process) and autre.pid == self.pid

    def __hash__(self) -> int:
        return hash(self.pid)

    def _vivant(self) -> None:
        if not pid_exists(self.pid):
            raise NoSuchProcess(self.pid)

    def is_running(self) -> bool:
        return pid_exists(self.pid)

    def status(self) -> str:
        self._vivant()
        return STATUS_RUNNING

    def name(self) -> str:
        self._vivant()
        return os.path.basename(sys.executable) or "python"

    def cmdline(self) -> list[str]:
        self._vivant()
        return [sys.executable, *sys.argv] if self.pid == os.getpid() else []

    def ppid(self) -> int:
        self._vivant()
        return 0

    def terminal(self) -> str | None:
        return None

    def children(self, recursive: bool = False) -> list[Process]:
        self._vivant()
        return []

    def cpu_percent(self, interval: float | None = None) -> float:
        return 0.0

    def memory_info(self) -> Any:
        self._vivant()
        return _InfoMemoire(0, 0, 0, 0, 0, 0, 0)

    def memory_full_info(self) -> Any:
        return self.memory_info()  # sans champ « pss » : ipykernel se rabat sur rss

    def memory_percent(self, memtype: str = "rss") -> float:
        self._vivant()
        return 0.0

    @contextlib.contextmanager
    def oneshot(self) -> Iterator[None]:
        yield

    def send_signal(self, sig: int) -> None:
        self._vivant()
        if self.pid == os.getpid():
            raise AccessDenied(self.pid)
        retirer(self.pid)

    def terminate(self) -> None:
        self.send_signal(15)

    def kill(self) -> None:
        self.send_signal(9)

    def wait(self, timeout: float | None = None) -> int | None:
        """Un processus factice ne vit que tant que le registre le dit : attendre sa fin, bornée par ``timeout``."""
        fin = None if timeout is None else time.monotonic() + timeout
        while self.is_running():
            if fin is not None and time.monotonic() >= fin:
                raise TimeoutExpired(timeout, pid=self.pid)
            time.sleep(0.01)
        return None


def wait_procs(procs: list[Process], timeout: float | None = None,
               callback: Callable[[Process], Any] | None = None) -> tuple[list[Process], list[Process]]:
    """Sépare les processus morts des vivants, sans attendre au-delà de ``timeout``."""
    fin = None if timeout is None else time.monotonic() + timeout
    morts: list[Process] = []
    restants = list(procs)
    while True:
        for p in [p for p in restants if not p.is_running()]:
            restants.remove(p)
            morts.append(p)
            if callback is not None:
                callback(p)
        if not restants or (fin is not None and time.monotonic() >= fin):
            return morts, restants
        time.sleep(0.01)


# --- La machine ---------------------------------------------------------------------------------------------------

def cpu_count(logical: bool = True) -> int:
    return os.cpu_count() or 1


def cpu_percent(interval: float | None = None, percpu: bool = False) -> float:
    return 0.0


def virtual_memory() -> Any:
    total = _MEMOIRE_TOTALE
    return _MemoireVirtuelle(total, total, 0.0, 0, total, 0, 0, 0, 0, 0, 0)


def net_if_addrs() -> dict[str, list[Any]]:
    return {}


# --- Installation -------------------------------------------------------------------------------------------------

def installer() -> None:
    """Enregistre ce module sous le nom ``psutil`` si psutil n'est pas importable, et déclare vivant le parent de la
    page (``JPY_PARENT_PID``) : SpyderParentPoller arrête le noyau quand ``pid_exists(parent)`` est faux."""
    import importlib.util
    if "psutil" not in sys.modules and importlib.util.find_spec("psutil") is None:
        sys.modules["psutil"] = sys.modules[__name__]
    parent = os.environ.get("JPY_PARENT_PID")
    if parent and parent.isdigit():
        inscrire(int(parent))
