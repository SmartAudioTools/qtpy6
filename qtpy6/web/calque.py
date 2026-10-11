"""Un élément HTML de la page calé sur un widget (``Calque``) : la base des doublures dont le contenu est dessiné par le
navigateur au-dessus du canevas de Qt, ``QPdfView`` (``pdf``) et ``QWebEngineView`` (``moteur_web``)."""

from __future__ import annotations

from qtpy6.QtCore import QPoint, QTimer
from qtpy6.QtWidgets import QApplication, QWidget


class Calque(QWidget):
    """Appelle ``_placer(x, y, largeur, hauteur, visible)`` (coordonnées de la page) à chaque changement de place.
    L'élément n'est visible que quand le widget se voit, est activé (un widget désactivé cache son élément : un rideau
    posé par ``setEnabled(False)`` le couvre) et qu'aucune boîte modale d'une autre fenêtre ni menu n'est ouvert, que Qt
    dessinerait dessous."""

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._place = None
        # Le filet : ce qu'aucun événement du widget ne signale (un ancêtre qui bouge, une boîte modale, un menu)
        self._minuterie = QTimer(self, interval=100, timeout=self._synchroniser)
        self._minuterie.start()

    def _placer(self, x: float, y: float, largeur: int, hauteur: int, visible: bool) -> None:
        raise NotImplementedError

    def _synchroniser(self) -> None:
        import js  # noqa: PLC0415

        modale = QApplication.activeModalWidget()
        visible = (self.isVisible() and self.isEnabled() and QApplication.activePopupWidget() is None
                   and modale in (None, self.window()))
        coin = self.mapToGlobal(QPoint(0, 0)) - self.screen().geometry().topLeft()
        boite = js.window.qtpy6Conteneur.getBoundingClientRect()
        place = (coin.x() + boite.left, coin.y() + boite.top, self.width(), self.height(), visible)
        if place != self._place:
            self._place = place
            self._placer(*place)

    def showEvent(self, evenement):
        super().showEvent(evenement)
        self._synchroniser()

    def hideEvent(self, evenement):
        super().hideEvent(evenement)
        self._synchroniser()

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        self._synchroniser()

    def changeEvent(self, evenement):
        super().changeEvent(evenement)
        self._synchroniser()
