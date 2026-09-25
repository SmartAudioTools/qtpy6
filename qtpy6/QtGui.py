"""The binding's QtGui, with PySide6's `mode=` keyword on QTextCursor.move_position."""
from . import PYSIDE6, _binding

_binding.load(globals(), 'QtGui')

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

_binding.finish(globals())
