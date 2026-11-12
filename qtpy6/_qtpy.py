"""``qtpy`` served by qtpy6: ``import qtpy.QtWidgets`` gives qtpy6.QtWidgets (its doublures in the browser, its names),
plus what qtpy adds over Qt6 for code written for Qt5 too - Spyder, qtconsole, qtawesome, superqt (12/11/2026, the
user: « fais dans un premier temps l'alias qtpy dans qtpy6 »). The real qtpy package is then never imported.

    installer()   puts the finder first on sys.meta_path; idempotent. Refused (RuntimeError) once the real qtpy is
                  imported: two qtpy in one process would split the classes' patches and the binding choice.

The Qt6 shims below are those of qtpy 2.4 (MIT, the Spyder Development Team: QtCore.py, QtGui.py, QtWidgets.py,
compat.py, _utils.py), PySide6 and PyQt6 branches only; qtpy applies them to the binding's classes at import, so do we,
once, at the first ``qtpy.Qt*`` import. Not served: ``qtpy.uic`` (no user found in Spyder and its dependencies, 12/11),
``enums_compat.promote_enums`` for PyQt6 (short enum names)."""
import importlib
import importlib.abc
import importlib.machinery
import sys
import types

__version__ = '2.4.3'  # the qtpy release whose API this serves (Spyder 6.1 asks qtpy >= 2.4)


def installer():
    if any(isinstance(f, _Chercheur) for f in sys.meta_path):
        return
    if 'qtpy' in sys.modules:
        raise RuntimeError('qtpy is already imported: install the qtpy6 alias before the first import of qtpy')
    sys.meta_path.insert(0, _Chercheur())


class _Chercheur(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'qtpy' or fullname.startswith('qtpy.'):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=fullname == 'qtpy')
        return None

    def create_module(self, spec):
        return _paquet() if spec.name == 'qtpy' else _sous_module(spec.name.partition('.')[2])

    def exec_module(self, module):
        pass


# --- qtpy -------------------------------------------------------------------------------------------------------------

class PythonQtError(RuntimeError):
    """Generic error superclass for QtPy."""


class PythonQtWarning(RuntimeWarning):
    """Warning class for QtPy."""


class PythonQtValueError(ValueError):
    """Error raised if an invalid QT_API is specified."""


class QtModuleNotFoundError(ModuleNotFoundError, PythonQtError):
    def __init__(self, *, name, msg=None, **msg_kwargs):
        super().__init__(msg or f'The {name} module was not found.', name=name)


class QtModuleNotInOSError(QtModuleNotFoundError):
    pass


class QtModuleNotInQtVersionError(QtModuleNotFoundError):
    pass


class QtBindingMissingModuleError(QtModuleNotFoundError):
    pass


class QtModuleNotInstalledError(QtModuleNotFoundError):
    def __init__(self, *, name, missing_package=None, **kwargs):
        super().__init__(name=name, msg=f'The {name} module was not found. It must be installed separately as '
                                        f'{missing_package}.' if missing_package else None)


def _paquet():
    import qtpy6
    m = types.ModuleType('qtpy', __doc__)
    m.__path__ = []
    m.__file__ = __file__  # Spyder (programs.is_module_installed) juge « NOK » un module sans __file__
    m.__version__ = __version__
    m.__dict__.update(
        API=qtpy6.API, API_NAME=qtpy6.API_NAME, QT_VERSION=qtpy6.QT_VERSION, PYQT_VERSION=qtpy6.PYQT_VERSION,
        PYSIDE_VERSION=qtpy6.PYSIDE_VERSION, PYQT6=qtpy6.PYQT6, PYSIDE6=qtpy6.PYSIDE6, QT6=True,
        PYQT4=False, PYQT5=False, PYSIDE=False, PYSIDE2=False, QT4=False, QT5=False,
        QT_API='QT_API', API_NAMES=qtpy6.API_NAMES, PYQT5_API=['pyqt5'], PYQT6_API=['pyqt6'],
        PYSIDE2_API=['pyside2'], PYSIDE6_API=['pyside6'], QT6_VERSION_MIN='6.2.0', QtBindingsNotFoundError=qtpy6.QtBindingsNotFoundError,
        PythonQtError=PythonQtError, PythonQtWarning=PythonQtWarning, PythonQtValueError=PythonQtValueError,
        QtModuleNotFoundError=QtModuleNotFoundError, QtModuleNotInOSError=QtModuleNotInOSError,
        QtModuleNotInQtVersionError=QtModuleNotInQtVersionError, QtBindingMissingModuleError=QtBindingMissingModuleError,
        QtModuleNotInstalledError=QtModuleNotInstalledError, scaled=qtpy6.scaled)
    return m


# --- qtpy.QtXxx -------------------------------------------------------------------------------------------------------

# Names qtpy moves between modules for Qt5-era code: QAction lived in QtWidgets, QFileSystemModel in QtGui.
_DEPLACES = {'QtWidgets': ('QtGui', ('QAction', 'QActionGroup', 'QShortcut', 'QUndoCommand', 'QFileSystemModel')),
             'QtGui': ('QtWidgets', ('QFileSystemModel',)),
             'QtWebEngineWidgets': ('QtWebEngineCore', ('QWebEnginePage', 'QWebEngineSettings', 'QWebEngineProfile',
                                                        'QWebEngineScript'))}


def _sous_module(nom):
    if nom == 'compat':
        return _compat()
    if nom in ('shiboken', 'sip'):
        source = importlib.import_module('shiboken6' if nom == 'shiboken' else 'PyQt6.sip')
    else:
        source = importlib.import_module(f'qtpy6.{nom}')  # ModuleNotFoundError for a module the binding lacks
        _corriger()
    m = types.ModuleType(f'qtpy.{nom}', source.__doc__)
    m.__dict__.update((n, v) for n, v in vars(source).items() if not n.startswith('__'))
    if nom in _DEPLACES:
        autre, noms = _DEPLACES[nom]
        try:
            autre = importlib.import_module(f'qtpy6.{autre}')
        except ImportError:
            autre = None
        for n in noms:
            if autre is not None and hasattr(autre, n):
                m.__dict__.setdefault(n, getattr(autre, n))
    if nom == 'QtWebEngineWidgets':
        m.WEBENGINE = True

    def __getattr__(n):  # names qtpy6 serves on demand (lazy mode, PEP 562)
        return getattr(source, n)

    m.__getattr__ = __getattr__
    m.__all__ = [n for n in dir(source) if not n.startswith('_')]
    return m


def _possibly_static_exec(cls, *args, **kwargs):
    """``self.exec`` when ``self`` is given, the static ``exec`` otherwise (qtpy's _utils)."""
    if not args and not kwargs:
        return cls.exec()
    if isinstance(args[0], cls):
        return args[0].exec(*args[1:], **kwargs)
    return cls.exec(*args, **kwargs)


_CORRIGE = []


def _corriger():
    """qtpy's patches of the binding's classes, Qt6 branches, applied once."""
    if _CORRIGE:
        return
    import qtpy6
    from qtpy6 import QtCore, QtGui, QtWidgets

    Qt = QtCore.Qt
    Qt.BackgroundColorRole = Qt.ItemDataRole.BackgroundColorRole = Qt.BackgroundRole
    Qt.TextColorRole = Qt.ItemDataRole.TextColorRole = Qt.ForegroundRole
    Qt.MidButton = Qt.MiddleButton
    if getattr(Qt, 'mightBeRichText', None) is None and hasattr(QtGui.Qt, 'mightBeRichText'):
        Qt.mightBeRichText = QtGui.Qt.mightBeRichText
    for cls in (QtCore.QCoreApplication, QtGui.QGuiApplication, QtWidgets.QApplication, QtWidgets.QMenu):
        cls.exec_ = (lambda c: lambda *a, **k: _possibly_static_exec(c, *a, **k))(cls)
    for cls in (QtCore.QEventLoop, QtCore.QThread, QtGui.QDrag, QtWidgets.QDialog):
        cls.exec_ = lambda self, *a, **k: self.exec(*a, **k)
    if qtpy6.PYSIDE6:
        QtCore.QTextStreamManipulator.exec_ = lambda self, *a, **k: self.exec(*a, **k)
        QtCore.QDate.toPyDate = lambda self, *a, **k: self.toPython(*a, **k)
        QtCore.QDateTime.toPyDateTime = lambda self, *a, **k: self.toPython(*a, **k)
        QtCore.QTime.toPyTime = lambda self, *a, **k: self.toPython(*a, **k)
    else:
        QtCore.QDate.toPython = lambda self, *a, **k: self.toPyDate(*a, **k)
        QtCore.QDateTime.toPython = lambda self, *a, **k: self.toPyDateTime(*a, **k)
        QtCore.QTime.toPython = lambda self, *a, **k: self.toPyTime(*a, **k)
        QtWidgets.QTextEdit.print_ = lambda self, *a, **k: self.print(*a, **k)
        QtWidgets.QPlainTextEdit.print_ = lambda self, *a, **k: self.print(*a, **k)
    QtCore.QLibraryInfo.location = QtCore.QLibraryInfo.path
    QtCore.QLibraryInfo.LibraryLocation = QtCore.QLibraryInfo.LibraryPath

    QtGui.QFontMetrics.width = lambda self, *a, **k: self.horizontalAdvance(*a, **k)
    QtGui.QFontMetricsF.width = lambda self, *a, **k: self.horizontalAdvance(*a, **k)
    for cls in (QtGui.QNativeGestureEvent, QtGui.QEnterEvent, QtGui.QTabletEvent, QtGui.QHoverEvent,
                QtGui.QMouseEvent):
        for obsolete in ('pos', 'x', 'y', 'globalPos', 'globalX', 'globalY'):
            if obsolete in cls.__dict__:
                try:
                    delattr(cls, obsolete)
                except (AttributeError, TypeError):
                    pass
    e = QtGui.QSinglePointEvent
    e.pos = lambda self: self.position().toPoint()
    e.posF = lambda self: self.position()
    e.localPos = lambda self: self.position()
    e.x = lambda self: self.position().toPoint().x()
    e.y = lambda self: self.position().toPoint().y()
    e.globalPos = lambda self: self.globalPosition().toPoint()
    e.globalX = lambda self: self.globalPosition().toPoint().x()
    e.globalY = lambda self: self.globalPosition().toPoint().y()

    for cls in (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit):
        cls.setTabStopWidth = lambda self, *a, **k: self.setTabStopDistance(*a, **k)
        cls.tabStopWidth = lambda self, *a, **k: self.tabStopDistance(*a, **k)
    QtWidgets.QLineEdit.getTextMargins = lambda self: (
        self.textMargins().left(), self.textMargins().top(), self.textMargins().right(), self.textMargins().bottom())
    # QFileDialog : `dir`/`directory` déjà acceptés tous deux par qtpy6.QtWidgets (keyword_alias).
    _CORRIGE.append(True)  # après les correctifs : un échec en route se répète au prochain import, pas en silence


# --- qtpy.compat ------------------------------------------------------------------------------------------------------

def _compat():
    from qtpy6 import PYSIDE6, QtWidgets

    QFileDialog = QtWidgets.QFileDialog
    m = types.ModuleType('qtpy.compat', 'qtpy.compat served by qtpy6: the QFileDialog wrappers Spyder calls.')

    def appel(attr, parent=None, caption='', basedir='', filters='', selectedfilter='', options=None):
        if options is None:
            options = QFileDialog.Option(0)
        return tuple(getattr(QFileDialog, attr)(parent, caption, basedir, filters, selectedfilter, options))

    def isalive(obj):
        if PYSIDE6:
            import shiboken6
            return shiboken6.isValid(obj)
        from PyQt6 import sip
        return not sip.isdeleted(obj)

    m.__dict__.update(
        TEXT_TYPES=(str,), PYQT_API_1=False, isalive=isalive,
        is_text_string=lambda obj: isinstance(obj, str),
        to_text_string=lambda obj, encoding=None: str(obj) if encoding is None or isinstance(obj, str)
        else str(obj, encoding),
        to_qvariant=lambda obj=None: obj, from_qvariant=lambda qobj=None, pytype=None: qobj,
        getexistingdirectory=lambda parent=None, caption='', basedir='', options=QFileDialog.Option.ShowDirsOnly:
        QFileDialog.getExistingDirectory(parent, caption, basedir, options),
        getopenfilename=lambda *a, **k: appel('getOpenFileName', *a, **k),
        getopenfilenames=lambda *a, **k: appel('getOpenFileNames', *a, **k),
        getsavefilename=lambda *a, **k: appel('getSaveFileName', *a, **k))
    return m
