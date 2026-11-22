"""Un navigateur sans JSPI (``WebAssembly.Suspending`` absent : Safari avant 27, Chrome ou Edge avant 137, Firefox
ancien) : ``preparer`` (``qtpy6web.js``) le refuse avant tout téléchargement par une erreur ``NavigateurSansJSPI`` qui
nomme le navigateur et dit quoi faire, au lieu du « WebAssembly stack switching not supported in this JavaScript
runtime » de Pyodide (élève du 22/11/2026, W925 de SmartTeacher). Sous node (``navigateur_harnais.mjs``)."""
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
    sortie = subprocess.run(["node", str(ICI / "navigateur_harnais.mjs"), JS.as_uri()],
                            capture_output=True, text=True, timeout=60, check=True).stdout
    return json.loads(sortie.strip().splitlines()[-1])


def test_refus_avant_tout_telechargement(mesure: dict) -> None:
    assert mesure["refus"]["nom"] == "NavigateurSansJSPI"
    assert mesure["demandes"] == []


def test_le_message_nomme_le_navigateur_et_dit_quoi_faire(mesure: dict) -> None:
    assert mesure["refus"]["navigateur"] == "iOS 26.1"
    assert "(iOS 26.1)" in mesure["refus"]["message"] and "Chrome" in mesure["refus"]["message"]


def test_navigateurs_reconnus(mesure: dict) -> None:
    assert mesure["navigateurs"] == {"chrome_windows": "Chrome 131", "edge": "Edge 120", "firefox": "Firefox 128",
                                     "safari_mac": "Safari 26.1", "chrome_iphone": "iOS 26.1"}
