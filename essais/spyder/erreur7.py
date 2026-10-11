"""Jalon 7 avec une exception levée dans un slot une seconde après post_visible_setup : la console interne de Spyder
doit l'afficher, pas boucler (cascade RecursionError vue dans le navigateur, 12/10/2026). Instrumenté : la première
exception de handle_exception est écrite sur la vraie sortie d'erreur."""
import os
import sys
import traceback

os.environ["JALON7_ERREUR"] = "1"  # lu par jalon7.py : une exception dans un slot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tempfile  # noqa: E402
os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="jalon7-")
import preparer  # noqa: E402, F401  (doublures avant tout import de Spyder)
from spyder.plugins.console.widgets.main_widget import ConsoleWidget  # noqa: E402

_handle = ConsoleWidget.handle_exception
_vues = []


def handle_exception(self, *args, **kwargs):
    sys.__stderr__.write(f"ERREUR7 reçue : {str(args)[:160]}\n")
    try:
        resultat = _handle(self, *args, **kwargs)
        sys.__stderr__.write("ERREUR7 traitée sans exception\n")
        return resultat
    except BaseException as e:
        if len(_vues) < 2:
            _vues.append(e)
            sys.__stderr__.write("ERREUR7 handle_exception :\n" + "".join(traceback.format_exc(limit=-12)))
        raise


ConsoleWidget.handle_exception = handle_exception
exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon7.py")).read(), "jalon7.py", "exec"))
