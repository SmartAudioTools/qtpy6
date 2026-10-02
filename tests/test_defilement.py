"""``qtpy6.web.defilement`` : le décalage de lignes, qui remplace le ``scroll()`` que Qt-WASM n'a pas, se vérifie en natif
sur une image à motif ; la ZoneDefilante, elle, n'est en natif qu'une QScrollArea ordinaire (le raccourci ne vaut que dans
le navigateur, mesuré par ``python -m qtpy6.web.sonde`` sur le lecteur QCM de SmartTeacher)."""

from qtpy6.QtGui import QImage
from qtpy6.QtWidgets import QLabel

from qtpy6.web import defilement


def motif(largeur=6, hauteur=10):
    image = QImage(largeur, hauteur, QImage.Format.Format_ARGB32)
    for y in range(hauteur):
        for x in range(largeur):
            image.setPixel(x, y, 0xFF000000 | (y << 8) | x)  # chaque pixel dit sa ligne et sa colonne
    return image


def ligne(image, y):
    return [image.pixel(x, y) & 0xFFFF for x in range(image.width())]


def test_decaler_vers_le_bas():
    image, origine = motif(), motif()
    defilement.decaler_lignes(image, 1, 2, 4, 6, 2)  # le rectangle x 1..4, y 2..7, descendu de 2 lignes
    for y in range(10):
        attendu = ligne(origine, y)
        if 4 <= y <= 7:
            attendu[1:5] = ligne(origine, y - 2)[1:5]
        assert ligne(image, y) == attendu, y


def test_decaler_vers_le_haut():
    image, origine = motif(), motif()
    defilement.decaler_lignes(image, 0, 3, 6, 5, -3)  # y 3..7 remonté de 3 : y 3, 4 reçoivent y 6, 7 ; y 5..7 inchangées
    for y in range(10):
        attendu = ligne(origine, y + 3) if y in (3, 4) else ligne(origine, y)
        assert ligne(image, y) == attendu, y


def test_zone_ordinaire_en_natif(app):
    zone = defilement.ZoneDefilante()
    zone.setWidget(QLabel("\n".join(map(str, range(200)))))
    zone.resize(100, 100)
    zone.show()
    app.processEvents()
    zone.verticalScrollBar().setValue(50)
    app.processEvents()
    assert zone._dy == 0 and zone.widget().pos().y() == -50
