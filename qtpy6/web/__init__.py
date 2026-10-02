"""Une application qtpy6 (PyQt6) dans le navigateur, sous Pyodide-Qt : le code de l'application ne change pas, il
s'exécute en WebAssembly dans un élément de la page. Ce que Qt-WASM n'a pas et qui a un nom Qt est doublé là où qtpy6
charge ce nom, sans rien à importer d'ici :

    QtCore.QProcess                  un Web Worker Pyodide sous sa surface (``travailleur.ProcessusWeb``)
    QtGui.QFontDatabase.systemFont(FixedFont)   la première police à chasse fixe que l'application a chargée
    QtCore.QThread, QThreadPool, QMutex…      des fils coopératifs (``fils``)
    subprocess.run (posé par QtCore)           un script Python dans ce même worker, attendu par JSPI (``sous_processus``)
    exec() et boîtes statiques de QtWidgets    suspendus par JSPI jusqu'à leur fin (``bloquant``)
    QtPdf.QPdfDocument, QtPdfWidgets.QPdfView  pdf.js dans un <div> de la page calé sur le widget (``pdf``)

Le reste, qui n'a pas d'équivalent Qt, est dans ce paquet :

    navigateur()                     True sous Pyodide (``sys.platform == "emscripten"``) : l'interrupteur de tout le reste
    application(polices, defaut)     la QApplication, créée au besoin ; hors écran sans session graphique ; les polices
                                     livrées avec l'application dans le navigateur, qui n'en a aucune ;
                                     le ramasse-miettes entre deux événements, jamais au milieu d'un appel de Qt
    tactile                          détecter un écran au doigt, grossir les cibles, faire défiler au doigt
    dispositions                     des dispositions qui se replient quand la place manque (Disposition, Rangee)
    defilement                       ZoneDefilante : une QScrollArea qui, dans le navigateur, ne repeint que la bande qui entre
    travailleur                      le Web Worker Pyodide piloté depuis Qt (Travailleur, ProcessusWeb, configurer)
    lancer(script, args, pret)       exécute un script écrit pour le bureau, ``sys.exit(app.exec())`` compris
    lanceur                          un .py ou un .zip quelconque, dont il trouve le point d'entrée (la page du site)
    bloquant                         exec() des boîtes, menus, boucles et de l'application, et les boîtes statiques
    fils                             QThread, QThreadPool, verrous : des fils coopératifs sur le fil unique de la page
    stockage                         localStorage et téléchargement d'un fichier depuis l'application
    audio                            jouer un son embarqué (octets en mémoire), natif ou navigateur
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
    l'interface. En natif, ni l'un ni l'autre ne s'appliquent : le système a les siennes. Partout, le ramasse-miettes
    ne passe plus qu'entre deux événements (``_ramasser``)."""
    from qtpy6.QtGui import QFont, QFontDatabase  # noqa: PLC0415 - voir la docstring du module
    from qtpy6.QtWidgets import QApplication  # noqa: PLC0415

    global _APP
    if QApplication.instance() is None:
        if not navigateur() and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _APP = app = QApplication(sys.argv[:1])  # gardée : sous PyQt6, une
        # QApplication dont la dernière référence Python disparaît est détruite, et toutes ses fenêtres avec elle
        _ramasser(app)
        if navigateur():
            for police in sorted(Path(polices).glob("*.[to]tf")) if polices else ():
                QFontDatabase.addApplicationFont(str(police))
            if defaut is not None:
                app.setFont(defaut if isinstance(defaut, QFont) else QFont(*defaut))
            _coller()
            _dessiner_aussitot()
    return QApplication.instance()


def _ramasser(app):
    """Le ramasse-miettes de Python ne passe plus n'importe quand, mais entre deux événements de Qt. Livré à lui-même,
    il se déclenche au hasard d'une allocation, parfois au milieu d'un appel de Qt : s'il libère alors un cycle qui tient
    un widget sans parent (un enfant qui garde son widget, une lambda branchée sur un signal), le widget est
    détruit sous les pieds de Qt, qui plante (segmentation fault, mesuré sur les tests de SmartTeacher le 01/10/2026).
    Ici, une minuterie regarde toutes les demi-secondes les compteurs du ramasse-miettes, et ramasse la génération qu'il
    aurait ramassée lui-même : le même travail, à un moment où aucun appel de Qt n'est en cours."""
    import gc  # noqa: PLC0415

    from qtpy6.QtCore import QTimer  # noqa: PLC0415

    gc.disable()
    seuils = gc.get_threshold()

    def passer():
        n0, n1, n2 = gc.get_count()
        if n0 > seuils[0]:
            gc.collect(2 if n2 > seuils[2] else 1 if n1 > seuils[1] else 0)

    minuterie = QTimer(app)
    minuterie.timeout.connect(passer)
    minuterie.start(500)


def _coller():
    """Ctrl+V colle le texte du presse-papiers du système dans le champ qui a le focus. Qt-WASM laisse passer Ctrl+V au
    navigateur pour recevoir son événement ``paste``, mais n'en fait rien : ni texte, ni touche (mesuré dans Firefox,
    28/09/2026, sur un QLineEdit ; ``paste()`` depuis le presse-papiers interne de Qt marche). L'événement est pris ici,
    avant Qt (phase de capture, sur le document) et arrêté : si Qt apprend à coller, le texte n'arrivera pas deux fois.
    Le texte passe par Qt comme sur le bureau : posé dans le presse-papiers de Qt, puis un Ctrl+V envoyé au champ, que
    voient les filtres d'événements de l'application (un filtre qui interdit de coller depuis l'extérieur le bloque ici
    aussi ; SmartTeacher, 02/10/2026 : insérer le texte directement passait outre)."""
    import js  # noqa: PLC0415 - voir la docstring du module
    from pyodide.ffi import create_proxy  # noqa: PLC0415
    from qtpy6.QtCore import QEvent, Qt  # noqa: PLC0415
    from qtpy6.QtGui import QKeyEvent  # noqa: PLC0415
    from qtpy6.QtWidgets import QApplication  # noqa: PLC0415

    def coller(evenement):
        champ = QApplication.focusWidget()
        texte = evenement.clipboardData and evenement.clipboardData.getData("text/plain")
        if not texte or champ is None:
            return
        evenement.preventDefault()
        evenement.stopPropagation()
        QApplication.clipboard().setText(texte)
        for genre in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(champ, QKeyEvent(genre, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier, "\x16"))

    js.document.addEventListener("paste", create_proxy(coller), True)


def _dessiner_aussitot():
    """Ce qui change à l'écran est envoyé au canevas dans l'image où cela change, pas une sur deux. Un widget ne se
    redessine pas tout de suite : Qt poste un ``UpdateRequest``, traité plus tard par la boucle d'événements, et
    Qt-WASM n'envoie le dessin au canevas qu'au ``requestAnimationFrame`` que demande ce dessin : l'image SUIVANTE.
    Pendant un défilement, une image sur deux restait ainsi sans envoi (56 envois pour 110 roulements, un par image ;
    86 à 89 pour 110 pas d'une minuterie de 16 ms : Firefox, 01/10/2026). Deux moments, chacun nécessaire (mesuré en
    retirant l'autre) :
      - au début de chaque image, avant le rappel qu'elle exécute, les ``UpdateRequest`` en attente sont traités, et
        les images que leur dessin demande sont servies DANS celle-ci : animations, minuteries, défilement au doigt
        (minuterie : 103 à 104 envois, le plafond étant les ~105 images de la durée) ;
      - sitôt une entrée traitée par Qt (molette, souris, clavier ; bouillonnement sur ``window``, donc après Qt) :
        une entrée qui arrive pendant la phase des rappels d'image serait sinon dessinée après (molette : 110 sur 110,
        57 sans ces écouteurs)."""
    import js  # noqa: PLC0415 - voir la docstring du module
    from pyodide.ffi import create_proxy  # noqa: PLC0415
    from qtpy6.QtCore import QEvent  # noqa: PLC0415
    from qtpy6.QtWidgets import QApplication  # noqa: PLC0415

    vider = create_proxy(lambda: QApplication.sendPostedEvents(None, QEvent.Type.UpdateRequest))
    js.Function.new("vider", """const raf = window.requestAnimationFrame.bind(window);
        let pendant = null;
        window.requestAnimationFrame = rappel => {
          if (pendant) { pendant.push(rappel); return 0; }
          return raf(t => { pendant = []; try { vider(); } finally { const p = pendant; pendant = null; p.forEach(r => r(t)); } rappel(t); });
        };
        for (const nom of ["wheel", "pointerdown", "pointermove", "pointerup", "keydown", "keyup"])
          window.addEventListener(nom, () => vider());""")(vider)


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
