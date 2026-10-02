"""Un dessin coûteux peint une fois en image à la taille des pixels, puis copié tel quel aux peintures suivantes.

``QSvgRenderer.render``, la réduction d'une grande image, un chemin compliqué : relancés à chaque ``paintEvent``, ils
coûtent à chaque image d'un défilement ou d'une animation. ``en_image(peintre, rect, cle, dessiner)`` appelle
``dessiner(peintre, rect)`` la première fois dans une ``QImage`` (ARGB32 prémultipliée, à la taille des pixels du
périphérique, avec le même décalage sous le pixel que le tracé direct, arrondi au 1/64), puis la pose sur la grille par
``drawImage``, sans rééchantillonnage. Mesuré sur le lecteur QCM de SmartTeacher (figures SVG d'un sujet de bac, repeint
complet) : 30-48 → 15-18 ms en natif à l'échelle 1, 75 → 42 ms dans le navigateur à l'échelle 2 ; pixels à 3/255 près au
plus (arrondi du compositage prémultiplié, invisible).

Seulement sur un moteur raster (fenêtre, ``QImage``) sans rotation ni cisaillement : un ``QPdfWriter`` ou un
``QSvgGenerator`` garde les vecteurs, sans rien à désactiver. Toutes les images partagent un plafond en octets
(``PLAFOND``), les plus anciennes sortent d'abord : à l'échelle 2 une figure pleine largeur pèse ~2 Mo, et chaque largeur
de fenêtre en produit une nouvelle. ``ACTIF = False`` rend le tracé direct (comparaisons)."""

import collections
import math

from qtpy6.QtCore import QPointF, QRectF, Qt
from qtpy6.QtGui import QImage, QPainter, QPaintEngine

ACTIF = True
PLAFOND = 48 << 20  # octets
IMAGES = collections.OrderedDict()  # (clé, largeur, hauteur, dx, dy, échelle) -> QImage


def en_image(peintre, rect, cle, dessiner):
    """``dessiner(peintre, rect)`` gardé en image. ``cle`` désigne CE QUI est dessiné (hachable) et tout ce dont le
    dessin dépend hors de sa taille : deux appels de même clé doivent donner la même figure. Un objet détruit ne doit pas
    léguer sa clé à un autre (préférer un numéro tiré d'un compteur à ``id()``)."""
    t = peintre.deviceTransform()
    if (not ACTIF or peintre.paintEngine().type() != QPaintEngine.Type.Raster or t.m12() or t.m21() or t.m13() or t.m23()
            or t.m11() != t.m22() or t.m11() <= 0):
        dessiner(peintre, rect)
        return
    e, coin = t.m11(), t.map(rect.topLeft())
    x, y = math.floor(coin.x()), math.floor(coin.y())
    dx, dy = round((coin.x() - x) * 64) / 64, round((coin.y() - y) * 64) / 64
    cle = cle, round(rect.width() * e), round(rect.height() * e), dx, dy, e
    pixels = IMAGES.get(cle)
    if pixels is None:
        pixels = QImage(math.ceil(rect.width() * e + dx), math.ceil(rect.height() * e + dy), QImage.Format.Format_ARGB32_Premultiplied)
        pixels.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixels)
        p.setRenderHints(peintre.renderHints())
        p.translate(dx, dy)
        p.scale(e, e)
        dessiner(p, QRectF(0, 0, rect.width(), rect.height()))
        p.end()
        pixels.setDevicePixelRatio(e)
        IMAGES[cle] = pixels
        total = sum(i.sizeInBytes() for i in IMAGES.values())
        while total > PLAFOND and len(IMAGES) > 1:
            total -= IMAGES.popitem(last=False)[1].sizeInBytes()
    else:
        IMAGES.move_to_end(cle)
    peintre.drawImage(t.inverted()[0].map(QPointF(x, y)), pixels)
