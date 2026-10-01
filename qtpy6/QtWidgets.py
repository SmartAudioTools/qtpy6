"""The binding's QtWidgets with PySide6's names (QFileSystemModel included), QFileDialog's `dir` keyword,
the QT_FONT / QT_FONT_SIZE settings applied by QApplication - and, in the browser, the blocking exec() of
dialogs and menus, and their static functions (qtpy6.web.bloquant)."""
import sys

from . import PYQT6, QT_FONT, QT_FONT_SIZE, _binding

_binding.load(globals(), 'QtWidgets')

# QFileSystemModel: in QtWidgets for PySide6 (its Qt5 place), moved to QtGui by PyQt6.
if PYQT6:
    from PyQt6.QtGui import QFileSystemModel  # noqa: F401

if sys.platform == 'emscripten':
    from .web.bloquant import doubler_qtwidgets
    doubler_qtwidgets(globals())

# QFileDialog's static functions: the keyword is `dir` in PySide6, `directory` in PyQt6; both work.
_alias, _name = ('dir', 'directory') if PYQT6 else ('directory', 'dir')
for _function in ('getExistingDirectory', 'getOpenFileName', 'getOpenFileNames', 'getSaveFileName'):
    setattr(QFileDialog, _function,  # noqa: F821
            staticmethod(_binding.keyword_alias(getattr(QFileDialog, _function), _alias, _name)))  # noqa: F821

if QT_FONT != 'default' or QT_FONT_SIZE != 'default':
    _init = QApplication.__init__  # noqa: F821

    def _init_with_font(self, *args, **kwargs):
        _init(self, *args, **kwargs)
        font = self.font()
        if QT_FONT_SIZE.endswith('pixels'):
            font.setPixelSize(int(QT_FONT_SIZE[:-6]))
        elif QT_FONT_SIZE != 'default':
            font.setPointSizeF(float(QT_FONT_SIZE))
        if QT_FONT != 'default':
            font.setFamily(QT_FONT)
        self.setFont(font)

    QApplication.__init__ = _init_with_font  # noqa: F821

_binding.finish(globals())
