"""Des dispositions Qt qui se REPLIENT quand la place manque, ce que ``QHBoxLayout`` ne sait pas faire : il impose la
somme de ses colonnes comme largeur minimale, ce qui donne un ascenseur horizontal, ou un plancher de plusieurs centaines
de pixels à la fenêtre, à la largeur d'un téléphone (mesuré sur le lecteur de SmartTeacher : barre de boutons 574 px,
barre d'outils d'une console 357 px, fenêtre 451 px au minimum)."""

from qtpy6.QtCore import QRect, QSize, Qt
from qtpy6.QtWidgets import QLayout, QSizePolicy, QSpacerItem


class Disposition(QLayout):
    """Le minimum est le plus large des items, pas leur somme, et la hauteur suit la largeur (``heightForWidth``), que
    les dispositions parentes et la zone défilante savent remonter. Les sous-classes écrivent ``_disposer(rect, poser)`` :
    place les items dans ``rect`` si ``poser``, et rend la hauteur occupée dans tous les cas."""

    def __init__(self, espacement):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(espacement)
        self.items = []

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if 0 <= i < len(self.items) else None

    def takeAt(self, i):
        return self.items.pop(i) if 0 <= i < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, largeur):
        return self._disposer(QRect(0, 0, largeur, 0), False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        taille = QSize()
        for item in self.items:
            if not item.isEmpty():
                taille = taille.expandedTo(item.minimumSize())
        return taille

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._disposer(rect, True)


class Rangee(Disposition):
    """Une rangée de widgets qui passe à la ligne quand la place manque. Un ``addStretch`` y garde son sens : ce qui
    le suit est poussé à droite de sa ligne ; un ``addSpacing`` est un blanc fixe, comme dans un ``QHBoxLayout``. Les
    widgets de politique horizontale ``Expanding`` se partagent la largeur de leur ligne à parts égales, sauf un plus
    large que sa part, qui garde sa largeur. ``uniforme`` les coupe en lignes comme s'ils avaient tous la largeur du plus
    large, pour que les parts soient vraiment égales, mais seulement si cela ne coûte pas de ligne de plus : quand la
    place manque, chacun reprend la largeur de son texte."""

    def __init__(self, espacement, uniforme=False):
        super().__init__(espacement)
        self.uniforme = uniforme

    def addStretch(self):
        self.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

    def addSpacing(self, largeur):
        self.addItem(QSpacerItem(largeur, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

    def _lignes(self, largeur):
        """Les lignes : des listes d'items visibles, coupées là où le suivant ne tient plus ; ``None`` marque le ressort."""
        lignes = self._couper(largeur, 0)
        extensibles = [i.sizeHint().width() for i in self.items if self._extensible(i)]
        if self.uniforme and extensibles:
            egales = self._couper(largeur, max(extensibles))
            if len(egales) == len(lignes):
                return egales
        return lignes

    def _couper(self, largeur, large):
        """Les lignes, chaque item extensible compté au moins ``large``."""
        lignes, x = [[]], 0
        for item in self.items:
            if item.isEmpty():
                continue
            if item.spacerItem() is not None and item.expandingDirections() & Qt.Orientation.Horizontal:
                lignes[-1].append(None)
                continue
            l = max(item.sizeHint().width(), large if self._extensible(item) else 0)
            if x and x + self.spacing() + l > largeur:
                lignes.append([])
                x = 0
            lignes[-1].append(item)
            x += (self.spacing() if x else 0) + l
        return lignes

    @staticmethod
    def _extensible(item):
        return not item.isEmpty() and item.spacerItem() is None and bool(item.expandingDirections() & Qt.Orientation.Horizontal)

    def _disposer(self, rect, poser):
        y = rect.y()
        for ligne in self._lignes(rect.width()):
            items = [i for i in ligne if i is not None]
            if not items:
                continue
            hauteur_ligne = max(i.sizeHint().height() for i in items)
            largeurs = [i.sizeHint().width() for i in items]
            extensibles = sorted((n for n, i in enumerate(items) if i.expandingDirections() & Qt.Orientation.Horizontal),
                                 key=lambda n: -largeurs[n])
            libre = (rect.width() - self.spacing() * (len(items) - 1)
                     - sum(l for n, l in enumerate(largeurs) if n not in extensibles))
            for k, n in enumerate(extensibles):  # les plus larges d'abord : qui dépasse la part égale garde sa largeur
                largeurs[n] = max(largeurs[n], libre // (len(extensibles) - k))
                libre -= largeurs[n]
            x, apres = rect.x(), None
            if None in ligne:  # ce qui suit le ressort, calé à droite s'il y a la place
                apres = ligne.index(None)
                x_droite = rect.right() + 1 - sum(largeurs[apres:]) - self.spacing() * max(len(items) - apres - 1, 0)
            for n, item in enumerate(items):
                if n == apres:
                    x = max(x, x_droite)
                if poser:
                    item.setGeometry(QRect(x, y, largeurs[n], hauteur_ligne))
                x += largeurs[n] + self.spacing()
            y += hauteur_ligne + self.spacing()
        return y - rect.y() - (self.spacing() if y > rect.y() else 0)
