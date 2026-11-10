"""La boîte noire de ``qtpy6web.js`` sous node (``boite_noire_harnais.mjs``) : un onglet caché ou une page reprise du cache
du navigateur ne sont pas des gels (50 des 90 alertes des boîtes noires des élèves, 06-09/11/2026, jusqu'à 596 s, n'étaient
que le temps passé ailleurs) ; un vrai gel l'est toujours."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent
JS = ICI.parent / "qtpy6" / "web" / "js" / "qtpy6web.js"


@pytest.fixture(scope="module")
def scenarios() -> dict:
    if shutil.which("node") is None:
        pytest.skip("node absent")
    sortie = subprocess.run(["node", str(ICI / "boite_noire_harnais.mjs"), JS.as_uri()], capture_output=True, text=True,
                            timeout=60, check=True).stdout
    return json.loads(sortie.strip().splitlines()[-1])


def alertes(lignes: list[str]) -> list[str]:
    return [l for l in lignes if l.startswith(("gel de la page", "la boucle de Qt ne tourne plus"))]


def test_onglet_cache_n_est_pas_un_gel(scenarios: dict) -> None:
    assert alertes(scenarios["onglet_cache"]["lignes"]) == []


def test_retour_du_cache_n_est_ni_un_gel_ni_une_page_quittee(scenarios: dict) -> None:
    s = scenarios["cache_navigateur"]
    assert alertes(s["lignes"]) == []
    assert "page reprise du cache du navigateur" in s["lignes"]
    assert s["fin"] is None


def test_retour_du_cache_sans_visibilitychange(scenarios: dict) -> None:
    s = scenarios["cache_sans_visibilite"]
    assert alertes(s["lignes"]) == []
    assert s["fin"] is None


def test_un_fil_bloque_reste_un_gel(scenarios: dict) -> None:
    lignes = alertes(scenarios["fil_bloque"]["lignes"])
    assert any(l.startswith("gel de la page : 11.0 s") for l in lignes), lignes


def test_une_boucle_de_qt_arretee_reste_notee(scenarios: dict) -> None:
    lignes = scenarios["qt_arretee"]["lignes"]
    assert alertes(lignes) == [l for l in lignes if l.startswith("la boucle de Qt ne tourne plus depuis 4.0 s")] != [], lignes
