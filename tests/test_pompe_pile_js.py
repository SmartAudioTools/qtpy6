"""La pompe promettante de ``qtpy6web.js`` sous node (``pompe_harnais.mjs``) : chaque ``callPromising`` de Pyodide 0.29.3
laisse 16 octets de pile C ; cent tours par seconde épuisaient les 5 Mio de pile en 50 min et Pyodide mourait (B1, W744)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent
JS = ICI.parent / "qtpy6" / "web" / "js" / "qtpy6web.js"


@pytest.fixture(scope="module")
def mesure() -> dict:
    if shutil.which("node") is None:
        pytest.skip("node absent")
    sortie = subprocess.run(["node", str(ICI / "pompe_harnais.mjs"), JS.as_uri()], capture_output=True, text=True,
                            timeout=60, check=True).stdout
    return json.loads(sortie.strip().splitlines()[-1])


def test_la_pompe_rend_la_pile_a_chaque_tour(mesure: dict) -> None:
    assert mesure["seule"] == 0


def test_la_pompe_ne_libere_pas_le_cadre_d_une_autre_entree(mesure: dict) -> None:
    assert mesure["cadre_vivant"] == 16 + 64
