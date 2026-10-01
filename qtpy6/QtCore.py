"""The binding's QtCore with PySide6's names: Signal, Slot, Property,
SignalInstance, QEnum, ClassInfo, __version__ - and, in the browser, what
Qt-WASM lacks: QProcess, the threads and locks, a nested exec() (qtpy6.web)."""
import sys

from . import PYQT6, _binding
from . import QT_VERSION as _QT_VERSION  # PyQt's QtCore has an integer QT_VERSION

_binding.load(globals(), 'QtCore')

if PYQT6:
    for _pyqt, _pyside in {'pyqtSignal': 'Signal', 'pyqtSlot': 'Slot', 'pyqtProperty': 'Property',
                           'pyqtBoundSignal': 'SignalInstance', 'pyqtEnum': 'QEnum',
                           'pyqtClassInfo': 'ClassInfo'}.items():
        globals()[_pyside] = globals().pop(_pyqt)

    # QTimer.singleShot(msec, receiver, slot): PySide6's three-argument form, whose shot is
    # dropped if receiver is destroyed first. PyQt6 only has (msec, slot) and
    # (msec, timerType, slot): a QTimer child of receiver gives the same service.
    _singleShot = QTimer.singleShot

    def _singleShot_with_receiver(msec, *args):
        if len(args) == 2 and isinstance(args[0], QObject):
            receiver, slot = args
            timer = QTimer(receiver)
            timer.setSingleShot(True)
            timer.timeout.connect(slot)
            timer.timeout.connect(timer.deleteLater)
            timer.start(msec)
        else:
            _singleShot(msec, *args)

    QTimer.singleShot = staticmethod(_singleShot_with_receiver)

if sys.platform == 'emscripten':
    # Qt-WASM has no QProcess (a browser has no processes): a Pyodide Web Worker under its surface.
    from .web.travailleur import ProcessusWeb as QProcess  # noqa: F401
    from .web import sous_processus
    sous_processus.doubler()  # subprocess.run : le même worker, attendu par JSPI
    # One thread, and no nested event loop: cooperative threads, and exec() suspended by JSPI.
    from .web import bloquant, fils
    fils.doubler(globals())
    bloquant.doubler_qtcore(globals())
    fils.doubler_sleep()

__version__ = _QT_VERSION
__version_info__ = tuple(int(part) for part in _QT_VERSION.split('.'))

_binding.finish(globals())
