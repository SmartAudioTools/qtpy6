"""``subprocess.run`` dans le navigateur, qui n'a pas de processus : un programme Python y est lancé par ``ProcessusWeb``
(un Web Worker Pyodide, voir ``travailleur``), et l'appel attend sa fin suspendu par JSPI (``bloquant``), la page et Qt
continuant pendant ce temps. ``call`` aussi : ``check_output`` passe par ``run`` et ``check_call`` par ``call``, ils en
profitent donc.

Ce qui se lance : ``sys.executable`` (ou ``python``, ``python3``…) suivi d'un script ou de ``-m module`` ; tout autre
programme lève ``FileNotFoundError``, comme sur un bureau où il n'est pas installé. ``input``, ``capture_output``,
``stdout``/``stderr`` (``PIPE``, ``DEVNULL``, ``STDOUT``, un fichier ouvert), ``text``/``encoding``, ``timeout``,
``check`` et ``cwd`` sont tenus ; ``shell``, ``env`` et les autres sont ignorés.

Comme ``exec()``, l'attente n'est possible que dans une entrée suspendable (le script principal, un slot) : ailleurs
(méthode virtuelle appelée par Qt), ``RuntimeError``."""

import os
import subprocess
import sys

_PYTHONS = ("python", "python3", f"python3.{sys.version_info.minor}")


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


def doubler():
    subprocess.run, subprocess.call = run, call
