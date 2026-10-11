"""The binding's QtWebEngineCore; in the browser, where Qt-WASM has no QtWebEngine, qtpy6.web.moteur_web's
QWebEnginePage (an <iframe> of the browser), QWebEngineSettings, and empty QWebEngineProfile and QWebEngineScript."""
import sys

from . import _binding

if sys.platform == 'emscripten':
    from .web.moteur_web import QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineSettings  # noqa: F401
else:
    _binding.load(globals(), 'QtWebEngineCore')
    _binding.finish(globals())
