"""What qtpy6 does at import, seen from fresh processes: the choice of the
binding, and the session settings applied to QApplication. Every installed
binding is exercised, whatever QT_API the test process itself runs on."""
import importlib.util
import os
import subprocess
import sys
import textwrap

import pytest

import qtpy6
from qtpy6 import API_NAMES

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='the session file is Plasma\'s')

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(qtpy6.__file__)))  # the qtpy6 under test
INSTALLED = [api for api, name in API_NAMES.items() if importlib.util.find_spec(name) is not None]


def run(code, home, *options, **env):
    """`code` in a fresh interpreter whose session file is under `home`: (return code, stdout, stderr)."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith('QT_')}
    environment.update(QT_QPA_PLATFORM='offscreen', HOME=str(home), **env,
                       PYTHONPATH=os.pathsep.join(filter(None, [PACKAGE_DIR, os.environ.get('PYTHONPATH')])))
    result = subprocess.run([sys.executable, *options, '-c', textwrap.dedent(code)],
                            env=environment, capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout.strip(), result.stderr


def session_file(home, **settings):
    path = home / '.config' / 'plasma-workspace' / 'env' / 'QtEnvironment.sh'
    path.parent.mkdir(parents=True)
    path.write_text(''.join(f'export {key}={value}\n' for key, value in settings.items()))


REPORT = '''
    import os, qtpy6
    from qtpy6 import QtCore
    print(qtpy6.API, qtpy6.API_NAME, os.environ['QT_API'], qtpy6.PYSIDE6, qtpy6.PYQT6,
          qtpy6.QT_VERSION == QtCore.qVersion(), qtpy6.PYQT_VERSION is None, qtpy6.PYSIDE_VERSION is None)
'''


def expected(api):
    name = API_NAMES[api]
    return f'{api} {name} {api} {api == "pyside6"} {api == "pyqt6"} True {api != "pyqt6"} {api != "pyside6"}'


@pytest.mark.parametrize('api', INSTALLED)
def test_qt_api_from_environment(api, tmp_path):
    assert run(REPORT, tmp_path, QT_API=api.upper()) == (0, expected(api), '')


@pytest.mark.parametrize('api', INSTALLED)
def test_qt_api_from_session_file(api, tmp_path):
    session_file(tmp_path, QT_API=API_NAMES[api])
    assert run(REPORT, tmp_path)[:2] == (0, expected(api))


def test_first_installed_binding_by_default(tmp_path):
    assert run(REPORT, tmp_path)[:2] == (0, expected(INSTALLED[0]))
    assert run(REPORT, tmp_path, QT_API='auto')[:2] == (0, expected(INSTALLED[0]))


@pytest.mark.parametrize('api', INSTALLED)
def test_already_imported_binding_wins(api, tmp_path):
    other = next((name for name in INSTALLED if name != api), 'auto')
    code = f'\n    import {API_NAMES[api]}.QtCore' + REPORT
    assert run(code, tmp_path, QT_API=other)[:2] == (0, expected(api))


def test_unknown_qt_api(tmp_path):
    returncode, _, stderr = run('import qtpy6', tmp_path, QT_API='pyqt5')
    assert returncode == 1 and "ValueError: QT_API='pyqt5': expected auto or one of pyside6, pyqt6" in stderr


def test_no_binding_installed(tmp_path):
    returncode, _, stderr = run('import qtpy6', tmp_path, '-S')  # no site-packages, so no binding
    assert returncode == 1 and 'QtBindingsNotFoundError: none of PySide6, PyQt6 is installed' in stderr


FONT = '''
    from qtpy6 import QtWidgets
    font = QtWidgets.QApplication([]).font()
    print(font.family(), font.pointSizeF(), font.pixelSize())
'''


@pytest.mark.parametrize('api', INSTALLED)
def test_font_settings(api, tmp_path):
    assert run(FONT, tmp_path, QT_API=api, QT_FONT='DejaVu Sans', QT_FONT_SIZE='13.5') == (0, 'DejaVu Sans 13.5 -1', '')
    assert run(FONT, tmp_path, QT_API=api, QT_FONT_SIZE='20 pixels')[:2] == (0, f'{default_family(api, tmp_path)} -1.0 20')
    session_file(tmp_path, QT_FONT='Serif', QT_FONT_SIZE='"9 PIXELS"')
    assert run(FONT, tmp_path, QT_API=api)[:2] == (0, 'Serif -1.0 9')


def default_family(api, home):
    return run('from qtpy6 import QtWidgets; print(QtWidgets.QApplication([]).font().family())', home, QT_API=api)[1]


SCALE = '''
    import qtpy6
    from qtpy6 import QtWidgets
    app = QtWidgets.QApplication([])
    print(qtpy6.scaled(100), qtpy6.QT_SCALE)
'''


@pytest.mark.parametrize('api', INSTALLED)
def test_scale_setting(api, tmp_path):
    assert run(SCALE, tmp_path, QT_API=api, QT_SCALE='1.5') == (0, '150 1.5', '')
    returncode, out, _ = run(SCALE, tmp_path, QT_API=api, QT_SCALE='AUTO')
    scaled, factor = out.split()
    assert returncode == 0 and int(scaled) > 0 and float(factor) > 0


@pytest.mark.parametrize('api', INSTALLED)
def test_selector_and_demo_start(api, tmp_path):
    code = '''
        import runpy
        from qtpy6 import QtWidgets
        QtWidgets.QApplication.exec = lambda self: 0  # the event loop would never return
        try:
            runpy.run_module('qtpy6.QtSelector', run_name='__main__')  # python -m qtpy6.QtSelector
        except SystemExit as exit:
            assert exit.code == 0
        runpy.run_module('qtpy6.QtSelector_demo', run_name='__main__')
    '''
    returncode, _, stderr = run(code, tmp_path, QT_API=api)
    assert returncode == 0, stderr
