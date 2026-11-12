"""Item 18 du TODO Portage (W560, 12/11/2026) : « Exécuter » reste sur « Récupération des variables d'environnement… ».
La console de Spyder attend ``get_user_environment_variables()`` (``spyder/utils/environ.py:101``, coroutine sous
``@AsyncDispatcher``) puis ``_connect_new_client_to_kernel`` par ``future.connect(AsyncDispatcher.QtSlot(...))``.
Cet essai fait ce seul appel, comme ``ipythonconsole/widgets/main_widget.py:1999``, et dit où il s'arrête.
``site/index.html?script=env18.py`` ; sur le bureau : ``$P env18.py``.

Instrumentation d'essai : les ``print`` (« env18 … ») et ``js.window.etat`` sont lus par la sonde, pas du code
d'application."""

import os
import sys
import time

from preparer import ICI, T0

if sys.platform == "emscripten":  # spyder/locale est hors de l'archive ; Spyder ne fait que le lister
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
    import js
    js.window.etat = "env18"
from qtpy.QtCore import QTimer  # noqa: E402
from qtpy.QtWidgets import QApplication  # noqa: E402


def note(texte):
    print(f"env18 {time.monotonic() - T0:7.2f}s {texte}", flush=True)


def finir(etat):
    note(f"FIN {etat}")
    if sys.platform == "emscripten":
        js.window.etat = "fini"
    else:
        QApplication.instance().quit()


app = QApplication.instance() or QApplication(sys.argv)
from spyder.api.asyncdispatcher import AsyncDispatcher  # noqa: E402
from spyder.utils import environ, programs  # noqa: E402

_shell = environ.run_shell_command


def run_shell_command(*args, **kwargs):  # instrumentation : l'appel et son retour
    note(f"run_shell_command({args[0][:60]!r}, {kwargs})")
    r = _shell(*args, **kwargs)
    note(f"run_shell_command -> {type(r).__name__}")
    return r


environ.run_shell_command = run_shell_command
note("imports faits")
import psutil  # noqa: E402
try:
    note(f"psutil terminal() = {psutil.Process(os.getpid()).terminal()!r}")
except Exception as e:  # noqa: BLE001
    note(f"psutil terminal() CASSE {type(e).__name__}: {e}")

future = environ.get_user_environment_variables()
note(f"future rendu : {type(future).__name__}, done={future.done()}")


def recu(f):
    try:
        note(f"QtSlot appelé : {len(f.result())} variables")
        finir("ok")
    except Exception as e:  # noqa: BLE001
        note(f"QtSlot appelé, résultat CASSE {type(e).__name__}: {e}")
        finir("casse")


future.connect(AsyncDispatcher.QtSlot(recu))
debut = time.monotonic()


def veiller():
    note(f"veille : done={future.done()}")
    if time.monotonic() - debut > 40:
        finir("délai : QtSlot jamais appelé")


minuterie = QTimer()
minuterie.timeout.connect(veiller)
minuterie.start(2000)
if sys.platform != "emscripten":
    app.exec()
