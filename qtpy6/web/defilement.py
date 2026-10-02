"""``ZoneDefilante`` : une QScrollArea dont le défilement, dans le navigateur, ne repeint que la bande qui entre.

Qt-WASM n'a pas de défilement de surface (``QWasmBackingStore`` n'a pas de ``scroll()``) : chaque pas de défilement y
repeint TOUT le viewport, et chaque pixel coûte en WebAssembly. Mesuré sur le lecteur de SmartTeacher le 02/10/2026,
à l'échelle 2 (1772 × 1494 px) : 12 à 28 ms par image, là où l'écran en accorde 16,7, d'où des images perdues pendant une
animation de défilement. En natif, ``QRasterBackingStore::scroll`` décale les pixels de sa surface et seule la bande
nouvelle est peinte, ce qui explique qu'à la même échelle le bureau ne bronche pas.

Ici, le geste du natif, fait à la main : le contenu est déplacé sans que Qt ne salisse rien (``WA_UpdatesDisabled`` sur le
contenu le temps du déplacement), la bande qui entre est demandée au contenu, et à l'``UpdateRequest`` qui précède la
peinture de l'image, les lignes de l'image de Qt (celle du backing store) qui couvrent le viewport sont décalées ligne à
ligne, sur la largeur du viewport seulement (rien d'autre ne bouge, ni la barre de défilement, ni ce qui borde la zone).
Qt peint alors la bande, puis recopie dans l'image qu'il montre (un ``ImageData``, envoyé entier au canevas à chaque
image) le rectangle ENGLOBANT de tout ce qui a été peint depuis l'image précédente : la bande d'un côté et un pixel de
l'autre coin du viewport, demandé exprès, font que c'est le viewport entier, désormais juste, qui est recopié (mesuré
sur Qt 6.10.2, échelles 1 et 2 : bande + barre de défilement donnent une seule recopie, le viewport ; la bande seule,
elle seule). L'image de Qt n'est atteignable que pendant un Paint (le ``paintDevice()`` du moteur de peinture d'un
widget) : elle est relevée une fois, au premier Paint qui suit une ``UpdateRequest`` de la fenêtre (le Paint d'un
``render()`` ou d'un ``grab()`` peindrait ailleurs, dans un QPixmap), et gardée, l'objet C++ vivant autant que le
backing store (lâchée si la fenêtre se cache ou change de fenêtre native, et vérifiée à sa taille avant chaque usage).

*Mesuré, et à savoir : ``QWasmBackingStore::beginPaint`` EFFACE (transparent) la région à peindre avant que les widgets
ne peignent, et c'est pourquoi le décalage se fait à l'``UpdateRequest`` et non au Paint : fait au Paint, il recopiait
la bande déjà effacée seize lignes plus haut, une raie blanche à chaque pas. ``viewport().update(rect)`` ne repeint
RIEN quand le contenu opaque couvre le viewport (Qt retranche les enfants opaques de la région à peindre et ne la
propage pas à l'enfant), ``window().update(rect)`` pas davantage : la bande se demande au widget de contenu lui-même, et
la zone découverte, s'il y en a une, au viewport. Écartés, mesurés avant : décaler le canevas lui-même par ``drawImage``
(Qt-WASM l'écrase entier à chaque image) ; décaler l'``ImageData`` attrapé au passage de ``putImageData`` (juste tant
que Qt n'y recopie que la bande, mais dès que la barre de défilement est peinte dans la même image, Qt recopie le
viewport entier depuis son image, restée ancienne : un patchwork).*

Ce que ce raccourci laisse derrière lui : un ``repaint()`` entre le pas et l'image suivante peint avant le décalage, et
tout est alors repeint à l'image suivante (juste, mais au prix d'un repeint complet). Le raccourci ne s'applique qu'à un
pas vertical plus petit que le viewport, à une échelle entière (à 1,25 ou 1,5 le décalage tomberait entre deux lignes)
et une fois l'image de Qt relevée ; sinon, et en natif, une QScrollArea ordinaire."""

from qtpy6.QtCore import QEvent, QPoint, QRect, Qt
from qtpy6.QtGui import QImage, QPainter
from qtpy6.QtWidgets import QApplication, QScrollArea, QWidget

from . import navigateur

ACTIF = True  # False : le défilement ordinaire de Qt-WASM, pour le mesurer contre celui-ci (sonde de SmartTeacher)


class ZoneDefilante(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dy = 0  # décalage du viewport (px logiques, vers le bas si positif) dû à l'image de Qt à la prochaine image
        self._image = None  # l'image du backing store, relevée au premier Paint qui suit une UpdateRequest de la fenêtre
        self._attend = False  # une UpdateRequest vient de passer : le Paint qui suit peint dans l'image de Qt
        if ACTIF and navigateur():  # l'UpdateRequest va à la QWindow, les Paint à chaque widget : un filtre sur tout
            QApplication.instance().installEventFilter(self)  # (en natif, il ralentissait tout : test_aide 39 s → > 5 min)

    def scrollContentsBy(self, dx, dy):
        contenu, vue = self.widget(), self.viewport()
        r = vue.devicePixelRatioF()
        if not ACTIF or not navigateur() or dx or not dy or contenu is None or not contenu.updatesEnabled() or r != int(r):
            self._dy = 0
            super().scrollContentsBy(dx, dy)
            return
        contenu.setAttribute(Qt.WidgetAttribute.WA_UpdatesDisabled, True)
        try:
            super().scrollContentsBy(dx, dy)  # le contenu est déplacé, rien n'est marqué sale
        finally:
            contenu.setAttribute(Qt.WidgetAttribute.WA_UpdatesDisabled, False)
        self._dy += dy  # un pas avant que le précédent ne soit peint : les deux se cumulent, bande comprise
        if abs(self._dy) >= vue.height():
            self._dy = 0
            self._repeindre(vue.rect())
            return
        bande = abs(self._dy)
        self._repeindre(QRect(0, 0 if self._dy > 0 else vue.height() - bande, vue.width(), bande))
        coin = QPoint(vue.width() - 1, vue.height() - 1) if self._dy > 0 else QPoint(0, 0)
        self._repeindre(QRect(coin, coin))  # l'englobant de ce qui est peint = le viewport entier, recopié d'un bloc

    def _repeindre(self, rect):
        """``rect`` du viewport : au contenu (seul à peindre ce qu'il couvre) et au viewport (le reste, découvert)."""
        self.widget().update(rect.translated(-self.widget().pos()))
        self.viewport().update(rect)

    def eventFilter(self, objet, evenement):
        t = evenement.type()
        fenetre = self.window()
        if t == QEvent.Type.UpdateRequest:
            if objet is fenetre.windowHandle():  # la QWindow seule : à celui du widget de fenêtre, 338 pixels faux (mesuré)
                self._attend = self._image is None
                if self._dy:
                    self._decaler_image()
        elif t == QEvent.Type.Paint:
            if self._attend and isinstance(objet, QWidget) and objet.window() is fenetre:
                self._image, self._attend = _image(objet), False
            if self._dy:  # peint sans UpdateRequest (exposition, redimensionnement) : rien n'est décalé, tout est à repeindre
                self._dy = 0
                self.widget().update()
        elif self._attend:
            self._attend = False  # autre chose qu'un Paint a suivi l'UpdateRequest : un Paint ultérieur serait un render()
        elif objet is fenetre and t in (QEvent.Type.Hide, QEvent.Type.WinIdChange):
            self._image = None  # le backing store peut être recréé : l'image sera relevée de nouveau
        return False

    def _decaler_image(self):
        """Avant que Qt ne peigne : les lignes du viewport décalées dans son image, ou tout repeint si elle manque."""
        dy, self._dy = self._dy, 0
        vue = self.viewport()
        r = int(vue.devicePixelRatioF())
        if self._image is None or self._image.size() != vue.window().size() * r:
            self.widget().update()
            return
        p = vue.mapTo(vue.window(), QPoint(0, 0))
        decaler_lignes(self._image, p.x() * r, p.y() * r, vue.width() * r, vue.height() * r, dy * r)


def _image(widget):
    """L'image du backing store, pendant un Paint de ``widget`` : le périphérique du moteur de peinture, que PyQt6 et
    PySide6 rendent sous sa classe de base QPaintDevice (sans ``devType`` dans le navigateur : transtypé à l'aveugle,
    c'est à l'appelant de vérifier ses dimensions) ; None s'il n'est pas atteignable."""
    peintre = QPainter(widget)
    if not peintre.isActive():
        return None
    peripherique = peintre.paintEngine().paintDevice()
    peintre.end()
    if peripherique is None or isinstance(peripherique, QImage):
        return peripherique
    try:
        from PyQt6 import sip  # noqa: PLC0415 - PyQt6 seulement
        return sip.cast(peripherique, QImage)
    except ImportError:
        pass
    try:
        import shiboken6  # noqa: PLC0415 - PySide6 seulement
        return shiboken6.wrapInstance(shiboken6.getCppPointer(peripherique)[0], QImage)
    except ImportError:
        return None


def decaler_lignes(image, x, y, l, h, dy):
    """Décale de ``dy`` lignes (vers le bas si positif) le rectangle ``x, y, l, h`` de ``image`` (32 bits par pixel), en
    pixels physiques : ce qui sort du rectangle est perdu, les ``dy`` lignes qui entrent gardent ce qu'elles avaient."""
    octets = image.bits()
    if hasattr(octets, "setsize"):  # PyQt6 : un sip.voidptr sans taille ; PySide6 rend déjà un memoryview
        octets.setsize(image.sizeInBytes())
        octets = memoryview(octets)
    pas, a, n = image.bytesPerLine(), x * 4, l * 4
    for i in range(y + h - 1, y + dy - 1, -1) if dy > 0 else range(y, y + h + dy):
        octets[i * pas + a:i * pas + a + n] = octets[(i - dy) * pas + a:(i - dy) * pas + a + n]
