"""Settings of the desktop session, so that a change made by the QtSelector
widget applies to the next Qt program without logging out: the Windows
registry, or KDE Plasma's ``~/.config/plasma-workspace/env/QtEnvironment.sh``.
"""
import os
import shlex

if os.name == 'nt':
    import ctypes
    import subprocess
    import winreg
    from nt import environ as _nt_environ

    _redefined_in_python = {key for key, value in os.environ.items() if _nt_environ.get(key.upper()) != value}

    def get_env(key, default=None):
        if key in _redefined_in_python:
            return os.environ[key]
        for root, path in ((winreg.HKEY_CURRENT_USER, r'Environment'),
                           (winreg.HKEY_LOCAL_MACHINE, r'System\CurrentControlSet\Control\Session Manager\Environment')):
            try:
                with winreg.OpenKey(root, path) as reg_key:
                    return winreg.QueryValueEx(reg_key, key)[0]
            except FileNotFoundError:
                pass
        return os.environ.get(key, default)

    def set_env(key, value):
        os.environ[key] = value
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(['setx', key, value], startupinfo=info)

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

    def get_env(key, default=None):
        if key in os.environ:
            return os.environ[key]
        for line in _env_file_lines():
            words = shlex.split(line, comments=True)
            if len(words) == 2 and words[0] == 'export' and words[1].startswith(key + '='):
                return words[1][len(key) + 1:]
        return default

    def set_env(key, value):
        os.environ[key] = value
        new_line = f'export {key}={shlex.quote(value)}\n'
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
