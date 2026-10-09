"""L'écran se touche au doigt (téléphone, tablette, portable tactile) : les cibles de Qt, faites pour la souris (26 px),
montent à ``CIBLE`` (44 pt chez Apple, 48 dp chez Google) et la zone défilante suit le doigt. À activer AVANT de construire
les widgets : la feuille de style s'applique aux widgets à venir comme aux existants, mais les hauteurs déjà calculées
par les dispositions ne sont pas toutes refaites."""

import time

from qtpy6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from qtpy6.QtGui import QInputDevice, QMouseEvent
from qtpy6.QtWidgets import QApplication, QScroller, QScrollerProperties, QWidget

from . import navigateur

CIBLE = 44  # la hauteur d'une cible au doigt, en pixels
ACTIF = False  # posé par ``activer`` : ``defiler_au_doigt`` et les applications le lisent


def detecte():
    """Un écran au doigt : téléphone, tablette, portable tactile. Dans le navigateur, parmi ses pointeurs (``any-pointer:
    coarse``) ou par le nombre de doigts qu'il sait suivre (``navigator.maxTouchPoints`` : un portable tactile dont la
    souris est le pointeur principal ne se dit pas toujours « coarse ») ; en natif, parmi les périphériques que Qt a
    recensés (``QInputDevice``, une ``QApplication`` doit exister). Un écran tactile dont personne ne se sert compte aussi :
    le navigateur fait de même. Certains navigateurs ne disent rien (Firefox sous Linux) : ``activer_au_doigt``."""
    if not navigateur():
        return any(d.type() == QInputDevice.DeviceType.TouchScreen for d in QInputDevice.devices())
    import js  # noqa: PLC0415 - le module de Pyodide, qui n'existe que dans le navigateur

    return bool(js.window.matchMedia("(any-pointer: coarse)").matches) or (js.navigator.maxTouchPoints or 0) > 0


def activer_au_doigt(app=None):
    """``activer`` tout de suite si l'écran se dit tactile (``detecte``) ; sinon, dans le navigateur, au premier doigt posé
    sur la page (``pointerdown`` de type ``touch``, écouté avant Qt) : le seul signe sûr quand le navigateur ne dit rien
    de son écran. Les widgets construits APRÈS ce doigt sont faits pour lui (sur un écran d'accueil, c'est l'application
    qui suit), ceux d'avant reçoivent la feuille de style sans toutes leurs hauteurs refaites (``activer``)."""
    if detecte():
        activer(app)
    elif navigateur():
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy  # noqa: PLC0415

        def doigt(evenement):
            if evenement.pointerType == "touch" and not ACTIF:
                activer(app)
                js.window.removeEventListener("pointerdown", ecouteur, True)

        ecouteur = create_proxy(doigt)
        js.window.addEventListener("pointerdown", ecouteur, True)  # en capture : avant le canevas de Qt


def activer(app=None, cible=CIBLE, case=None):
    """Boutons, listes déroulantes et champs montent à ``cible``, les cases et boutons radio grossissent (``case`` pixels :
    par défaut les 3/4 de ``cible``, un disque plein restant net dans le rond qui l'entoure ; à donner en pixels pour
    l'ajuster), les lignes d'une liste déroulée aussi, l'ascenseur s'élargit. La feuille est AJOUTÉE à celle de
    l'application, pas substituée. Les champs incrustés dans un texte (``QTextDocument``) gardent la hauteur de leur
    ligne : c'est à l'application de les espacer (``marge``)."""
    global ACTIF, CIBLE
    ACTIF, CIBLE = True, cible
    case = cible * 3 // 4 if case is None else case
    app = app or QApplication.instance()
    # Fusion ajoute 8 px de marges à un bouton et 6 à un champ : le padding les remplace, la hauteur donnée fait la cible
    app.setStyleSheet(app.styleSheet() + (
        f"QPushButton {{ min-height: {cible}px; padding: 0px 6px; }} QComboBox, QLineEdit {{ min-height: {cible - 6}px; }}"
        f"QCheckBox::indicator, QRadioButton::indicator {{ width: {case}px; height: {case}px; }}"
        f"QComboBox QAbstractItemView::item {{ min-height: {cible}px; }} QScrollBar:vertical {{ width: 18px; }}"))
    while _EN_ATTENTE:
        defiler_au_doigt(_EN_ATTENTE.pop(0))


def marge(souris=2, hauteur_ligne=26):
    """L'espace à ajouter au-dessus et au-dessous d'un widget d'une ligne (``hauteur_ligne`` px : texte 22, bordures et
    espace 4) pour qu'il fasse une cible au doigt ; ``souris`` sinon."""
    return (CIBLE - hauteur_ligne) // 2 if ACTIF else souris


def defiler_au_doigt(zone):
    """Une ``QScrollArea`` (ou tout ``QAbstractScrollArea``) que le doigt fait défiler, comme partout ailleurs sur un
    téléphone : sans cela, il ne fait rien. Avant ``activer``, la zone attend : ``activer`` l'accroche (un écran que le
    navigateur ne dit pas tactile, Chromium sous Linux, n'est activé qu'au premier doigt, souvent après la construction
    de la page : sans cette attente, rien n'y défilait au doigt, 05/10/2026). Dans le navigateur, la course après le
    lâcher suit les images de l'écran (``_Inertie``)."""
    if not ACTIF:
        _EN_ATTENTE.append(zone)
        zone.destroyed.connect(lambda *_: _EN_ATTENTE.remove(zone) if zone in _EN_ATTENTE else None)
        return
    QScroller.grabGesture(zone.viewport(), QScroller.ScrollerGestureType.TouchGesture)
    if navigateur():
        _Inertie(zone)


_EN_ATTENTE = []  # les zones de ``defiler_au_doigt`` construites avant ``activer``


class _Inertie(QObject):
    """La course de ``QScroller`` une fois le doigt levé, finie au rythme des images de l'écran. ``QScroller`` avance
    à la minuterie de Qt, que rien ne cale sur l'écran : sur un téléphone simulé (bac NSI, 412 px, densité 2,6),
    40 % des images restaient sans mouvement (pas espacés de 32 à 48 ms) alors qu'une image coûtait 2-3 ms à dessiner
    (``QCM/web/pyqt6/sonde_lecteur.html``, scénario ``doigt``). Au passage en ``Scrolling``, la position où ``QScroller``
    s'arrêterait (``finalPosition``, bornée à la plage : le rebond de fin est perdu) est relevée, lui arrêté, et une
    ``QPropertyAnimation`` de qtpy6 (menée par les images, ``qtpy6.animation``) mène chaque ascenseur jusqu'à elle en
    décélérant : ``OutQuad`` part à la vitesse du doigt quand sa durée vaut deux fois la distance divisée par cette
    vitesse. La vitesse est celle des positions des ascenseurs pendant les ``FENETRE`` dernières secondes du glissé :
    ``QScroller.velocity`` est en mètres par seconde, convertis par une densité d'écran que le navigateur ne connaît
    pas. Un doigt reposé, une plage qui change ou la zone détruite arrêtent la course ; le doigt qui l'arrête n'est pas
    un clic : son appui et son relâchement n'atteignent pas la page (sans cela, mesuré, il cochait la case dessous 12
    fois sur 12, QScroller seul compris : dans le navigateur, il laisse passer la souris que Qt tire du doigt). Mesuré
    au même profil : après le lâcher, 0 image sans mouvement au lieu de 33 à 48 %, pas d'avant et d'après du même ordre
    (20-30 px) ; écarté, ``QScrollerProperties.FrameRate`` à ``Fps60`` : encore 26 à 42 %, la minuterie restant décalée
    des images.

    Pas de dépassement de la borne non plus, au doigt posé comme à la lancée (``OvershootAlwaysOff``) : la page tirée
    au-delà du bas ou du haut déplace le viewport par-dessus ce qui le borde, et le canevas du navigateur n'y repeint
    pas : l'en-tête gardait des morceaux de page (sonde Blink tactile, ``doigt`` avec ``avant_fin=150``, 4 fois sur 4,
    09/10/2026 ; 0 sur 4 sans dépassement). Coût accepté : plus aucun rebond élastique au doigt dans le navigateur."""

    FENETRE = 0.1  # s

    def __init__(self, zone):
        super().__init__(zone)
        self.zone, self.courses, self.trace, self.avale = zone, [], [], False
        self.scroller = QScroller.scroller(zone.viewport())
        proprietes = self.scroller.scrollerProperties()
        for metrique in (QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy,
                         QScrollerProperties.ScrollMetric.VerticalOvershootPolicy):
            proprietes.setScrollMetric(metrique, QScrollerProperties.OvershootPolicy.OvershootAlwaysOff)
        self.scroller.setScrollerProperties(proprietes)
        self.scroller.stateChanged.connect(self._etat)
        for barre in self._barres():
            barre.valueChanged.connect(self._noter)
            barre.rangeChanged.connect(self.arreter)

    def _barres(self):
        return self.zone.horizontalScrollBar(), self.zone.verticalScrollBar()

    def _noter(self):
        if self.scroller.state() == QScroller.State.Dragging:
            self.trace.append((time.perf_counter(), *(b.value() for b in self._barres())))

    def arreter(self, *_):
        for course in self.courses:
            course.stop()
            course.deleteLater()
        self.courses = []

    def _etat(self, etat):
        if etat == QScroller.State.Pressed:
            self._avaler(any(c.state() == QAbstractAnimation.State.Running for c in self.courses))  # une course finie : clic
            self.arreter()
            self.trace = []
        elif etat == QScroller.State.Scrolling:
            maintenant = time.perf_counter()
            recents = [p for p in self.trace if maintenant - p[0] <= self.FENETRE]
            self.trace = []
            if len(recents) < 2:
                return  # trop peu de positions pour une vitesse : QScroller finit seul
            (t0, *p0), (t1, *p1) = recents[0], recents[-1]
            fin = self.scroller.finalPosition()
            if self.courir(fin.x(), fin.y(), sum((b - a) ** 2 for a, b in zip(p0, p1)) ** 0.5 / max(t1 - t0, 1e-3)):
                self.scroller.stop()

    def _avaler(self, oui):
        if oui != self.avale:
            (QApplication.instance().installEventFilter if oui else QApplication.instance().removeEventFilter)(self)
            self.avale = oui

    def eventFilter(self, objet, evenement):
        vue = self.zone.viewport()
        if evenement.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonRelease) \
                and isinstance(objet, QWidget) and (objet is vue or vue.isAncestorOf(objet)):
            if evenement.type() == QEvent.Type.MouseButtonRelease:
                self._avaler(False)
            return True
        return False

    def courir(self, x, y, vitesse):
        """Mène les ascenseurs vers (``x``, ``y``), bornés à leur plage, en partant à ``vitesse`` px/s ; faux s'il n'y a
        pas de course (déjà arrivé, ou vitesse nulle)."""
        buts = [(b, min(max(round(v), b.minimum()), b.maximum())) for b, v in zip(self._barres(), (x, y))]
        distance = sum((but - b.value()) ** 2 for b, but in buts) ** 0.5
        if distance < 1 or vitesse < 1:
            return False
        duree = min(max(round(2000 * distance / vitesse), 100), 4000)
        self.arreter()
        for barre, but in buts:
            if but != barre.value():
                course = QPropertyAnimation(barre, b"value", self, duration=duree, easingCurve=QEasingCurve.Type.OutQuad)
                course.setStartValue(barre.value())
                course.setEndValue(but)
                course.start()
                self.courses.append(course)
        return True


_GESTES = {QEvent.Type.TouchBegin: QEvent.Type.MouseButtonPress, QEvent.Type.TouchUpdate: QEvent.Type.MouseMove,
           QEvent.Type.TouchEnd: QEvent.Type.MouseButtonRelease}


def relayer_en_souris(widget, evenement):
    """Un ``QTouchEvent`` (premier doigt seulement) rejoué en ``QMouseEvent`` sur les gestionnaires souris de
    ``widget`` (``mousePressEvent``/``mouseMoveEvent``/``mouseReleaseEvent``, inchangés) : ce que ``widget`` sait déjà
    faire au clic, il le refait au doigt. À appeler depuis un ``event()`` qui a mis ``WA_AcceptTouchEvents`` sur
    ``widget``. Le doigt est alors au widget : chaque événement relayé arrête le ``QScroller`` des ancêtres
    (``defiler_au_doigt``), que l'acceptation seule n'empêche PAS de faire défiler la page en même temps, en natif comme
    dans le navigateur (mesuré le 04/10/2026 : ``tests/test_tactile.py``, web.md, « Pièges »). Rend ``True``
    (traité) ou ``False`` (type ou doigt absent : rien à faire)."""
    genre = _GESTES.get(evenement.type())
    points = evenement.points() if genre is not None else ()
    if not points:
        return False
    position = points[0].position()
    boutons = Qt.MouseButton.NoButton if genre == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
    souris = QMouseEvent(genre, position, position, Qt.MouseButton.LeftButton, boutons, evenement.modifiers())
    arreter_le_defilement(widget)
    {QEvent.Type.MouseButtonPress: widget.mousePressEvent, QEvent.Type.MouseMove: widget.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: widget.mouseReleaseEvent}[genre](souris)
    evenement.accept()
    return True


def arreter_le_defilement(widget):
    """Arrête le ``QScroller`` de chaque ancêtre de ``widget`` (``defiler_au_doigt``) : le doigt est à ``widget``."""
    while widget is not None:
        if QScroller.hasScroller(widget):
            QScroller.scroller(widget).stop()
        widget = widget.parentWidget()


class Toucher:
    """Au doigt (``ACTIF``), un toucher (doigt posé et levé sur place) se distingue d'un glissé, qui fait défiler la page
    (``defiler_au_doigt``) : un widget qui agit au clic n'agit qu'au lever d'un toucher. Pour un widget qui laisse la page
    défiler sous le doigt, contrairement à ``relayer_en_souris`` qui la lui prend ; à la souris, rien ne change.

    ``appui`` (dans ``mousePressEvent``) rend ``True`` pour la souris que Qt tire d'un doigt : ne rien faire encore.
    ``bouge`` (``mouseMoveEvent``) oublie l'appui dès que le doigt s'éloigne de plus de ``startDragDistance``.
    ``leve`` (``mouseReleaseEvent``) rend ``True`` pour un toucher : agir maintenant.
    Les positions sont GLOBALES : quand la page suit le doigt, le point touché ne bouge pas dans le widget, et des
    positions locales n'y verraient aucun glissé. Un toucher que le navigateur annule sans relâchement (la page a pris
    le glissé) est oublié à l'appui suivant, et un relâchement sans appui noté n'est pas un toucher."""

    def __init__(self):
        self.point = None

    def appui(self, evenement):
        doigt = ACTIF and evenement.source() != Qt.MouseEventSource.MouseEventNotSynthesized
        self.point = evenement.globalPosition() if doigt else None
        return doigt

    def bouge(self, evenement):
        if self.point is not None and (evenement.globalPosition() - self.point).manhattanLength() > QApplication.startDragDistance():
            self.point = None

    def leve(self, evenement):
        self.bouge(evenement)
        touche, self.point = self.point is not None, None
        return touche


class AppuiLong(QObject):
    """Au doigt (``ACTIF``), un doigt posé immobile ``DELAI`` ms sur ``widget`` le lui donne : le défilement de la page
    (``defiler_au_doigt``) s'arrête et ``prendre(position)`` est appelé (une liste y lance son glisser) ; avant ce délai, un
    glissé fait défiler la page comme ailleurs. La convention des téléphones pour saisir un élément d'une liste qui défile.
    ``widget`` est celui qui reçoit la souris (le ``viewport()`` d'une vue). À la souris, rien ne change.

    ``DELAI`` reste sous l'appui long des téléphones, qui ouvre le menu ou la sélection du navigateur : 400 ms sous
    Android 12 et suivants (500 avant), environ 500 ms sous iOS. Le menu est de toute façon refusé sur l'écran de Qt
    (``qtpy6web.js``, ``sans_menu``)."""

    DELAI = 300

    def __init__(self, widget, prendre):
        from qtpy6.QtCore import QTimer  # noqa: PLC0415

        super().__init__(widget)
        self.widget, self.prendre = widget, prendre
        self.toucher = Toucher()
        self.minuterie = QTimer(self)
        self.minuterie.setSingleShot(True)
        self.minuterie.setInterval(self.DELAI)
        self.minuterie.timeout.connect(self._prendre)
        widget.installEventFilter(self)

    def eventFilter(self, objet, evenement):
        genre = evenement.type()
        if genre in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):  # un second appui rapide est un double-clic
            if self.toucher.appui(evenement):
                self.position = evenement.position()
                self.minuterie.start()
        elif genre == QEvent.Type.MouseMove:
            self.toucher.bouge(evenement)
            if self.toucher.point is None:
                self.minuterie.stop()
        elif genre == QEvent.Type.MouseButtonRelease:
            self.minuterie.stop()
            self.toucher.point = None
        return False

    def _prendre(self):
        self.toucher.point = None
        arreter_le_defilement(self.widget)
        self.prendre(self.position)
