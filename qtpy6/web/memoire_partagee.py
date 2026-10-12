"""``multiprocessing.shared_memory.SharedMemory`` entre la page et ses Web Workers (un noyau, un ``ProcessusWeb``) : le
segment est un ``SharedArrayBuffer`` (page isolée : ``service_worker(…, { isoler: true })``, sans quoi il n'existe pas).
Le code du bureau tourne tel quel : ``SharedMemory(name=…, create=True, size=…)`` dans la page,
``SharedMemory(name=…)`` dans le Worker, ``struct.pack_into(…, shm.buf, …)`` des deux côtés.

Un Pyodide ne voit que sa propre mémoire wasm : ``buf`` est une copie locale (un ``bytearray``), réconciliée avec le
``SharedArrayBuffer`` en JavaScript, sans entrer dans Python (``_MOTEUR``) : toutes les 4 ms, et à la création ou à
l'attache. Dans la page, entre deux exécutions Python ; dans un Worker, pendant que Python est suspendu (``time.sleep``
par JSPI, chaque image de ``pyxel.flip``) : une suite d'écritures Python sans attente arrive donc entière. Réconciliation
par mot de 32 bits (la queue, par octet), contre l'image du dernier passage : un mot changé ici est poussé (de la fin vers le début), puis un
mot changé ailleurs est tiré (du début vers la fin) ; un même mot écrit des deux côtés entre deux passages : le dernier
passage gagne. L'ordre des deux boucles sert le verrou de séquence d'un en-tête placé AVANT ses données (spyder_pyxel :
``OFF_SEQ`` puis ``OFF_FRAMEBUFFER``) : qui voit le nouvel en-tête a déjà les nouvelles données.

Les segments sont créés par la page et lui appartiennent : elle les envoie à chaque Worker (``enregistrer_worker``, à sa
naissance, puis à chaque création). Un segment créé dans un Worker ne sort pas de ce Worker (non requis à ce jour)."""

from __future__ import annotations

import errno
import os
import secrets
import sys
import time
from typing import Any

_MOTEUR = """
(() => {
  if (self.qtpy6_memoire) return self.qtpy6_memoire;
  const liste = new Set();
  const passe = m => {
    const H = m.module.HEAPU8.buffer;  // relu à chaque passe : la mémoire wasm peut avoir grandi
    const q = m.n & ~3, vues = (T, k) => [new T(H, m.l, k), new T(H, m.s, k), new T(m.sab, 0, k)];  // q : la queue d'octets
    const [L, S, P] = vues(Int32Array, q >> 2), [l, s, p] = vues(Uint8Array, m.n);
    for (let i = m.n - 1; i >= q; i--) if (l[i] !== s[i]) p[i] = s[i] = l[i];
    for (let i = (q >> 2) - 1; i >= 0; i--) if (L[i] !== S[i]) P[i] = S[i] = L[i];
    for (let i = 0; i < q >> 2; i++) if (P[i] !== S[i]) L[i] = S[i] = P[i];
    for (let i = q; i < m.n; i++) if (p[i] !== s[i]) l[i] = s[i] = p[i];
  };
  setInterval(() => liste.forEach(passe), 4);
  self.qtpy6_memoires ??= new Map();  // nom → SharedArrayBuffer : ceux que la page a envoyés (travailleur.js) ou créés ici
  return self.qtpy6_memoire = {
    ajouter: (module, l, s, sab, n) => { const m = { module, l, s, sab, n }; passe(m); liste.add(m); return m; },
    retirer: m => liste.delete(m),
    passer: () => liste.forEach(passe),
    envoyer: (w, nom, sab) => w.postMessage({ memoire: { nom, sab } }),
  };
})()
"""
_SEGMENTS: dict[str, Any] = {}  # page : les segments créés, envoyés à chaque Worker
_WORKERS: list[Any] = []


def _moteur() -> Any:
    from pyodide.code import run_js  # noqa: PLC0415
    return run_js(_MOTEUR)


def _dans_worker() -> bool:
    import js  # noqa: PLC0415
    return not hasattr(js, "document")


def enregistrer_worker(worker: Any) -> None:
    """Page : un Worker qui vient de naître reçoit les segments existants, puis chaque segment créé ensuite."""
    _WORKERS.append(worker)
    if _SEGMENTS:
        moteur = _moteur()
        for nom, sab in _SEGMENTS.items():
            moteur.envoyer(worker, nom, sab)


def reconcilier() -> None:
    """Une passe tout de suite, hors minuterie : un Worker dont ``time.sleep`` ne peut pas suspendre Python (contexte sans
    JSPI : ``can_run_sync()`` faux, constaté dans le noyau IPython, essai 27e du 12/10/2026) bloque, et la minuterie ne
    passe jamais ; ``time.sleep`` appelle donc ceci avant et après son attente bloquante."""
    import js  # noqa: PLC0415
    moteur = getattr(js.self, "qtpy6_memoire", None)
    if moteur is not None:
        moteur.passer()


def _adresse(tampon: bytearray) -> int:
    from pyodide.ffi import create_proxy  # noqa: PLC0415
    proxy = create_proxy(tampon)
    vue = proxy.getBuffer("u8")
    try:
        return vue.data.byteOffset
    finally:
        vue.release()
        proxy.destroy()


class SharedMemory:
    """La surface de ``multiprocessing.shared_memory.SharedMemory`` utilisée par le code du bureau."""

    def __init__(self, name: str | None = None, create: bool = False, size: int = 0, *, track: bool = True) -> None:
        import js  # noqa: PLC0415
        import pyodide_js  # noqa: PLC0415

        if not hasattr(js, "SharedArrayBuffer"):
            raise OSError("SharedMemory : page non isolée (qtpy6web.service_worker(…, { isoler: true }))")
        moteur = _moteur()
        segments = js.self.qtpy6_memoires
        if create:
            if size <= 0:
                raise ValueError("'size' must be a positive number different from zero")
            name = name or "wnsm_" + secrets.token_hex(4)
            if name in _SEGMENTS or segments.has(name):
                raise FileExistsError(17, "File exists", name)
            sab = js.SharedArrayBuffer.new(size)
            segments.set(name, sab)
            if not _dans_worker():
                _SEGMENTS[name] = sab
                for worker in _WORKERS:
                    moteur.envoyer(worker, name, sab)
        else:
            if name is None:
                raise ValueError("'name' can only be None if create=True")
            fin = time.monotonic() + 2  # dans un Worker, le message de la page peut être encore en route
            while not segments.has(name):
                if not _dans_worker() or time.monotonic() > fin:
                    raise FileNotFoundError(2, "No such file or directory", name)
                time.sleep(0.01)
            sab = segments.get(name)
            size = sab.byteLength
        self._name, self._size = name, size
        self._local, self._image = bytearray(size), bytearray(size)
        self._buf: memoryview | None = memoryview(self._local)[:size]  # tient le bytearray : jamais redimensionné
        adresses = _adresse(self._local), _adresse(self._image)
        assert all(a % 4 == 0 for a in adresses), adresses
        self._lien = moteur.ajouter(pyodide_js._module, *adresses, sab, size)

    @property
    def buf(self) -> memoryview | None:
        return self._buf

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        return self._size

    def close(self) -> None:
        if self._buf is not None:
            _moteur().retirer(self._lien)
            self._buf.release()
            self._buf = None

    def unlink(self) -> None:
        import js  # noqa: PLC0415
        js.self.qtpy6_memoires.delete(self._name)
        _SEGMENTS.pop(self._name, None)

    def __reduce__(self) -> tuple[Any, ...]:
        return (self.__class__, (self.name, False, self.size))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r}, size={self.size})"


def installer() -> None:
    """``multiprocessing.shared_memory.SharedMemory`` (et ``ShareableList``, qui la construit) : cette classe."""
    try:
        from multiprocessing import shared_memory  # noqa: PLC0415
    except ImportError:  # _posixshmem absent : le module réduit à la classe
        import multiprocessing  # noqa: PLC0415
        import types  # noqa: PLC0415
        shared_memory = types.ModuleType("multiprocessing.shared_memory")
        sys.modules[shared_memory.__name__] = shared_memory
        multiprocessing.shared_memory = shared_memory
    shared_memory.SharedMemory = SharedMemory
    if not hasattr(os, "mkfifo"):  # absent sous emscripten : AttributeError là où le code POSIX attend OSError
        os.mkfifo = _mkfifo


def _mkfifo(path, mode=0o666, *, dir_fd=None) -> None:
    """Pas de tube nommé dans le navigateur : l'échec qu'une plateforme sans FIFO rend, que l'appelant sait rattraper
    (spyder_pyxel retombe alors sur son sondage, 12/10/2026)."""
    raise OSError(errno.ENOSYS, os.strerror(errno.ENOSYS), path)
