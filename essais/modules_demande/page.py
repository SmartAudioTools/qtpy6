"""Essai des modules Qt à la demande dans une page (notes/2026-10-10 - Modules Qt à la demande.md) : un QOpenGLWidget qui
peint en vert (WebGL par le module principal), un GET de la page elle-même par QNetworkAccessManager (fetch), les deux
modules importés ici, donc chargés par le finder au premier import. Même script sur le bureau. État de la page :
« essai_fini » quand le premier rendu OpenGL et la réponse réseau sont arrivés, « erreur » sinon ; le journal dit ce que chacun a donné.

Résultat (10/10/2026, Firefox 155, hors bac à sable : le Firefox headless du bac n'a pas de WebGL) : les deux modules
chargés au premier import (0,04 s, `.so.br` vus dans les ressources), GET OK (HTTP 200, NoError) ; `QOpenGLWidget`
exécuté (contexte ES 3.0, paintGL appelé) mais jamais affiché : « Context is lost » à chaque image puis plantage wasm.
Qt ne le supporte pas sous WebAssembly (un contexte WebGL par surface, pas de partage) : voir la note. Le journal du
navigateur ne contient pas les qWarning de Qt : les lire avec `sonde_console.py`, mêmes arguments que la sonde.

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "Modules à la demande"
    $P -m qtpy6.web.sonde site/index.html capture.png --racine site --delai 300 --etat essai_fini
"""

import sys
import time

from qtpy6 import QtCore, QtGui, QtWidgets
from qtpy6.web import application

T0 = time.monotonic()
from PySide6 import QtNetwork, QtOpenGLWidgets  # noqa: E402 - après T0 : c'est leur chargement qu'on mesure

print(f"import QtNetwork, QtOpenGLWidgets : {time.monotonic() - T0:.2f} s")
WEB = sys.platform == "emscripten"
if WEB:
    import js  # noqa: E402 - instrumentation : témoin de phase


FAIT = {"gl": False, "get": False}  # l'état « fini » attend le premier paintGL ET la réponse réseau


def fait(quoi, ok=True):
    if not ok:
        return etat("erreur")
    FAIT[quoi] = True
    if all(FAIT.values()):
        if WEB:  # les .so chargés à la demande, vus du navigateur : la preuve qu'ils viennent du réseau, pas de l'agrégat
            print("ressources :", ", ".join(f"{r.name.rsplit('/', 1)[-1]} {int(r.duration)} ms"
                                            for r in js.performance.getEntriesByType("resource") if "pyside_Qt" in r.name))
        etat("essai_fini")  # pas « fini » : le gabarit le pose lui-même dès que le script est lancé


def etat(valeur):
    if WEB:
        js.window.etat = valeur


class Vert(QtOpenGLWidgets.QOpenGLWidget):
    def initializeGL(self):
        f = self.context().functions()
        f.initializeOpenGLFunctions()
        version = self.context().format()
        print(f"OpenGL : contexte valide {self.context().isValid()}, {version.majorVersion()}.{version.minorVersion()}, "
              f"profil {version.profile()}, renderable {version.renderableType()}")

    def paintGL(self):
        # Pas f.glClearColor : la liaison WASM de QOpenGLFunctions n'a aucune méthode gl* (constaté le 10/10/2026, hors
        # bac à sable : AttributeError), le bureau les a toutes. QPainter passe par le moteur GL du widget des deux côtés.
        peintre = QtGui.QPainter(self)
        peintre.fillRect(self.rect(), QtGui.QColor(25, 153, 51))
        peintre.setPen(QtCore.Qt.GlobalColor.white)
        peintre.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "QOpenGLWidget")
        peintre.end()
        if not FAIT["gl"]:
            print(f"paintGL : {self.width()}x{self.height()}, {time.monotonic() - T0:.2f} s")
            fait("gl")


app = application()
fenetre = QtWidgets.QWidget()
fenetre.setWindowTitle("Modules à la demande")
colonne = QtWidgets.QVBoxLayout(fenetre)
gl = Vert()
gl.setMinimumSize(300, 200)
etiquette = QtWidgets.QLabel("GET en cours…")
colonne.addWidget(gl)
colonne.addWidget(etiquette)
fenetre.resize(400, 320)
fenetre.show()

url = QtCore.QUrl(js.location.href) if WEB else QtCore.QUrl("https://smartaudiotools.github.io/qtpy6/")
reseau = QtNetwork.QNetworkAccessManager()
reponse = reseau.get(QtNetwork.QNetworkRequest(url))


def fini():
    octets = bytes(reponse.readAll())
    code = reponse.attribute(QtNetwork.QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    texte = f"GET {url.toString()} : HTTP {code}, {len(octets)} octets, erreur {reponse.error().name}, {time.monotonic() - T0:.2f} s"
    print(texte)
    etiquette.setText(texte)
    fait("get", bool(octets) and reponse.error() == QtNetwork.QNetworkReply.NetworkError.NoError)


reponse.finished.connect(fini)
app.exec()
