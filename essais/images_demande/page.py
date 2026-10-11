"""Les greffons d'images mng et jp2 dans le navigateur (notes/2026-10-10 - Modules Qt à la demande.md, section « mng et
jp2 » ; l'utilisateur, 11/10/2026 : « teste-le dans Chrome par la sonde »). Depuis un slot : mng et jp2 absents, puis
`import qtpy6.QtImageFormats` (pyside_QtImageFormats.so téléchargé à ce moment), jp2 écrit et relu par Qt, mng de deux
images (rouge puis bleue) lu image par image ; les images lues sont affichées, agrandies.

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "mng et jp2"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 60 --etat essai_fini [--chromium]
"""

import base64
import sys
import time

from qtpy6 import QtCore, QtGui, QtWidgets
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
MNG = base64.b64decode(
    "ik1ORw0KGgoAAAAcTUhEUgAAAAQAAAADAAAACgAAAAAAAAAAAAAAAAAAAAFtsOezAAAAClRFUk0DAAAAAAF/////Z5eL6QAAAAFzUkdCAK7OHOkAAAANSUhEUgAAAAQ"
    "AAAADAQMAAACOOjyFAAAAA1BMVEX/AAAZ4gk3AAAAB3RJTUUH6goLDiEUemHhcAAAAAtJREFUCNdjYAABAAAGAAFm9MlsAAAAAElFTkSuQmCCAAAADUlIRFIAAAAEAAA"
    "AAwEDAAAAjjo8hQAAAANQTFRFAAD/injSVwAAAAd0SU1FB+oKCw4hFHph4XAAAAALSURBVAjXY2AAAQAABgABZvTJbAAAAABJRU5ErkJgggAAAABNRU5EISD31Q==")


def etat(valeur: str) -> None:
    if WEB:
        js.window.etat = valeur


def formats() -> set[str]:
    return {bytes(f).decode() for f in QtGui.QImageReader.supportedImageFormats()} & {"mng", "jp2"}


def montrer(image: QtGui.QImage) -> None:
    etiquette = QtWidgets.QLabel()
    etiquette.setPixmap(QtGui.QPixmap.fromImage(image.scaled(160, 120)))
    colonne.addWidget(etiquette)


def essai() -> None:
    try:
        avant = formats()
        t = time.monotonic()
        import qtpy6.QtImageFormats  # noqa: F401, PLC0415
        print(f"import qtpy6.QtImageFormats : {time.monotonic() - t:.2f} s ; formats avant {sorted(avant)}, après {sorted(formats())}")
        image = QtGui.QImage(4, 3, QtGui.QImage.Format.Format_RGB32)
        image.fill(QtGui.QColor("red"))
        tampon = QtCore.QBuffer()
        tampon.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        ecrit = image.save(tampon, "jp2")
        jp2 = QtGui.QImage.fromData(bytes(tampon.data()), "jp2")
        montrer(jp2)
        with open("/tmp/essai.mng", "wb") as f:
            f.write(MNG)
        lecteur = QtGui.QImageReader("/tmp/essai.mng")
        images = [lecteur.read() for _ in range(2)]
        for i in images:
            montrer(i)
        couleurs = [hex(i.pixel(0, 0)) for i in images]
        ok = (not avant and formats() == {"mng", "jp2"} and ecrit and jp2.size() == QtCore.QSize(4, 3)
              and QtGui.QColor(jp2.pixel(0, 0)).red() > 200 and couleurs == ["0xffff0000", "0xff0000ff"])
        print(f"VERDICT images : {'OK' if ok else 'ECHEC'} jp2 écrit={ecrit} {jp2.width()}x{jp2.height()} "
              f"pixel={hex(jp2.pixel(0, 0))} mng={couleurs} ({time.monotonic() - T0:.2f} s)")
    except BaseException as e:  # noqa: BLE001 - le verdict doit sortir quoi qu'il arrive
        print(f"VERDICT images : ECHEC exception {type(e).__name__} : {e}")
    if WEB:
        print("navigateur :", js.navigator.userAgent)
    etat("essai_fini")
    if not WEB:
        app.quit()


app = application()
fenetre = QtWidgets.QWidget()
colonne = QtWidgets.QVBoxLayout(fenetre)
fenetre.resize(300, 500)
fenetre.show()
QtCore.QTimer.singleShot(500, essai)
app.exec()
