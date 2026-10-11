"""Les modules QML d'appoint de Quick3D dans le navigateur (notes/2026-10-10 - Modules Qt à la demande.md, point ouvert
« QtQuick3D.Helpers, .Effects, .Particles3D… manquent à un QML qui les importe » ; l'utilisateur, 11/10/2026 : « continues »).
Une scène par module, chacune dans un QQuickWidget créé depuis un slot ; verdict : statut Ready, aucune erreur QML, et des
pixels rendus (grabFramebuffer, comme `essais/rendu_webgl/page.py`) :

  - helpers : AxisHelper et OrbitCameraController (QtQuick3D.Helpers), ExtendedSceneEnvironment (Helpers.impl) ;
  - effects : SceneEnvironment avec un effet Vignette (QtQuick3D.Effects) ;
  - particules : ParticleSystem3D, ParticleEmitter3D de sprites rouges (QtQuick3D.Particles3D) ;
  - particle_effects : un `import QtQuick3D.ParticleEffects` (son seul enregistrement).

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "Quick3D : modules d'appoint"
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

FOND = 'Rectangle { anchors.fill: parent; color: "#203040" }'
CUBE = 'Model { source: "#Cube"; eulerRotation.y: 30; eulerRotation.x: 20; materials: PrincipledMaterial { baseColor: "red" } }'
QML = {
    "helpers": f"""import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
Item {{ width: 320; height: 170
  View3D {{ id: vue; anchors.fill: parent
    environment: ExtendedSceneEnvironment {{ backgroundMode: SceneEnvironment.Color; clearColor: "#203040"; vignetteEnabled: true }}
    Node {{ id: origine; PerspectiveCamera {{ id: camera; z: 300 }} }}
    DirectionalLight {{ }}
    AxisHelper {{ enableXYGrid: true }}
    {CUBE} }}
  OrbitCameraController {{ anchors.fill: parent; origin: origine; camera: camera }} }}
""",
    "effects": f"""import QtQuick
import QtQuick3D
import QtQuick3D.Effects
View3D {{ width: 320; height: 170
  environment: SceneEnvironment {{ backgroundMode: SceneEnvironment.Color; clearColor: "#203040"; effects: [ Vignette {{ }} ] }}
  PerspectiveCamera {{ z: 300 }}
  DirectionalLight {{ }}
  {CUBE} }}
""",
    "particules": """import QtQuick
import QtQuick3D
import QtQuick3D.Particles3D
View3D { width: 320; height: 170
  environment: SceneEnvironment { backgroundMode: SceneEnvironment.Color; clearColor: "#203040" }
  PerspectiveCamera { z: 300 }
  ParticleSystem3D {
    SpriteParticle3D { id: point; color: "red"; maxAmount: 400; particleScale: 6 }
    ParticleEmitter3D { particle: point; emitRate: 200; lifeSpan: 3000; particleScale: 6
      velocity: VectorDirection3D { direction: Qt.vector3d(0, 40, 0); directionVariation: Qt.vector3d(60, 20, 0) } } } }
""",
    "particle_effects": """import QtQuick
import QtQuick3D
import QtQuick3D.ParticleEffects
Rectangle { width: 320; height: 170; color: "red" }
""",
}
NOMS = tuple(QML)


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
fenetre.resize(520, 900)
fenetre.show()
ACTIFS = []


def rouges(image) -> int:
    return sum(1 for x in range(0, image.width(), 4) for y in range(0, image.height(), 4)
               if (c := image.pixelColor(x, y)).red() > 100 and c.green() < 70 and c.blue() < 70)


def scene(nom: str) -> None:
    t = time.monotonic()
    from PySide6 import QtQuick3D, QtQuickWidgets  # noqa: F401 - QtQuick3D charge le module QML et ses greffons
    print(f"import : {time.monotonic() - t:.2f} s")
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
        n = 0 if image.isNull() else rouges(image)
        verdict(nom, n > 10 and qw.status() == QtQuickWidgets.QQuickWidget.Status.Ready and not erreurs,
                f"statut={qw.status().name}, erreurs={erreurs}, framebuffer {image.width()}x{image.height()}, {n} points rouges")
    QtCore.QTimer.singleShot(3000, lambda: essayer(nom, controle))


for i, nom in enumerate(NOMS):
    QtCore.QTimer.singleShot(500 + 4000 * i, lambda nom=nom: essayer(nom, lambda: scene(nom)))
app.exec()
