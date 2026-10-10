"""Jalon 6 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) : la
mesure que la note met en premier — un `import spyder.app.mainwindow` NU sous Pyodide-Qt, durée et mémoire, sans ouvrir de
fenêtre. Même script sur le bureau (où il relève aussi les paquets tirés par l'import, pour construire_site.py) et dans la
page (construire_site.py, sonde). État de la page : « jalon6 » pendant le travail, « fini » à la fin, « erreur » sinon."""

import os
import sys
import time
import traceback

from preparer import ICI, T0, etape

if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
WEB = sys.platform == "emscripten"
if WEB:
    import js  # noqa: E402 - instrumentation : témoin de phase et journal
    js.window.etat = "jalon6"

PLUGINS = """appearance application completion debugger editor explorer externalterminal findinfiles help history console
ipythonconsole layout maininterpreter mainmenu onlinehelp outlineexplorer plots preferences profiler projects pylint
pythonpath remoteclient run shortcuts statusbar switcher toolbar tours updatemanager variableexplorer
workingdirectory""".split()
PLUGINS = [f"spyder.plugins.{n}.plugin" for n in PLUGINS]
avant = set(sys.modules)


def memoire():
    """Mio du tas wasm dans la page, RSS sur le bureau."""
    if WEB:
        import pyodide_js
        return pyodide_js._module.HEAPU8.length / 1048576
    with open("/proc/self/status") as f:
        for ligne in f:
            if ligne.startswith("VmRSS:"):
                return int(ligne.split()[1]) / 1024


try:
    m0 = memoire()
    t = time.monotonic()
    import spyder  # noqa: E402
    etape("import spyder")
    import spyder.app.mainwindow  # noqa: E402,F401
    etape("import spyder.app.mainwindow")
    print(f"import mainwindow : {time.monotonic() - t:.2f} s, mémoire {m0:.0f} → {memoire():.0f} Mio")
    # Les 33 plugins internes (points d'entrée de setup.py, que find_internal_plugins lit dans les métadonnées : le fork
    # n'en a pas sur sys.path, la liste est recopiée) : importés un par un, chacun chronométré, les échecs relevés.
    import importlib
    t = time.monotonic()
    m1 = memoire()
    echecs = []
    for module in PLUGINS:
        t1 = time.monotonic()
        try:
            importlib.import_module(module)
        except Exception as e:  # noqa: BLE001 - c'est la mesure : quel plugin ne s'importe pas, et pourquoi
            echecs.append((module, f"{type(e).__name__}: {e}"))
            print(f"  {module} : ÉCHEC {type(e).__name__}: {e}")
            continue
        d = time.monotonic() - t1
        if d > 0.1:
            print(f"  {module} : {d:.2f} s")
    print(f"import des {len(PLUGINS)} plugins : {time.monotonic() - t:.2f} s, {len(echecs)} échec(s), mémoire {m1:.0f} → {memoire():.0f} Mio")
    nouveaux = sorted({n.split(".")[0] for n in set(sys.modules) - avant})
    tiers = [n for n in nouveaux if not n.startswith("_") and n not in sys.stdlib_module_names]
    print(f"paquets tiers tirés par l'import ({len(tiers)}) : {' '.join(tiers)}")
    print(f"modules chargés : {len(sys.modules)}, mémoire finale {memoire():.0f} Mio, {time.monotonic() - T0:.1f} s")
    if WEB:
        js.window.etat = "fini"
except Exception:
    traceback.print_exc()
    if WEB:
        js.window.etat = "erreur"
    raise
