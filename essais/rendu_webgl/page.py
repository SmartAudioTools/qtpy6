"""Le RENDU de Graphs et de Quick3D dans un navigateur avec WebGL (notes/2026-10-10 - Modules Qt à la demande.md, point
ouvert « Reste : le rendu 3D et Graphs dans un vrai navigateur (WebGL), et Chrome » ; l'utilisateur, 11/10/2026 : « le rendu
WebGL dans Chrome »). `essais/modules_qt_fin/page.py` n'a vérifié que le statut Ready : le Firefox du bac à sable n'a pas
de WebGL. Ici, chaque scène est rendue dans un QQuickWidget, et le verdict compte des pixels de son grabFramebuffer(),
comme le contrôle « quick » de `essais/modules_qt_suite/page.py` :

  - graphs2d : GraphsView, une LineSeries verte épaisse → points verts ;
  - quick3d : View3D, un cube rouge éclairé → points rouges ;
  - bars3d : Bars3D de QtGraphs (3D) → nombre de couleurs distinctes (une scène vide en a une ou deux).

Ordre : du plus sûr au plus risqué (un échec de rendu 3D peut tuer le moteur wasm), un QQuickWidget à la fois, chacun créé
depuis un slot (chargement à la demande). État de la page : « essai_fini » quand les trois verdicts sont écrits.

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "Rendu WebGL : Graphs et Quick3D"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 150 --etat essai_fini [--chromium]
"""

import os
import sys
import tempfile
import time

from qtpy6 import QtCore, QtWidgets
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
VERDICTS = {}
NOMS = ("graphs2d", "quick3d", "bars3d")


def etat(valeur: str) -> None:
    if WEB:
        js.window.etat = valeur


def verdict(nom: str, ok: bool, detail: str = "") -> None:
    if nom in VERDICTS:
        return
    VERDICTS[nom] = ok
    print(f"VERDICT {nom} : {'OK' if ok else 'ECHEC'} {detail} ({time.monotonic() - T0:.2f} s)")
    if len(VERDICTS) == len(NOMS):
        if WEB:
            print("navigateur :", js.navigator.userAgent)
        etat("essai_fini")
        if not WEB:
            app.quit()


def essayer(nom: str, f) -> None:
    try:
        f()
    except BaseException as e:  # noqa: BLE001 - un contrôle qui échoue ne doit pas masquer les autres
        verdict(nom, False, f"exception {type(e).__name__} : {e}")


app = application()
fenetre = QtWidgets.QWidget()
colonne = QtWidgets.QVBoxLayout(fenetre)
fenetre.resize(520, 760)
fenetre.show()
ACTIFS = []

QML = {
    "graphs2d": """import QtQuick
import QtGraphs
GraphsView { width: 320; height: 170
  axisX: ValueAxis { max: 10 }
  axisY: ValueAxis { max: 100 }
  LineSeries { color: "#00ff00"; width: 6
    XYPoint { x: 0; y: 0 } XYPoint { x: 5; y: 80 } XYPoint { x: 10; y: 20 } } }
""",
    "quick3d": """import QtQuick
import QtQuick3D
Rectangle { width: 320; height: 170; color: "#203040"
  View3D { anchors.fill: parent
    PerspectiveCamera { z: 300 }
    DirectionalLight { }
    Model { source: "#Cube"; eulerRotation.y: 30; eulerRotation.x: 20
      materials: PrincipledMaterial { baseColor: "red" } } } }
""",
    "bars3d": """import QtQuick
import QtGraphs
Bars3D { width: 320; height: 170
  Bar3DSeries { ItemModelBarDataProxy { rowRole: "r"; columnRole: "c"; valueRole: "v"
    itemModel: ListModel { ListElement { r: "a"; c: "x"; v: 3 } ListElement { r: "a"; c: "y"; v: 5 }
                           ListElement { r: "b"; c: "x"; v: 2 } ListElement { r: "b"; c: "y"; v: 4 } } } } }
""",
}


def compter(nom: str, image) -> tuple[bool, str]:
    points = [image.pixelColor(x, y) for x in range(0, image.width(), 4) for y in range(0, image.height(), 4)]
    if nom == "graphs2d":
        n = sum(1 for c in points if c.green() > 180 and c.red() < 90 and c.blue() < 90)
        return n > 10, f"{n} points verts"
    if nom == "quick3d":
        n = sum(1 for c in points if c.red() > 100 and c.green() < 70 and c.blue() < 70)
        return n > 10, f"{n} points rouges"
    n = len({c.rgb() for c in points})
    return n > 8, f"{n} couleurs distinctes"


def scene(nom: str, modules: tuple[str, ...]) -> None:
    t = time.monotonic()
    import importlib
    for m in modules:
        importlib.import_module(f"PySide6.{m}")
    from PySide6 import QtQuickWidgets
    print(f"import {', '.join(modules)} : {time.monotonic() - t:.2f} s")
    chemin = os.path.join(tempfile.gettempdir(), f"{nom}.qml")
    with open(chemin, "w") as f:
        f.write(QML[nom])
    qw = QtQuickWidgets.QQuickWidget()
    qw.setResizeMode(QtQuickWidgets.QQuickWidget.ResizeMode.SizeRootObjectToView)
    qw.setMinimumSize(320, 170)
    qw.setSource(QtCore.QUrl.fromLocalFile(chemin))
    colonne.addWidget(qw)
    ACTIFS.append(qw)

    def controle() -> None:
        erreurs = [e.toString() for e in qw.errors()]
        image = qw.grabFramebuffer()
        ok, detail = (False, "framebuffer vide") if image.isNull() else compter(nom, image)
        verdict(nom, ok and qw.status() == QtQuickWidgets.QQuickWidget.Status.Ready and not erreurs,
                f"statut={qw.status().name}, erreurs={erreurs}, framebuffer {image.width()}x{image.height()}, {detail}, "
                f"{time.monotonic() - t:.2f} s depuis l'import")
    QtCore.QTimer.singleShot(3000, lambda: essayer(nom, controle))


QtCore.QTimer.singleShot(500, lambda: essayer("graphs2d", lambda: scene("graphs2d", ("QtGraphs",))))
QtCore.QTimer.singleShot(4500, lambda: essayer("quick3d", lambda: scene("quick3d", ("QtQuick3D",))))
QtCore.QTimer.singleShot(8500, lambda: essayer("bars3d", lambda: scene("bars3d", ("QtGraphs",))))
app.exec()
