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
Qt peint alors la bande, mais ne recopie vers le canevas que ce qu'il a peint : le viewport décalé lui est donc envoyé
explicitement (``backingStore().flush``). Sans cet envoi, la bande seule arrivait à l'écran et le reste du viewport y
restait à l'ancienne position (mesuré le 02/10/2026 sur le bac à l'échelle 2 : jusqu'à 1,2 million de pixels faux
pendant une animation, vu aussi par l'utilisateur sur son écran) ; l'ancien moyen, un pixel du coin opposé demandé pour
que l'englobant recopié soit le viewport entier, ne suffit pas sur le chemin de la pompe d'animation.
L'image de Qt n'est atteignable que pendant un Paint (le ``paintDevice()`` du moteur de peinture d'un widget) : elle
est relevée une fois, au premier Paint qui suit une ``UpdateRequest`` de la fenêtre (le Paint d'un ``render()`` ou
d'un ``grab()`` peindrait ailleurs, dans un QPixmap), et gardée, l'objet C++ vivant autant que le backing store (lâchée
si la fenêtre se cache ou change de fenêtre native, et vérifiée à sa taille avant chaque usage).

*Mesuré, et à savoir : ``QWasmBackingStore::beginPaint`` EFFACE (transparent) la région à peindre avant que les widgets
ne peignent, et c'est pourquoi le décalage se fait à l'``UpdateRequest`` et non au Paint : fait au Paint, il recopiait
la bande déjà effacée seize lignes plus haut, une raie blanche à chaque pas. ``viewport().update(rect)`` ne repeint
RIEN quand le contenu opaque couvre le viewport (Qt retranche les enfants opaques de la région à peindre et ne la
propage pas à l'enfant), ``window().update(rect)`` pas davantage : la bande se demande au viewport ET à chacun de ses
descendants qu'elle touche (``_salir`` : le contenu retranche à son tour ses propres enfants opaques, l'en-tête d'un
QTableWidget, qui restait vide sur l'écran réel). Écartés, mesurés avant : décaler le canevas lui-même par ``drawImage``
(Qt-WASM l'écrase entier à chaque image) ; décaler l'``ImageData`` attrapé au passage de ``putImageData`` (juste tant
que Qt n'y recopie que la bande, mais dès que la barre de défilement est peinte dans la même image, Qt recopie le
viewport entier depuis son image, restée ancienne : un patchwork).*

Ce que ce raccourci laisse derrière lui : un ``repaint()`` entre le pas et l'image suivante peint avant le décalage, et
tout est alors repeint à l'image suivante (juste, mais au prix d'un repeint complet). Le raccourci ne s'applique qu'à un
pas vertical plus petit que le viewport, à une échelle entière (à 1,25 ou 1,5 le décalage tomberait entre deux lignes)
et une fois l'image de Qt relevée ; sinon, et en natif, une QScrollArea ordinaire."""

from qtpy6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from qtpy6.QtGui import QImage, QPainter, QRegion
from qtpy6.QtWidgets import QApplication, QScrollArea, QWidget

from . import navigateur

ACTIF = True  # False : le défilement ordinaire de Qt-WASM, pour le mesurer contre celui-ci (sonde de SmartTeacher)


class ZoneDefilante(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dy = 0  # décalage du viewport (px logiques, vers le bas si positif) dû à l'image de Qt à la prochaine image

    def scrollContentsBy(self, dx, dy):
        contenu, vue = self.widget(), self.viewport()
        r = vue.devicePixelRatioF()
        if not ACTIF or not navigateur() or dx or not dy or contenu is None or not contenu.updatesEnabled() or r != int(r):
            self._poser(0)
            super().scrollContentsBy(dx, dy)
            return
        _Relais.installer()  # au premier pas seulement : construire un écran sous un filtre d'application, c'était
        # 138 000 appels Python avant le premier affichage (lecteur de SmartTeacher, mesuré le 02/10/2026)
        contenu.setAttribute(Qt.WidgetAttribute.WA_UpdatesDisabled, True)
        try:
            super().scrollContentsBy(dx, dy)  # le contenu est déplacé, rien n'est marqué sale
        finally:
            contenu.setAttribute(Qt.WidgetAttribute.WA_UpdatesDisabled, False)
        self._poser(self._dy + dy)  # un pas avant que le précédent ne soit peint : les deux se cumulent, bande comprise
        if abs(self._dy) >= vue.height():
            self._poser(0)
            _salir(vue, vue.rect())
            return
        bande = abs(self._dy)
        _salir(vue, QRect(0, 0 if self._dy > 0 else vue.height() - bande, vue.width(), bande))

    def _poser(self, dy):
        """``_dy``, et la zone inscrite au relais tant qu'il est non nul : seules celles-là y sont visitées."""
        self._dy = dy
        if _Relais.seul is not None:
            (_Relais.seul.decalees.add if dy else _Relais.seul.decalees.discard)(self)

    def _decaler_image(self, image):
        """Avant que Qt ne peigne : les lignes du viewport décalées dans ``image``, ou tout repeint si elle manque."""
        dy = self._dy
        self._poser(0)
        vue = self.viewport()
        r = int(vue.devicePixelRatioF())
        if image is None or image.size() != vue.window().size() * r:
            _salir(vue, vue.rect())
            return
        p = vue.mapTo(vue.window(), QPoint(0, 0))
        decaler_lignes(image, p.x() * r, p.y() * r, vue.width() * r, vue.height() * r, dy * r)
        # Qt-WASM n'envoie au canevas que ce qu'il peint : les lignes décalées hors de la bande, il faut les lui envoyer
        vue.window().backingStore().flush(QRegion(QRect(p, vue.size())), vue.window().windowHandle())


def _salir(widget, rect):
    """``rect`` à repeindre dans ``widget`` ET dans chaque descendant qu'il touche. Qt retire de la région d'un widget
    ses enfants opaques (``autoFillBackground`` : l'en-tête d'un QTableWidget) sans la leur transmettre, ce qui suppose
    leurs pixels intacts ; ici ils ont été décalés ou effacés, et l'en-tête restait vide (vu sur l'écran réel le
    02/10/2026 sur le bac, 115 000 pixels contre ``grab()``). Seuls les enfants que touche la bande sont visités."""
    widget.update(rect)
    for enfant in widget.children():
        if isinstance(enfant, QWidget) and not enfant.isWindow() and enfant.isVisible():
            zone = rect.intersected(enfant.geometry())
            if not zone.isEmpty():
                _salir(enfant, zone.translated(-enfant.pos()))


class _Relais(QObject):
    """Le filtre d'application UNIQUE des zones. L'UpdateRequest va au widget de fenêtre (ou à sa QWindow, selon le
    chemin qui a demandé l'image) et les Paint à chaque widget, d'où un filtre sur toute l'application (en natif, il
    ralentissait tout : test_aide 39 s → > 5 min, d'où le navigateur seul).
    Un seul pour toutes les zones, et non un par zone : le lecteur de SmartTeacher en a une par page (218 pour un TP), et
    chaque événement traversait alors 218 filtres Python (128 600 appels pour vingt redimensionnements, mesuré le
    02/10/2026). L'image du backing store est gardée par fenêtre, puisqu'elle est la même pour toutes ses zones, et seules
    les zones qui ont un décalage en attente (``decalees``) sont visitées."""
    seul = None

    @classmethod
    def installer(cls):
        if cls.seul is None:
            cls.seul = cls()
            QApplication.instance().installEventFilter(cls.seul)

    def __init__(self):
        super().__init__()
        self.images = {}  # QWindow → l'image de son backing store, relevée au premier Paint qui suit une UpdateRequest
        self.attend = None  # la QWindow dont l'UpdateRequest vient de passer sans image : le Paint qui suit la donne
        self.decalees = set()

    def eventFilter(self, objet, evenement):
        t = evenement.type()
        if t == QEvent.Type.UpdateRequest:
            # celle du widget de fenêtre est la seule que Qt-WASM 6.10 envoie quand un widget est sali (QWidget.update) :
            # ne prendre que celle de la QWindow laissait chaque pas sans décalage, puis tout repeint au Paint (mesuré le
            # 02/10/2026 sur la figure du bac à l'échelle 2 : 18 à 20 ms par image au lieu de 16,7, fil occupé à 93 %)
            fenetre = objet if objet.isWindowType() else \
                objet.windowHandle() if isinstance(objet, QWidget) and objet.isWindow() else None
            if fenetre is not None:
                image = self.images.get(fenetre)
                self.attend = fenetre if image is None else None
                for zone in [z for z in self.decalees if z.window().windowHandle() is fenetre]:
                    zone._decaler_image(image)
        elif t == QEvent.Type.Paint:
            if self.attend is not None:
                if isinstance(objet, QWidget) and objet.window().windowHandle() is self.attend:
                    self.images[self.attend] = _image(objet)
                self.attend = None
            for zone in list(self.decalees):  # peint sans UpdateRequest (exposition, redimensionnement) : rien n'est
                zone._poser(0)                 # décalé, tout est à repeindre
                zone.widget().update()
        elif self.attend is not None:
            self.attend = None  # autre chose qu'un Paint a suivi l'UpdateRequest : un Paint ultérieur serait un render()
        elif t in (QEvent.Type.Hide, QEvent.Type.WinIdChange) and isinstance(objet, QWidget) and objet.isWindow():
            self.images.pop(objet.windowHandle(), None)  # le backing store peut être recréé : l'image sera relevée de nouveau
        return False


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
    if navigateur():
        _decaler_js()(octets, pas, a, n, y, h, dy)
        return
    for i in range(y + h - 1, y + dy - 1, -1) if dy > 0 else range(y, y + h + dy):
        octets[i * pas + a:i * pas + a + n] = octets[(i - dy) * pas + a:(i - dy) * pas + a + n]


_JS = None


def _decaler_js():
    """La boucle de ``decaler_lignes`` en JavaScript, compilée une fois : la vue de ``getBuffer`` est un Uint8Array sur la
    mémoire WebAssembly même (aucune copie), et ``copyWithin`` y déplace chaque ligne. En Python, une tranche de
    memoryview par ligne coûtait 2 à 4 ms par image à l'échelle 2 (1 500 lignes), mesuré le 02/10/2026."""
    global _JS
    if _JS is None:
        import js  # noqa: PLC0415 - navigateur seulement
        _JS = js.Function.new("octets", "pas", "a", "n", "y", "h", "dy", """
            const tampon = octets.getBuffer("u8");
            try {
                const d = tampon.data;
                if (dy > 0) for (let i = y + h - 1; i > y + dy - 1; i--) d.copyWithin(i * pas + a, (i - dy) * pas + a, (i - dy) * pas + a + n);
                else for (let i = y; i < y + h + dy; i++) d.copyWithin(i * pas + a, (i - dy) * pas + a, (i - dy) * pas + a + n);
            } finally {
                tampon.release();
            }""")
    return _JS
