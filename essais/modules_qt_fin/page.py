"""Essai page des quatre derniers modules chargés à la demande (notes/2026-10-10 - Modules Qt à la demande.md, « Suite
(15 h 20 →) », point ouvert « Sonde page (Firefox) non faite pour ces quatre ») : chacun importé depuis un slot, comme
`essais/modules_qt_suite/page.py`, chacun avec son verdict dans le journal (« VERDICT <nom> : OK/ECHEC <détail> »).
Ordre : images, WebSockets, Graphs, puis Quick3D en dernier (WebGL : un échec de Qt Quick peut tuer le moteur wasm).
État de la page : « essai_fini » quand les quatre verdicts sont écrits.

  - images : QImageReader.supportedImageFormats() et un aller-retour webp/tiff (QImage.save puis relu, même pixel).
  - websockets : QWebSocket construit, ouvert sur un port fermé de 127.0.0.1 ; verdict = un signal d'erreur ou de
    changement d'état arrive (le chemin réseau du navigateur répond).
  - graphs : import QtGraphs et QtGraphsWidgets, séries construites (le rendu passe par Qt Quick, donc WebGL).
  - quick3d : QQuickWidget sur un QML qui importe QtQuick3D ; verdict = statut Ready (le module QML est enregistré), le
    rendu n'est pas vérifiable sans WebGL.

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "WebSockets, Quick3D, Graphs, images"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 120 --etat essai_fini > sonde.log 2>&1
"""

import os
import sys
import tempfile
import time

from qtpy6 import QtCore, QtGui, QtWidgets
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
VERDICTS = {}
NOMS = ("images", "websockets", "graphs", "quick3d")


def etat(valeur):
    if WEB:
        js.window.etat = valeur


def ressources():
    if WEB:
        print("ressources :", ", ".join(f"{r.name.rsplit('/', 1)[-1]} {int(r.startTime)}+{int(r.duration)} ms"
                                        for r in js.performance.getEntriesByType("resource") if "pyside_Qt" in r.name))


def verdict(nom, ok, detail=""):
    if nom in VERDICTS:
        return
    VERDICTS[nom] = ok
    print(f"VERDICT {nom} : {'OK' if ok else 'ECHEC'} {detail} ({time.monotonic() - T0:.2f} s)")
    if len(VERDICTS) == len(NOMS):
        ressources()
        etat("essai_fini")


def essayer(nom, f):
    try:
        f()
    except BaseException as e:  # noqa: BLE001 - un contrôle qui échoue ne doit pas masquer les autres
        verdict(nom, False, f"exception {type(e).__name__} : {e}")


app = application()
fenetre = QtWidgets.QWidget()
colonne = QtWidgets.QVBoxLayout(fenetre)
journal = QtWidgets.QLabel("…")
journal.setWordWrap(True)
colonne.addWidget(journal)
fenetre.resize(520, 700)
fenetre.show()
ACTIFS = []


def note(texte):
    print(texte)
    journal.setText(journal.text() + "\n" + texte)


# ---------- images ----------
def images():
    formats = sorted(bytes(f).decode() for f in QtGui.QImageReader.supportedImageFormats())
    note(f"formats lus : {formats}")
    source = QtGui.QImage(16, 16, QtGui.QImage.Format.Format_RGB32)
    source.fill(QtGui.QColor(10, 200, 30))
    details, ok = [f"{len(formats)} formats"], True
    for f in ("webp", "tiff"):
        chemin = os.path.join(tempfile.gettempdir(), f"essai.{f}")
        ecrit = source.save(chemin, f.upper())
        relu = QtGui.QImage(chemin)
        pixel = QtGui.QColor(relu.pixel(8, 8)).getRgb()[:3] if not relu.isNull() else None
        details.append(f"{f} écrit={ecrit} relu={pixel}")
        ok &= ecrit and pixel is not None and abs(pixel[1] - 200) < 10
    ok &= all(f in formats for f in ("webp", "tiff", "tga", "wbmp", "icns"))
    verdict("images", ok, "; ".join(details))


# ---------- WebSockets ----------
def websockets():
    t = time.monotonic()
    from PySide6 import QtWebSockets
    note(f"import QtWebSockets : {time.monotonic() - t:.2f} s")
    ws = QtWebSockets.QWebSocket()
    ACTIFS.append(ws)
    evenements = []
    ws.stateChanged.connect(lambda s: evenements.append(f"état {s.name}"))
    ws.errorOccurred.connect(lambda e: evenements.append(f"erreur {e.name} {ws.errorString()!r}"))
    ws.open(QtCore.QUrl("ws://127.0.0.1:9/"))

    def fin():
        verdict("websockets", bool(evenements), f"{evenements}, {time.monotonic() - t:.2f} s depuis l'import")
    QtCore.QTimer.singleShot(2000, lambda: essayer("websockets", fin))


# ---------- Graphs ----------
def graphs():
    t = time.monotonic()
    from PySide6 import QtGraphs
    note(f"import QtGraphs : {time.monotonic() - t:.2f} s")
    from PySide6 import QtGraphsWidgets
    note(f"import QtGraphsWidgets : {time.monotonic() - t:.2f} s")
    serie = QtGraphs.QLineSeries()
    for x in range(10):
        serie.append(x, x * x)
    barres = QtGraphs.QBarSet("b")
    barres.append([1.0, 2.0, 3.0])
    ACTIFS.extend([serie, barres])
    verdict("graphs", serie.count() == 10 and barres.count() == 3,
            f"QLineSeries {serie.count()} points, QBarSet {barres.count()}, "
            f"Q3DBarsWidgetItem={hasattr(QtGraphsWidgets, 'Q3DBarsWidgetItem')}, {time.monotonic() - t:.2f} s")


# ---------- Quick3D ----------
QML = """import QtQuick
import QtQuick3D
Rectangle { width: 300; height: 150; color: "#203040"
  View3D { anchors.fill: parent
    PerspectiveCamera { z: 300 }
    DirectionalLight { }
    Model { source: "#Cube"; materials: PrincipledMaterial { baseColor: "red" } } } }
"""


def quick3d():
    t = time.monotonic()
    from PySide6 import QtQuick3D, QtQuickWidgets
    note(f"import QtQuick3D + QtQuickWidgets : {time.monotonic() - t:.2f} s")
    chemin = os.path.join(tempfile.gettempdir(), "essai3d.qml")
    with open(chemin, "w") as f:
        f.write(QML)
    qw = QtQuickWidgets.QQuickWidget()
    qw.setMinimumSize(320, 170)
    qw.setSource(QtCore.QUrl.fromLocalFile(chemin))
    colonne.addWidget(qw)
    ACTIFS.append(qw)

    def controle():
        erreurs = [e.toString() for e in qw.errors()]
        verdict("quick3d", qw.status() == QtQuickWidgets.QQuickWidget.Status.Ready,
                f"statut={qw.status().name}, erreurs={erreurs}, {time.monotonic() - t:.2f} s depuis l'import")
    QtCore.QTimer.singleShot(2500, lambda: essayer("quick3d", controle))


essayer("images", images)
QtCore.QTimer.singleShot(500, lambda: essayer("websockets", websockets))
QtCore.QTimer.singleShot(3000, lambda: essayer("graphs", graphs))
QtCore.QTimer.singleShot(4500, lambda: essayer("quick3d", quick3d))
app.exec()
