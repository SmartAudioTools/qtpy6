"""qtpy6: PySide6's API (snake_case names, Signal/Slot/Property, exec()) on
top of PySide6 or PyQt6.

    from qtpy6 import QtWidgets
    app = QtWidgets.QApplication([])
    button = QtWidgets.QPushButton()
    button.set_window_title('Hello')
    button.clicked.connect(app.quit)
    app.exec()

The binding is the one already imported if any (a process cannot switch),
else the ``QT_API`` setting (``pyside6``, ``pyqt6`` or ``auto``; environment
variable, or the session setting written by the QtSelector widget), else the
first one installed, in that order.

The other session settings, all read the same way: ``QT_SCALE`` (a factor
for `scaled()`, or ``auto`` for the first screen's DPI / 192), ``QT_FONT``
(a family, or ``default``) and ``QT_FONT_SIZE`` (in points, ``12 pixels``,
or ``default``), the last two applied by QApplication.
"""
import importlib
import importlib.util
import os
import sys

from ._env import get_env, set_env  # noqa: F401  (set_env is part of the API)

__version__ = '0.2.0'

API_NAMES = {'pyside6': 'PySide6', 'pyqt6': 'PyQt6'}

# Qt's own scaling stays off: `scaled()` does it, from QT_SCALE.
os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
os.environ['QT_USE_PHYSICAL_DPI'] = '1'
QT_FONT = get_env('QT_FONT', 'default')
QT_FONT_SIZE = get_env('QT_FONT_SIZE', 'default').lower()
QT_SCALE = get_env('QT_SCALE', 'auto').lower()
QT_SCALE = None if QT_SCALE == 'auto' else float(QT_SCALE)


class QtBindingsNotFoundError(ImportError):
    pass


def _select_api():
    for api, module in API_NAMES.items():
        if module in sys.modules:
            return api
    api = get_env('QT_API', 'auto').lower()
    if api != 'auto':
        if api not in API_NAMES:
            raise ValueError(f'QT_API={api!r}: expected auto or one of {", ".join(API_NAMES)}')
        return api
    for api, module in API_NAMES.items():
        if importlib.util.find_spec(module) is not None:
            return api
    raise QtBindingsNotFoundError(f'none of {", ".join(API_NAMES.values())} is installed')


API = _select_api()
API_NAME = API_NAMES[API]
# Shared with qtpy, pyqtgraph and matplotlib so they pick the same binding.
os.environ['QT_API'] = API
PYSIDE6, PYQT6 = (API == name for name in API_NAMES)

_core = importlib.import_module(f'{API_NAME}.QtCore')
QT_VERSION = _core.qVersion()  # the library loaded, which may be newer than the binding's build (PyQt6 wheels)
PYQT_VERSION, PYSIDE_VERSION = (_core.PYQT_VERSION_STR, None) if PYQT6 else (None, sys.modules[API_NAME].__version__)
del _core

from . import _binding  # noqa: E402, F401  (serves qtpy6.QtXxx modules that have no file of their own)
from . import QtCore, QtWidgets  # noqa: E402

_EPS = sys.float_info.epsilon


def scaled(obj, *more):
    """`obj` (int, float, QRect, QSize, QMargins, tuple, list...) scaled by QT_SCALE; several values give a tuple."""
    global QT_SCALE
    if more:
        return scaled((obj,) + more)
    if QT_SCALE is None:
        QT_SCALE = QtWidgets.QApplication.screens()[0].logicalDotsPerInch() / 192.0
    if QT_SCALE == 1:
        return obj
    if isinstance(obj, QtCore.QRect):
        return QtCore.QRect(*(round(value * QT_SCALE + _EPS) for value in obj.getRect()))
    if isinstance(obj, int):
        return round(obj * QT_SCALE + _EPS)
    if isinstance(obj, tuple):
        return tuple(scaled(value) for value in obj)
    if isinstance(obj, list):
        return [scaled(value) for value in obj]
    return obj * QT_SCALE
