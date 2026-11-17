"""Garde du coût d'import de qtpy6 en natif (item 21 du TODO Portage, W581, 17/11/2026).

Mesuré ce jour-là (venv SmartPythonEditor, PySide6 6.11.1, médianes sur 10) : `import qtpy.QtCore, QtGui, QtWidgets,
QtWebEngineWidgets` 231-267 ms servi par qtpy6, 223-228 ms par le vrai qtpy. Le vrai qtpy fait `from PySide6.QtXxx
import *`, qui crée tous les types PySide6 : c'est la référence ici, sans dépendre de qtpy (absent du venv de test).
Ratio mesuré ≈ 1,2 ; plafond 2 (la cible de l'item), relatif à la machine, pas un chiffre absolu.
"""
import os
import statistics
import subprocess
import sys

import pytest

pytest.importorskip('PySide6')

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QTPY6 = 'import qtpy6.QtCore, qtpy6.QtGui, qtpy6.QtWidgets'
PYSIDE6 = 'from PySide6.QtCore import *; from PySide6.QtGui import *; from PySide6.QtWidgets import *'


def _mediane(code, n=5):
    mesure = f'import time; t = time.perf_counter(); {code}; print(time.perf_counter() - t)'
    env = dict(os.environ, QT_API='PySide6', QT_QPA_PLATFORM='offscreen', PYTHONPATH=RACINE)
    return statistics.median(float(subprocess.run([sys.executable, '-c', mesure], env=env, cwd=RACINE, check=True,
                                                  capture_output=True, text=True).stdout) for _ in range(n))


def test_import_qtpy6_au_plus_deux_fois_pyside6_entier():
    reference, qtpy6 = _mediane(PYSIDE6), _mediane(QTPY6)
    assert qtpy6 <= 2 * reference, f'qtpy6 {qtpy6 * 1000:.0f} ms, PySide6 entier {reference * 1000:.0f} ms'
