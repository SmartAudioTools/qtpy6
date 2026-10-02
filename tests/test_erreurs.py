"""``qtpy6.erreurs`` : une exception non rattrapée passe au crochet précédent puis s'affiche, depuis n'importe quel fil."""

import sys
import threading

import pytest

from qtpy6.QtCore import Qt
from qtpy6.QtWidgets import QApplication

from qtpy6 import erreurs


@pytest.fixture
def installe(app, monkeypatch):
    vues, montrees = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *e: vues.append(e[0]))
    monkeypatch.setattr(threading, "excepthook", lambda a: vues.append(a.exc_type))
    monkeypatch.setattr(erreurs, "_relais", None)
    monkeypatch.setattr(erreurs._Relais, "montrer", lambda self, m: montrees.append((m, threading.current_thread())))
    erreurs.installer()
    return vues, montrees


def lever(exc):
    try:
        raise exc
    except Exception:  # noqa: BLE001
        sys.excepthook(*sys.exc_info())


def test_crochet_precedent_puis_boite(installe):
    vues, montrees = installe
    lever(ValueError("perdue"))
    assert vues == [ValueError]
    assert len(montrees) == 1 and "ValueError: perdue" in montrees[0][0]


def test_autre_fil_affiche_dans_le_fil_principal(installe):
    vues, montrees = installe
    fil = threading.Thread(target=lever, args=(KeyError("fil"),))
    fil.start()
    fil.join()
    assert vues == [KeyError] and montrees == []
    QApplication.processEvents()
    assert len(montrees) == 1 and montrees[0][1] is threading.main_thread()


def test_threading_thread(installe):
    vues, montrees = installe

    def fil(exc):
        raise exc

    for exc in (OSError("fil"), SystemExit()):
        f = threading.Thread(target=fil, args=(exc,))
        f.start()
        f.join()
    QApplication.processEvents()
    assert vues == [OSError, SystemExit]
    assert len(montrees) == 1 and "OSError: fil" in montrees[0][0]


def test_second_appel_ne_double_pas(installe):
    vues, montrees = installe
    erreurs.installer()
    lever(ValueError())
    assert len(vues) == 1 and len(montrees) == 1


def test_boite_selectionnable_sans_toucher_au_style(app):
    app.setStyleSheet("QLabel { color: red; }")
    b = erreurs.boite("Traceback ...")
    assert "Traceback ..." in b.text()
    assert b.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    assert app.styleSheet() == "QLabel { color: red; }"
    app.setStyleSheet("")
