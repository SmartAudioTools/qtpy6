"""``QPropertyAnimation`` menée par les images de l'écran : la doublure que ``qtpy6.QtCore`` pose à la place de celle
de la liaison, sans rien changer à son API.

Qt Widgets ne cale pas ses animations sur l'écran : ``QPropertyAnimation`` avance à une minuterie de 16 ms, que rien
ne synchronise avec le rafraîchissement, si bien qu'une image en reçoit parfois deux pas (le premier n'est jamais
affiché) et la suivante aucun. Ici, quand la cible est un widget dont la fenêtre existe, ``start()`` retire aussitôt
l'animation de cette minuterie (``pause()`` : en pause, ``setCurrentTime`` pose encore la propriété et, au bout,
arrête l'animation comme en natif, ``finished`` compris) et la fait avancer à chaque ``UpdateRequest`` de la fenêtre,
obtenu par ``QWindow.requestUpdate`` : sur Wayland le rappel d'image du compositeur, dans le navigateur
``requestAnimationFrame``. À chaque image, la propriété prend la valeur de l'heure de cette image. Hors écran
(``offscreen``), Qt remplace le rappel par une minuterie de 5 ms : l'animation se déroule, plus finement, sans rien
prouver. Mesuré sur le lecteur de SmartTeacher (Wayland, 60 Hz, 1833 ms de défilement) : peintures perdues 4 → 0, pas
réguliers de 8 px au lieu d'alterner 7 et 8 (``QCM/outils/sonde_vsync_bureau.py``).

Tout le reste est celui de Qt : sans fenêtre (cible jamais montrée, ou qui n'est pas un widget), dans un groupe
(c'est lui qui mène), en boucle infinie, ou après un ``pause()``/``resume()`` de l'application, la minuterie de Qt
mène comme d'habitude. ``state()`` rend ``Running`` pendant qu'une image mène, et ``stateChanged`` ne dit rien de la
pause intérieure. ``par_image = False``, sur la classe ou sur une instance, rend l'animation de Qt telle quelle :

    QPropertyAnimation.par_image = False  # toute l'application : la minuterie de 16 ms de Qt

Une ``QPropertyAnimation`` créée par Qt lui-même (jamais en pratique) reste celle de la liaison."""
import time


def doubler(ns):
    """Pose ``QPropertyAnimation`` dans l'espace de noms de ``qtpy6.QtCore`` (appelé par lui, au chargement)."""
    Base, QEvent = ns["QPropertyAnimation"], ns["QEvent"]
    Etat, Sens = Base.State, Base.Direction

    class QPropertyAnimation(Base):
        par_image = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._fenetre = None  # celle dont les images mènent l'animation, de start() à la fin
            self._t0 = 0.0
            self.stateChanged.connect(self._etat)

        def start(self, *args):
            super().start(*args)
            cible = self.targetObject()
            fenetre = cible.window().windowHandle() if cible is not None and cible.isWidgetType() else None
            if (not self.par_image or fenetre is None or super().state() != Etat.Running or self.group() is not None
                    or self.loopCount() < 0):
                return
            self.blockSignals(True)  # la pause intérieure n'est pas un changement d'état pour l'application
            super().pause()
            self.blockSignals(False)
            self._fenetre, self._t0 = fenetre, time.perf_counter()
            fenetre.installEventFilter(self)
            fenetre.requestUpdate()

        def eventFilter(self, objet, evenement):
            if objet is self._fenetre and evenement.type() == QEvent.Type.UpdateRequest:
                total = self.totalDuration()
                t = min(round((time.perf_counter() - self._t0) * 1000), total)
                self.setCurrentTime(t if self.direction() == Sens.Forward else total - t)  # au bout : stop(), finished
                if super().state() == Etat.Stopped:
                    self._lacher()
                else:
                    objet.requestUpdate()
            return False

        def state(self):
            return Etat.Running if self._fenetre is not None else super().state()

        def pause(self):
            self._lacher()  # déjà en pause pour Qt : l'application reprendra par resume(), à sa minuterie
            super().pause()

        def resume(self):
            self._lacher()
            super().resume()

        def setPaused(self, en_pause):
            self.pause() if en_pause else self.resume()

        def stop(self):
            self._lacher()
            super().stop()

        def _etat(self, nouveau, ancien):
            if nouveau != Etat.Paused:  # arrêté ou repris autrement (cible détruite, setCurrentTime au bout…)
                self._lacher()

        def _lacher(self):
            fenetre, self._fenetre = self._fenetre, None
            if fenetre is not None:
                try:
                    fenetre.removeEventFilter(self)
                except RuntimeError:  # la fenêtre a été détruite pendant l'animation
                    pass

    QPropertyAnimation.__doc__ = __doc__
    QPropertyAnimation.__module__ = Base.__module__
    QPropertyAnimation.__qualname__ = "QPropertyAnimation"
    ns["QPropertyAnimation"] = QPropertyAnimation
