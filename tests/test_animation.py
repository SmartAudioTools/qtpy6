"""AnimationParImage, hors écran : les UpdateRequest viennent de la minuterie de repli de Qt (5 ms)."""
from qtpy6 import QtCore, QtWidgets
from qtpy6.animation import AnimationParImage


def barre_visible(app):
    barre = QtWidgets.QScrollBar()
    barre.setRange(0, 1000)
    barre.show()
    app.processEvents()
    return barre


def attendre(animation, app):
    fini = []
    animation.finished.connect(lambda: fini.append(True))
    animation.start()
    while not fini:
        app.processEvents()


def test_avance_a_chaque_image_jusqu_a_la_fin(app):
    barre = barre_visible(app)
    valeurs = []
    barre.valueChanged.connect(valeurs.append)
    animation = AnimationParImage(barre, 'value', duree=100)
    animation.setStartValue(0)
    animation.setEndValue(880)
    attendre(animation, app)
    assert barre.value() == 880 and valeurs == sorted(valeurs) and len(valeurs) > 3
    assert animation._fenetre is None  # le filtre est retiré : plus d'image demandée


def test_courbe_et_flottants(app):
    fenetre = QtWidgets.QWidget()
    fenetre.show()
    app.processEvents()
    animation = AnimationParImage(fenetre, 'windowOpacity', duree=50, courbe=QtCore.QEasingCurve.Type.OutCubic)
    animation.setStartValue(1.0)
    animation.setEndValue(0.5)
    attendre(animation, app)
    assert abs(fenetre.windowOpacity() - 0.5) < 0.01  # Qt la range sur 8 bits


def test_stop_arrete_la(app):
    barre = barre_visible(app)
    animation = AnimationParImage(barre, 'value', duree=10_000)
    animation.setEndValue(1000)
    animation.start()
    while barre.value() == 0:
        app.processEvents()
    animation.stop()
    valeur = barre.value()
    for _ in range(20):
        app.processEvents()
    assert 0 < valeur == barre.value() < 1000


def test_sans_fenetre_la_valeur_finale(app):
    barre = QtWidgets.QScrollBar()  # jamais montrée : pas de QWindow
    barre.setRange(0, 1000)
    animation = AnimationParImage(barre, 'value')
    animation.setEndValue(500)
    fini = []
    animation.finished.connect(lambda: fini.append(True))
    animation.start()
    assert barre.value() == 500 and fini
