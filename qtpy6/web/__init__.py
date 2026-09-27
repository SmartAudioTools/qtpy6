"""Une application qtpy6 (PyQt6) dans le navigateur, sous Pyodide-Qt : le code de l'application ne change pas, il
s'exécute en WebAssembly dans un élément de la page. Ce que Qt-WASM n'a pas et qui a un nom Qt est doublé là où qtpy6
charge ce nom, sans rien à importer d'ici :

    QtCore.QProcess                  un Web Worker Pyodide sous sa surface (``travailleur.ProcessusWeb``)
    QtGui.QFontDatabase.systemFont(FixedFont)   la première police à chasse fixe que l'application a chargée
    QtCore.QThread, QThreadPool, QMutex…      des fils coopératifs (``fils``)
    subprocess.run (posé par QtCore)           un script Python dans ce même worker, attendu par JSPI (``sous_processus``)
    exec() et boîtes statiques de QtWidgets    suspendus par JSPI jusqu'à leur fin (``bloquant``)

Le reste, qui n'a pas d'équivalent Qt, est dans ce paquet :

    navigateur()                     True sous Pyodide (``sys.platform == "emscripten"``) : l'interrupteur de tout le reste
    application(polices, defaut)     la QApplication, créée au besoin ; hors écran sans session graphique ; les polices
                                     livrées avec l'application dans le navigateur, qui n'en a aucune
    tactile                          détecter un écran au doigt, grossir les cibles, faire défiler au doigt
    dispositions                     des dispositions qui se replient quand la place manque (Disposition, Rangee)
    travailleur                      le Web Worker Pyodide piloté depuis Qt (Travailleur, ProcessusWeb, configurer)
    lancer(script, args, pret)       exécute un script écrit pour le bureau, ``sys.exit(app.exec())`` compris
    lanceur                          un .py ou un .zip quelconque, dont il trouve le point d'entrée (la page du site)
    bloquant                         exec() des boîtes, menus, boucles et de l'application, et les boîtes statiques
    fils                             QThread, QThreadPool, verrous : des fils coopératifs sur le fil unique de la page
    stockage                         localStorage et téléchargement d'un fichier depuis l'application
    assembler                        l'archive que la page dépaquette : fichiers, paquets, distributions, polices
    construire                       ``python -m qtpy6.web.construire app.py site/`` : la page, l'archive, le chargeur
    sonde                            ``python -m qtpy6.web.sonde`` : la page dans Firefox sans interface, journal et capture

Côté page, ``js/qtpy6web.js`` charge Pyodide-Qt et l'archive de l'application (``preparer``), ``js/travailleur.js`` est le
Worker, ``js/gabarit.html`` la page minimale. Rien ici n'importe ``js`` au niveau du module, ni Qt : le paquet s'importe
tel quel en natif, où tout est inerte, et ``QtCore`` l'importe en cours de chargement pour y prendre ``QProcess``."""

import os
import sys
from pathlib import Path

_APP = None


def navigateur():
    """Le code tourne dans le navigateur (Pyodide). Une fonction, pas une constante : un test peut forcer ``sys.platform``."""
    return sys.platform == "emscripten"


def application(polices=None, defaut=None):
    """La QApplication du processus, créée au besoin et rendue. Hors session graphique (ni DISPLAY ni WAYLAND_DISPLAY),
    ``QT_QPA_PLATFORM`` passe à ``offscreen`` : les tests et les exports tournent sans écran. Dans le navigateur, Qt n'a
    AUCUNE police système : les fichiers ``.ttf``/``.otf`` du dossier ``polices`` y sont chargés (la première à chasse
    fixe devient ``systemFont(FixedFont)``), et ``defaut`` (un QFont, ou ``("Noto Sans", 9)``) devient la police de
    l'interface. En natif, ni l'un ni l'autre ne s'appliquent : le système a les siennes."""
    from qtpy6.QtGui import QFont, QFontDatabase  # noqa: PLC0415 - voir la docstring du module
    from qtpy6.QtWidgets import QApplication  # noqa: PLC0415

    global _APP
    if QApplication.instance() is None:
        if not navigateur() and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _APP = app = QApplication(sys.argv[:1])  # gardée : sous PyQt6, une
        # QApplication dont la dernière référence Python disparaît est détruite, et toutes ses fenêtres avec elle
        if navigateur():
            for police in sorted(Path(polices).glob("*.[to]tf")) if polices else ():
                QFontDatabase.addApplicationFont(str(police))
            if defaut is not None:
                app.setFont(defaut if isinstance(defaut, QFont) else QFont(*defaut))
    return QApplication.instance()


def lancer(script, args=(), pret=None, module=None):
    """Exécute ``script`` comme ``python script args…`` sur un bureau : ``__name__ == "__main__"``, ``sys.argv``, le
    dossier du script en tête de ``sys.path`` et comme dossier courant. Avec ``module``, ``script`` est son
    ``__main__.py`` et c'est ``python -m module`` qui est imité, depuis le dossier qui contient le paquet (ses imports
    relatifs marchent). ``app.exec()`` y suspend jusqu'à ``quit()`` (la
    page continue), ``sys.exit`` est rattrapé. À appeler depuis une entrée suspendable (``lancer`` de qtpy6web.js,
    ``runPythonAsync``). ``pret()`` est appelé une fois, quand l'application entre dans ``exec()`` ou, à défaut, quand le
    script se termine. Rend le code de sortie."""
    import runpy  # noqa: PLC0415

    from . import bloquant  # noqa: PLC0415

    chemin = os.path.abspath(script)
    appele = []

    def prevenir():
        if pret is not None and not appele:
            appele.append(True)
            pret()

    dossier = os.path.dirname(os.path.dirname(chemin) if module else chemin)
    sys.argv = [chemin, *args]
    sys.path.insert(0, dossier)
    os.chdir(dossier)
    bloquant._au_demarrage.append(prevenir)
    avant, bloquant._actif = bloquant._actif, True  # une entrée promettante connue (voir bloquant._peut_suspendre)
    try:
        if module:
            runpy.run_module(module, run_name="__main__", alter_sys=True)
        else:
            runpy.run_path(chemin, run_name="__main__")
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else int(e.code is not None)
    finally:
        bloquant._actif = avant
        prevenir()
