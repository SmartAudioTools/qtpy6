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


# --- TCP de boucle locale (``boucle_locale``, vrai sous emscripten) --------------------------------------------------

import importlib  # noqa: E402
import selectors  # noqa: E402
import select  # noqa: E402
import signal  # noqa: E402
import socket  # noqa: E402
import socketserver  # noqa: E402
import threading  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402

from qtpy6.web import socket_web, threading_web, zmq_web  # noqa: E402

WEB = RACINE / "qtpy6" / "web"


@pytest.fixture
def boucle_locale(monkeypatch):
    """La doublure posée comme sous emscripten ; ``socket``, ``select``, ``selectors`` et ``socketserver`` rendus après."""
    zmq_web.reinitialiser()
    for module, nom in ((socket, "socket"), (select, "select"), (selectors, "DefaultSelector"),
                        (selectors, "SelectSelector"), (selectors, "PollSelector"), (socketserver, "_ServerSelector")):
        monkeypatch.setattr(module, nom, getattr(module, nom))
    monkeypatch.setattr(socket_web, "boucle_locale", True)
    monkeypatch.setattr(socket_web, "_installe", False)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("blocage (15 s)")))
    signal.alarm(15)
    socket_web.installer()
    yield
    signal.alarm(0)
    zmq_web.reinitialiser()


class Majuscules(socketserver.StreamRequestHandler):
    """Rend chaque ligne reçue en majuscules, comme pylsp lit ``rfile`` et écrit ``wfile``."""

    def handle(self):
        for ligne in self.rfile:
            self.wfile.write(ligne.upper())


def test_socketserver_threading_et_makefile(boucle_locale):
    serveur = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Majuscules)
    assert isinstance(serveur.socket, socket_web.Socket) and serveur.socket.fileno() in zmq_web._par_fd
    port = serveur.server_address[1]
    assert zmq_web._ecoutes[port] is serveur.socket
    fil = threading.Thread(target=serveur.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    fil.start()
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    assert client.getpeername() == ("127.0.0.1", port) and client.getsockname() != client.getpeername()
    lecteur = client.makefile("rb")
    client.sendall(b"bonjour\nle ser")
    assert lecteur.readline() == b"BONJOUR\n"
    client.send(b"veur\n")
    assert lecteur.readline() == b"LE SERVEUR\n"
    client.shutdown(socket.SHUT_WR)
    assert lecteur.read() == b""  # le gestionnaire a fini : le serveur ferme
    lecteur.close()
    client.close()
    serveur.shutdown()
    serveur.server_close()
    fil.join(2)
    assert port not in zmq_web._ecoutes


def test_connect_refuse_puis_accepte(boucle_locale):
    client = socket.socket()
    with pytest.raises(ConnectionRefusedError):
        client.connect(("127.0.0.1", 50123))
    ecoute = socket.socket()
    ecoute.bind(("127.0.0.1", 50123))
    ecoute.listen()
    with pytest.raises(OSError):
        socket.socket().bind(("127.0.0.1", 50123))  # port pris
    client = socket.socket()
    client.connect(("localhost", 50123))
    serveur, adresse = ecoute.accept()
    assert adresse == client.getsockname()
    ecoute.setblocking(False)
    with pytest.raises(BlockingIOError):
        ecoute.accept()
    serveur.settimeout(0.05)
    with pytest.raises(socket.timeout):
        serveur.recv(10)
    client.send(b"abc")
    assert serveur.recv(2) == b"ab" and serveur.recv(10) == b"c"
    client.close()
    assert serveur.recv(10) == b""


def test_select_et_selecteur(boucle_locale):
    ecoute = socket.socket()
    ecoute.bind(("127.0.0.1", 0))
    ecoute.listen()
    assert select.select([ecoute], [], [], 0) == ([], [], [])
    client = socket.create_connection(ecoute.getsockname())
    assert select.select([ecoute], [], [], 1)[0] == [ecoute]
    serveur, _ = ecoute.accept()
    with selectors.DefaultSelector() as selecteur:
        selecteur.register(serveur, selectors.EVENT_READ, "donnees")
        assert selecteur.select(0) == []
        client.send(b"x")
        (cle, evenements), = selecteur.select(1)
        assert cle.data == "donnees" and evenements == selectors.EVENT_READ
    r, w = os.pipe()  # un vrai descripteur passe au vrai select
    os.write(w, b"!")
    assert select.select([r], [], [], 0)[0] == [r]


def test_autres_hotes_et_familles_passent_au_vrai(boucle_locale):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))  # le port libre de jupyter_client, comme avant
    assert udp.fileno() not in zmq_web._par_fd and udp.getsockname()[1] >= 49152
    udp.close()
    distant = socket.socket()
    distant.settimeout(0.01)
    assert distant.connect_ex(("192.0.2.1", 9)) != 0  # autre hôte : la vraie socket (refusée, ou délai échu)
    assert distant.fileno() not in zmq_web._par_fd and distant.fileno() < 1000
    distant.close()


# --- Deux interpréteurs simulés : des copies des modules, reliées par ``recevoir`` ---------------------------------

def _interpreteur(nom: str) -> types.SimpleNamespace:
    """Une copie de ``zmq_web``, ``threading_web`` et ``socket_web`` (registres propres) qui joue un Worker : ses
    crochets sont ceux de la page (une seule file), ce qu'elle poste arrive au ``recevoir`` de la page."""
    paquet = types.ModuleType(nom)
    paquet.__path__ = [str(WEB)]
    sys.modules[nom] = paquet
    pose, socket.socket = socket.socket, socket_web._Socket  # la copie double la vraie socket, pas celle de la page
    copie = types.SimpleNamespace(**{m: importlib.import_module(f"{nom}.{m}")
                                     for m in ("threading_web", "zmq_web", "socket_web")})
    socket.socket = pose
    copie.zmq_web.en_travailleur = True
    copie.socket_web.boucle_locale = True
    copie.threading_web.poser_crochets(threading_web.attendre, threading_web.plus_tard,
                                       lambda _dest, message: threading_web.plus_tard(
                                           lambda: zmq_web.recevoir(nom, message)))
    return copie


@pytest.fixture
def interpretes(boucle_locale):
    """La page (les vrais modules) et deux Workers ``w1``, ``w2`` ; la page poste à ``interpretes[nom]``."""
    copies = {nom: _interpreteur(nom) for nom in ("w1", "w2")}
    threading_web.poser_crochets(poster=lambda dest, message: threading_web.plus_tard(
        lambda: copies[dest].zmq_web.recevoir(None, message)))
    yield copies
    for nom in list(sys.modules):
        if nom.split(".")[0] in copies:
            del sys.modules[nom]


def test_worker_vers_worker_relaye_par_la_page(interpretes):
    w1, w2 = interpretes["w1"], interpretes["w2"]
    client = w1.socket_web.Socket()
    with pytest.raises(ConnectionRefusedError):  # pylsp n'écoute pas encore : la passerelle réessaie
        client.connect(("127.0.0.1", 2087))
    ecoute = w2.socket_web.Socket()
    ecoute.bind(("127.0.0.1", 2087))
    ecoute.listen()
    threading_web.attendre(lambda: 2087 in zmq_web._distants, 1000)  # l'annonce ``bind`` de w2
    assert zmq_web._distants[2087] == "w2"
    client = w1.socket_web.Socket()
    client.connect(("127.0.0.1", 2087))  # w1 → page → w2, et la réponse par le même chemin
    serveur, _ = ecoute.accept()
    assert list(zmq_web._relais_flux.values())[0][:2] == ["w1", "w2"]
    client.sendall(b"Content-Length: 2\r\n\r\n{}")
    lecteur = serveur.makefile("rb")
    assert lecteur.readline() == b"Content-Length: 2\r\n" and lecteur.readline() == b"\r\n"
    assert lecteur.read(2) == b"{}"
    serveur.sendall(b"reponse")
    assert client.recv(100) == b"reponse"
    client.close()
    assert lecteur.read() == b""
    lecteur.close()  # ``makefile`` garde la socket ouverte, comme la vraie
    serveur.close()
    threading_web.attendre(lambda: not zmq_web._relais_flux, 1000)
    assert not zmq_web._relais_flux


def test_page_cliente_d_un_worker_et_worker_mort(interpretes):
    w2 = interpretes["w2"]
    ecoute = w2.socket_web.Socket()
    ecoute.bind(("127.0.0.1", 0))
    ecoute.listen()
    port = ecoute.getsockname()[1]
    threading_web.attendre(lambda: port in zmq_web._distants, 1000)
    client = socket.socket()
    client.connect(("127.0.0.1", port))
    serveur, _ = ecoute.accept()
    serveur.send(b"a")
    assert client.recv(10) == b"a"
    zmq_web.oublier("w2")  # le Worker meurt : la page voit la fin du flux
    assert client.recv(10) == b""
