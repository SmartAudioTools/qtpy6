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
        self.hauteurs = {}  # heightForWidth par largeur : Qt la redemande des centaines de fois par redimensionnement
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
        if largeur not in self.hauteurs:
            self.hauteurs[largeur] = self._disposer(QRect(0, 0, largeur, 0), False)
        return self.hauteurs[largeur]

    def invalidate(self):
        """Un item ajouté, montré, caché ou dont la taille change : Qt appelle ceci, les hauteurs sont à recalculer."""
        self.hauteurs.clear()
        super().invalidate()

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

    def _mesurer(self):
        """Les items à ranger, ``(item, largeur, hauteur, extensible)`` d'après leur ``sizeHint`` ; ``None`` pour le
        ressort, les items vides écartés (un QSpacerItem est toujours « vide » pour Qt : un blanc fixe reste). Lu une fois
        par calcul, pas à chaque étape (l'ouverture d'un sujet calcule 3 400 fois ses 354 rangées). Pas d'un calcul à
        l'autre : Qt n'invalide une disposition imbriquée qu'en activant sa parente, et un sizeHint gardé jusque-là
        changeait la mise en page (python_tp, mesuré le 02/10/2026)."""
        mesures = []
        for item in self.items:
            large, blanc = bool(item.expandingDirections() & Qt.Orientation.Horizontal), item.spacerItem() is not None
            if blanc and large:
                mesures.append(None)
            elif blanc or not item.isEmpty():
                taille = item.sizeHint()
                mesures.append((item, taille.width(), taille.height(), large and not blanc))
        return mesures

    def _lignes(self, largeur, mesures):
        """Les lignes : des listes de mesures (``_mesurer``), coupées là où la suivante ne tient plus ; ``None`` marque
        le ressort."""
        lignes = self._couper(largeur, 0, mesures)
        extensibles = [m[1] for m in mesures if m is not None and m[3]]
        if self.uniforme and extensibles:
            egales = self._couper(largeur, max(extensibles), mesures)
            if len(egales) == len(lignes):
                return egales
        return lignes

    def _couper(self, largeur, large, mesures):
        """Les lignes, chaque item extensible compté au moins ``large``."""
        lignes, x, espace = [[]], 0, self.spacing()
        for m in mesures:
            if m is None:
                lignes[-1].append(None)
                continue
            l = max(m[1], large) if m[3] else m[1]
            if x and x + espace + l > largeur:
                lignes.append([])
                x = 0
            lignes[-1].append(m)
            x += (espace if x else 0) + l
        return lignes

    def _disposer(self, rect, poser):
        y = rect.y()
        for ligne in self._lignes(rect.width(), self._mesurer()):
            mesures = [m for m in ligne if m is not None]
            if not mesures:
                continue
            items = [m[0] for m in mesures]
            hauteur_ligne = max(m[2] for m in mesures)
            largeurs = [m[1] for m in mesures]
            extensibles = sorted((n for n, m in enumerate(mesures) if m[3]), key=lambda n: -largeurs[n])
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
