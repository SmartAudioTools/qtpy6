"""Une liste qu'on réordonne en glissant, à la souris comme au doigt (appui long) : ce que Qt fait en natif, avec son propre
``startDrag`` et sa boucle ``QDrag.exec``. ``lancer()`` est appelé par index.html (``?glisse``) ; ``tests/test_web.py``
(``test_glisser_depose``) y fait glisser un vrai pointeur WebDriver et lit l'ordre dans ``window.ordre``."""

import json

import js
from qtpy6 import QtCore, QtWidgets
from qtpy6.web import tactile


def lancer():
    global LISTE
    tactile.activer_au_doigt()  # au doigt (sonde --tactile), AppuiLong saisit
    LISTE = QtWidgets.QListWidget()
    LISTE.addItems(["A", "B", "C", "D"])
    LISTE.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
    LISTE.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
    LISTE.resize(300, 240)

    def saisir(position):  # au doigt, l'appui long lance le glisser de Qt (le geste des téléphones)
        element = LISTE.itemAt(position.toPoint())
        if element is not None:
            LISTE.setCurrentItem(element)
            js.window.saisi = "appui long"  # le test vérifie que c'est lui, pas le glissé de Qt, qui saisit
            LISTE.startDrag(QtCore.Qt.DropAction.MoveAction)

    tactile.AppuiLong(LISTE.viewport(), saisir)

    def publier(*_):
        js.window.ordre = "".join(LISTE.item(i).text() for i in range(LISTE.count()))

    modele = LISTE.model()
    for signal in (modele.rowsMoved, modele.rowsInserted, modele.rowsRemoved, modele.layoutChanged):
        signal.connect(lambda *_: QtCore.QTimer.singleShot(0, publier))
    publier()
    LISTE.show()


def centres():
    """Le centre de chaque ligne en coordonnées de la page (l'écran de Qt commence au canevas), en JSON."""
    canevas = max(js.document.querySelector("#qt-shadow-container").shadowRoot.querySelectorAll("canvas").to_py(),
                  key=lambda c: c.width * c.height)
    r, ecran = canevas.getBoundingClientRect(), LISTE.screen().geometry()
    points = []
    for i in range(LISTE.count()):
        g = LISTE.viewport().mapToGlobal(LISTE.visualItemRect(LISTE.item(i)).center())
        points.append([g.x() - ecran.left() + r.left, g.y() - ecran.top() + r.top])
    return json.dumps(points)
