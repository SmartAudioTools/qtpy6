"""What turns a binding's module into a qtpy6 module: PySide6's names and
snake_case aliases - and the finder that does it for every Qt module without
a file of its own (``qtpy6.QtNetwork``, ``qtpy6.QtTest``...).

Two modes. Eager: every class of the module gets its names at import (≈250 ms
in the browser, 680 classes). Lazy, with our PySide6 build for WebAssembly
only: a class gets them the moment shiboken creates it - its ``Shiboken.setTypeCreationHook``
(wasm/patches/pyside-shiboken-crochet-type.patch) calls `_pyside6_class` on
every type, including the ones no code ever named (events, style options
coming back from Qt) - and the qtpy6 module serves its names on demand
(PEP 562). PySide6 as shipped has no such hook, and PyQt6's sip types are
immutable: both stay eager.
"""
import enum
import functools
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import re
import string
import sys

from . import API_NAME, PYQT6, PYSIDE6

if PYSIDE6:
    from shiboken6 import Shiboken as _Shiboken
    LAZY = hasattr(_Shiboken, 'setTypeCreationHook')
else:
    LAZY = False

_TWO_CAPITALS = re.compile('[A-Z]{2}').search
_SNAKE = str.maketrans({letter: '_' + letter.lower() for letter in string.ascii_uppercase})


@functools.lru_cache(maxsize=None)  # 12,800 methods share 6,500 names
def snake_case(name):
    """The name PySide6's ``snake_case`` feature gives to a method (shiboken's
    getSnakeCaseName): unchanged under 3 characters, when it starts with 'gl'
    + capital, or when two capitals touch; else each capital becomes '_' + lower."""
    if name.islower() or len(name) < 3 or _TWO_CAPITALS(name) or (name[:2] == 'gl' and name[2].isupper()):
        return name
    return name.translate(_SNAKE)


def keyword_alias(function, alias, name):
    """`function` also accepting the keyword `alias` for its parameter `name`."""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        if alias in kwargs:
            kwargs[name] = kwargs.pop(alias)
        return function(*args, **kwargs)
    return wrapper


def _names(namespace, source):
    # A lazy shiboken module also lists its nested types not yet created ('QCalendar.YearMonthDay').
    return {*namespace, *(attr for attr in dir(source) if attr.isidentifier())}


def load(namespace, name, *needed):
    """Fill `namespace` (a qtpy6 module's) with the binding's module `name`.
    In lazy mode only `needed` - the names the qtpy6 module's own code uses
    before it exists - come now; everything else comes at first use."""
    source = importlib.import_module(f'{API_NAME}.{name}')
    if not LAZY:
        namespace.update((attr, getattr(source, attr)) for attr in dir(source) if not attr.startswith('_'))
        return

    def __getattr__(attr):
        if attr == '__all__':  # `from qtpy6.QtXxx import *`: what eager mode's namespace would hold
            return [public for public in _names(namespace, source) if not public.startswith('_')]
        if attr.startswith('_') or not hasattr(source, attr):
            raise AttributeError(f"module {namespace['__name__']!r} has no attribute {attr!r}")
        value = getattr(source, attr)
        if isinstance(value, type):
            _pyside6_class(value)  # created before the hook was set, if ever: done once anyway
        namespace[attr] = value
        return value

    def __dir__():
        return sorted(_names(namespace, source))

    namespace.update(__getattr__=__getattr__, __dir__=__dir__)
    for attr in needed:
        __getattr__(attr)


def finish(namespace):
    """The last pass on a qtpy6 module, after its fixes: PySide6's names on every class."""
    for name, obj in list(namespace.items()):
        if isinstance(obj, type) and not name.startswith('_'):
            _pyside6_class(obj)


_prepared = set()
_BINDING = {API_NAME, 'shiboken6', 'Shiboken', 'builtins'}


class _Alias:
    """A snake_case alias that gives way to the application: the name defined
    by a Python class of the instance's MRO placed after the Qt class (a mixin
    listed after its Qt base: Spyder's BaseEditMixin.move_cursor), then what a
    Python ``__getattr__`` gives (a delegating proxy: Spyder's FrameWebView ->
    its WebView's set_font) - what the name would be without qtpy6 - and only
    else the Qt method. A plain class attribute would mask both."""
    __slots__ = ('qt', 'name', 'plain')

    def __init__(self, qt, name):
        self.qt, self.name, self.plain = qt, name, set()  # plain: the classes where only Qt has the name

    def __get__(self, obj, owner=None):
        owner = type(obj) if owner is None else owner
        if owner not in self.plain:
            python = [c for c in owner.__mro__ if c.__module__.partition('.')[0] not in _BINDING]
            for c in python:
                found = vars(c).get(self.name, self)
                if not isinstance(found, _Alias):  # a doublure (Python class) carries aliases too: skipped
                    return found.__get__(obj, owner) if hasattr(found, '__get__') else found
            if any('__getattr__' in vars(c) for c in python):
                if obj is not None:
                    try:
                        return owner.__getattr__(obj, self.name)
                    except AttributeError:
                        pass
            else:
                self.plain.add(owner)  # measured: 1.9 µs per access without it, 0.15 for the camelCase name
        return self.qt.__get__(obj, owner) if hasattr(self.qt, '__get__') else self.qt


def _pyside6_class(cls):
    """PySide6's names on `cls`, added to the binding's own: `exec`/`print` for
    `exec_`/`print_`, unscoped enum members (PyQt6 only has scoped ones), and a
    snake_case alias of every camelCase method, static method and signal.
    Done once per class: in lazy mode shiboken calls this for every type it creates."""
    if cls in _prepared:
        return
    _prepared.add(cls)
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
                signal = type(attr).__name__ in ('Signal', 'pyqtSignal')  # connected by its object: kept as is
                setattr(cls, snake, attr if signal else _Alias(attr, snake))


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
if LAZY:
    _Shiboken.setTypeCreationHook(_pyside6_class)
