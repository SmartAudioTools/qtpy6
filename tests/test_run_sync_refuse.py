"""``run_sync`` de Pyodide quand une frame JavaScript le sépare de l'entrée promettante (un rappel JS → wasm qui n'est pas
une entrée de Pyodide, comme ceux de Qt-WASM ou d'embind) : Safari levait un SuspendError (« JavaScript frames found between
WebAssembly.Suspending and WebAssembly.promising ») qui tuait Pyodide (99 journaux d'élèves, W933, 22/11/2026). Avec
``boucles_qt`` (``qtpy6web.js``), l'aiguilleur de ``syncifyHandler`` change ce refus en JsException dans Python. Le vrai
Pyodide (``site/pyodide-qt``) sous bun (JavaScriptCore) et node (V8), harnais ``run_sync_harnais.mjs``."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent
JS = ICI.parent / "qtpy6" / "web" / "js" / "qtpy6web.js"
PYODIDE = ICI.parent / "site" / "pyodide-qt"


def lancer(moteur: str, mode: str) -> dict:
    sortie = subprocess.run([moteur, str(ICI / "run_sync_harnais.mjs"), JS.as_uri(), PYODIDE.as_uri() + "/", mode],
                            capture_output=True, text=True, timeout=120, check=True).stdout
    return json.loads(sortie.strip().splitlines()[-1])


@pytest.fixture(scope="module", params=["node", "bun"])
def moteur(request: pytest.FixtureRequest) -> str:
    m = (os.environ.get("BUN") or shutil.which("bun")) if request.param == "bun" else shutil.which("node")
    if not m or not (PYODIDE / "pyodide.mjs").exists():
        pytest.skip(f"{request.param} ou site/pyodide-qt absent")
    return m


def test_sans_aiguilleur_le_refus_casse_l_appel(moteur: str) -> None:
    # le témoin : sans boucles_qt, le refus n'arrive pas dans Python comme une exception (l'appel casse)
    r = lancer(moteur, "sans")
    assert r["note"] == "[True]" and str(r["retour"]).startswith("erreur")


def test_avec_aiguilleur_le_refus_est_une_exception_python(moteur: str) -> None:
    r = lancer(moteur, "avec")
    assert r["mort"] is None and r["vivant"] is True
    assert r["note"] == "[True, 'refus']" and r["retour"] == 0 and r["refus_sync"] == 1
    assert r["normal"] == "suspendu"  # une suspension ordinaire passe toujours


def test_refus_dans_un_chercheur_d_import_l_import_aboutit(moteur: str) -> None:
    # la Pause de qtpy6.web.importer : le refus arrive dans find_spec pendant un import (iPhone, 25/11/2026, W1027)
    r = lancer(moteur, "import")
    assert r["mort"] is None and r["vivant"] is True and r["retour"] == 0
    assert r["note"].startswith("[True, 'refus'") and r["note"].endswith("'importé']")
