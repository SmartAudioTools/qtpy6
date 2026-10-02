"""``qtpy6.peinture.en_image`` : un dessin gardé en image sur un moteur raster, redessiné à chaque fois ailleurs."""

from qtpy6.QtCore import QRectF
from qtpy6.QtGui import QColor, QImage, QPainter, QPicture

from qtpy6 import peinture


def peindre(appareil, cle, appels):
    p = QPainter(appareil)
    peinture.en_image(p, QRectF(2.5, 3.25, 20, 10), cle, lambda q, r: (appels.append(r), q.fillRect(r, QColor("red"))))
    p.end()


def test_garde_en_image_et_pose_au_meme_endroit(app):
    peinture.IMAGES.clear()
    direct, gardee = QImage(40, 30, QImage.Format.Format_ARGB32_Premultiplied), QImage(40, 30, QImage.Format.Format_ARGB32_Premultiplied)
    for image in (direct, gardee):
        image.fill(0)
    appels = []
    p = QPainter(direct)
    p.fillRect(QRectF(2.5, 3.25, 20, 10), QColor("red"))
    p.end()
    peindre(gardee, "a", appels)
    peindre(gardee, "a", appels)
    assert len(appels) == 1 and len(peinture.IMAGES) == 1
    assert gardee == direct  # même décalage sous le pixel que le tracé direct


def test_vecteurs_hors_raster_et_inactif(app):
    peinture.IMAGES.clear()
    appels = []
    peindre(QPicture(), "b", appels)  # moteur Picture, comme un QPdfWriter : jamais en image
    peinture.ACTIF = False
    try:
        peindre(QImage(40, 30, QImage.Format.Format_ARGB32_Premultiplied), "b", appels)
    finally:
        peinture.ACTIF = True
    assert len(appels) == 2 and not peinture.IMAGES


def test_plafond(app):
    peinture.IMAGES.clear()
    garde, peinture.PLAFOND = peinture.PLAFOND, 1000  # une image de 20 x 10 pèse 800 octets : la plus ancienne sort
    try:
        for cle in "xyz":
            peindre(QImage(40, 30, QImage.Format.Format_ARGB32_Premultiplied), cle, [])
    finally:
        peinture.PLAFOND = garde
    assert [cle[0] for cle in peinture.IMAGES] == ["z"]
