"""Instrumentation du démarrage (W577, item 22 du TODO Portage) : ``&profil=1`` dans la page, ``PROFIL_DEMARRAGE=1`` sur
le bureau. ``preparer`` l'importe en premier ; ``jalon7`` appelle ``rapport()`` à la fin de ``post_visible_setup``.
Imprime le temps de la page à l'entrée dans Python (performance.now()), puis, si demandé, le profil cProfile de
l'import de Spyder à la fin de post_visible_setup : les fonctions triées par temps cumulé et par temps propre."""

import os
import sys

WEB = sys.platform == "emscripten"
if WEB:
    import js  # instrumentation
    print(f"entrée dans Python : {js.performance.now() / 1000:.2f} s depuis l'ouverture de la page")
    ACTIF = js.URLSearchParams.new(js.location.search).get("profil") == "1"
else:
    ACTIF = bool(os.environ.get("PROFIL_DEMARRAGE"))

PROFIL = None
if ACTIF:
    import cProfile
    PROFIL = cProfile.Profile()
    PROFIL.enable()


def rapport(n=45):
    if PROFIL is None:
        return
    PROFIL.disable()
    import io
    import pstats
    for cle in ("cumulative", "tottime"):
        s = io.StringIO()
        pstats.Stats(PROFIL, stream=s).sort_stats(cle).print_stats(n)
        texte = s.getvalue().replace("/home/pyodide/app/", "").replace("/lib/python3.13/", "")
        print(f"PROFIL {cle}\n{texte}", file=sys.__stdout__)
    if WEB:
        print(f"fin du profil : {js.performance.now() / 1000:.2f} s depuis l'ouverture de la page", file=sys.__stdout__)
