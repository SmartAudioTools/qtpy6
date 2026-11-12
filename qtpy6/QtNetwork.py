"""The binding's QtNetwork; in the browser, where Qt-WASM's has no QNetworkInterface and no engine that listens,
qtpy6.web.reseau_web's QTcpServer, QTcpSocket and QNetworkInterface, on the loopback of qtpy6.web.socket_web."""
import sys

from . import _binding

_binding.load(globals(), 'QtNetwork')
if sys.platform == 'emscripten':
    from .web.reseau_web import QNetworkAddressEntry, QNetworkInterface, QTcpServer, QTcpSocket  # noqa: F401

_binding.finish(globals())
