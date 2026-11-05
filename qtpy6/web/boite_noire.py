"""La boîte noire de la page (``qtpy6web.js``, ``ouvrir_boite_noire``) vue de Python : ce que la page a vécu, gardé dans
localStorage à chaque seconde, pour diagnostiquer après coup un gel qu'on n'a pu quitter qu'en rechargeant la page
(demande de l'utilisateur, 06/11/2026, gels du lecteur de SmartTeacher chez les élèves).

La page la tient seule (journal, erreurs JS, onglet, plein écran, fil bloqué) ; ``demarrer`` y ajoute le battement de la
boucle de Qt, qui distingue une page bloquée d'une boucle de Qt arrêtée dans une page vivante. ``precedente`` rend ce
qu'a vécu la visite précédente de la même page, que l'application envoie où elle veut. En natif, rien de tout cela n'a
de sens : ``demarrer`` ne fait rien, ``precedente`` rend None, ``noter`` ne fait rien. Chaque fonction importe ``js`` à
l'appel : le module s'importe en natif.
"""
from __future__ import annotations

import sys

from qtpy6.QtCore import QObject, QTimer

_minuterie: QTimer | None = None


def _boite():
    if sys.platform != "emscripten":
        return None
    import js  # noqa: PLC0415
    return getattr(js.window, "qtpy6BoiteNoire", None)


def demarrer(parent: QObject | None = None) -> None:
    """Le battement de la boucle de Qt, chaque seconde, dans la boîte noire ; une fois suffit (les appels suivants ne font
    rien)."""
    global _minuterie
    boite = _boite()
    if boite is None or _minuterie is not None:
        return
    _minuterie = QTimer(parent, interval=1000)
    _minuterie.timeout.connect(lambda: boite.battement_qt())
    _minuterie.start()
    boite.battement_qt()


def precedente() -> str | None:
    """La boîte de la visite précédente de cette page, en texte (en tête : quittée proprement ou tuée, dernier signe de
    vie, dernier battement de Qt, navigateur ; puis ses lignes datées), ou None."""
    boite = _boite()
    if boite is None:
        return None
    from pyodide.ffi import jsnull  # noqa: PLC0415
    texte = boite.precedente()
    return None if texte in (None, jsnull) else str(texte)


def noter(texte: str) -> None:
    """Une ligne dans la boîte noire, sans passer par le journal ni la console."""
    boite = _boite()
    if boite is not None:
        boite.noter(texte)
