"""Settings of the desktop session, so that a change made by the QtSelector
widget applies to the next Qt program without logging out: the Windows
registry, or KDE Plasma's ``~/.config/plasma-workspace/env/QtEnvironment.sh``.

A program started from the desktop inherits the values of the login, which a later
change does not reach: the session setting wins over them. To tell them from a value
set on purpose (``QT_STYLE=Fusion python app.py``, a launcher, Python code), each
setting is written with a copy, ``QTPY6_LOGIN_<key>``, exported with it: a value that
differs from its copy was set after the login, and wins over the session setting.
"""
import os
import shlex

_LOGIN = 'QTPY6_LOGIN_'


def get_env(key, default=None):
    value = os.environ.get(key)
    if value is not None and value != os.environ.get(_LOGIN + key):
        return value
    session = _session_value(key)
    return session if session is not None else os.environ.get(key, default)


if os.name == 'nt':
    import ctypes
    import subprocess
    import winreg

    def _session_value(key):
        for root, path in ((winreg.HKEY_CURRENT_USER, r'Environment'),
                           (winreg.HKEY_LOCAL_MACHINE, r'System\CurrentControlSet\Control\Session Manager\Environment')):
            try:
                with winreg.OpenKey(root, path) as reg_key:
                    return winreg.QueryValueEx(reg_key, key)[0]
            except FileNotFoundError:
                pass
        return None

    def set_env(key, value):
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        for name in (key, _LOGIN + key):
            os.environ[name] = value
            subprocess.Popen(['setx', name, value], startupinfo=info)

    # Same effect as the "DPI aware" property of pythonw.exe: no blurry window scaling with Qt6.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):  # before Windows 8.1
        ctypes.windll.user32.SetProcessDPIAware()

else:
    _ENV_FILE = os.path.expanduser('~/.config/plasma-workspace/env/QtEnvironment.sh')

    def _env_file_lines():
        try:
            with open(_ENV_FILE) as file:
                return file.readlines()
        except FileNotFoundError:
            return []

    def _session_value(key):
        for line in _env_file_lines():
            words = shlex.split(line, comments=True)
            if len(words) >= 2 and words[0] == 'export' and words[1].startswith(key + '='):
                return words[1][len(key) + 1:]
        return None

    def set_env(key, value):
        os.environ[key] = os.environ[_LOGIN + key] = value
        new_line = f'export {key}={shlex.quote(value)} {_LOGIN}{key}={shlex.quote(value)}\n'
        lines = _env_file_lines()
        for i, line in enumerate(lines):
            if line.startswith(f'export {key}='):
                lines[i] = new_line
                break
        else:
            lines.append(new_line)
        os.makedirs(os.path.dirname(_ENV_FILE), exist_ok=True)
        with open(_ENV_FILE, 'w') as file:
            file.writelines(lines)
