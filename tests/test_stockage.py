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


def test_monter_laisse_le_navigateur_recopier_seul(pyodide, monkeypatch, tmp_path):
    """Le montage demande ``autoPersist`` à IDBFS (la copie après chaque écriture est au navigateur, pas à l'application),
    restaure (``syncfs(True)``) en suspendant, et note le dossier dans ``_montes`` pour ``application(persistant=...)``."""
    montages = []
    fs = sys.modules["pyodide_js"].FS
    fs.filesystems = types.SimpleNamespace(IDBFS="idbfs")
    fs.mount = lambda type_, options, chemin: montages.append((type_, options, chemin))
    monkeypatch.setitem(sys.modules, "js", types.SimpleNamespace(Object=types.SimpleNamespace(new=types.SimpleNamespace),
                                                                 navigator=types.SimpleNamespace()))
    monkeypatch.setattr(bloquant, "_suspendre", lambda brancher: (brancher(lambda e=None: None), pyodide[-1][1]()) and None)
    monkeypatch.setattr(stockage, "_montes", set())
    dossier = tmp_path / "eleve"
    stockage.monter(dossier)
    assert dossier.is_dir()
    assert [(t, o.autoPersist, c) for t, o, c in montages] == [("idbfs", True, str(dossier))]
    assert [p for p, _ in pyodide] == [True]  # la restauration, et aucune copie à la charge de l'application
    assert stockage._montes == {str(dossier)}


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
