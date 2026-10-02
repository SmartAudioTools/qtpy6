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
    ressorts d'une même ligne s'en partagent la place libre à parts égales, comme dans un ``QHBoxLayout`` : un ressort
    entre chaque widget les espace régulièrement. Les widgets de politique horizontale ``Expanding`` se partagent la
    largeur de leur ligne à parts égales, sauf un plus large que sa part, qui garde sa largeur. Avec ``elargir``, ils
    gardent au contraire leur largeur et chacun reçoit la même part de la place libre, comme dans un ``QHBoxLayout`` :
    des boutons sans cadre au texte centré s'y espacent comme avec un ressort entre deux, mais la zone qui réagit au
    pointeur couvre l'écart."""

    def __init__(self, espacement, elargir=False):
        super().__init__(espacement)
        self.elargir = elargir

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
        lignes, x, espace = [[]], 0, self.spacing()
        for m in mesures:
            if m is None:
                lignes[-1].append(None)
                continue
            l = m[1]
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
            if self.elargir:  # la place libre ajoutée à chacun, à parts égales
                libre -= sum(largeurs[n] for n in extensibles)
                for k, n in enumerate(extensibles):
                    largeurs[n] += max(libre, 0) * (k + 1) // len(extensibles) - max(libre, 0) * k // len(extensibles)
            else:
                for k, n in enumerate(extensibles):  # les plus larges d'abord : qui dépasse la part égale garde sa largeur
                    largeurs[n] = max(largeurs[n], libre // (len(extensibles) - k))
                    libre -= largeurs[n]
            # la place libre aux ressorts, à parts égales (rien quand elle manque)
            reste, ressorts = max(rect.width() - sum(largeurs) - self.spacing() * (len(items) - 1), 0), ligne.count(None)
            x, n, r = rect.x(), 0, 0
            for m in ligne:
                if m is None:
                    x += reste * (r + 1) // ressorts - reste * r // ressorts
                    r += 1
                    continue
                if poser:
                    m[0].setGeometry(QRect(x, y, largeurs[n], hauteur_ligne))
                x += largeurs[n] + self.spacing()
                n += 1
            y += hauteur_ligne + self.spacing()
        return y - rect.y() - (self.spacing() if y > rect.y() else 0)
