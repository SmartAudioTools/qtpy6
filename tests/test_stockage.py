"""``qtpy6.web.stockage`` hors navigateur : la file des copies vers IndexedDB, Pyodide remplacé par une doublure. Le
montage lui-même (restauration, copie, relecture après démontage) est éprouvé dans Firefox :
web.md, « Rendre une application qtpy6 compatible », point 5."""

import sys
import types

import pytest

from qtpy6.web import bloquant, stockage


@pytest.fixture
def pyodide(monkeypatch):
    """Un ``FS.syncfs`` qui garde ses rappels : le test décide quand chaque copie finit."""
    rappels = []
    fs = types.SimpleNamespace(syncfs=lambda peupler, rappel: rappels.append((peupler, rappel)))
    monkeypatch.setitem(sys.modules, "pyodide_js", types.SimpleNamespace(FS=fs))
    ffi = types.ModuleType("pyodide.ffi")
    ffi.create_once_callable = lambda f: f
    monkeypatch.setitem(sys.modules, "pyodide", types.ModuleType("pyodide"))
    monkeypatch.setitem(sys.modules, "pyodide.ffi", ffi)
    monkeypatch.setattr(stockage, "_synchro", {"etat": None, "attente": []})
    return rappels


def test_monter_hors_navigateur():
    with pytest.raises(ModuleNotFoundError):
        stockage.monter("/tmp/x")


def test_une_ecriture_pendant_la_copie_en_relance_une_seule(pyodide):
    stockage.synchroniser()
    stockage.synchroniser()
    stockage.synchroniser()
    assert [p for p, _ in pyodide] == [False]  # une copie en cours, les deux écritures suivantes attendent sa fin
    pyodide[0][1]()
    assert len(pyodide) == 2  # une seule relance pour les deux
    pyodide[1][1]()
    assert len(pyodide) == 2 and stockage._synchro["etat"] is None


def test_attendre_reprend_quand_tout_est_copie(pyodide, monkeypatch, capsys):
    repris = []
    monkeypatch.setattr(bloquant, "_suspendre", lambda brancher: brancher(lambda: repris.append(True)))
    stockage.synchroniser(attendre=True)
    stockage.synchroniser()
    pyodide[0][1]("QuotaExceededError")
    assert not repris  # la relance n'est pas finie
    pyodide[1][1]()
    assert repris == [True]
    assert "QuotaExceededError" in capsys.readouterr().out
