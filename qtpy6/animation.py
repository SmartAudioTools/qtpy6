"""Une animation menée par les images de l'écran, là où ``QPropertyAnimation`` avance à la minuterie de 16 ms de Qt.

Qt Widgets ne cale pas ses animations sur l'écran : ``QPropertyAnimation`` avance à une minuterie de 16 ms, que
rien ne synchronise avec le rafraîchissement, si bien qu'une image en reçoit parfois deux pas (le premier n'est
jamais affiché) et la suivante aucun. ``AnimationParImage`` avance au contraire à chaque ``UpdateRequest`` de la
fenêtre, obtenu par ``QWindow.requestUpdate`` : sur Wayland le rappel d'image du compositeur, dans le navigateur
``requestAnimationFrame``. À chaque image, la propriété prend la valeur de l'heure de cette image (durée et courbe
de ``QEasingCurve``), puis l'image suivante est demandée. Hors écran (``offscreen``), Qt remplace le rappel par une
minuterie de 5 ms : l'animation se déroule, plus finement, sans rien prouver.

Mesuré sur le lecteur de SmartTeacher (Wayland, 60 Hz, 1833 ms de défilement) : peintures perdues 4 → 0 ou 1, et
des pas réguliers de 8 px au lieu d'alterner 7 et 8 (``QCM/outils/sonde_vsync_bureau.py``).

    descente = AnimationParImage(barre, 'value', parent, duree=450, courbe=QEasingCurve.Type.OutCubic)
    descente.setStartValue(0); descente.setEndValue(880); descente.start()

La cible est un widget ; tant que sa fenêtre n'est pas créée (jamais montrée), elle reçoit la valeur finale tout de
suite : rien n'est à l'écran pour voir une animation."""
import time

from .QtCore import QEasingCurve, QEvent, QObject, Signal


class AnimationParImage(QObject):
    finished = Signal()

    def __init__(self, cible, propriete, parent=None, duree=250, courbe=QEasingCurve.Type.Linear):
        super().__init__(parent)
        self.cible, self.propriete, self.duree, self.courbe = cible, propriete, duree, QEasingCurve(courbe)
        self.debut = self.fin = 0
        self._fenetre = None  # celle qui reçoit les UpdateRequest, le temps de l'animation
        self._t0 = 0.0

    def setStartValue(self, valeur):
        self.debut = valeur

    def setEndValue(self, valeur):
        self.fin = valeur

    def start(self):
        self.stop()
        fenetre = self.cible.window().windowHandle()
        if fenetre is None:
            self._poser(1.0)
            self.finished.emit()
            return
        self._fenetre = fenetre
        self._t0 = time.perf_counter()
        fenetre.installEventFilter(self)
        fenetre.requestUpdate()

    def stop(self):
        if self._fenetre is not None:
            self._fenetre.removeEventFilter(self)
            self._fenetre = None

    def _poser(self, x):
        valeur = self.debut + (self.fin - self.debut) * self.courbe.valueForProgress(x)
        if isinstance(self.debut, int) and isinstance(self.fin, int):
            valeur = round(valeur)
        self.cible.setProperty(self.propriete, valeur)

    def eventFilter(self, objet, evenement):
        if objet is self._fenetre and evenement.type() == QEvent.Type.UpdateRequest:
            x = min(1.0, (time.perf_counter() - self._t0) * 1000 / self.duree)
            self._poser(x)
            if x < 1:
                objet.requestUpdate()
            else:
                self.stop()
                self.finished.emit()
        return False
