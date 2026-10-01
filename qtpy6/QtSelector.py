"""Widgets that choose, for the whole desktop session, the binding, scale, font
and font size that qtpy6 reads at start-up (QT_API, QT_SCALE, QT_FONT,
QT_FONT_SIZE). Run ``python -m qtpy6.QtSelector`` or ``qtselector``."""
import importlib.util
import os
import sys

from . import API_NAMES, QtGui, QtWidgets, get_env, set_env


class _SettingComboBox(QtWidgets.QComboBox):
    """The session's value of `key` among `choices` (added when unknown), written back on change."""
    key = default = None
    choices = ()

    def __init__(self, parent=None):
        super().__init__(parent)
        choices = list(self.choices)
        current = get_env(self.key, self.default)
        lower = [choice.lower() for choice in choices]
        if current.lower() not in lower:
            choices.append(current)
            lower.append(current.lower())
        self.add_items(choices)
        self.set_max_visible_items(self.count())
        self.set_current_index(lower.index(current.lower()))
        self.current_text_changed.connect(self._write)

    def _write(self, value):
        set_env(self.key, value)


class QtApiSelector(_SettingComboBox):
    key, default = 'QT_API', 'auto'
    choices = ['auto'] + [name for name in API_NAMES.values() if importlib.util.find_spec(name) is not None]


class QtScaleSelector(_SettingComboBox):
    key, default = 'QT_SCALE', 'auto'
    choices = ['auto'] + [str(tenths / 10) for tenths in range(1, 20)] + [str(fifths / 5) for fifths in range(10, 21)]


class QtFontSizeSelector(_SettingComboBox):
    key, default = 'QT_FONT_SIZE', 'default'
    choices = ['default'] + [str(points) for points in range(7, 15)] + [f'{pixels} pixels' for pixels in range(81)]


class QtFontSelector(QtWidgets.QFontComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.insert_item(0, 'default')
        current = get_env('QT_FONT', 'default')
        if self.find_text(current) < 0:
            self.add_item(current)
        self.set_current_text(current)
        self.set_max_visible_items(self.count())
        self.current_text_changed.connect(self._write)

    def _write(self, value):
        set_env('QT_FONT', value)


class QtSelector(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        selectors = (('QT_API', QtApiSelector), ('QT_SCALE', QtScaleSelector),
                     ('QT_FONT', QtFontSelector), ('QT_FONT_SIZE', QtFontSizeSelector))
        for row, (name, selector) in enumerate(selectors):
            layout.add_widget(QtWidgets.QLabel(name), row, 0)
            layout.add_widget(selector(), row, 1)
        layout.set_column_stretch(1, 2)


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    widget = QtSelector()
    widget.set_window_title('Qt Selector')
    widget.set_window_icon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'Qt_selector.svg')))
    widget.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
