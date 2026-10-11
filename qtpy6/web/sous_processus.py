"""``subprocess.run`` dans le navigateur, qui n'a pas de processus : un programme Python y est lancé par ``ProcessusWeb``
(un Web Worker Pyodide, voir ``travailleur``), et l'appel attend sa fin suspendu par JSPI (``bloquant``), la page et Qt
continuant pendant ce temps. ``call`` aussi : ``check_output`` passe par ``run`` et ``check_call`` par ``call``, ils en
profitent donc.

Ce qui se lance : ``sys.executable`` (ou ``python``, ``python3``…) suivi d'un script ou de ``-m module`` ; tout autre
programme lève ``FileNotFoundError``, comme sur un bureau où il n'est pas installé. ``input``, ``capture_output``,
``stdout``/``stderr`` (``PIPE``, ``DEVNULL``, ``STDOUT``, un fichier ouvert), ``text``/``encoding``, ``timeout``,
``check`` et ``cwd`` sont tenus ; ``shell``, ``env`` et les autres sont ignorés.

``Popen`` aussi, pour un programme qui parle à son enfant par ses tubes (jupyter_client lance ainsi le noyau de Spyder) :
``stdin``, ``stdout``, ``stderr``, ``poll``, ``wait``, ``kill``… sur le même worker. Son ``pid`` est factice, déclaré
vivant à ``psutil_web`` (ipykernel teste que son parent existe).

Comme ``exec()``, l'attente n'est possible que dans une entrée suspendable (le script principal, un slot) : ailleurs
(méthode virtuelle appelée par Qt), ``RuntimeError``."""

import itertools
import os
import subprocess
import sys
import types

_PYTHONS = ("python", "python3", f"python3.{sys.version_info.minor}")
_fabrique = None  # () -> ProcessusWeb : les tests de Popen y mettent un faux processus
_pids = itertools.count(40000)  # les pid factices de Popen


def run(args, *, input=None, capture_output=False, stdout=None, stderr=None, timeout=None, check=False,  # noqa: A002
        cwd=None, text=None, encoding=None, errors=None, universal_newlines=None, **_):
    from qtpy6.QtCore import QTimer  # noqa: PLC0415

    from . import bloquant  # noqa: PLC0415
    from .travailleur import ProcessusWeb  # noqa: PLC0415

    commande = [os.fspath(a) for a in ([args] if isinstance(args, (str, bytes, os.PathLike)) else args)]
    if commande[0] != sys.executable and os.path.basename(commande[0]) not in _PYTHONS:
        raise FileNotFoundError(2, "dans le navigateur, seul Python se lance", commande[0])
    if not bloquant._peut_suspendre():
        raise RuntimeError("subprocess.run appelé hors d'un slot (méthode virtuelle ?) : rien ne peut y attendre")
    if capture_output:
        stdout = stderr = subprocess.PIPE
    texte = text or universal_newlines or encoding is not None or errors is not None
    encoder = lambda o: o.encode(encoding or "utf-8", errors or "strict") if isinstance(o, str) else o  # noqa: E731
    decoder = lambda o: o.decode(encoding or "utf-8", errors or "strict") if texte else o  # noqa: E731

    p = ProcessusWeb()
    if stderr == subprocess.STDOUT:
        p.setProcessChannelMode(ProcessusWeb.ProcessChannelMode.MergedChannels)
    if cwd is not None:
        p.setWorkingDirectory(os.fspath(cwd))
    p.start(commande[0], commande[1:])
    if input is not None:
        p.write(encoder(input))
    p.closeWriteChannel()

    def brancher(resoudre):  # ``finished`` par le connect de PyQt : le relais de bloquant le reporterait d'un tour
        bloquant._connect_qt[0](p.finished, resoudre) if bloquant._connect_qt else p.finished.connect(resoudre)
        if timeout is not None:
            QTimer.singleShot(int(timeout * 1000), lambda: resoudre(None))
    code = bloquant._suspendre(brancher)
    if code is None:
        p.kill()
    sorties = []
    for voulu, octets, flux in ((stdout, p.readAllStandardOutput(), sys.stdout), (stderr, p.readAllStandardError(), sys.stderr)):
        if voulu == subprocess.PIPE:
            sorties.append(decoder(octets))
            continue
        sorties.append(None)
        if voulu is None and octets:  # hérités : la sortie du parent
            flux.write(octets.decode("utf-8", "replace"))
        elif voulu not in (subprocess.DEVNULL, subprocess.STDOUT, None):
            voulu.write(octets.decode("utf-8", "replace") if "b" not in getattr(voulu, "mode", "") else octets)
    if code is None:
        raise subprocess.TimeoutExpired(commande, timeout, *sorties)
    fini = subprocess.CompletedProcess(commande, code, *sorties)
    if check:
        fini.check_returncode()
    return fini


def call(*args, **kwargs):
    return run(*args, **kwargs).returncode


class _Flux:
    """``stdout`` ou ``stderr`` d'un ``Popen`` : ce que le worker a imprimé, lu comme un fichier binaire. Une lecture
    suspend (JSPI) tant qu'il n'y a rien et que le processus n'est pas fini."""

    def __init__(self) -> None:
        self.tampon, self.fini, self.closed = bytearray(), False, False

    def _prendre(self, n: int) -> bytes:
        n = len(self.tampon) if n is None or n < 0 else n
        octets, self.tampon = bytes(self.tampon[:n]), self.tampon[n:]
        return octets

    def read1(self, n: int = -1) -> bytes:
        from . import fils  # noqa: PLC0415

        fils._attendre(lambda: self.tampon or self.fini)
        return self._prendre(n)

    def read(self, n: int = -1) -> bytes:
        from . import fils  # noqa: PLC0415

        fils._attendre(lambda: self.fini or 0 <= n <= len(self.tampon))
        return self._prendre(n)

    def readline(self) -> bytes:
        from . import fils  # noqa: PLC0415

        fils._attendre(lambda: self.fini or b"\n" in self.tampon)
        return self._prendre(self.tampon.find(b"\n") + 1 or None)

    def close(self) -> None:
        self.closed = True


class _Entree:
    """``stdin`` d'un ``Popen`` : l'entrée standard du worker."""

    def __init__(self, processus) -> None:
        self._p, self.closed = processus, False

    def write(self, octets: bytes) -> int:
        return self._p.write(octets)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._p.closeWriteChannel()


class Popen:
    """``subprocess.Popen`` d'un programme Python, dans un worker (``ProcessusWeb``). Tout autre programme :
    ``FileNotFoundError``. ``start_new_session``, ``preexec_fn``, ``shell``… sont sans objet et ignorés."""

    __class_getitem__ = classmethod(types.GenericAlias)  # « subprocess.Popen[bytes] » dans une annotation (IPython)

    def __init__(self, args, bufsize=-1, executable=None, stdin=None, stdout=None, stderr=None,  # noqa: ARG002
                 *_, cwd=None, env=None, **__) -> None:
        from .travailleur import ProcessusWeb  # noqa: PLC0415

        commande = [os.fspath(a) for a in ([args] if isinstance(args, (str, bytes, os.PathLike)) else args)]
        if commande[0] != sys.executable and os.path.basename(commande[0]) not in _PYTHONS:
            raise FileNotFoundError(2, "dans le navigateur, seul Python se lance", commande[0])
        self.args, self.returncode, self._signale = args, None, None
        self.pid = next(_pids)
        try:
            from . import psutil_web  # noqa: PLC0415
        except ImportError:
            psutil_web = None
        self._psutil = psutil_web
        if psutil_web is not None:
            psutil_web.inscrire(self.pid)
        self._sorties = (stdout, stderr)
        self.stdout = _Flux() if stdout == subprocess.PIPE else None
        self.stderr = _Flux() if stderr == subprocess.PIPE else None
        self._p = p = (_fabrique or ProcessusWeb)()
        if stderr == subprocess.STDOUT:
            p.setProcessChannelMode(ProcessusWeb.ProcessChannelMode.MergedChannels)
        if cwd is not None:
            p.setWorkingDirectory(os.fspath(cwd))
        if env is not None:
            p.setProcessEnvironment(env)
        p.readyReadStandardOutput.connect(lambda: self._arrive(p.readAllStandardOutput(), self.stdout, stdout))
        p.readyReadStandardError.connect(lambda: self._arrive(p.readAllStandardError(), self.stderr, stderr))
        p.finished.connect(self._fini)
        p.start(commande[0], commande[1:])
        self.stdin = _Entree(p) if stdin == subprocess.PIPE else None

    def _arrive(self, octets: bytes, flux: "_Flux | None", voulu) -> None:
        if flux is not None:
            flux.tampon += octets
        elif hasattr(voulu, "write"):  # un fichier : sa part ; sinon (DEVNULL, hérité) la sortie est jetée
            voulu.write(octets)

    def _fini(self, code: int) -> None:
        self._arrive(self._p.readAllStandardOutput(), self.stdout, self._sorties[0])
        self._arrive(self._p.readAllStandardError(), self.stderr, self._sorties[1])
        self.returncode = code if self._signale is None else -self._signale
        for flux in (self.stdout, self.stderr):
            if flux is not None:
                flux.fini = True
        if self._psutil is not None:
            self._psutil.retirer(self.pid)

    def poll(self) -> "int | None":
        return self.returncode

    def wait(self, timeout: "float | None" = None) -> int:
        from . import fils  # noqa: PLC0415

        if not fils._attendre(lambda: self.returncode is not None, -1 if timeout is None else int(timeout * 1000)):
            raise subprocess.TimeoutExpired(self.args, timeout)
        return self.returncode

    def send_signal(self, sig: int) -> None:
        if not sig or self.returncode is not None:  # le signal 0 ne fait que tester l'existence
            return
        if sig in (9, 15):  # SIGKILL, SIGTERM : la fin du processus
            self._signale = int(sig)
            self._p.kill()
        else:  # SIGINT… : au Python du Worker, qui appelle son gestionnaire (``KeyboardInterrupt``), comme sur un bureau
            self._p.signaler(int(sig))

    def terminate(self) -> None:
        self.send_signal(15)

    def kill(self) -> None:
        self.send_signal(9)

    def __enter__(self) -> "Popen":
        return self

    def __exit__(self, *_) -> None:
        from . import fils  # noqa: PLC0415

        for flux in (self.stdout, self.stderr, self.stdin):
            if flux is not None:
                flux.close()
        fils._attendre(lambda: self.returncode is not None)


def doubler():
    subprocess.run, subprocess.call, subprocess.Popen = run, call, Popen


def doubler_zmq() -> None:
    """Le canal entre la page et le noyau d'un worker : ``zmq`` et ``threading`` de qtpy6 (crochets de la page : attente
    suspendue par JSPI, tâche suivante de ``bloquant``, message au worker destinataire), ``psutil`` et ``socket`` (choix d'un port libre)."""
    import asyncio  # noqa: PLC0415

    from . import bloquant, fils, socket_web, threading_web, zmq_web  # noqa: PLC0415

    def plus_tard(fonction, delai_ms=0) -> None:
        if delai_ms:
            asyncio.get_event_loop().call_later(delai_ms / 1000, bloquant._plus_tard, fonction)
        else:
            bloquant._plus_tard(fonction)

    def poster(destination, message) -> None:
        if destination is not None:  # None : la page elle-même
            destination._poster_zmq(message)

    threading_web.installer(fils._attendre, plus_tard)  # _attendre(condition, None) attend sans échéance
    threading_web.partager_boucle(asyncio.get_event_loop())  # les boucles que jupyter_client crée par fil
    zmq_web.installer(fils._attendre, plus_tard, poster)
    socket_web.installer()  # le port libre que jupyter_client choisit pour chaque canal
    try:
        from . import psutil_web  # noqa: PLC0415
    except ImportError:
        return
    psutil_web.installer()
