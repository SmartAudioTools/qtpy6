"""The binding's QtGui, with PySide6's `mode=` keyword on QTextCursor.move_position
- and, in the browser, a fixed system font that Qt-WASM lacks."""
import sys

from . import PYSIDE6, _binding

_binding.load(globals(), 'QtGui', 'QTextCursor', 'QFontDatabase', 'QFont', 'QGuiApplication')  # names this code uses

if PYSIDE6:
    # PySide calls movePosition's `mode` parameter `arg__2` (PYSIDE-185).
    _move_position = QTextCursor.movePosition  # noqa: F821

    def movePosition(self, operation, mode=QTextCursor.MoveMode.MoveAnchor, n=1):  # noqa: F821
        return _move_position(self, operation, mode, n)

    QTextCursor.movePosition = movePosition  # noqa: F821
else:
    from .QtCore import QObject

    class QPyTextObject(QObject, QTextObjectInterface):  # noqa: F821
        """PySide's ready-made QObject + QTextObjectInterface (its multiple inheritance can't); PyQt's can."""

if sys.platform == 'emscripten':
    # Qt-WASM has no system fonts: the fixed one is the first fixed-pitch family the application
    # loaded (qtpy6.web.application), at the size of the interface's font.
    _application_families = []
    _add_application_font = QFontDatabase.addApplicationFont  # noqa: F821
    _system_font = QFontDatabase.systemFont  # noqa: F821

    def addApplicationFont(file_name):
        font_id = _add_application_font(file_name)
        _application_families.extend(QFontDatabase.applicationFontFamilies(font_id))  # noqa: F821  ([] for -1)
        return font_id

    def systemFont(font_type):
        if font_type == QFontDatabase.SystemFont.FixedFont:  # noqa: F821
            for family in _application_families:
                if QFontDatabase.isFixedPitch(family):  # noqa: F821
                    return QFont(family, QGuiApplication.font().pointSize())  # noqa: F821
        return _system_font(font_type)

    QFontDatabase.addApplicationFont = staticmethod(addApplicationFont)  # noqa: F821
    QFontDatabase.systemFont = staticmethod(systemFont)  # noqa: F821

    from .web.bloquant import doubler_exec_application
    doubler_exec_application(QGuiApplication)  # noqa: F821

_binding.finish(globals())
