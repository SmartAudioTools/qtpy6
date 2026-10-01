"""La ``QPropertyAnimation`` de qtpy6, hors écran : les UpdateRequest viennent de la minuterie de repli de Qt (5 ms)."""
import time

import pytest

from qtpy6 import QtCore, QtWidgets
from qtpy6.QtCore import QAbstractAnimation, QPropertyAnimation

Etat = QAbstractAnimation.State


@pytest.fixture
def montre(app):
    """Montre un widget, et le ferme à la fin du test : un test suivant compte les fenêtres visibles (test_selector_main)."""
    montres = []

    def montrer(widget):
        widget.show()
        app.processEvents()
        montres.append(widget)
        return widget

    yield montrer
    for widget in montres:
        widget.close()


def barre_visible(montre):
    barre = QtWidgets.QScrollBar()
    barre.setRange(0, 1000)
    return montre(barre)


def animation(cible, propriete, duree, **proprietes):
    a = QPropertyAnimation(cible, propriete.encode(), duration=duree, **proprietes)
    a.setEndValue(880)
    return a


def attendre(a, app, note=None):
    fini, valeurs = [], []
    a.finished.connect(lambda: fini.append(True))
    while not fini:
        app.processEvents()
        if note is not None:
            valeurs.append(note())
    return valeurs


def test_doublure_de_qtpy6_menee_par_les_images(app, montre):
    assert QPropertyAnimation.__module__ == QAbstractAnimation.__module__ and QPropertyAnimation.par_image
    barre = barre_visible(montre)
    a = animation(barre, "value", 150)
    a.start()
    assert a.state() == Etat.Running and a._fenetre is not None  # Qt la croit en pause, l'application la voit tourner
    valeurs = attendre(a, app, barre.value)
    assert barre.value() == 880 and a.state() == Etat.Stopped and a._fenetre is None  # plus d'image demandée
    assert valeurs == sorted(valeurs) and len(set(valeurs)) > 3


def test_courbe_flottants_et_sens(app, montre):
    fenetre = montre(QtWidgets.QWidget())
    a = QPropertyAnimation(fenetre, b"windowOpacity", duration=60, easingCurve=QtCore.QEasingCurve.Type.OutCubic)
    a.setStartValue(1.0)
    a.setEndValue(0.5)
    a.start()
    attendre(a, app)
    assert abs(fenetre.windowOpacity() - 0.5) < 0.01  # Qt la range sur 8 bits
    barre = barre_visible(montre)
    a = animation(barre, "value", 60, loopCount=2, direction=QAbstractAnimation.Direction.Backward)
    a.start()
    valeurs = attendre(a, app, barre.value)
    assert barre.value() == 0 and max(valeurs) > 400 and valeurs[0] >= valeurs[-1]


def test_stop_pause_et_resume_de_l_application(app, montre):
    barre = barre_visible(montre)
    a = animation(barre, "value", 10_000)
    a.start()
    while barre.value() == 0:
        app.processEvents()
    a.stop()
    valeur = barre.value()
    for _ in range(20):
        app.processEvents()
    assert 0 < valeur == barre.value() < 880 and a.state() == Etat.Stopped and a._fenetre is None
    a = animation(barre, "value", 200)
    a.start()
    while barre.value() < 100:
        app.processEvents()
    a.pause()
    valeur, fin = barre.value(), time.perf_counter() + 0.05
    while time.perf_counter() < fin:
        app.processEvents()
    assert barre.value() == valeur and a.state() == Etat.Paused and a._fenetre is None
    a.resume()
    assert a.state() == Etat.Running and a._fenetre is None  # la minuterie de Qt a repris
    attendre(a, app)
    assert barre.value() == 880


@pytest.mark.parametrize("par_image", [True, False])
def test_sans_fenetre_ou_sans_par_image_qt_mene(app, montre, par_image):
    barre = barre_visible(montre) if not par_image else QtWidgets.QScrollBar()  # jamais montrée : pas de QWindow
    barre.setRange(0, 1000)
    a = animation(barre, "value", 60)
    a.par_image = par_image
    a.start()
    assert a.state() == Etat.Running and a._fenetre is None
    attendre(a, app)
    assert barre.value() == 880
