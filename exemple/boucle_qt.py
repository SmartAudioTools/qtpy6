"""Une boucle de Qt (``QDrag.exec``) ouverte par une minuterie : le cas de l'appui long au doigt. Le slot du ``QTimer``,
appelé pendant la pompe de ``bloquant``, y est reporté dans une tâche (``_plus_tard``) ; Qt doit pouvoir y suspendre sa
boucle imbriquée, sinon il refuse en boucle et la page se fige (05/10/2026). ``lancer()`` est appelé par index.html
(``?boucle``). Personne ne lâche : un glisser web ne finit qu'au pointerup d'un vrai pointeur (WebDriver), que la page
n'imite pas (un PointerEvent synthétique laisse ``exec`` suspendu, essayé le 05/10/2026)."""

import js
from qtpy6 import QtCore, QtGui, QtWidgets


def lancer():
    global FENETRE
    FENETRE = QtWidgets.QLabel("glisser ouvert par une minuterie")
    FENETRE.show()

    def glisser():
        drag = QtGui.QDrag(FENETRE)
        donnees = QtCore.QMimeData()
        donnees.setText("x")
        drag.setMimeData(donnees)
        js.window.boucle_qt = "ouverte"
        action = drag.exec(QtCore.Qt.DropAction.MoveAction)
        js.window.boucle_qt = f"rendue {action.name}"

    QtCore.QTimer.singleShot(300, glisser)
