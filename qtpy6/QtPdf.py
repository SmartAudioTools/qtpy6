"""The binding's QtPdf - and, in the browser, where Qt-WASM has none, qtpy6.web.pdf's QPdfDocument (pdf.js)."""
import sys

from . import _binding

if sys.platform == 'emscripten':
    from .web.pdf import QPdfDocument  # noqa: F401
else:
    _binding.load(globals(), 'QtPdf')

_binding.finish(globals())
