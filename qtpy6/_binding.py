"""What turns a binding's module into a qtpy6 module: PySide6's names and
snake_case aliases - and the finder that does it for every Qt module without
a file of its own (``qtpy6.QtNetwork``, ``qtpy6.QtTest``...).
"""
import enum
import functools
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys

from . import API_NAME, PYQT6


def snake_case(name):
    """The name PySide6's ``snake_case`` feature gives to a method (shiboken's
    getSnakeCaseName): unchanged under 3 characters, when it starts with 'gl'
    + capital, or when two capitals touch; else each capital becomes '_' + lower."""
    if len(name) < 3 or (name.startswith('gl') and name[2].isupper()):
        return name
    if any(a.isupper() and b.isupper() for a, b in zip(name, name[1:])):
        return name
    return ''.join('_' + char.lower() if char.isupper() else char for char in name)


def keyword_alias(function, alias, name):
    """`function` also accepting the keyword `alias` for its parameter `name`."""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        if alias in kwargs:
            kwargs[name] = kwargs.pop(alias)
        return function(*args, **kwargs)
    return wrapper


def load(namespace, name):
    """Fill `namespace` (a qtpy6 module's) with the binding's module `name`."""
    source = importlib.import_module(f'{API_NAME}.{name}')
    namespace.update((attr, getattr(source, attr)) for attr in dir(source) if not attr.startswith('_'))


def finish(namespace):
    """The last pass on a qtpy6 module, after its fixes: PySide6's names on every class."""
    for name, obj in list(namespace.items()):
        if isinstance(obj, type) and not name.startswith('_'):
            _pyside6_class(obj)


def _pyside6_class(cls):
    """PySide6's names on `cls`, added to the binding's own: `exec`/`print` for
    `exec_`/`print_`, unscoped enum members (PyQt6 only has scoped ones), and a
    snake_case alias of every camelCase method, static method and signal."""
    members = dict(vars(cls))
    for name, attr in members.items():
        if isinstance(attr, type):
            if not issubclass(attr, enum.Enum):
                _pyside6_class(attr)
            elif PYQT6:
                for member_name, member in attr.__members__.items():
                    if not hasattr(cls, member_name):
                        setattr(cls, member_name, member)
        elif name in ('exec_', 'print_'):
            if name[:-1] not in members:
                setattr(cls, name[:-1], attr)
        elif name[0].islower() and '_' not in name:
            snake = snake_case(name)
            if snake != name and snake not in members:
                setattr(cls, snake, attr)


class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """`qtpy6.QtXxx` for every QtXxx the binding has."""

    def find_spec(self, fullname, path=None, target=None):
        package, _, name = fullname.rpartition('.')
        if package != __package__ or not name.startswith('Qt'):
            return None
        if importlib.util.find_spec(f'{API_NAME}.{name}') is None:
            return None
        return importlib.machinery.ModuleSpec(fullname, self)

    def exec_module(self, module):
        namespace = vars(module)
        load(namespace, module.__name__.rpartition('.')[2])
        finish(namespace)


sys.meta_path.append(_Finder())
