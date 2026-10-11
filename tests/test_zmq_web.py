"""Doublures ``zmq`` et ``threading`` du navigateur (qtpy6/web/zmq_web.py et threading_web.py), testées en natif et
sans Qt : les crochets par défaut (une file vidée par ``pomper()``) rendent tout vérifiable hors navigateur. Le
transport réel (``postMessage``) n'est pas ici : le protocole entre interpréteurs est exercé avec un ``poster``
qui enregistre."""

import asyncio
import importlib.util
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from qtpy6.web import threading_web, zmq_web

RACINE = Path(__file__).resolve().parents[1]
PYZMQ_PRESENT = importlib.util.find_spec("zmq") is not None


@pytest.fixture(autouse=True)
def propre():
    """Registres et crochets vierges avant et après chaque test ; une alarme change un blocage en échec."""
    zmq_web.reinitialiser()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("blocage coopératif (15 s)")))
    signal.alarm(15)
    yield
    signal.alarm(0)
    zmq_web.reinitialiser()


def sous_processus(code: str) -> subprocess.CompletedProcess:
    """Lance ``code`` dans un interpréteur neuf dont le PYTHONPATH est le dépôt."""
    env = {**os.environ, "PYTHONPATH": str(RACINE)}
    commande = [sys.executable, "-c", textwrap.dedent(code)]
    return subprocess.run(commande, capture_output=True, text=True, timeout=30, env=env)


def paire(type_serveur=zmq_web.ROUTER, type_client=zmq_web.DEALER, adresse="tcp://127.0.0.1:5600"):
    """Un contexte, une socket liée à ``adresse`` et une socket connectée."""
    contexte = zmq_web.Context()
    serveur = contexte.socket(type_serveur)
    serveur.bind(adresse)
    client = contexte.socket(type_client)
    client.connect(adresse)
    return contexte, serveur, client


# --- zmq_web -------------------------------------------------------------------------------------------------------

def test_constantes_et_enums():
    assert zmq_web.ROUTER == 6 and zmq_web.DEALER == 5 and zmq_web.REQ == 3 and zmq_web.SUB == 2
    assert zmq_web.SocketType.DEALER == 5 and zmq_web.SocketType.ROUTER == 6
    assert zmq_web.NOBLOCK == zmq_web.DONTWAIT == 1 and zmq_web.SNDMORE == 2
    assert (zmq_web.POLLIN, zmq_web.POLLOUT, zmq_web.POLLERR) == (1, 2, 4)
    assert zmq_web.LINGER == 17 and zmq_web.IDENTITY == zmq_web.ROUTING_ID == 5 and zmq_web.LAST_ENDPOINT == 32
    assert zmq_web.QUEUE == 3
    assert zmq_web.EAGAIN == 11 and zmq_web.ETERM == 156384765 and zmq_web.EFSM == 156384763
    assert zmq_web.__version__ == "26.0.0"
    assert zmq_web.zmq_version() == "4.3.5" and zmq_web.zmq_version_info() == (4, 3, 5)
    assert zmq_web.pyzmq_version() == "26.0.0"


def test_bind_connect_dealer_routeur():
    contexte, routeur, dealer = paire()
    dealer.send_multipart([b"a", b"b"])
    recu = routeur.recv_multipart(zmq_web.NOBLOCK)
    assert recu[1:] == [b"a", b"b"] and len(recu) == 3
    routeur.send_multipart([recu[0], b"reponse"])
    assert dealer.recv_multipart(zmq_web.NOBLOCK) == [b"reponse"]
    assert routeur.getsockopt(zmq_web.LAST_ENDPOINT) == b"tcp://127.0.0.1:5600"


def test_bind_to_random_port_et_adresse_prise():
    contexte = zmq_web.Context()
    s1 = contexte.socket(zmq_web.ROUTER)
    port = s1.bind_to_random_port("tcp://127.0.0.1")
    assert isinstance(port, int) and 49152 <= port < 65536
    s2 = contexte.socket(zmq_web.ROUTER)
    with pytest.raises(zmq_web.ZMQError) as exc:
        s2.bind(f"tcp://127.0.0.1:{port}")
    assert exc.value.errno == zmq_web.EADDRINUSE
    with pytest.raises(zmq_web.ZMQBindError):
        s2.bind_to_random_port("tcp://127.0.0.1", min_port=port, max_port=port + 1, max_tries=3)


def test_identite_posee_ou_aleatoire():
    contexte, routeur, dealer = paire()
    dealer.setsockopt(zmq_web.IDENTITY, b"x")
    dealer.send(b"m")
    assert routeur.recv_multipart(zmq_web.NOBLOCK)[0] == b"x"
    autre = contexte.socket(zmq_web.DEALER)
    autre.connect("tcp://127.0.0.1:5600")
    autre.send(b"m")
    identite = routeur.recv_multipart(zmq_web.NOBLOCK)[0]
    assert len(identite) == 5 and identite.startswith(b"\x00")


def test_hwm():
    """Le client LSP de Spyder fait ``set_hwm(0)`` (jalon 7 dans le navigateur, 12/10/2026)."""
    _contexte, routeur, _dealer = paire()
    assert routeur.hwm == 1000
    routeur.set_hwm(0)
    assert routeur.get_hwm() == routeur.getsockopt(zmq_web.RCVHWM) == 0


def test_recv_sans_message():
    contexte, routeur, dealer = paire()
    with pytest.raises(zmq_web.Again) as exc:
        dealer.recv(zmq_web.NOBLOCK)
    assert isinstance(exc.value, zmq_web.ZMQError) and exc.value.errno == zmq_web.EAGAIN


def test_recv_bloquant_delai_echu():
    contexte, routeur, dealer = paire()
    dealer.setsockopt(zmq_web.RCVTIMEO, 50)
    debut = time.monotonic()
    with pytest.raises(zmq_web.Again):
        dealer.recv()
    assert 0.03 <= time.monotonic() - debut < 1.0


def test_recv_bloquant_satisfait_par_plus_tard():
    contexte, routeur, dealer = paire()
    dealer.send(b"?")
    identite = routeur.recv_multipart(zmq_web.NOBLOCK)[0]
    zmq_web.plus_tard(lambda: routeur.send_multipart([identite, b"enfin"]), 20)
    assert dealer.recv() == b"enfin"


def test_recv_sans_copie_rend_des_frames():
    contexte, routeur, dealer = paire()
    dealer.send(b"?")
    identite = routeur.recv_multipart(zmq_web.NOBLOCK)[0]
    routeur.send_multipart([identite, b"donnee"])
    frames = dealer.recv_multipart(zmq_web.NOBLOCK, copy=False)
    assert isinstance(frames[0], zmq_web.Frame)
    assert frames[0].bytes == b"donnee" and bytes(frames[0].buffer) == b"donnee"


def test_connect_avant_bind():
    contexte = zmq_web.Context()
    dealer = contexte.socket(zmq_web.DEALER)
    dealer.connect("tcp://127.0.0.1:5601")
    dealer.send_multipart([b"tot"])
    routeur = contexte.socket(zmq_web.ROUTER)
    routeur.bind("tcp://127.0.0.1:5601")
    assert routeur.recv_multipart(zmq_web.NOBLOCK)[1:] == [b"tot"]


def test_req_routeur_device_et_term():
    contexte = zmq_web.Context()
    routeur = contexte.socket(zmq_web.ROUTER)
    routeur.bind("tcp://127.0.0.1:5602")
    req = contexte.socket(zmq_web.REQ)
    req.connect("tcp://127.0.0.1:5602")
    etat = {}

    def lancer():
        try:
            zmq_web.device(zmq_web.QUEUE, routeur, routeur)
        except zmq_web.ZMQError as erreur:
            etat["errno"] = erreur.errno

    fil = threading_web.Thread(target=lancer)
    fil.start()
    zmq_web.plus_tard(lambda: (req.send(b"ping"), etat.update(reponse=req.recv())), 10)
    zmq_web.plus_tard(contexte.term, 300)
    fil.join(1)
    assert etat.get("reponse") == b"ping"
    assert not fil.is_alive()
    assert etat.get("errno") == zmq_web.ETERM


def test_pub_sub():
    contexte, pub, sub = paire(zmq_web.PUB, zmq_web.SUB, "tcp://127.0.0.1:5603")
    sub.subscribe("a")
    sans = contexte.socket(zmq_web.SUB)
    sans.connect("tcp://127.0.0.1:5603")
    pub.send_multipart([b"b", b"2"])
    pub.send_multipart([b"ab", b"1"])
    assert sub.recv_multipart(zmq_web.NOBLOCK) == [b"ab", b"1"]
    with pytest.raises(zmq_web.Again):
        sub.recv_multipart(zmq_web.NOBLOCK)
    with pytest.raises(zmq_web.Again):
        sans.recv_multipart(zmq_web.NOBLOCK)


def test_push_pull_et_pair():
    contexte, pull, push = paire(zmq_web.PULL, zmq_web.PUSH, "tcp://127.0.0.1:5604")
    push.send(b"travail")
    assert pull.recv(zmq_web.NOBLOCK) == b"travail"
    contexte, p1, p2 = paire(zmq_web.PAIR, zmq_web.PAIR, "tcp://127.0.0.1:5605")
    p2.send(b"salut")
    assert p1.recv(zmq_web.NOBLOCK) == b"salut"


def test_poller():
    contexte, routeur, dealer = paire()
    poller = zmq_web.Poller()
    poller.register(routeur, zmq_web.POLLIN)
    assert poller.poll(0) == []
    dealer.send(b"x")
    assert poller.poll(100) == [(routeur, zmq_web.POLLIN)]
    poller.register(dealer, zmq_web.POLLOUT)
    assert (dealer, zmq_web.POLLOUT) in poller.poll(0)
    routeur.recv_multipart(zmq_web.NOBLOCK)
    assert poller.poll(0) == [(dealer, zmq_web.POLLOUT)]
    dealer.send(b"y")
    lisibles, ecrivables, autres = zmq_web.select([routeur], [dealer], [], 0.1)
    assert (lisibles, ecrivables, autres) == ([routeur], [dealer], [])


def test_zmqstream():
    contexte, routeur, dealer = paire()
    flux = zmq_web.ZMQStream(routeur)
    recus = []
    flux.on_recv(recus.append)
    dealer.send_multipart([b"1"])
    assert recus == []  # pas synchrone
    zmq_web.pomper()
    assert len(recus) == 1 and recus[0][1:] == [b"1"]
    dealer.send_multipart([b"2"])
    assert flux.flush() >= 1 and recus[1][1:] == [b"2"]
    flux.on_recv(None)
    dealer.send_multipart([b"3"])
    zmq_web.pomper()
    assert len(recus) == 2
    assert flux.linger == routeur.linger
    assert not flux.closed()
    flux.close()
    assert flux.closed()


def test_zmqstream_rappel_coroutine_planifie():
    """ipykernel passe une coroutine (``Kernel.dispatch_control``) à ``on_recv`` du canal control : comme pyzmq, la
    doublure doit la planifier, sinon tout message control est perdu (« coroutine … was never awaited »)."""
    contexte, routeur, dealer = paire()
    flux = zmq_web.ZMQStream(routeur)
    recus = []

    async def rappel(frames):
        recus.append(frames)

    async def principal():
        flux.on_recv(rappel)
        dealer.send_multipart([b"1"])
        zmq_web.pomper()
        for _ in range(3):
            await asyncio.sleep(0)

    asyncio.run(principal())
    assert len(recus) == 1 and recus[0][1:] == [b"1"]
    flux.close()


def test_asyncio():
    asyn = zmq_web.asyncio
    contexte = asyn.Context()
    routeur = contexte.socket(zmq_web.ROUTER)
    routeur.bind("tcp://127.0.0.1:5606")
    dealer = contexte.socket(zmq_web.DEALER)
    dealer.connect("tcp://127.0.0.1:5606")
    boucle = asyncio.new_event_loop()

    async def scenario():
        futur = dealer.recv_multipart()
        assert asyncio.isfuture(futur) and not futur.done()
        await dealer.send_multipart([b"q"])
        identite = (await routeur.recv_multipart())[0]
        await routeur.send_multipart([identite, b"r"])
        zmq_web.pomper()
        return await asyncio.wait_for(futur, 1)

    try:
        assert boucle.run_until_complete(scenario()) == [b"r"]
    finally:
        boucle.close()


@pytest.mark.skipif(PYZMQ_PRESENT, reason="pyzmq est installé dans cet interpréteur : installer() ne remplace pas")
def test_installer_sans_crochets_expose_les_modules():
    zmq_web.installer()
    import zmq
    from zmq.error import ZMQError
    from zmq.eventloop.zmqstream import ZMQStream
    from zmq.utils import jsonapi
    import zmq.asyncio  # noqa: F401
    assert zmq.Context and ZMQStream and ZMQError and jsonapi.loads(jsonapi.dumps({"a": 1})) == {"a": 1}


# Simule l'absence de pyzmq sans toucher à sys.path (le site-packages qui le porte porte aussi PySide6) : chaque
# chercheur de sys.meta_path est enveloppé et ne voit plus ``zmq`` ni ses sous-modules.
MASQUER_PYZMQ = """
    import sys

    class _Masque:
        def __init__(self, chercheur):
            self.chercheur = chercheur

        def find_spec(self, nom, chemin=None, cible=None):
            if nom == "zmq" or nom.startswith("zmq."):
                return None
            return self.chercheur.find_spec(nom, chemin, cible)

    sys.meta_path[:] = [_Masque(c) for c in sys.meta_path]
    for _nom in [n for n in sys.modules if n == "zmq" or n.startswith("zmq.")]:
        del sys.modules[_nom]
"""


def sans_pyzmq(code: str) -> subprocess.CompletedProcess:
    """Lance ``code`` dans un interpréteur neuf où pyzmq est masqué."""
    return sous_processus(textwrap.dedent(MASQUER_PYZMQ) + textwrap.dedent(code))


def test_installer_cache_pyzmq_dans_un_interpreteur_sans_pyzmq():
    """pyzmq est masqué (finder en tête de chaîne) dans un sous-processus : installer() doit alors fournir ``zmq``."""
    resultat = sans_pyzmq("""
        try:
            import zmq
        except ImportError:
            pass
        else:
            raise SystemExit("pyzmq n'est pas masqué")
        from qtpy6.web import zmq_web
        zmq_web.installer()
        import zmq
        from zmq.error import ZMQError
        from zmq.eventloop.zmqstream import ZMQStream
        from zmq.utils import jsonapi
        import zmq.asyncio
        assert zmq.Context is zmq_web.Context and ZMQStream and ZMQError
        assert jsonapi.loads(jsonapi.dumps({"a": 1})) == {"a": 1}
        print("ok", zmq.ROUTER)
    """)
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.strip() == "ok 6"


def test_installer_ne_remplace_pas_pyzmq_present():
    if not PYZMQ_PRESENT:
        pytest.skip("pyzmq absent de cet interpréteur : cas couvert par les autres tests")
    import zmq as reel
    zmq_web.installer()
    assert sys.modules["zmq"] is reel


def test_protocole_distant_cote_connecte():
    envoyes = []
    zmq_web.installer(poster=lambda destination, message: envoyes.append((destination, message)))
    zmq_web.declarer_distant(5555, "w1")
    contexte = zmq_web.Context()
    dealer = contexte.socket(zmq_web.DEALER)
    dealer.connect("tcp://127.0.0.1:5555")
    identite = dealer.getsockopt(zmq_web.IDENTITY)
    assert envoyes == [("w1", {"op": "connect", "port": 5555, "type": zmq_web.DEALER, "pair": identite,
                               "abonnements": []})]
    dealer.send_multipart([b"x"])
    destination, message = envoyes[-1]
    assert destination == "w1"
    assert message["op"] == "vers_lie" and message["port"] == 5555 and message["pair"] == identite
    assert message["frames"] == [b"x"]
    zmq_web.recevoir("w1", {"op": "vers_pair", "port": 5555, "pair": identite, "frames": [b"y"]})
    assert dealer.recv_multipart(zmq_web.NOBLOCK) == [b"y"]


def test_port_relie_ailleurs_reconnecte():
    """Un noyau redémarré relie les mêmes ports dans un autre Worker : le client s'y reconnecte, comme libzmq."""
    envoyes = []
    zmq_web.installer(poster=lambda destination, message: envoyes.append((destination, message)))
    zmq_web.declarer_distant(5555, "w1")
    dealer = zmq_web.Context().socket(zmq_web.DEALER)
    dealer.connect("tcp://127.0.0.1:5555")
    identite = dealer.getsockopt(zmq_web.IDENTITY)
    envoyes.clear()
    zmq_web.recevoir("w2", {"op": "bind", "port": 5555})
    assert envoyes == [("w2", {"op": "connect", "port": 5555, "type": zmq_web.DEALER, "pair": identite,
                               "abonnements": []})]
    dealer.send_multipart([b"x"])
    assert envoyes[-1][0] == "w2" and envoyes[-1][1]["op"] == "vers_lie"
    zmq_web.recevoir("w2", {"op": "bind", "port": 5555})  # même destination : rien de plus
    assert len(envoyes) == 2


def test_protocole_distant_cote_lie():
    envoyes = []
    zmq_web.installer(poster=lambda destination, message: envoyes.append((destination, message)))
    contexte = zmq_web.Context()
    routeur = contexte.socket(zmq_web.ROUTER)
    routeur.bind("tcp://127.0.0.1:6000")
    zmq_web.recevoir("w2", {"op": "connect", "port": 6000, "type": zmq_web.DEALER, "pair": b"\x00abcd",
                            "abonnements": []})
    zmq_web.recevoir("w2", {"op": "vers_lie", "port": 6000, "pair": b"\x00abcd", "frames": [b"z"]})
    assert routeur.recv_multipart(zmq_web.NOBLOCK) == [b"\x00abcd", b"z"]
    routeur.send_multipart([b"\x00abcd", b"r"])
    assert envoyes == [("w2", {"op": "vers_pair", "port": 6000, "pair": b"\x00abcd", "frames": [b"r"]})]


def test_protocole_port_inconnu_ignore():
    zmq_web.recevoir("w3", {"op": "vers_lie", "port": 6999, "pair": b"\x00zzzz", "frames": [b"?"]})
    zmq_web.recevoir("w3", {"op": "vers_pair", "port": 6999, "pair": b"\x00zzzz", "frames": [b"?"]})
    zmq_web.recevoir("w3", {"op": "disconnect", "port": 6999, "pair": b"\x00zzzz"})


def test_term_reveille_recv_bloquant():
    contexte, routeur, dealer = paire()
    etat = {}

    def lire():
        try:
            dealer.recv()
        except zmq_web.ContextTerminated as erreur:
            etat["errno"] = erreur.errno

    fil = threading_web.Thread(target=lire)
    zmq_web.plus_tard(contexte.term, 30)
    fil.start()
    fil.join(2)
    assert not fil.is_alive()
    assert etat == {"errno": zmq_web.ETERM}


# --- threading_web -------------------------------------------------------------------------------------------------

def test_thread_cooperatif():
    traces = []
    vus = {}

    def f():
        traces.append("f")
        vus["courant"] = threading_web.current_thread()

    fil = threading_web.Thread(target=f)
    assert not fil.is_alive()
    fil.start()
    assert traces == []  # pas exécuté tout de suite
    assert fil.is_alive()
    zmq_web.pomper()
    assert traces == ["f"] and vus["courant"] is fil
    assert not fil.is_alive()
    fil.join()
    assert threading_web.current_thread() is threading_web.main_thread()
    assert threading_web.main_thread().name == "MainThread" and threading_web.main_thread().is_alive()
    with pytest.raises(RuntimeError):
        fil.start()
    autre = threading_web.Thread(target=lambda: None)
    autre.start()
    assert fil.ident != autre.ident


def test_event():
    evenement = threading_web.Event()
    debut = time.monotonic()
    assert evenement.wait(timeout=0.05) is False
    assert time.monotonic() - debut >= 0.04
    threading_web.Thread(target=evenement.set).start()
    assert evenement.wait(1) is True and evenement.is_set()


def test_lock_rlock_condition_semaphore():
    verrou = threading_web.Lock()
    assert not verrou.locked()
    with verrou:
        assert verrou.locked()
    assert verrou.acquire() and verrou.locked()
    verrou.release()
    pris = threading_web.Lock()
    threading_web.Thread(target=pris.acquire).start()
    zmq_web.pomper()
    assert pris.locked() and pris.acquire(blocking=False) is False

    rverrou = threading_web.RLock()
    with rverrou:
        with rverrou:
            pass

    condition = threading_web.Condition()
    with condition:
        threading_web.Thread(target=lambda: (condition.acquire(), condition.notify(), condition.release())).start()
        assert condition.wait(1) is True

    semaphore = threading_web.Semaphore(1)
    assert semaphore.acquire(blocking=False) is True
    assert semaphore.acquire(blocking=False) is False
    semaphore.release()
    assert semaphore.acquire(blocking=False) is True


def test_timer():
    traces = []
    minuteur = threading_web.Timer(0.02, lambda: traces.append(time.monotonic()))
    debut = time.monotonic()
    minuteur.start()
    zmq_web.pomper()
    assert traces == []
    minuteur.join(1)
    assert len(traces) == 1 and traces[0] - debut >= 0.015
    annule = threading_web.Timer(0.02, lambda: traces.append("annule"))
    annule.start()
    annule.cancel()
    zmq_web.attendre(lambda: False, 60)
    assert "annule" not in traces


def test_local():
    donnees = threading_web.local()
    donnees.valeur = 1

    def ecrire():
        donnees.valeur = 2
        assert not hasattr(donnees, "autre")

    fil = threading_web.Thread(target=ecrire)
    fil.start()
    fil.join(1)
    assert donnees.valeur == 1
    fil2 = threading_web.Thread(target=lambda: setattr(donnees, "interne", 3))
    fil2.start()
    fil2.join(1)
    assert not hasattr(donnees, "interne")


def test_installer_threading_en_sous_processus():
    code = """
        import threading
        from qtpy6.web import threading_web
        originaux = (threading.Thread, threading.Lock, threading.Event)
        threading_web.installer()
        assert threading.Thread is threading_web.Thread
        assert threading.Event is threading_web.Event
        threading_web.desinstaller()
        assert (threading.Thread, threading.Lock, threading.Event) == originaux
        print("ok")
    """
    resultat = sous_processus(code)
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.strip() == "ok"


async def _attendre(poller):
    return await poller.poll(0)


def test_poller_asyncio_accepte_une_socket_ordinaire():
    """jupyter_client enregistre des sockets ordinaires dans un ``zmq.asyncio.Poller``."""
    _, serveur, client = paire()
    client.send(b"x")
    poller = zmq_web.asyncio.Poller()
    poller.register(serveur, zmq_web.POLLIN)
    assert asyncio.run(_attendre(poller)) == [(serveur, zmq_web.POLLIN)]


def test_socket_underlying_et_shadow():
    contexte = zmq_web.Context()
    socket = contexte.socket(zmq_web.DEALER)
    assert isinstance(socket.underlying, int)
    assert zmq_web.Socket.shadow(socket.underlying) is socket
    assert zmq_web.Socket.shadow(socket) is socket
    ombre = zmq_web.asyncio.Socket.shadow(socket.underlying)
    assert isinstance(ombre, zmq_web.asyncio.Socket) and ombre.underlying == socket.underlying
    assert ombre.type == socket.type


def test_context_socket_class():
    assert zmq_web.Context()._socket_class is zmq_web.Socket
    assert zmq_web.asyncio.Context()._socket_class is zmq_web.asyncio.Socket


def test_log_handlers_pubhandler_dans_un_interpreteur_sans_pyzmq():
    resultat = sans_pyzmq("""
        import logging
        from qtpy6.web import zmq_web
        zmq_web.installer()
        import zmq
        from zmq.log.handlers import PUBHandler
        contexte = zmq.Context()
        pub, sub = contexte.socket(zmq.PUB), contexte.socket(zmq.SUB)
        pub.bind("tcp://127.0.0.1:5701")
        sub.connect("tcp://127.0.0.1:5701")
        sub.subscribe(b"")
        journal = logging.getLogger("essai")
        journal.addHandler(PUBHandler(pub))
        journal.warning("bonjour")
        zmq_web.pomper()
        topic, message = sub.recv_multipart()
        assert b"bonjour" in message and topic.startswith(b"WARNING")
        print("ok")
    """)
    assert resultat.returncode == 0, resultat.stderr
    assert resultat.stdout.strip() == "ok"


def test_boucle_partagee_des_fils_cooperatifs():
    """jupyter_client (IOLoopThread, HBChannel) crée dans chaque fil sa boucle : ``new_event_loop``, ``set_event_loop``,
    ``run_until_complete``, ``close``. Le navigateur n'en fait tourner qu'une (« attached to a different loop », mesuré
    au jalon 8a) : la boucle « neuve » délègue tout à la boucle commune, et sa fermeture ne la ferme pas."""
    code = """
        import asyncio
        from qtpy6.web import threading_web
        commune = asyncio.new_event_loop()
        threading_web.partager_boucle(commune)
        neuve = asyncio.new_event_loop()
        asyncio.set_event_loop(neuve)
        assert neuve is not commune and neuve.create_future().get_loop() is commune
        async def dormir():
            await asyncio.sleep(0)
            return asyncio.get_running_loop()
        assert neuve.run_until_complete(dormir()) is commune
        neuve.close()
        assert not commune.is_closed() and not neuve.is_closed()
        print("ok")
    """
    fini = sous_processus(code)
    assert fini.stdout.strip() == "ok", fini.stderr


def test_futures_sur_fils_cooperatifs():
    """Pyodide n'a pas ``ThreadPoolExecutor`` (``concurrent.futures`` le refuse sans fils) : IPython l'importe
    (``terminal/debugger.py``), le noyau du Worker n'allait donc pas plus loin que ``import IPython`` (jalon 8a). La
    doublure fait tourner chaque tâche à une tâche suivante ; ``result``, ``wait``, ``as_completed`` et la sortie du
    ``with`` attendent par le crochet."""
    code = """
        import concurrent.futures as cf
        from qtpy6.web import threading_web
        threading_web.doubler_futures(threading_web.attendre, threading_web.plus_tard)
        vus = []
        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            fs = [ex.submit(lambda i=i: vus.append(i) or i * i) for i in range(4)]
            assert not vus  # rien ne tourne avant la première attente
            assert fs[3].result() == 9
            assert sorted(f.result() for f in cf.as_completed(fs)) == [0, 1, 4, 9]
            fini, reste = cf.wait([ex.submit(lambda: 1 / 0)])
            assert isinstance(fini.pop().exception(), ZeroDivisionError) and not reste
            assert list(ex.map(str, [1, 2])) == ["1", "2"]
            tard = ex.submit(lambda: "tard")
        assert tard.done()  # la sortie du with a attendu
        print("ok")
    """
    fini = sous_processus(code)
    assert fini.stdout.strip() == "ok", fini.stderr


def test_adresses_en_octets():
    """pyzmq accepte une adresse en octets, celle que rend ``getsockopt(LAST_ENDPOINT)`` : ipykernel y connecte sa socket
    de débogage (``init_control``, jalon 8a)."""
    contexte, routeur, dealer = paire()
    autre = contexte.socket(zmq_web.DEALER)
    autre.connect(routeur.getsockopt(zmq_web.LAST_ENDPOINT))
    autre.send(b"x")
    assert routeur.recv_multipart(zmq_web.NOBLOCK)[1:] == [b"x"]
    lie = contexte.socket(zmq_web.PAIR)
    lie.bind(b"inproc://octets")
    assert lie.getsockopt(zmq_web.LAST_ENDPOINT) == b"inproc://octets"


def test_meme_identite_sur_deux_ports_distants():
    """jupyter_client donne la même identité (celle de la session) aux sockets shell, stdin et control d'un client : la
    réponse d'un port distant revient à la socket connectée à CE port, pas à la dernière connectée (jalon 8a)."""
    envoyes = []
    zmq_web.installer(poster=lambda destination, message: envoyes.append((destination, message)))
    contexte = zmq_web.Context()
    shell, control = contexte.socket(zmq_web.DEALER), contexte.socket(zmq_web.DEALER)
    shell.identity = control.identity = b"session"
    for port in (5601, 5602):
        zmq_web.declarer_distant(port, "w1")
    shell.connect("tcp://127.0.0.1:5601")
    control.connect("tcp://127.0.0.1:5602")
    zmq_web.recevoir("w1", {"op": "vers_pair", "port": 5601, "pair": b"session", "frames": [b"reponse"]})
    assert shell.recv_multipart(zmq_web.NOBLOCK) == [b"reponse"]
    with pytest.raises(zmq_web.Again):
        control.recv_multipart(zmq_web.NOBLOCK)
    routeur = contexte.socket(zmq_web.ROUTER)  # côté lié : le port part avec la réponse
    routeur.bind("tcp://127.0.0.1:5603")
    zmq_web.recevoir("w2", {"op": "connect", "port": 5603, "type": zmq_web.DEALER, "pair": b"session",
                            "abonnements": []})
    routeur.send_multipart([b"session", b"r"])
    assert envoyes[-1] == ("w2", {"op": "vers_pair", "port": 5603, "pair": b"session", "frames": [b"r"]})


def test_fil_suspendu_n_est_plus_le_fil_courant():
    """Sous JSPI, un fil suspendu dans une attente laisse tourner le reste (le script principal, un slot) : ce reste
    n'est pas dans ce fil, et le fil s'y retrouve à la reprise (``hb_channel.stop()`` → ``join`` levait « cannot join
    current thread » dans le script principal, jalon 8a)."""
    vus = []

    def attendre_hote(condition, delai_ms):  # pendant la suspension, un autre code tourne
        vus.append(threading_web.current_thread())
        return condition()

    threading_web.poser_crochets(attendre=attendre_hote)

    def f():
        vus.append(threading_web.current_thread())
        threading_web.attendre(lambda: True, None)
        vus.append(threading_web.current_thread())

    fil = threading_web.Thread(target=f)
    fil.start()
    threading_web.pomper()
    assert vus == [fil, threading_web.main_thread(), fil]
    assert threading_web.current_thread() is threading_web.main_thread()


def test_battement_annonce_par_le_worker():
    """Le Heartbeat d'ipykernel est ``device(QUEUE, s, s)`` sur un port lié : dans un Worker, un calcul qui ne rend
    jamais la main arrêterait l'écho. Le Worker annonce donc ce port à la page (``echo``), qui répondra à sa place
    (jalon 8b)."""
    envoyes = []
    zmq_web.installer(poster=lambda destination, message: envoyes.append((destination, message)))
    zmq_web.en_travailleur = True
    contexte = zmq_web.Context()
    rep = contexte.socket(zmq_web.ROUTER)
    rep.bind("tcp://127.0.0.1:5620")
    def lancer():
        with pytest.raises(zmq_web.ZMQError):
            zmq_web.device(zmq_web.QUEUE, rep, rep)

    fil = threading_web.Thread(target=lancer, daemon=True)
    fil.start()
    zmq_web.plus_tard(contexte.term, 50)
    fil.join(1)
    assert (None, {"op": "echo", "port": 5620}) in envoyes


def test_battement_repondu_par_la_page_tant_que_le_worker_vit():
    """Côté page : un port annoncé ``echo`` répond tout de suite, sans aller au Worker (occupé ou non) ; une fois le
    Worker oublié (``oublier``, à sa mort), plus de réponse : jupyter_client le voit mort, comme en natif."""
    envoyes = []
    zmq_web.installer(poster=lambda destination, message: envoyes.append((destination, message)))
    zmq_web.recevoir("w1", {"op": "bind", "port": 5621})
    zmq_web.recevoir("w1", {"op": "echo", "port": 5621})
    contexte = zmq_web.Context()
    req = contexte.socket(zmq_web.REQ)
    req.connect("tcp://127.0.0.1:5621")
    req.send(b"ping")
    assert req.recv(zmq_web.NOBLOCK) == b"ping"
    assert not [m for _, m in envoyes if m["op"] == "vers_lie"]
    zmq_web.oublier("w1")
    req.send(b"ping")
    with pytest.raises(zmq_web.Again):
        req.recv(zmq_web.NOBLOCK)
