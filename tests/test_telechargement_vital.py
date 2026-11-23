"""Un fichier vital de Pyodide (``python_stdlib.zip``, ``pyodide.asm.wasm``) refusé par le réseau : ``preparer``
(``qtpy6web.js``) le redemande (``NOUVEAUX_ESSAIS``), et s'il manque pour de bon, rejette par une erreur
``TelechargementImpossible`` qui nomme le fichier et dit quoi faire, au lieu d'attendre un Pyodide qui finit en « Fatal
Python error: … No module named 'encodings' » sans rendre la main (élève du 22/11/2026, W955 de SmartTeacher). Sous node
(``telechargement_harnais.mjs``, faux Pyodide de ``faux_pyodide/``)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent
JS = ICI.parent / "qtpy6" / "web" / "js" / "qtpy6web.js"


def mesurer(refus: int) -> dict:
    if shutil.which("node") is None:
        pytest.skip("node absent")
    sortie = subprocess.run(["node", str(ICI / "telechargement_harnais.mjs"), JS.as_uri(),
                             (ICI / "faux_pyodide").as_uri() + "/", str(refus)],
                            capture_output=True, text=True, timeout=60, check=True).stdout
    return json.loads(sortie.strip().splitlines()[-1])


def test_un_refus_passager_est_redemande() -> None:
    mesure = mesurer(2)
    assert mesure["recu"] == 1234, mesure
    assert mesure["essais_stdlib"] == 3


def test_un_refus_durable_dit_quoi_faire_sans_attendre_pyodide() -> None:
    mesure = mesurer(99)
    assert mesure["issue"] == "erreur" and mesure["nom"] == "TelechargementImpossible", mesure
    assert mesure["fichier"] == "python_stdlib.zip"
    assert "python_stdlib.zip" in mesure["message"] and "antivirus" in mesure["message"]
    assert mesure["duree"] < 10
