"""Jalon 7 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) : la
vraie MainWindow de Spyder, instanciée comme `spyder.app.mainwindow.main` le fait (create_application, puis
create_window), et un verdict par plugin — passe, casse (avec la cause), non mesuré (sauté par Spyder lui-même :
désactivé, ou Help et OnlineHelp sans QtWebEngine, cas du bureau PyQt6 sans PyQt6-WebEngine). Le même script sur le
bureau (offscreen) et dans la page (construire_site.py, sonde) ; seule l'instrumentation (témoin d'état de la page, mémoire) sait où elle tourne. Configuration de Spyder dans un
dossier jetable (SPYDER_CONFDIR) : jamais la réelle. État de la page : « jalon7 » pendant le travail, « fini » à la fin,
« erreur » sinon."""

import os
import sys
import tempfile
import time
import traceback

os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="jalon7-")
from preparer import ICI, T0, etape  # noqa: E402

WEB = sys.platform == "emscripten"
if WEB:
    import js  # noqa: E402 - instrumentation : témoin de phase
    js.window.etat = "jalon7"
ATTENTE = 8000  # ms après l'entrée dans exec() : ce que les plugins démarrent en différé (console, noyau) a le temps d'échouer


def memoire():
    """Mio du tas wasm dans la page, RSS sur le bureau (instrumentation)."""
    if WEB:
        import pyodide_js
        return pyodide_js._module.HEAPU8.length / 1048576
    with open("/proc/self/status") as f:
        for ligne in f:
            if ligne.startswith("VmRSS:"):
                return int(ligne.split()[1]) / 1024


verdicts = {}  # nom du plugin → (verdict, détail)


def fin(etat):
    if WEB:
        js.window.etat = etat


try:
    from qtpy6.QtCore import QTimer
    from qtpy6.web import application
    from spyder.api.plugin_registration.registry import PLUGIN_REGISTRY
    from spyder.app.cli_options import get_options
    from spyder.app.find_plugins import find_internal_plugins
    from spyder.app.mainwindow import MainWindow
    from spyder.app.utils import create_application, create_window
    etape("imports")
    m0 = memoire()
    # Contournement d'ESSAI, défaut du fork commun au bureau et à la page (PySide6 6.11 comme PyQt6 6.11) : le plugin
    # Completions passe à inspect.signature tous les create_* de sa page de préférences, dont QWidget.create et
    # createWindowContainer, natifs et sans signature (ValueError). Signalé à la session du fork, pas corrigé ici.
    import inspect
    signature = inspect.signature

    def signature_(f, *a, **k):
        try:
            return signature(f, *a, **k)
        except ValueError:
            return inspect.Signature()

    inspect.signature = signature_
    # Help et OnlineHelp : QtWebEngine sur le bureau, la doublure QWebEngineView de qtpy6 dans la page (preparer.py).
    # --new-instance : contournement d'ESSAI. Le serveur d'instance unique (post_visible_setup) écoute un socket dans un
    # threading.Thread, que la page ne sait pas démarrer (RuntimeError) ; sa doublure est un point ouvert de la note.
    options, _ = get_options(["--new-instance"])
    app = create_application()  # avant l'énumération des plugins, qui les importe (qtawesome veut l'application)
    application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))  # polices de la page ; sur le bureau,
    etape(f"{type(app).__name__}")  # ne fait que garder l'application

    attendus = sorted(find_internal_plugins())
    print(f"plugins internes trouvés par les points d'entrée : {len(attendus)}")
    inscrire = PLUGIN_REGISTRY.register_plugin

    def register_plugin(main, PluginClass, *a, **k):
        """Celle du registre, chronométrée, et qui ne laisse pas un plugin cassé arrêter les suivants (setup s'arrête
        au premier) : c'est la mesure."""
        t = time.monotonic()
        try:
            plugin = inscrire(main, PluginClass, *a, **k)
        except Exception as e:  # noqa: BLE001
            verdicts[PluginClass.NAME] = ("casse", f"{type(e).__name__}: {e}")
            print(f"  {PluginClass.NAME} : CASSE")
            traceback.print_exc()
            return None
        verdicts[PluginClass.NAME] = ("passe", f"{time.monotonic() - t:.2f} s")
        return plugin

    PLUGIN_REGISTRY.register_plugin = register_plugin

    def tableau():
        for nom in attendus:
            v, detail = verdicts.get(nom, ("non mesuré", "pas instancié par setup (widgets web absents ou désactivés)"))
            print(f"  {nom:22} {v:11} {detail}")
        compte = {v: sum(1 for x, _ in verdicts.values() if x == v) for v in ("passe", "casse")}
        print(f"verdicts : {compte['passe']} passe, {compte['casse']} casse, {len(attendus) - len(verdicts)} non mesuré ; "
              f"mémoire {m0:.0f} → {memoire():.0f} Mio, {time.monotonic() - T0:.1f} s")

    pre_visible_setup = MainWindow.pre_visible_setup

    def pre_visible_setup_(self):
        etape("fin de setup (plugins inscrits)")
        tableau()  # avant la suite : un plantage dans show ou post_visible_setup ne doit pas emporter les verdicts
        pre_visible_setup(self)
        etape("pre_visible_setup")

    MainWindow.pre_visible_setup = pre_visible_setup_
    post_visible_setup = MainWindow.post_visible_setup

    def post_visible_setup_(self):
        etape("show")
        post_visible_setup(self)
        etape("post_visible_setup")

    MainWindow.post_visible_setup = post_visible_setup_

    def rapport():
        main = getattr(app, "_main_window", None)
        if main is None:  # le délai a couru pendant setup (qui traite des événements) : repartir de l'entrée dans exec()
            QTimer.singleShot(ATTENTE, rapport)
            return
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__  # la console interne de Spyder les a redirigés
        print(f"fenêtre : {type(main).__name__}, {'visible' if main.isVisible() else 'invisible'}, "
              f"{ATTENTE / 1000:.0f} s après exec() ; mémoire {memoire():.0f} Mio, {time.monotonic() - T0:.1f} s")
        fin("fini")
        try:
            main.closing(cancelable=False, close_immediately=True)  # arrête le noyau que la console a démarré
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        app.quit()

    QTimer.singleShot(ATTENTE, rapport)  # armé avant create_window : exec() est dedans
    create_window(MainWindow, app, None, options, None)
    etape("sortie de exec()")
except Exception:
    traceback.print_exc()
    fin("erreur")
    raise
