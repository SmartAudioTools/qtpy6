"""SmartPythonEditor tel qu'un élève l'ouvrirait (12/10/2026) : la fenêtre de Spyder (jalon7.py) avec les panneaux que
l'utilisateur affiche (éditeur, console IPython, explorateur de variables, fichiers, projets, plan, recherche), sans
instrumentation et sans fermeture automatique : ``site/index.html?script=spe.py``.

Un réglage de CONFIGURATION, pas de branche dans le code de l'application : les panneaux que l'utilisateur n'affiche
pas sont désactivés (``<section>/enable``), comme le ferait la page de préférences de Spyder : Plots, aide, aide en
ligne, historique, pylint, complétions. (``--no-web-widgets`` retiré le 12/11/2026 : le gel de la page de chargement
était l'alert() de loading.html, corrigé dans qtpy6/web/moteur_web.py par W546.)"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="spe-")
# La configuration de SmartPythonEditor, comme installation_SmartPythonEditor.sh la pose (SmartOS) : le spyder.ini et le
# transient.ini de référence du fork (déjà estampillés de sa CONF_VERSION), __HOME__ substitué (substituer_home.sh),
# avant tout import de Spyder, qui les lit au chargement de CONF. Sans elle, c'est la disposition de Spyder nu (12/10/2026).
_REFERENCE = next(d for d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "config-reference"),
                              "/DATA/Python/FORKS/SmartPythonEditor/smartos-support/config-reference") if os.path.isdir(d))
os.makedirs(os.path.join(os.environ["SPYDER_CONFDIR"], "config"))
for _nom in ("spyder.ini", "transient.ini"):
    with open(os.path.join(_REFERENCE, _nom), encoding="utf-8") as _f:
        _texte = _f.read().replace("__HOME__", os.path.expanduser("~"))
    with open(os.path.join(os.environ["SPYDER_CONFDIR"], "config", _nom), "w", encoding="utf-8") as _f:
        _f.write(_texte)
os.environ["JUPYTER_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="spe-runtime-")  # comme jalon8c.py
import preparer  # noqa: E402, F401  (doublures avant tout import de Spyder)
from spyder.app import cli_options  # noqa: E402
from spyder.config.manager import CONF  # noqa: E402

for section in "plots help onlinehelp historylog pylint completions".split():
    CONF.set(section, "enable", False)
# Les réglages délibérés de installation_SmartPythonEditor.sh (spyder_config_set.py), hors main/version, déjà juste.
for section, option, valeur in (("editor", "show_filename_toolbar", False),
                                ("shortcuts", "_/switch to pylint", "Ctrl+Alt+Shift+C"),
                                ("shortcuts", "_/switch to variable_explorer", "Ctrl+Alt+Shift+V"),
                                ("shortcuts", "editor/enter array table", ""),
                                ("shortcuts", "ipython_console/enter array table", ""),
                                ("statusbar", "memory_usage/enable", False), ("statusbar", "cpu_usage/enable", False),
                                ("statusbar", "clock/enable", False), ("statusbar", "show_status_bar", False)):
    CONF.set(section, option, valeur)
# La liste de la barre Interpréteur (main_interpreter/custom_interpreters_list), que update_spyder_interpreters.py
# remplit à l'installation avec les environnements pyenv de la machine : ici le seul interpréteur, celui qui exécute
# l'essai. Dans la page, qtpy6 donne à sys.executable un vrai fichier au chemin pyenv (…/versions/3.13/bin/python,
# _executable du lanceur de qtpy6, W559) : le combo le nomme « 3.13 » ; custom reste faux, le noyau prend sys.executable.
CONF.set("main_interpreter", "custom_interpreters_list", [sys.executable])
CONF.set("main_interpreter", "custom_interpreter", sys.executable)
CONF.set("toolbar", "last_visible_toolbars",
         [b for b in CONF.get("toolbar", "last_visible_toolbars", []) if b != "main_toolbar"])

# Contournement d'ESSAI : 30 s après le démarrage, Spyder liste ses dépendances obligatoires absentes (pylsp, jedi 0.20,
# aiohttp…) dans une boîte d'erreur ; aucune préférence ne la coupe, et ces modules manquent réellement dans la page
# (complétions désactivées ci-dessus). Point ouvert : une liste de dépendances propre au web, côté qtpy6 ou construction.
from spyder.plugins.application.container import ApplicationContainer  # noqa: E402
ApplicationContainer.report_missing_dependencies = lambda self: None


def SUITE(main, rapport):  # noqa: N802, ARG001 - jalon7.py l'appelle après post_visible_setup : la fenêtre reste ouverte
    """Contournement d'ESSAI : le centrage des boutons Exécuter…Interpréteur (mainmenu du fork, ``_recenter``) suppose à
    droite la barre ``window_controls_toolbar`` du greffon spyder_window_controls, dont la zone extensible prend la place
    restante ; sans elle, c'est la barre Interpréteur qui la prend, et le groupe colle à Fichiers (journal
    smartos_rangee.jsonl relevé dans la page, 12/10/2026). Le greffon lui-même n'est pas embarqué : il porte aussi les
    boutons Réduire/Agrandir/Fermer, sans objet dans une page. Ici sa seule zone extensible. Point ouvert : le greffon
    qui masque ses boutons quand la fenêtre est en plein écran (à décider, il change aussi le bureau)."""
    from qtpy6.QtCore import Qt
    from qtpy6.QtWidgets import QSizePolicy, QToolBar, QWidget
    barre = QToolBar(main)
    barre.setObjectName("window_controls_toolbar")
    barre.setMovable(False)
    zone = QWidget(barre)
    zone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    barre.addWidget(zone)
    main.addToolBar(Qt.ToolBarArea.TopToolBarArea, barre)
    # À la place des boutons de fenêtre : le bouton Plein écran de Spyder (Affichage, F11), qui dans la page passe le
    # navigateur en plein écran (qtpy6.web.application).
    from spyder.plugins.layout.container import LayoutContainerActions
    layout = main.get_plugin("layout")
    plein = layout.get_action(LayoutContainerActions.Fullscreen)

    def icone():  # celles du bouton Agrandir des volets ; Spyder pose les siennes (qtawesome) à chaque bascule
        plein.setIcon(layout.create_icon("window_collapse" if layout._fullscreen_flag else "window_full_screen"))

    icone()
    plein.triggered.connect(icone)  # branché après toggle_fullscreen : passe après lui
    barre.addAction(plein)
    # Instrumentation : la fenêtre reste ouverte, rapport() n'est jamais appelé, la sonde attendait « fini » jusqu'à son
    # délai, sans capture (cause relevée par W559, 12/11/2026) ; `--etat ouvert` capture la fenêtre ouverte.
    from qtpy6.QtCore import QTimer
    def ouvert():
        from qtpy6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():  # le rapporteur d'erreur de Spyder garde la trace pour lui : au journal
            if type(w).__name__ == "SpyderErrorDialog" and w.isVisible():
                print("rapporteur d'erreur :", w.error_traceback, file=sys.__stdout__)
        print("interpréteurs :", CONF.get("main_interpreter", "custom_interpreters_list"), file=sys.__stdout__)
        fin("ouvert")  # noqa: F821 - fin() de jalon7.py, exécuté dans ces globales
    QTimer.singleShot(2000, ouvert)


exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon7.py")).read(), "jalon7.py", "exec"))
