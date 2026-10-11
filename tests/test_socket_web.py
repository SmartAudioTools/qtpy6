"""Doublure ``socket`` de la page (qtpy6/web/socket_web.py) : le choix d'un port libre par jupyter_client
(``LocalPortCache.find_available_port`` : SO_LINGER, bind sur le port 0, getsockname), que les sockets d'Emscripten ne
savent pas faire (« Protocol not available », mesuré dans Firefox). Testée en natif, sous-processus pour ne pas laisser
``socket.socket`` remplacé."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def lancer(code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(RACINE)}
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True, env=env,
                          timeout=60)


def test_port_libre_sans_socket_reelle():
    r = lancer("""
        import errno, socket
        class Emscripten(socket.socket):  # ce que fait la socket de la page
            def setsockopt(self, *a):
                raise OSError(errno.ENOPROTOOPT, "Protocol not available")
            def bind(self, adresse):
                raise OSError(errno.EADDRNOTAVAIL, "pas de réseau")
        socket.socket = Emscripten
        from qtpy6.web import socket_web, zmq_web
        socket_web.installer()
        zmq_web._lies[50000] = object()
        from jupyter_client.connect import LocalPortCache
        cache = LocalPortCache.instance()
        ports = {cache.find_available_port("127.0.0.1") for _ in range(20)}
        assert len(ports) == 20, ports
        assert all(49152 <= p < 65536 for p in ports), ports
        assert 50000 not in ports
        print("ok")
    """)
    assert r.stdout.strip().endswith("ok"), r.stderr


def test_bind_explicite_et_autres_options_passent_au_vrai():
    r = lancer("""
        import socket
        from qtpy6.web import socket_web
        socket_web.installer()
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        assert s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        s.close()
        print("ok")
    """)
    assert r.stdout.strip().endswith("ok"), r.stderr
