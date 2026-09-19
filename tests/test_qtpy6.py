"""Run with QT_API=pyside6 and with QT_API=pyqt6 (one binding per process)."""
import enum
import importlib.util
import os
import sys

import pytest

import qtpy6
from qtpy6 import QtCore, QtGui, QtWidgets, _binding, _env


# --- snake_case names ---------------------------------------------------------

@pytest.mark.parametrize('name, expected', [
    ('setWindowTitle', 'set_window_title'), ('toUtf8', 'to_utf8'), ('x11Info', 'x11_info'),
    ('addAction', 'add_action'), ('setX', 'set_x'), ('exec', 'exec'), ('ok', 'ok'), ('a', 'a'),
    ('glClear', 'glClear'), ('glBindTexture', 'glBindTexture'), ('isOK', 'isOK'), ('setDPI', 'setDPI'),
    ('toHTML', 'toHTML'), ('x11', 'x11'),
])
def test_snake_case(name, expected):
    assert _binding.snake_case(name) == expected


def test_methods_signals_statics(app):
    combo = QtWidgets.QComboBox()
    combo.add_items(['a', 'b'])
    got = []
    combo.current_index_changed.connect(got.append)
    combo.set_current_index(1)
    assert got == [1] and combo.current_index() == 1
    assert QtCore.QDir.home_path() == QtCore.QDir.homePath()
    assert combo.setCurrentIndex  # camelCase kept: third-party code gets the same objects


def test_alias_follows_override():
    assert vars(QtWidgets.QWidget)['set_parent'] is vars(QtWidgets.QWidget)['setParent']
    assert QtWidgets.QWidget.find_children == QtWidgets.QWidget.findChildren


@pytest.mark.parametrize('module', [QtCore, QtGui, QtWidgets])
def test_every_camel_case_member_has_its_alias(module):
    """Every camelCase method, static method or signal of every class (nested ones included)."""
    def check(cls):
        members = vars(cls)
        for name, attr in members.items():
            if isinstance(attr, type):
                check(attr)
            elif (name[0].islower() and '_' not in name and _binding.snake_case(name) != name
                  and not isinstance(attr, enum.Enum)):  # Qt.darkGray and the like are values, not methods
                assert _binding.snake_case(name) in members, f'{cls.__name__}.{name}'
    for name, obj in vars(module).items():
        if isinstance(obj, type) and not name.startswith('_'):
            check(obj)


# --- PySide6's names ----------------------------------------------------------

def test_qtcore_names():
    for name in ('Signal', 'Slot', 'Property', 'SignalInstance', 'QEnum', 'ClassInfo'):
        assert hasattr(QtCore, name), name
    for name in ('pyqtSignal', 'pyqtSlot', 'pyqtProperty', 'pyqtBoundSignal', 'pyqtEnum', 'pyqtClassInfo'):
        assert not hasattr(QtCore, name), name

    class Emitter(QtCore.QObject):
        fired = QtCore.Signal(int)

        @QtCore.Slot(int)
        def twice(self, value):
            self.fired.emit(2 * value)

    got = []
    emitter = Emitter()
    assert isinstance(emitter.fired, QtCore.SignalInstance)
    emitter.fired.connect(got.append)
    emitter.twice(7)
    assert got == [14]


def test_versions():
    assert qtpy6.QT_VERSION == QtCore.qVersion()
    assert QtCore.__version__ == qtpy6.QT_VERSION
    assert QtCore.__version_info__ == tuple(int(part) for part in qtpy6.QT_VERSION.split('.'))
    assert (qtpy6.PYQT_VERSION is None) == qtpy6.PYSIDE6 and (qtpy6.PYSIDE_VERSION is None) == qtpy6.PYQT6
    assert qtpy6.API_NAME == qtpy6.API_NAMES[qtpy6.API] and os.environ['QT_API'] == qtpy6.API
    assert qtpy6.PYSIDE6 != qtpy6.PYQT6


def test_enums_scoped_and_unscoped():
    assert QtCore.Qt.AlignmentFlag.AlignLeft == QtCore.Qt.AlignLeft
    assert QtCore.Qt.AlignmentFlag.AlignCenter == QtCore.Qt.AlignCenter
    assert QtCore.QEvent.Type.MouseButtonPress == QtCore.QEvent.MouseButtonPress
    assert QtGui.QFont.Weight.Bold == QtGui.QFont.Bold
    assert QtWidgets.QDialog.DialogCode.Accepted == QtWidgets.QDialog.Accepted
    assert QtWidgets.QMessageBox.StandardButton.Ok == QtWidgets.QMessageBox.Ok


def test_exec_and_print(app):
    for cls in (QtWidgets.QApplication, QtWidgets.QDialog, QtWidgets.QMenu, QtGui.QDrag,
                QtCore.QEventLoop, QtCore.QThread):
        assert hasattr(cls, 'exec'), cls
    for cls in (QtGui.QTextDocument, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit):
        assert hasattr(cls, 'print'), cls
    loop = QtCore.QEventLoop()
    QtCore.QTimer.single_shot(0, loop.quit)
    assert loop.exec() == 0


def test_single_shot_with_receiver(app):
    """QTimer.singleShot(msec, receiver, slot), PySide6's three-argument form: the shot
    is dropped if receiver is destroyed first. PyQt6 lacks it natively."""
    fired = []
    alive = QtCore.QObject()
    QtCore.QTimer.singleShot(0, alive, lambda: fired.append('alive'))
    dead = QtCore.QObject()
    QtCore.QTimer.single_shot(0, dead, lambda: fired.append('dead'))
    if qtpy6.PYQT6:
        from PyQt6 import sip
        sip.delete(dead)
    else:
        import shiboken6
        shiboken6.delete(dead)
    for _ in range(10):
        app.processEvents()
    assert fired == ['alive']


def test_event_positions():
    event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, QtCore.QPointF(3, 4), QtCore.QPointF(13, 14),
                              QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton,
                              QtCore.Qt.KeyboardModifier.NoModifier)
    assert event.position() == QtCore.QPointF(3, 4)
    assert event.global_position() == QtCore.QPointF(13, 14)


def test_move_position_keywords():
    document = QtGui.QTextDocument('hello world')
    cursor = QtGui.QTextCursor(document)
    assert cursor.move_position(QtGui.QTextCursor.MoveOperation.Right, mode=QtGui.QTextCursor.MoveMode.KeepAnchor, n=5)
    assert cursor.selected_text() == 'hello'
    assert cursor.movePosition(QtGui.QTextCursor.MoveOperation.End, QtGui.QTextCursor.MoveMode.MoveAnchor)
    assert cursor.position() == 11 and not cursor.has_selection()


def test_filedialog_dir_keyword():
    function = _binding.keyword_alias(lambda **kwargs: kwargs, 'dir', 'directory')
    assert function(dir='x') == {'directory': 'x'} and function(directory='y') == {'directory': 'y'}
    for camel in ('getOpenFileName', 'getOpenFileNames', 'getSaveFileName', 'getExistingDirectory'):
        wrapped = getattr(QtWidgets.QFileDialog, camel).__wrapped__  # the binding's function, under both names
        assert getattr(QtWidgets.QFileDialog, _binding.snake_case(camel)).__wrapped__ is wrapped



def test_file_system_model_in_qtwidgets():
    """PySide6 keeps QFileSystemModel in QtWidgets; PyQt6 moved it to QtGui."""
    assert QtWidgets.QFileSystemModel.__name__ == 'QFileSystemModel'
    assert hasattr(QtWidgets.QFileSystemModel, 'set_root_path')
# --- modules ------------------------------------------------------------------

def test_any_binding_module_is_served():
    from qtpy6 import QtNetwork
    import qtpy6.QtTest
    assert QtNetwork.QNetworkRequest.set_header and qtpy6.QtTest.QTest.mouse_click
    assert QtNetwork is sys.modules['qtpy6.QtNetwork']
    assert qtpy6.QtTest.QTest.mouseClick == qtpy6.QtTest.QTest.mouse_click
    with pytest.raises(ModuleNotFoundError):
        import qtpy6.QtNope  # noqa: F401
    with pytest.raises(ModuleNotFoundError):
        import qtpy6.nope  # noqa: F401
    assert importlib.util.find_spec('qtpy6.QtSvgWidgets') is not None
    assert importlib.util.find_spec('qtpy6.QtNope') is None


def test_module_without_its_library():
    """A module the binding ships but cannot load (PyQt6 wheels: QtStateMachine) raises the binding's error."""
    try:
        from qtpy6 import QtStateMachine
    except ImportError as error:
        assert 'StateMachine' in str(error)
    else:
        assert QtStateMachine.QStateMachine.add_state


def test_select_api(monkeypatch):
    names = qtpy6.API_NAMES
    monkeypatch.setattr(qtpy6, 'API_NAMES', {'fake': 'NoSuchBinding_'})
    monkeypatch.setenv('QT_API', 'fake')
    assert qtpy6._select_api() == 'fake'
    monkeypatch.setenv('QT_API', 'AUTO')
    with pytest.raises(qtpy6.QtBindingsNotFoundError, match='none of NoSuchBinding_ is installed'):
        qtpy6._select_api()
    monkeypatch.setenv('QT_API', 'pyqt5')
    with pytest.raises(ValueError, match="QT_API='pyqt5': expected auto or one of fake"):
        qtpy6._select_api()
    monkeypatch.setattr(qtpy6, 'API_NAMES', names)
    assert qtpy6._select_api() == qtpy6.API  # the binding already imported wins over QT_API


# --- session settings ---------------------------------------------------------

def test_scaled(app, monkeypatch):
    monkeypatch.setattr(qtpy6, 'QT_SCALE', 2.0)
    assert qtpy6.scaled(3) == 6 and qtpy6.scaled(1, 2) == (2, 4) and qtpy6.scaled([1.5]) == [3.0]
    assert qtpy6.scaled(0.5) == 1.0 and qtpy6.scaled((1, [2])) == (2, [4])
    assert qtpy6.scaled(QtCore.QRect(1, 2, 3, 4)) == QtCore.QRect(2, 4, 6, 8)
    assert qtpy6.scaled(QtCore.QSize(1, 2)) == QtCore.QSize(2, 4)
    assert qtpy6.scaled(QtCore.QMargins(1, 2, 3, 4)) == QtCore.QMargins(2, 4, 6, 8)
    monkeypatch.setattr(qtpy6, 'QT_SCALE', 1.5)
    assert qtpy6.scaled(1) == 2 and qtpy6.scaled(QtCore.QRect(1, 1, 1, 1)) == QtCore.QRect(2, 2, 2, 2)
    monkeypatch.setattr(qtpy6, 'QT_SCALE', 1.0)
    assert qtpy6.scaled(QtCore.QSize(1, 2)) == QtCore.QSize(1, 2)
    monkeypatch.setattr(qtpy6, 'QT_SCALE', None)
    assert qtpy6.scaled(100) > 0 and qtpy6.QT_SCALE is not None


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / 'env' / 'QtEnvironment.sh'
    monkeypatch.setattr(_env, '_ENV_FILE', str(path))
    for key in ('QT_API', 'QT_SCALE', 'QT_FONT', 'QT_FONT_SIZE'):
        monkeypatch.delenv(key, raising=False)
    return path


@pytest.mark.skipif(os.name == 'nt', reason='the registry is not a file')
def test_env_file(env_file, monkeypatch):
    assert qtpy6.get_env('QT_FONT', 'default') == 'default'
    qtpy6.set_env('QT_FONT', 'DejaVu Sans')
    qtpy6.set_env('QT_SCALE', '1.5')
    qtpy6.set_env('QT_FONT', 'Noto Sans')
    assert os.environ['QT_FONT'] == 'Noto Sans' and qtpy6.get_env('QT_FONT') == 'Noto Sans'
    monkeypatch.delenv('QT_FONT')
    assert qtpy6.get_env('QT_FONT') == 'Noto Sans'
    assert env_file.read_text() == "export QT_FONT='Noto Sans'\nexport QT_SCALE=1.5\n"
    monkeypatch.setenv('QT_FONT', 'Serif')
    assert qtpy6.get_env('QT_FONT') == 'Serif'  # the environment comes first


@pytest.mark.skipif(os.name == 'nt', reason='the registry is not a file')
def test_env_file_written_by_hand(env_file):
    env_file.parent.mkdir()
    env_file.write_text('# Qt\n\nexport QT_FONT_SIZE=12  # points\nexport QT_FONT="Noto Sans"\n'
                        'QT_SCALE=2\nexport OTHER=x=y\nexport QT_API=\n')
    assert qtpy6.get_env('QT_FONT') == 'Noto Sans'  # not the QT_FONT_SIZE line
    assert qtpy6.get_env('QT_FONT_SIZE') == '12'
    assert qtpy6.get_env('QT_SCALE', 'auto') == 'auto'  # no `export`
    assert qtpy6.get_env('OTHER') == 'x=y' and qtpy6.get_env('QT_API') == ''
    qtpy6.set_env('QT_FONT', 'a"b')
    assert env_file.read_text() == '# Qt\n\nexport QT_FONT_SIZE=12  # points\nexport QT_FONT=\'a"b\'\n' \
                                   'QT_SCALE=2\nexport OTHER=x=y\nexport QT_API=\n'
    assert qtpy6.get_env('QT_FONT') == 'a"b'


# --- QtSelector ---------------------------------------------------------------

@pytest.mark.skipif(os.name == 'nt', reason='the registry is not a file')
def test_selector(app, env_file):
    from qtpy6.QtSelector import QtSelector
    widget = QtSelector()
    combos = widget.find_children(QtWidgets.QComboBox)
    assert [combo.current_text() for combo in combos] == ['auto', 'auto', 'default', 'default']
    combos[1].set_current_text('2.0')
    assert qtpy6.get_env('QT_SCALE') == '2.0' and 'QT_SCALE=2.0' in env_file.read_text()
    combos[3].set_current_text('80 pixels')
    assert qtpy6.get_env('QT_FONT_SIZE') == '80 pixels'


@pytest.mark.skipif(os.name == 'nt', reason='the registry is not a file')
def test_selector_choices(app, env_file):
    from qtpy6 import QtSelector
    assert QtSelector.QtApiSelector.choices == ['auto'] + [name for name in qtpy6.API_NAMES.values()
                                                           if importlib.util.find_spec(name) is not None]
    qtpy6.set_env('QT_API', qtpy6.API_NAME.upper())  # a known value, in another case
    qtpy6.set_env('QT_SCALE', '3.7')  # an unknown value: added to the list
    qtpy6.set_env('QT_FONT', 'No Such Family')
    api, scale, font = QtSelector.QtApiSelector(), QtSelector.QtScaleSelector(), QtSelector.QtFontSelector()
    assert api.current_text() == qtpy6.API_NAME and api.count() == len(QtSelector.QtApiSelector.choices)
    assert scale.current_text() == '3.7' and scale.count() == len(QtSelector.QtScaleSelector.choices) + 1
    assert font.current_text() == 'No Such Family' and font.item_text(0) == 'default'
    font.set_current_text('default')
    assert qtpy6.get_env('QT_FONT') == 'default'


def test_selector_main(app, env_file, monkeypatch):
    from qtpy6 import QtSelector
    shown = []
    monkeypatch.setattr(QtWidgets.QApplication, 'exec',
                        lambda self: shown.extend(w for w in self.top_level_widgets() if w.is_visible()) or 0)
    assert QtSelector.main() == 0
    assert [w.window_title() for w in shown] == ['Qt Selector'] and not shown[0].window_icon().is_null()
