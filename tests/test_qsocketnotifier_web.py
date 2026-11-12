"""Doublure ``QSocketNotifier`` du navigateur (``socket_web.doubler_qsocketnotifier``, posée par qtpy6.QtCore sous
emscripten) : le client LSP de Spyder veille le descripteur d'une socket zmq (``getsockopt(zmq.FD)``) et vide la socket à
chaque ``activated``. Testée en natif sur la doublure zmq_web, sans toucher le QtCore de la liaison (un module factice
reçoit la classe)."""

import os
import types

import pytest
from PySide6 import QtCore

from qtpy6.web import socket_web, threading_web, zmq_web


@pytest.fixture
def notifieur():
    zmq_web.reinitialiser()
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    module = types.SimpleNamespace(QSocketNotifier=QtCore.QSocketNotifier, QSocketDescriptor=QtCore.QSocketDescriptor)
    classe = socket_web.doubler_qsocketnotifier({"QObject": QtCore.QObject, "Signal": QtCore.Signal}, module)
    assert module.QSocketNotifier is classe
    yield classe
    zmq_web.reinitialiser()
    del app


class ClientLSP(QtCore.QObject):
    """Ce que fait ``LSPClient`` de Spyder : un slot sans argument, qui coupe le notifieur, vide la socket en non
    bloquant jusqu'à ``ZMQError`` et le rallume."""

    def __init__(self, classe, socket):
        super().__init__()
        self.socket, self.recus, self.appels = socket, [], 0
        self.notifier = classe(socket.getsockopt(zmq_web.FD), classe.Read, self)
        self.notifier.activated.connect(self.on_msg_received)

    @QtCore.Slot()
    def on_msg_received(self):
        self.appels += 1
        self.notifier.setEnabled(False)
        while True:
            try:
                self.recus.append(self.socket.recv_pyobj(flags=zmq_web.NOBLOCK))
            except zmq_web.ZMQError:
                self.notifier.setEnabled(True)
                break


def pomper(n=5):
    for _ in range(n):
        threading_web.pomper()


def test_fd_propre_a_chaque_socket():
    contexte = zmq_web.Context()
    a, b = contexte.socket(zmq_web.PAIR), contexte.socket(zmq_web.PAIR)
    assert a.getsockopt(zmq_web.FD) != b.getsockopt(zmq_web.FD)
    assert zmq_web._par_fd[a.getsockopt(zmq_web.FD)] is a


def test_activated_au_depot_comme_le_client_lsp(notifieur):
    contexte = zmq_web.Context()
    entree = contexte.socket(zmq_web.PAIR)
    port = entree.bind_to_random_port("tcp://127.0.0.1")
    sortie = contexte.socket(zmq_web.PAIR)
    sortie.connect(f"tcp://127.0.0.1:{port}")
    client = ClientLSP(notifieur, entree)
    assert isinstance(client.notifier, notifieur)
    pomper()
    assert client.appels == 0  # rien en file : rien d'émis
    arguments = []
    client.notifier.activated.connect(lambda *a: arguments.append(a))
    sortie.send_pyobj({"id": 1})
    sortie.send_pyobj({"id": 2})
    assert client.appels == 0  # jamais synchrone : à la tâche suivante
    pomper()
    assert client.recus == [{"id": 1}, {"id": 2}] and client.appels == 1
    descripteur, type_ = arguments[0]
    assert isinstance(descripteur, QtCore.QSocketDescriptor) and type_ == QtCore.QSocketNotifier.Type.Read
    client.notifier.setEnabled(False)
    sortie.send_pyobj({"id": 3})
    pomper()
    assert client.appels == 1  # coupé : rien
    client.notifier.setEnabled(True)  # un message attend : émis à la réactivation
    pomper()
    assert client.recus[-1] == {"id": 3} and client.appels == 2


def test_notifieur_sur_une_socket_tcp_de_la_doublure(notifieur, monkeypatch):
    monkeypatch.setattr(socket_web, "boucle_locale", True)
    ecoute = socket_web.Socket()
    ecoute.bind(("127.0.0.1", 0))
    ecoute.listen()
    notes = []
    veilleur = notifieur(ecoute.fileno(), notifieur.Read)
    veilleur.activated.connect(lambda *_: notes.append(1))
    client = socket_web.Socket()
    pomper()
    assert notes == []
    client.connect(ecoute.getsockname())
    pomper()
    assert notes  # une connexion attend accept()


def test_autre_descripteur_vraie_classe(notifieur):
    r, w = os.pipe()
    vrai = notifieur(r, notifieur.Read)
    assert type(vrai) is QtCore.QSocketNotifier
    vrai.setEnabled(False)
    os.close(r)
    os.close(w)
