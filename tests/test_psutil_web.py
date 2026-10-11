"""Doublure ``psutil`` du navigateur (qtpy6/web/psutil_web.py), testée en natif : ``psutil`` est masqué dans un
sous-processus (finder en tête de sys.meta_path, comme ``sans_pyzmq`` dans test_zmq_web) pour vérifier ce que
``installer()`` fournit à ipykernel, spyder_kernels et Spyder là où psutil n'existe pas."""

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from qtpy6.web import psutil_web

RACINE = Path(__file__).resolve().parents[1]
PSUTIL_PRESENT = importlib.util.find_spec("psutil") is not None

MASQUER_PSUTIL = """
    import sys

    class _Masque:
        def __init__(self, chercheur):
            self.chercheur = chercheur

        def find_spec(self, nom, chemin=None, cible=None):
            if nom == "psutil" or nom.startswith("psutil."):
                return None
            return self.chercheur.find_spec(nom, chemin, cible)

    sys.meta_path[:] = [_Masque(c) for c in sys.meta_path]
    for _nom in [n for n in sys.modules if n == "psutil" or n.startswith("psutil.")]:
        del sys.modules[_nom]
"""


def sans_psutil(code: str, **env_en_plus: str) -> subprocess.CompletedProcess:
    """Lance ``code`` dans un interpréteur neuf où psutil est masqué ; PYTHONPATH est le dépôt."""
    env = {**os.environ, "PYTHONPATH": str(RACINE), **env_en_plus}
    if "JPY_PARENT_PID" not in env_en_plus:
        env.pop("JPY_PARENT_PID", None)
    commande = [sys.executable, "-c", textwrap.dedent(MASQUER_PSUTIL) + textwrap.dedent(code)]
    return subprocess.run(commande, capture_output=True, text=True, timeout=60, env=env)


@pytest.fixture(autouse=True)
def propre():
    psutil_web.reinitialiser()
    yield
    psutil_web.reinitialiser()


def test_installer_pose_le_module_quand_psutil_est_absent():
    resultat = sans_psutil("""
        try:
            import psutil
        except ImportError:
            pass
        else:
            raise SystemExit("psutil n'est pas masqué")
        from qtpy6.web import psutil_web
        psutil_web.installer()
        import psutil
        assert psutil is psutil_web
        print("ok", psutil.__version__, psutil.version_info >= (5, 0))
    """)
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.split()[0] == "ok"


def test_pid_courant_et_parent_declare_existent():
    resultat = sans_psutil("""
        import os
        from qtpy6.web import psutil_web
        psutil_web.installer()
        import psutil
        assert psutil.pid_exists(os.getpid())
        assert psutil.pid_exists(4242)
        assert not psutil.pid_exists(4243)
        print("ok")
    """, JPY_PARENT_PID="4242")
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.strip() == "ok"


def test_import_ipykernel_kernelbase_avec_psutil_masque():
    resultat = sans_psutil("""
        from qtpy6.web import psutil_web
        psutil_web.installer()
        try:
            from qtpy6.web import zmq_web
            zmq_web.installer()
        except Exception:
            pass
        import ipykernel.kernelbase
        import spyder_kernels.console.kernelapp
        print("ok")
    """)
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.strip() == "ok"


@pytest.mark.skipif(not PSUTIL_PRESENT, reason="psutil absent de cet interpréteur")
def test_installer_ne_remplace_pas_psutil_present():
    import psutil as reel
    psutil_web.installer()
    assert sys.modules["psutil"] is reel


def test_registre_inscrire_retirer():
    assert psutil_web.pid_exists(os.getpid())
    assert not psutil_web.pid_exists(777)
    psutil_web.inscrire(777)
    assert psutil_web.pid_exists(777)
    assert psutil_web.Process(777).is_running()
    psutil_web.retirer(777)
    assert not psutil_web.pid_exists(777)
    with pytest.raises(psutil_web.NoSuchProcess):
        psutil_web.Process(777)
    psutil_web.retirer(777)  # retirer un pid absent est sans effet
    psutil_web.retirer(os.getpid())  # le pid courant ne se retire pas
    assert psutil_web.pid_exists(os.getpid())


def test_exceptions():
    assert issubclass(psutil_web.NoSuchProcess, psutil_web.Error)
    assert issubclass(psutil_web.AccessDenied, psutil_web.Error)
    assert issubclass(psutil_web.TimeoutExpired, psutil_web.Error)
    assert issubclass(psutil_web.ZombieProcess, psutil_web.NoSuchProcess)
    erreur = psutil_web.NoSuchProcess(12)
    assert erreur.pid == 12 and "12" in str(erreur)
    assert psutil_web.TimeoutExpired(3, pid=5).seconds == 3


def test_process_courant():
    p = psutil_web.Process()
    assert p.pid == os.getpid()
    assert p.children() == [] and p.children(recursive=True) == []
    assert isinstance(p.cpu_percent(), float)
    info = p.memory_info()
    assert info.rss >= 0 and info.vms >= 0
    assert p.memory_full_info().rss >= 0 and not hasattr(p.memory_full_info(), "pss")
    assert isinstance(p.memory_percent(), float)
    assert p.is_running()
    assert p.status() == psutil_web.STATUS_RUNNING
    assert isinstance(p.name(), str) and p.name()
    assert isinstance(p.cmdline(), list)
    assert isinstance(p.ppid(), int)
    assert p.terminal() is None
    with p.oneshot():
        assert p.pid == os.getpid()


def test_process_factice_kill_terminate_wait():
    psutil_web.inscrire(900)
    p = psutil_web.Process(900)
    p.terminate()
    assert not p.is_running() and not psutil_web.pid_exists(900)
    assert p.wait(timeout=1) is None
    with pytest.raises(psutil_web.NoSuchProcess):
        p.status()
    psutil_web.inscrire(901)
    q = psutil_web.Process(901)
    q.send_signal(9)
    assert not psutil_web.pid_exists(901)
    psutil_web.inscrire(902)
    psutil_web.Process(902).kill()
    assert not psutil_web.pid_exists(902)


def test_wait_procs():
    psutil_web.inscrire(910)
    psutil_web.inscrire(911)
    a, b = psutil_web.Process(910), psutil_web.Process(911)
    a.kill()
    vus = []
    morts, vivants = psutil_web.wait_procs([a, b], timeout=0, callback=vus.append)
    assert morts == [a] and vivants == [b] and vus == [a]


def test_processus_courant_ne_se_tue_pas():
    p = psutil_web.Process()
    with pytest.raises(psutil_web.AccessDenied):
        p.kill()
    assert psutil_web.pid_exists(os.getpid())


def test_machine():
    assert psutil_web.cpu_count() >= 1
    assert psutil_web.cpu_count(logical=True) >= 1
    assert isinstance(psutil_web.cpu_percent(), float)
    assert isinstance(psutil_web.cpu_percent(interval=0), float)
    memoire = psutil_web.virtual_memory()
    assert memoire.total >= memoire.available >= 0
    assert 0 <= memoire.percent <= 100 and memoire.used >= 0
    assert set(memoire._asdict()) >= {"total", "available", "percent", "used", "free"}
    assert psutil_web.net_if_addrs() == {}


def test_version():
    assert isinstance(psutil_web.__version__, str)
    assert psutil_web.version_info == tuple(int(x) for x in psutil_web.__version__.split("."))
