"""Item 18 (W560, 12/11/2026), dans Spyder entier : spe.py, puis, la fenêtre ouverte, ``create_new_client()`` de la
console IPython comme le fait « Exécuter » sans console ; relevé de chaque étape jusqu'à ``connect_kernel``.
``site/index.html?script=env18_spe.py`` ; sur le bureau : ``$P env18_spe.py``.

Instrumentation d'essai : les ``print`` (« env18 … ») sont lus par la sonde, pas du code d'application."""

import os
import time

ICI = os.path.dirname(os.path.abspath(__file__))
_source = open(os.path.join(ICI, "spe.py"), encoding="utf-8").read()
_exec = 'exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon7.py")).read(), "jalon7.py", "exec"))'
assert _source.count(_exec) == 1
_source = _source.replace(_exec, "SUITE_SPE = SUITE\nSUITE = SUITE_ENV18\n" + _exec)
T_ENV = time.monotonic()


def note(texte):
    import sys  # la console interne de Spyder redirige sys.stdout : la sonde lit la sortie d'origine
    print(f"env18 {time.monotonic() - T_ENV:7.2f}s {texte}", file=sys.__stdout__, flush=True)


def SUITE_ENV18(main, rapport):  # noqa: N802
    import functools

    from qtpy6.QtCore import QTimer
    from spyder.plugins.ipythonconsole.widgets import client as module_client
    from spyder.plugins.ipythonconsole.widgets import main_widget as module_mw
    from spyder.utils import environ

    SUITE_SPE(main, lambda: None)  # noqa: F821 - défini par la source de spe.py
    console = main.get_plugin("ipython_console")
    widget = console.get_widget()
    note(f"fenêtre ouverte ; clients déjà là : {len(widget.clients)}")

    def tracer(objet, nom):
        origine = getattr(objet, nom)

        @functools.wraps(origine)
        def trace(*args, **kwargs):
            note(f"-> {nom}" + (f" {str(args[1:])[:1500]}" if nom == "show_kernel_error" else ""))
            try:
                r = origine(*args, **kwargs)
            except BaseException as e:
                note(f"<- {nom} CASSE {type(e).__name__}: {e}")
                raise
            note(f"<- {nom} : {type(r).__name__}")
            return r
        setattr(objet, nom, trace)

    tracer(environ, "run_shell_command")
    tracer(module_mw, "get_user_environment_variables")
    tracer(module_mw.IPythonConsoleWidget, "_connect_new_client_to_kernel")
    tracer(module_mw.IPythonConsoleWidget, "get_cached_kernel")
    tracer(module_client.ClientWidget, "connect_kernel")
    tracer(module_client.ClientWidget, "show_kernel_error")
    from spyder.api.asyncdispatcher import AsyncDispatcher
    environ.get_user_environment_variables().connect(
        AsyncDispatcher.QtSlot(lambda f: note(f"environnement : {len(f.result())} variables")))
    debut = time.monotonic()
    client = widget.create_new_client()
    note(f"create_new_client rendu : {type(client).__name__}")

    def veiller():
        page = getattr(client, "info_page", None)
        quoi = ("env" if page is client.env_loading_page else "noyau" if page is client.kernel_loading_page
                else "vide" if page is client.blank_page else "autre")
        kh = getattr(client, "kernel_handler", None)
        etat = getattr(kh, "connection_state", None)
        sw = client.shellwidget
        texte = sw._control.toPlainText()
        note(f"veille : page d'attente = {quoi} ; noyau {etat} ; console cachée {sw.isHidden()} ; "
             f"résultat {'W560 42' in texte} ; fin de la console {texte[-120:]!r}")
        if str(etat) == "spyder_kernel_ready" and "In [1]" in texte and not veiller.lance:
            veiller.lance = True
            sw.execute("print('W560', 6 * 7)")
        if time.monotonic() - debut > 60:
            minuterie.stop()
            note("FIN délai")
            rapport()

    veiller.lance = False
    minuterie = QTimer(main)
    minuterie.timeout.connect(veiller)
    minuterie.start(3000)


exec(compile(_source, os.path.join(ICI, "spe.py"), "exec"))
