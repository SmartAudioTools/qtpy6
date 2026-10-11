"""Doublure de ``socket.socket`` dans la page, pour le choix d'un port libre par jupyter_client
(``LocalPortCache.find_available_port`` : ``SO_LINGER``, ``bind((ip, 0))``, ``getsockname``). Les sockets d'Emscripten ne
savent pas le faire (« Protocol not available » sur ``SO_LINGER``, mesuré dans Firefox au jalon 8a) ; or ce port ne sert
qu'à zmq, dont la doublure (zmq_web) tient le registre des ports liés : le port « libre » se tire donc dans ce registre,
sans socket réelle. Tout le reste passe à la vraie socket."""

from __future__ import annotations

import random
import socket

from . import zmq_web

_Socket = socket.socket


def port_libre() -> int:
    """Un port éphémère qu'aucune socket zmq de la page ni d'un Worker n'a lié."""
    while True:
        port = random.randrange(49152, 65536)
        if port not in zmq_web._lies and port not in zmq_web._distants:
            return port


class Socket(_Socket):
    _adresse: tuple | None = None

    def setsockopt(self, niveau: int, option: int, *valeur) -> None:
        try:
            super().setsockopt(niveau, option, *valeur)
        except OSError:
            if option != socket.SO_LINGER:  # sans objet : la socket n'est jamais réellement liée
                raise

    def bind(self, adresse) -> None:
        if isinstance(adresse, tuple) and len(adresse) >= 2 and adresse[1] == 0:
            self._adresse = (adresse[0], port_libre())
        else:
            super().bind(adresse)

    def getsockname(self):
        return self._adresse or super().getsockname()


def installer() -> None:
    socket.socket = Socket
