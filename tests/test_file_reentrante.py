"""Qt-WASM, ``QWasmSuspendResumeControl::sendPendingEvents`` : la file des événements du navigateur est comptée une fois,
puis vidée par autant de ``shift()`` ; un handler qui traite lui-même des événements (un slot pendant lequel le navigateur
livre un événement synchrone, ou un ``processEvents`` imbriqué) envoie et retire ceux qui restaient, et la boucle externe
lisait ``event["index"]`` sur undefined : « undefined is not an object (evaluating 'handle[key]') », Pyodide mort à
l'accueil sur un Safari Mac 26.4 (25/11/2026, [L-62]). Corrigé par ``wasm/patches/qtbase-wasm-file-reentrante.patch``.
Le Pyodide-Qt dynamique de construire.sh, sous node, harnais ``file_reentrante_harnais.mjs``."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ICI = Path(__file__).parent
DYNAMIQUE = Path(os.environ.get("PYODIDE_QT_DYNAMIQUE", "/DATA/Python/outils_wasm/pyside6/build/dynamique/dist"))


def test_un_handler_qui_vide_la_file_ne_tue_pas_pyodide() -> None:
    node = shutil.which("node")
    if not node or not (DYNAMIQUE / "pyodide.mjs").exists():
        pytest.skip("node ou le Pyodide-Qt de construire.sh absent")
    sortie = subprocess.run([node, str(ICI / "file_reentrante_harnais.mjs"), str(DYNAMIQUE)],
                            capture_output=True, text=True, timeout=180, check=True).stdout
    r = json.loads(sortie.strip().splitlines()[-1])
    assert r["mort"] is None
    assert r["slots"] == 1 and r["reste"] == 0  # le slot a tourné une fois, la file imbriquée a tout envoyé
