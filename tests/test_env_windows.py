"""The Windows branch of qtpy6._env, on any OS: `_env.py` is executed again with `os.name`
set to 'nt' against fake `nt`, `winreg`, `ctypes.windll` and `setx`. That proves the code
runs and takes the right branches, not that Windows behaves like the fakes."""
import ctypes
import importlib.util
import os
import subprocess
import sys
import types

import pytest

import qtpy6

ENV_PY = os.path.join(os.path.dirname(qtpy6.__file__), '_env.py')


class Registry(types.SimpleNamespace):
    """`winreg` with two roots; a root whose values are None does not exist."""
    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE = 'HKCU', 'HKLM'

    def OpenKey(self, root, path):
        values = {'HKCU': self.hkcu, 'HKLM': self.hklm}[root]
        if values is None:
            raise FileNotFoundError(path)
        return _Context(types.SimpleNamespace(values=values))

    @staticmethod
    def QueryValueEx(key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], 1  # REG_SZ


class _Context:
    def __init__(self, key):
        self.key = key

    def __enter__(self):
        return self.key

    def __exit__(self, *exc):
        pass


@pytest.fixture
def windows(monkeypatch):
    """Loads `_env.py` as on Windows; returns (module, calls) where calls records DPI and setx calls."""
    calls = []

    def load(hkcu=None, hklm=None, shcore='ok'):
        windll = types.SimpleNamespace(user32=types.SimpleNamespace(SetProcessDPIAware=lambda: calls.append('user32')))
        if shcore == 'ok':
            windll.shcore = types.SimpleNamespace(SetProcessDpiAwareness=lambda level: calls.append(('shcore', level)))
        elif shcore == 'fails':
            windll.shcore = types.SimpleNamespace(SetProcessDpiAwareness=lambda level: (_ for _ in ()).throw(OSError()))
        monkeypatch.setattr(ctypes, 'windll', windll, raising=False)
        monkeypatch.setattr(subprocess, 'STARTUPINFO', lambda: types.SimpleNamespace(dwFlags=0), raising=False)
        monkeypatch.setattr(subprocess, 'STARTF_USESHOWWINDOW', 1, raising=False)
        monkeypatch.setattr(subprocess, 'Popen', lambda args, startupinfo: calls.append((args, startupinfo.dwFlags)))
        monkeypatch.setitem(sys.modules, 'winreg', Registry(hkcu=hkcu, hklm=hklm))
        # nt.environ is what the process was started with; QT_FONT is then redefined from Python.
        started_with = {key.upper(): value for key, value in os.environ.items()}
        monkeypatch.setitem(sys.modules, 'nt', types.SimpleNamespace(environ=started_with))
        monkeypatch.setenv('QT_FONT', 'from python')
        spec = importlib.util.spec_from_file_location('qtpy6_env_on_windows', ENV_PY)
        module = importlib.util.module_from_spec(spec)
        with monkeypatch.context() as context:
            context.setattr(os, 'name', 'nt')
            spec.loader.exec_module(module)
        return module, calls
    return load


def test_get_env(windows, monkeypatch):
    env, _ = windows(hkcu={'QT_SCALE': '1.5'}, hklm={'QT_SCALE': '2', 'QT_API': 'PyQt6'})
    assert env.get_env('QT_FONT') == 'from python'  # redefined in this process: wins over the registry
    assert env.get_env('QT_SCALE') == '1.5'  # the user's registry wins over the machine's
    assert env.get_env('QT_API') == 'PyQt6'
    monkeypatch.setenv('QT_FONT_SIZE', 'inherited')  # not in the registry: from the environment
    assert env.get_env('QT_FONT_SIZE') == 'inherited'
    assert env.get_env('QT_NOPE', 'default') == 'default' and env.get_env('QT_NOPE') is None


def test_get_env_without_user_key(windows):
    env, _ = windows(hkcu=None, hklm={'QT_API': 'PySide6'})
    assert env.get_env('QT_API') == 'PySide6'


def test_set_env(windows):
    env, calls = windows()
    env.set_env('QT_SCALE', '2.0')
    assert os.environ['QT_SCALE'] == '2.0'
    assert calls[-1] == (['setx', 'QT_SCALE', '2.0'], subprocess.STARTF_USESHOWWINDOW)  # no console window


@pytest.mark.parametrize('shcore, expected', [('ok', ('shcore', 2)), ('absent', 'user32'), ('fails', 'user32')])
def test_dpi_awareness(windows, shcore, expected):
    _, calls = windows(shcore=shcore)
    assert calls == [expected]
