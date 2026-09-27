"""L'écran se touche au doigt (téléphone, tablette, portable tactile) : les cibles de Qt, faites pour la souris (26 px),
montent à ``CIBLE`` (44 pt chez Apple, 48 dp chez Google) et la zone défilante suit le doigt. À activer AVANT de construire
les widgets : la feuille de style s'applique aux widgets à venir comme aux existants, mais les hauteurs déjà calculées
par les dispositions ne sont pas toutes refaites."""

from qtpy6.QtCore import QEvent, Qt
from qtpy6.QtGui import QInputDevice, QMouseEvent
from qtpy6.QtWidgets import QApplication, QScroller

from . import navigateur

CIBLE = 44  # la hauteur d'une cible au doigt, en pixels
ACTIF = False  # posé par ``activer`` : ``defiler_au_doigt`` et les applications le lisent


def detecte():
    """Un écran au doigt : téléphone, tablette, portable tactile. Dans le navigateur, parmi ses pointeurs (``any-pointer:
    coarse``) ; en natif, parmi les périphériques que Qt a recensés (``QInputDevice``, une ``QApplication`` doit exister).
    Un écran tactile dont personne ne se sert compte aussi : le navigateur fait de même."""
    if not navigateur():
        return any(d.type() == QInputDevice.DeviceType.TouchScreen for d in QInputDevice.devices())
    import js  # noqa: PLC0415 - le module de Pyodide, qui n'existe que dans le navigateur

    return bool(js.window.matchMedia("(any-pointer: coarse)").matches)


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


def marge(souris=2, hauteur_ligne=26):
    """L'espace à ajouter au-dessus et au-dessous d'un widget d'une ligne (``hauteur_ligne`` px : texte 22, bordures et
    espace 4) pour qu'il fasse une cible au doigt ; ``souris`` sinon."""
    return (CIBLE - hauteur_ligne) // 2 if ACTIF else souris


def defiler_au_doigt(zone):
    """Une ``QScrollArea`` (ou tout ``QAbstractScrollArea``) que le doigt fait défiler, comme partout ailleurs sur un
    téléphone : sans cela, il ne fait rien. Sans effet tant que ``activer`` n'a pas été appelé."""
    if ACTIF:
        QScroller.grabGesture(zone.viewport(), QScroller.ScrollerGestureType.TouchGesture)


_GESTES = {QEvent.Type.TouchBegin: QEvent.Type.MouseButtonPress, QEvent.Type.TouchUpdate: QEvent.Type.MouseMove,
           QEvent.Type.TouchEnd: QEvent.Type.MouseButtonRelease}


def relayer_en_souris(widget, evenement):
    """Un ``QTouchEvent`` (premier doigt seulement) rejoué en ``QMouseEvent`` sur les gestionnaires souris de
    ``widget`` (``mousePressEvent``/``mouseMoveEvent``/``mouseReleaseEvent``, inchangés) : ce que ``widget`` sait déjà
    faire au clic, il le refait au doigt. À appeler depuis un ``event()`` qui a mis ``WA_AcceptTouchEvents`` sur
    ``widget`` — c'est cette acceptation qui empêche un ``QScroller`` ancêtre (``defiler_au_doigt``) de capter le même
    doigt pour faire défiler à sa place : Qt n'accorde pas les deux gestes au même point de contact. Rend ``True``
    (traité) ou ``False`` (type ou doigt absent : rien à faire)."""
    genre = _GESTES.get(evenement.type())
    points = evenement.points() if genre is not None else ()
    if not points:
        return False
    position = points[0].position()
    boutons = Qt.MouseButton.NoButton if genre == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
    souris = QMouseEvent(genre, position, position, Qt.MouseButton.LeftButton, boutons, evenement.modifiers())
    {QEvent.Type.MouseButtonPress: widget.mousePressEvent, QEvent.Type.MouseMove: widget.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: widget.mouseReleaseEvent}[genre](souris)
    evenement.accept()
    return True
