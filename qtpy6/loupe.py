"""Le zoom de toute l'interface d'une application qtpy6, le même appel en natif et dans le navigateur : polices, images,
cadres, boîtes, tout grossit d'un même facteur et la mise en page se refait sur l'écran logique réduit, comme sous le
Ctrl + d'un navigateur.

Qt ne sait changer ce facteur (``QT_SCALE_FACTOR``) qu'avant ses fenêtres. Dans le navigateur, ``zoomer`` le range
(``qtpy6|loupe``, lu par ``qtpy6web.preparer``) puis recharge la page : l'application doit avoir rangé son état avant
(la page se cache, puis se ferme). En natif, ``QHighDpiScaling::setGlobalFactor`` (Qt privé, exporté) puis les fenêtres
ouvertes recréées : elles ne suivent qu'avec une nouvelle fenêtre native (mesuré, W491 et W492, 10/11/2026) ; elles se
cachent et se remontrent, ce qu'une surveillance de l'application doit excuser.

La loupe CSS sur le conteneur de Qt-WASM a été écartée : il aurait fallu doubler ce que Qt lit des pointeurs, du toucher,
de la molette, des calques HTML, à chaque version de Qt-WASM."""
from __future__ import annotations

import os
import sys

CLE = "qtpy6|loupe"  # la place du facteur dans le navigateur
PALIERS = (1.0, 1.15, 1.3, 1.5)


def facteur() -> float:
    """Le facteur de zoom en cours (1 : aucun)."""
    try:
        return float(os.environ.get("QT_SCALE_FACTOR") or 1)
    except ValueError:
        return 1.0


def suivant() -> float:
    """Le palier qui suit le facteur en cours, le premier après le dernier (un seul bouton qui fait le tour)."""
    f = facteur()
    return next((p for p in PALIERS if p > f + 1e-6), PALIERS[0])


def choisi() -> bool:
    """Un facteur a déjà été choisi : dans ce navigateur (rangé, même 1), ou pour ce processus natif."""
    if sys.platform == "emscripten":
        from qtpy6.web import stockage  # noqa: PLC0415

        return stockage.lire(CLE) is not None
    return "QT_SCALE_FACTOR" in os.environ


def par_defaut(nouveau: float) -> None:
    """``zoomer(nouveau)`` tant que rien n'a été choisi : un zoom de départ que l'utilisateur peut quitter sans qu'il revienne."""
    if not choisi():
        zoomer(nouveau)


def zoomer(nouveau: float) -> None:
    """Toute l'interface au facteur ``nouveau``. Dans le navigateur, la page se recharge (rien ne revient de cet appel)."""
    if abs(nouveau - facteur()) < 1e-6:
        return
    if sys.platform == "emscripten":
        import js  # noqa: PLC0415

        from qtpy6.web import stockage  # noqa: PLC0415

        stockage.ecrire(CLE, str(nouveau))
        js.location.reload()
        return
    from qtpy6.QtWidgets import QApplication  # noqa: PLC0415

    fixer = _set_global_factor()
    if fixer is None:
        return
    fixer(nouveau)
    os.environ["QT_SCALE_FACTOR"] = str(nouveau)
    for w in QApplication.topLevelWidgets():
        if w.isVisible() and w.windowHandle() is not None:
            etat = w.windowState()
            w.hide()
            w.windowHandle().destroy()
            w.show()
            w.setWindowState(etat)


def _set_global_factor():
    """``QHighDpiScaling::setGlobalFactor(double)`` de la bibliothèque QtGui chargée, ou None (symbole absent)."""
    import ctypes  # noqa: PLC0415

    try:
        gui = ctypes.CDLL(_chemin_qtgui())
        f = gui._ZN15QHighDpiScaling15setGlobalFactorEd
    except (OSError, AttributeError):
        return None
    f.argtypes = [ctypes.c_double]
    return f


def _chemin_qtgui() -> str:
    """Le fichier de la bibliothèque QtGui que le module ``QtGui`` de la liaison a chargé (lu dans /proc/self/maps)."""
    with open("/proc/self/maps", encoding="utf-8") as cartes:
        for ligne in cartes:
            if "libQt6Gui.so" in ligne:
                return ligne.split()[-1]
    raise OSError("libQt6Gui non chargée")
