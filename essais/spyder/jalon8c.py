"""Jalon 8c du portage de SmartPythonEditor dans le navigateur (notes/2026-10-11 - Doublure zmq, plan.md) : la console
IPython de la vraie MainWindow (jalon7.py), avec son noyau dans un Web Worker côté page. Une fois la fenêtre affichée :
- l'invite « In [1] » paraît (noyau prêt) ;
- `1+1` donne « Out[1]: 2 » dans la console ;
- `a = 3` fait paraître `a` dans l'explorateur de variables ;
- le redémarrage du noyau rend une console neuve, où `a` n'existe plus.
Un verdict par étape, puis le rapport de jalon7 (qui ferme Spyder). Le même script sur le bureau (offscreen) et dans la
page ; état de la page : celui de jalon7."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tempfile  # noqa: E402
os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="jalon8c-")
os.environ["JUPYTER_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="jalon8c-runtime-")
import preparer  # noqa: E402, F401  (doublures avant tout import de Spyder)

if sys.platform == "emscripten":
    from qtpy6.web import travailleur  # noqa: E402 - instrumentation : le Pyodide-Qt du site pour le Worker (sonde sans réseau)
    travailleur.configurer("./pyodide-qt/")

DELAI = int(os.environ.get("JALON8C_DELAI", 180))  # s par étape : le premier noyau, à froid dans un Worker, charge Pyodide et ses roues


def SUITE(main, rapport):  # noqa: N802 - nom lu par jalon7.py
    from qtpy6.QtCore import QTimer
    from spyder.api.plugins import Plugins
    console = main.get_plugin(Plugins.IPythonConsole).get_widget()
    explorateur = main.get_plugin(Plugins.VariableExplorer).get_widget()

    def texte():
        sw = console.get_current_shellwidget()
        return sw._control.toPlainText() if sw is not None else ""

    def etat():
        """Où en est le client de la console : noyau, état de connexion, erreur affichée (instrumentation d'échec)."""
        client = console.get_current_client()
        if client is None:
            return "aucun client"
        kh = getattr(client, "kernel_handler", None)
        etat_kh = getattr(kh, "connection_state", None) if kh is not None else None
        km = getattr(kh, "kernel_manager", None) if kh is not None else None
        return (f"client {type(client).__name__}, kernel_handler {etat_kh}, manager {type(km).__name__}, "
                "erreur :\n" + str(client.error_text).replace("<br>", "\n").replace("&nbsp;", " ")[-2500:])

    def variables():
        nsb = explorateur.current_widget()
        modele = getattr(getattr(nsb, "editor", None), "source_model", None)
        return set(modele.get_data()) if modele is not None else set()

    nouveau = {}  # la console d'après le redémarrage : le texte qui précède est celui de l'ancienne
    etapes = [
        ("noyau prêt (In [1])", lambda: None, lambda: "In [1]:" in texte()),
        ("1+1 → Out[1]: 2", lambda: console.get_current_shellwidget().execute("1+1"), lambda: "Out[1]: 2" in texte()),
        ("a dans l'explorateur", lambda: console.get_current_shellwidget().execute("a = 3"), lambda: "a" in variables()),
        ("redémarrage", lambda: (nouveau.update(n=len(texte())),
                                 console.restart_kernel(ask_before_restart=False)),
         lambda: "In [1]:" in texte()[nouveau["n"]:] or (len(texte()) < nouveau["n"] and "In [1]:" in texte())),
        ("a oublié", lambda: console.get_current_shellwidget().execute("'a' in dir()"),
         lambda: "Out[1]: False" in texte()),
    ]
    resultats = []

    def suivante():
        if resultats[:1] == ["casse"]:  # pas de noyau : les étapes suivantes ne mesureraient rien
            resultats.extend(["non mesuré"] * (len(etapes) - len(resultats)))
        if len(resultats) == len(etapes):
            passe = sum(r == "passe" for r in resultats)
            print(f"jalon 8c : {passe} passe sur {len(etapes)}", file=sys.__stdout__, flush=True)
            rapport()
            return
        nom, agir, fait = etapes[len(resultats)]
        t0 = time.monotonic()
        try:
            agir()
        except Exception as e:  # noqa: BLE001
            resultats.append("casse")
            print(f"8c casse : {nom} ({type(e).__name__}: {e})", file=sys.__stdout__, flush=True)
            QTimer.singleShot(0, suivante)
            return

        def sonder():
            if fait():
                resultats.append("passe")
                print(f"8c passe : {nom} ({time.monotonic() - t0:.1f} s)", file=sys.__stdout__, flush=True)
                QTimer.singleShot(0, suivante)
            elif time.monotonic() - t0 > DELAI:
                resultats.append("casse")
                print(f"8c casse : {nom} (rien en {DELAI} s) ; console : {texte()[-300:]!r} ; {etat()}", file=sys.__stdout__, flush=True)
                QTimer.singleShot(0, suivante)
            else:
                QTimer.singleShot(250, sonder)
        sonder()

    QTimer.singleShot(0, suivante)


exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon7.py")).read(), "jalon7.py", "exec"))
