"""Une longue page défilante paresseuse : ce qui est loin de la vue ne coûte presque rien.

Les éléments empilés dans une ``QScrollArea`` passent par trois états : pas encore bâtis, endormis, éveillés.

- **Bâtir.** Un élément peut naître vide, ses widgets remis à plus tard : il a alors un attribut ``batie`` faux et une
  méthode ``batir()`` qui les crée (et met ``batie`` à vrai). Un ``Chantier`` les bâtit en tâche de fond, par tranches
  de ``TRANCHE`` secondes rendues à la boucle d'événements entre deux, et s'arrête tant qu'une page paresseuse défile :
  une tranche dépasse son budget d'un élément entier, ce qui se voit comme un saut pendant une animation de défilement.
  Dans le navigateur, une tranche attend l'image suivante (``requestAnimationFrame``) : enchaînées par la boucle
  d'événements, deux tranches passaient souvent dans la même image, que la page ne peignait qu'après.
  Un élément qui entre dans la vue avant son tour est bâti aussitôt par sa page.
- **Endormir.** La disposition (``QLayout.setEnabled(False)``) des éléments à plus de ``MARGE`` hauteurs de vue est
  désactivée : un redimensionnement de la fenêtre ne remet plus en page que ceux de l'écran.
- **Éveiller.** Un élément qui approche de la vue retrouve sa disposition.

Bâti ou éveillé, un élément change de hauteur : le défilement est compensé pour que ce qui est à l'écran ne bouge pas.

Mesuré sur le lecteur QCM de SmartTeacher (02/10/2026) : 85 questions, 20 redimensionnements 968 → 480 ms hors écran ;
218 questions bâties en tâche de fond, ouverture 2,2 s plus courte dans le navigateur ; la première descente du sujet de
bac sautait de 27 à 69 px quand le chantier ne s'arrêtait pas pendant le défilement, 8 px sinon. Une tranche par image
dans Firefox (04/10/2026, 217 questions de python_tp) : 186 à 207 images au lieu de 119 à 140 pendant la construction,
image médiane 33 à 49 ms au lieu de 66, construction 7,8 s au lieu de 7,5."""

import math
import time

from qtpy6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QTimer, Signal
from qtpy6.web import navigateur


class Paresse(QObject):
    """La paresse d'une zone défilante (``zone.paresse``) sur ``elements``, les widgets empilés dans son contenu.

    ``minuteries(elements)`` se redéfinit quand des widgets remettent une partie de leur mise en page à une minuterie
    (``QTimer``) : la compensation du défilement les achève sur-le-champ, pour se faire sur des positions définitives."""

    MARGE = 1  # en hauteurs de vue, au-dessus et au-dessous de l'écran
    defile = 0.0  # l'instant (``time.perf_counter``) du dernier défilement d'une page paresseuse : le ``Chantier`` attend

    def __init__(self, zone, elements):
        super().__init__(zone)
        self.zone, self.contenu, self.elements = zone, zone.widget(), elements
        zone.paresse = self
        barre = zone.verticalScrollBar()
        barre.valueChanged.connect(Paresse._defiler)
        barre.valueChanged.connect(self.rafraichir)
        zone.viewport().installEventFilter(self)
        self.rafraichir()

    @staticmethod
    def _defiler():
        Paresse.defile = time.perf_counter()

    def eventFilter(self, objet, evenement):
        if evenement.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self, self.rafraichir)  # après la mise en page que ce Resize déclenche
        return False

    def minuteries(self, elements):
        """Les ``(minuterie, slot)`` dont la mise en page de ``elements`` attend la fin."""
        return []

    def contient(self, element):
        return self.contenu.isAncestorOf(element)

    def _haut(self, e):
        return e.mapTo(self.contenu, QPoint()).y() - self.zone.verticalScrollBar().value()

    def _en_vue(self, e, marge=MARGE):
        vue, haut = self.zone.viewport().height(), self._haut(e)
        return haut + e.height() > -marge * vue and haut < (1 + marge) * vue

    def _repere(self):
        """Le premier élément visible et sa hauteur dans la vue : ``_recaler`` l'y garde."""
        repere = next((e for e in self.elements if self._haut(e) + e.height() > 0), None)
        return repere, self._haut(repere) if repere else 0

    def batir(self, elements, fin=math.inf):
        """Bâtit les ``elements`` de tête qui sont dans cette page, qu'il retire de la liste, jusqu'à l'instant ``fin``
        (``time.perf_counter``), sans que ce qui est à l'écran ne bouge : un seul recalage pour tous. Hors de la vue,
        une disposition gelée ne prévient pas son parent : l'élément y garderait la hauteur de l'élément vide."""
        repere, avant = self._repere()
        baties = []
        while elements and time.perf_counter() < fin and self.contient(elements[0]):
            baties.append(e := elements.pop(0))
            e.batir()
            e.updateGeometry()
        if baties and self._haut(baties[0]) < self.zone.viewport().height():  # sous la vue, rien ne bouge à l'écran
            self._recaler(baties, repere, avant)

    def rafraichir(self):
        # un élément encore à bâtir n'a pas de hauteur : bâtis un à un, ceux de l'écran repoussent les suivants
        while self.zone.isVisible() and (e := next((e for e in self.elements if not getattr(e, "batie", True)
                                                    and self._en_vue(e, 0)), None)):
            self.batir([e])
        repere, avant = self._repere()
        reveilles = []
        for e in self.elements:
            disposition, en_vue = e.layout(), self._en_vue(e)
            if disposition is None:
                continue
            if en_vue and not disposition.isEnabled():
                disposition.setEnabled(True)
                disposition.invalidate()
                # un LayoutRequest reçu désactivée l'a laissée « à refaire », état où Qt n'en reposte plus : sans cet
                # appel, un élément gelé dès la construction de la page ne serait jamais mis en page
                disposition.activate()
                reveilles.append(e)
            elif not en_vue and disposition.isEnabled():
                disposition.setEnabled(False)
        if reveilles:
            self._recaler(reveilles, repere, avant)

    def _recaler(self, elements, repere, avant):
        if repere:
            # la hauteur corrigée remonte niveau par niveau (élément, parents, contenu, zone défilante), chacun par un
            # LayoutRequest différé, et des widgets finissent leur mise en page par une minuterie : tout est fait tout
            # de suite, pour compenser le défilement sur des positions définitives
            minuteries = self.minuteries(elements)
            for _ in range(5):
                QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
                for minuterie, slot in minuteries:
                    if minuterie.isActive():
                        minuterie.stop()
                        slot()
            barre = self.zone.verticalScrollBar()
            if barre.value():  # tout en haut, ce qui grandit est dans la vue : la compensation la ferait descendre
                barre.setValue(barre.value() + self._haut(repere) - avant)


class Chantier(QObject):
    """Bâtit en tâche de fond, dans l'ordre, les ``elements`` pas encore bâtis (``batie`` faux) ; ``reste`` est ce qui
    reste à bâtir, ``fini`` est émis quand il n'y a plus rien. Un élément rangé dans une page paresseuse est bâti par
    elle (le défilement compensé) ; un élément hors de toute page (caché, en attente d'être placé) est bâti seul."""

    fini = Signal()
    TRANCHE = 0.02  # en s : la durée d'une tranche, entre deux passages par la boucle d'événements
    REPOS = 0.2  # en s : le chantier attend que le défilement soit arrêté depuis ce temps-là

    def __init__(self, parent, elements):
        super().__init__(parent)
        self.reste = [e for e in elements if not getattr(e, "batie", True)]
        if self.reste:
            QTimer.singleShot(0, self, self.tranche)

    @staticmethod
    def _page(element):
        w = element.parentWidget()
        while w is not None and not isinstance(getattr(w, "paresse", None), Paresse):
            w = w.parentWidget()
        return w and w.paresse

    def tranche(self):
        if (attente := Paresse.defile + self.REPOS - time.perf_counter()) > 0:
            QTimer.singleShot(math.ceil(attente * 1000), self, self.tranche)
            return
        fin = time.perf_counter() + self.TRANCHE
        while self.reste and time.perf_counter() < fin:
            if page := self._page(self.reste[0]):
                page.batir(self.reste, fin)
            else:
                self.reste.pop(0).batir()
        if not self.reste:
            self.fini.emit()
        elif navigateur():
            import js  # noqa: PLC0415 - Pyodide seulement
            from pyodide.ffi import create_once_callable  # noqa: PLC0415

            js.requestAnimationFrame(create_once_callable(lambda _: QTimer.singleShot(0, self, self.tranche)))
        else:
            QTimer.singleShot(0, self, self.tranche)
