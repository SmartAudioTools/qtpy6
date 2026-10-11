"""Ce que le Web Worker de ``ProcessusWeb`` exécute avant le programme (``js/travailleur.js`` le charge par son chemin) :
de quoi faire tourner dans le Worker un noyau Jupyter (ipykernel, spyder_kernels) qui parle pyzmq et ``threading`` à la
page. Python pur, sans Qt : ``js`` et ``pyodide`` ne sont importés que dans les fonctions, ce qui laisse les tests natifs
l'importer avec de faux modules.

    installer(dossier_web)   rend ``qtpy6.web.zmq_web`` et ``threading_web`` importables SANS exécuter ``qtpy6/__init__.py``
                             (il importe Qt, absent du Worker : deux paquets factices ``qtpy6`` et ``qtpy6.web`` dont le
                             ``__path__`` est le dossier zippé), pose leurs crochets (``attendre`` suspendu par JSPI,
                             ``plus_tard`` sur la boucle asyncio, ``poster`` vers la page) et les installe ; ``zmq`` et
                             ``threading`` sont alors ceux de qtpy6
    recevoir_page(message)   ce que ``travailleur.js`` appelle pour un ``{zmq}`` reçu de la page
    _vers_python(obj)        octets et conteneurs ramenés à des types Python ordinaires (voir plus bas)"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import types
from typing import Any, Callable


def _vers_python(obj: Any) -> Any:
    """Ce qui traverse ``postMessage`` revient en JsProxy, memoryview (Uint8Array) ou conteneurs : ``bytes`` pour tout
    tampon, ``list`` pour les séquences, ``dict`` pour les objets ; le reste (nombres, str, None) tel quel."""
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return bytes(obj)
    if isinstance(obj, dict):
        return {cle: _vers_python(valeur) for cle, valeur in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_vers_python(valeur) for valeur in obj]
    if isinstance(obj, (set, frozenset)):
        return {_vers_python(valeur) for valeur in obj}
    if hasattr(obj, "to_py"):
        return _vers_python(obj.to_py())
    return obj


def _attendre(condition: Callable[[], bool], delai_ms: int | None) -> bool:
    """Suspend le Python du Worker (JSPI) par pas de 10 ms jusqu'à ``condition()`` ou l'échéance ; la boucle asyncio, donc
    les messages de la page, continue pendant ce temps."""
    from pyodide.ffi import run_sync  # noqa: PLC0415

    fin = None if delai_ms is None or delai_ms < 0 else time.monotonic() + delai_ms / 1000
    while not condition() and (fin is None or time.monotonic() < fin):
        run_sync(asyncio.sleep(0.01))
    return condition()


def _plus_tard(fonction: Callable[[], Any], delai_ms: int = 0) -> None:
    asyncio.get_event_loop().call_later(delai_ms / 1000, fonction)


def _livrer_signaux() -> None:
    """Les signaux envoyés par la page (``Popen.send_signal`` : ``{signal: n}``, gardés dans ``self.signaux`` par
    travailleur.js) : le gestionnaire Python de chacun, appelé ici, dans la pile du programme. Celui de SIGINT, par défaut
    ou posé par ipykernel pendant une exécution, lève ``KeyboardInterrupt``."""
    import js  # noqa: PLC0415
    import signal  # noqa: PLC0415

    signaux = getattr(js, "signaux", None)
    while signaux is not None and signaux.length:
        sig = int(signaux.shift())
        gestionnaire = signal.getsignal(sig)
        if callable(gestionnaire):
            gestionnaire(sig, sys._getframe(1))


def _doubler_sleep() -> None:
    """``time.sleep`` suspend le Worker (JSPI) au lieu de le bloquer : les messages de la page (zmq, signaux) passent
    pendant l'attente, et les signaux reçus sont livrés au réveil (une boucle ``while True: time.sleep(…)`` s'interrompt)."""
    from pyodide.ffi import can_run_sync, run_sync  # noqa: PLC0415

    sleep = time.sleep

    def sleep_(secs: float) -> None:
        if can_run_sync():
            run_sync(asyncio.sleep(secs))
        else:
            sleep(secs)
        _livrer_signaux()

    time.sleep = sleep_


def _poster(destination: Any, message: dict[str, Any]) -> None:
    """Dans le Worker, la seule destination est la page : ``destination`` n'est pas lue."""
    import js  # noqa: PLC0415
    from pyodide.ffi import to_js  # noqa: PLC0415

    js.postMessage(to_js({"zmq": message}, dict_converter=js.Object.fromEntries))


def recevoir_page(message: Any) -> None:
    from qtpy6.web import zmq_web  # noqa: PLC0415

    zmq_web.recevoir(None, _vers_python(message))


def _garde_vie(boucle: asyncio.AbstractEventLoop) -> None:
    """Sur la WebLoop de Pyodide ``run_forever()`` rend la main aussitôt et ``stop()`` ne fait rien : ipykernel
    (``io_loop.start()``) laisserait finir le programme, donc le Worker. ``run_forever`` devient une attente suspendue
    (JSPI) sur un Future que ``stop()`` résout."""
    from pyodide.ffi import run_sync  # noqa: PLC0415

    futur: list[asyncio.Future] = []

    def run_forever() -> None:
        futur[:] = [boucle.create_future()]
        run_sync(futur[0])

    def stop() -> None:
        if futur and not futur[0].done():
            futur[0].set_result(None)

    boucle.run_forever, boucle.stop = run_forever, stop


def installer(dossier_web: str, boucle: asyncio.AbstractEventLoop | None = None) -> None:
    """``dossier_web`` : le dossier ``qtpy6/web`` dépaqueté dans le Worker ; ``boucle`` : celle du Worker (par défaut la
    courante)."""
    import js  # noqa: PLC0415
    from pyodide.ffi import create_proxy  # noqa: PLC0415

    paquet = types.ModuleType("qtpy6")
    paquet.__path__ = [os.path.dirname(dossier_web)]
    web = types.ModuleType("qtpy6.web")
    web.__path__ = [dossier_web]
    sys.modules.update({"qtpy6": paquet, "qtpy6.web": web})
    from qtpy6.web import psutil_web, threading_web, zmq_web  # noqa: PLC0415

    zmq_web.en_travailleur = True
    zmq_web.installer(_attendre, _plus_tard, _poster)
    threading_web.installer(_attendre, _plus_tard)
    threading_web.doubler_futures(_attendre, _plus_tard)  # IPython importe ThreadPoolExecutor, absent de Pyodide
    psutil_web.installer()  # ipykernel l'importe au chargement ; le noyau surveille son parent (JPY_PARENT_PID)
    boucle = boucle or asyncio.get_event_loop()
    threading_web.partager_boucle(boucle)  # les boucles qu'ipykernel crée par fil
    _garde_vie(boucle)
    _doubler_sleep()
    js.zmq_pret(create_proxy(recevoir_page))  # la page a pu écrire avant : travailleur.js vide ce qu'il a gardé
