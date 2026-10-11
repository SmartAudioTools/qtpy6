"""The binding's QtWebEngineWidgets; in the browser, where Qt-WASM has no QtWebEngine, qtpy6.web.moteur_web's
QWebEngineView, whose page is an <iframe> of the browser laid over the widget."""
import sys

from . import _binding

if sys.platform == 'emscripten':
    from .web.moteur_web import QWebEngineView  # noqa: F401
else:
    _binding.load(globals(), 'QtWebEngineWidgets')
    _binding.finish(globals())
