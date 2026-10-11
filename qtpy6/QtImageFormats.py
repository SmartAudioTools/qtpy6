"""Qt's extra image formats for QImage and QImageReader (mng, jp2), imported once before reading such a file.
Natively nothing to do: Qt finds the imageformats plugins of the binding by itself, if it ships them. In the browser
they live in their own module (pyside_QtImageFormats.so), left out of the start: the import loads it, and its plugins
register at load time."""
import sys

if sys.platform == 'emscripten':
    import PySide6.QtImageFormats  # noqa: F401
