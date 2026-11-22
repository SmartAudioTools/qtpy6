"""Le ``qtSuspendJs`` que ``boucles_qt`` (``qtpy6web.js``) donne à Qt, sous node (``suspension_harnais.mjs``), avec la JSPI
de V8 et sous la règle de JavaScriptCore (Safari : tout import ``WebAssembly.Suspending`` suspend, même s'il rend une valeur
ordinaire). Un refus de suspendre ne doit jamais passer par l'import Suspending : il y devenait un SuspendError
(« JavaScript frames found between WebAssembly.Suspending and WebAssembly.promising », iPhone d'un élève, L-7) ou une
suspension sans l'état de Pyodide sauvé."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent
JS = ICI.parent / "qtpy6" / "web" / "js" / "qtpy6web.js"


@pytest.fixture(scope="module", params=["v8", "jsc", "bun"])
def mesure(request: pytest.FixtureRequest) -> dict:
    # « bun » : le vrai JavaScriptCore (bun l'embarque, JSPI comprise), chemin dans $BUN ou bun dans le PATH
    moteur = (os.environ.get("BUN") or shutil.which("bun")) if request.param == "bun" else shutil.which("node")
    if not moteur:
        pytest.skip(f"moteur absent pour {request.param}")
    regle = "jsc" if request.param == "jsc" else "v8"
    sortie = subprocess.run([moteur, str(ICI / "suspension_harnais.mjs"), JS.as_uri(), regle],
                            capture_output=True, text=True, timeout=60, check=True).stdout
    return json.loads(sortie.strip().splitlines()[-1])


def test_refus_hors_entree_promettante(mesure: dict) -> None:
    assert mesure["refus_hors_promettant"] == "passe"


def test_refus_avec_une_frame_js_au_milieu(mesure: dict) -> None:
    assert mesure["refus_frame_js"] == "passe"


def test_un_refus_ne_suspend_pas(mesure: dict) -> None:
    assert mesure["refus_promettant"] == "passe" and mesure["refus_sans_suspendre"]


def test_un_refus_de_pyodide_dans_la_pompe_ne_suspend_pas(mesure: dict) -> None:
    assert mesure["refus_etat_vide"] == "passe" and mesure["etat_vide_sans_suspendre"]


def test_la_vraie_suspension_attend_la_reprise_de_qt(mesure: dict) -> None:
    assert mesure["suspension"] == "passe" and mesure["suspendue"] and mesure["reprise"]
    assert (mesure["suspensions"], mesure["sauves"], mesure["restaures"], mesure["refus"]) == (1, 1, 1, 4)


def test_une_frame_js_dans_la_pompe_refuse_au_lieu_de_tuer_pyodide(mesure: dict) -> None:
    # W929 : Safari (Mac, iPhone) des élèves, « Pyodide mort : JavaScript frames found between WebAssembly.Suspending and
    # WebAssembly.promising » ; rouge sans le catch_all de l'aiguilleur (SuspendError sous node comme sous bun)
    assert mesure["pompe_frame_js"] == "passe"
    assert mesure["pompe_frame_js_compteurs"] == [1, 0, 1, 1, True, False]
