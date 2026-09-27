"""L'écran se touche au doigt (téléphone, tablette, portable tactile) : les cibles de Qt, faites pour la souris (26 px),
montent à ``CIBLE`` (44 pt chez Apple, 48 dp chez Google) et la zone défilante suit le doigt. À activer AVANT de construire
les widgets : la feuille de style s'applique aux widgets à venir comme aux existants, mais les hauteurs déjà calculées
par les dispositions ne sont pas toutes refaites."""

from qtpy6.QtWidgets import QApplication, QScroller

from . import navigateur

CIBLE = 44  # la hauteur d'une cible au doigt, en pixels
ACTIF = False  # posé par ``activer`` : ``defiler_au_doigt`` et les applications le lisent


def detecte():
    """Un doigt parmi les pointeurs du navigateur (``any-pointer: coarse`` : téléphone, tablette, mais aussi un portable à
    écran tactile) ; False en natif, où c'est à l'application de le savoir (une option de ligne de commande)."""
    if not navigateur():
        return False
    import js  # noqa: PLC0415 - le module de Pyodide, qui n'existe que dans le navigateur

    return bool(js.window.matchMedia("(any-pointer: coarse)").matches)


def activer(app=None, cible=CIBLE):
    """Boutons, listes déroulantes et champs montent à ``cible``, les cases et boutons radio grossissent, les lignes d'une
    liste déroulée aussi, l'ascenseur s'élargit. La feuille est AJOUTÉE à celle de l'application, pas substituée. Les
    champs incrustés dans un texte (``QTextDocument``) gardent la hauteur de leur ligne : c'est à l'application de les
    espacer (``marge``)."""
    global ACTIF, CIBLE
    ACTIF, CIBLE = True, cible
    app = app or QApplication.instance()
    # Fusion ajoute 8 px de marges à un bouton et 6 à un champ : le padding les remplace, la hauteur donnée fait la cible
    app.setStyleSheet(app.styleSheet() + (
        f"QPushButton {{ min-height: {cible}px; padding: 0px 6px; }} QComboBox, QLineEdit {{ min-height: {cible - 6}px; }}"
        f"QCheckBox::indicator, QRadioButton::indicator {{ width: {cible * 5 // 8}px; height: {cible * 5 // 8}px; }}"
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
