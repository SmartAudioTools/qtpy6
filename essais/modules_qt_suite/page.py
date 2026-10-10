"""Essai de QtCharts, QtMultimedia et Qt Quick chargés à la demande (notes/2026-10-10 - Modules Qt à la demande.md) : trois
contrôles INDÉPENDANTS, chacun dans son try, chacun avec son verdict dans le journal (« VERDICT <nom> : OK/ECHEC <détail> »).
Ordre : Charts, Multimedia, puis Quick en dernier (WebGL : un échec de Qt Quick peut tuer le moteur wasm, les deux autres
auront déjà rendu leur verdict). État de la page : « essai_fini » quand les trois verdicts sont écrits, réussis ou non.
Même script sur le bureau.

  - Charts : QChartView + QLineSeries, rendu raster (QChartView n'utilise pas OpenGL par défaut) ; verdict = la capture du
    widget (grab) contient plus d'une couleur.
  - Multimedia : QMediaPlayer + QAudioOutput, QMediaDevices.defaultAudioOutput(), QSoundEffect sur un WAV généré.
  - Quick : QQuickWidget (Rectangle rouge + Text) ; à défaut QQuickView dans une fenêtre à part.

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "Quick, Multimedia, Charts"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 120 --etat essai_fini > sonde.log 2>&1
    (hors bac à sable : même commande, sortie dans sonde_hors_bac.log)

Résultat (10/10/2026, Firefox 155 sans interface DANS le bac à sable, paquet build/dynamique/dist servi tel quel : pas de
jumeaux .br, pyodide-qt.mjs retombe sur le .so brut après un 404 du .br) :
  - Charts : OK. `import QtCharts` 0,04 s (charge aussi OpenGLWidgets), graphique raster rendu et visible (23 couleurs).
  - Multimedia : objets OK, pas de son vérifié. QMediaPlayer + QAudioOutput créés, defaultAudioOutput = « WebAssembly audio
    playback device », QSoundEffect passe à Ready ; le QMediaPlayer reste NoMedia (« virtual void QWasmMediaPlayer::stop()
    319 » en console.warn) et le play() de l'élément audio est refusé (NotAllowedError : pas de geste utilisateur).
  - Quick : import et QQuickWidget Ready (14 h, après le correctif de pyodide-qt.mjs : dépendance OpenGL, chargement global) ;
    rendu non vérifié ici, ce Firefox n'a pas de WebGL (« Failed to get a QRhi »). Avant : SuspendError à l'import.
  - `?sans=quick` isole Charts et Multimedia (diagnostic). Journaux : sonde*.log. Jumeaux `.br` : `site/pyodide-qt-br/`
    (liens vers dist/ + `brotli -q 11` des nouveaux .so), `site/pyodide-qt` pointé dessus : chargés sans repli (sonde_br.log).
"""

import math
import os
import struct
import sys
import tempfile
import time
import wave

from qtpy6 import QtCore, QtGui, QtWidgets
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
VERDICTS = {}


def etat(valeur):
    if WEB:
        js.window.etat = valeur


def ressources():
    if WEB:
        print("ressources :", ", ".join(f"{r.name.rsplit('/', 1)[-1]} {int(r.startTime)}+{int(r.duration)} ms"
                                        for r in js.performance.getEntriesByType("resource") if "pyside_Qt" in r.name))


def verdict(nom, ok, detail=""):
    VERDICTS[nom] = ok
    print(f"VERDICT {nom} : {'OK' if ok else 'ECHEC'} {detail} ({time.monotonic() - T0:.2f} s)")
    if len(VERDICTS) == 3:
        ressources()
        etat("essai_fini")  # le gabarit pose « fini » dès le lancement : l'état de l'essai est un autre


def essayer(nom, f):
    try:
        f()
    except BaseException as e:  # noqa: BLE001 - un contrôle qui échoue ne doit pas masquer les autres
        verdict(nom, False, f"exception {type(e).__name__} : {e}")


app = application()
fenetre = QtWidgets.QWidget()
fenetre.setWindowTitle("Quick, Multimedia, Charts")
colonne = QtWidgets.QVBoxLayout(fenetre)
journal = QtWidgets.QLabel("…")
journal.setWordWrap(True)
colonne.addWidget(journal)
fenetre.resize(520, 700)
fenetre.show()
ACTIFS = []  # références des objets vivants


def note(texte):
    print(texte)
    journal.setText(journal.text() + "\n" + texte)


# ---------- Charts ----------
def charts():
    t = time.monotonic()
    from PySide6 import QtCharts
    note(f"import QtCharts : {time.monotonic() - t:.2f} s")
    serie = QtCharts.QLineSeries()
    for x in range(0, 21):
        serie.append(x, math.sin(x / 3) * 10 + x)
    graphique = QtCharts.QChart()
    graphique.addSeries(serie)
    graphique.setTitle("QLineSeries")
    graphique.createDefaultAxes()
    vue = QtCharts.QChartView(graphique)
    vue.setMinimumSize(480, 260)
    colonne.addWidget(vue)
    ACTIFS.append(vue)

    def controle():
        image = vue.grab().toImage()
        couleurs = {image.pixel(x, y) for x in range(0, image.width(), 7) for y in range(0, image.height(), 7)}
        verdict("charts", len(couleurs) > 2, f"grab {image.width()}x{image.height()}, {len(couleurs)} couleurs, "
                                              f"{serie.count()} points, {time.monotonic() - t:.2f} s depuis l'import")
    QtCore.QTimer.singleShot(800, lambda: essayer("charts", controle))


# ---------- Multimedia ----------
def wav():
    chemin = os.path.join(tempfile.gettempdir(), "bip.wav")
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 22050))) for i in range(4410)))
    return chemin


def multimedia():
    t = time.monotonic()
    from PySide6 import QtMultimedia
    note(f"import QtMultimedia : {time.monotonic() - t:.2f} s")
    details = []
    joueur = QtMultimedia.QMediaPlayer()
    sortie = QtMultimedia.QAudioOutput()
    joueur.setAudioOutput(sortie)
    ACTIFS.extend([joueur, sortie])
    details.append("QMediaPlayer+QAudioOutput créés")
    defaut = QtMultimedia.QMediaDevices.defaultAudioOutput()
    details.append(f"defaultAudioOutput nul={defaut.isNull()} description={defaut.description()!r}")
    details.append(f"audioOutputs={[d.description() for d in QtMultimedia.QMediaDevices.audioOutputs()]}")
    chemin = wav()
    joueur.errorOccurred.connect(lambda e, s: note(f"QMediaPlayer erreur {e} {s}"))
    joueur.setSource(QtCore.QUrl.fromLocalFile(chemin))
    joueur.play()
    details.append(f"player état={joueur.playbackState().name} statut={joueur.mediaStatus().name}")
    try:
        bip = QtMultimedia.QSoundEffect()
        bip.setSource(QtCore.QUrl.fromLocalFile(chemin))
        ACTIFS.append(bip)
        bip.statusChanged.connect(lambda: note(f"QSoundEffect statut {bip.status().name}"))
        bip.play()
        details.append(f"QSoundEffect statut={bip.status().name}")
    except Exception as e:  # noqa: BLE001
        details.append(f"QSoundEffect exception {e}")

    def fin():
        details.append(f"après 1 s : player statut={joueur.mediaStatus().name} erreur={joueur.error().name}")
        verdict("multimedia", True, "; ".join(details))  # OK = les objets se créent et les appels passent
    QtCore.QTimer.singleShot(1500, lambda: essayer("multimedia", fin))


# ---------- Quick ----------
QML = """import QtQuick
Rectangle { width: 300; height: 150; color: "#d02020"
  Text { anchors.centerIn: parent; text: "Qt Quick QML"; color: "white"; font.pixelSize: 28 } }
"""


def quick():
    t = time.monotonic()
    from PySide6 import QtQml
    note(f"import QtQml : {time.monotonic() - t:.2f} s")
    from PySide6 import QtQuick
    note(f"import QtQuick : {time.monotonic() - t:.2f} s")
    from PySide6 import QtQuickWidgets
    note(f"import QtQuickWidgets : {time.monotonic() - t:.2f} s")
    chemin = os.path.join(tempfile.gettempdir(), "essai.qml")
    with open(chemin, "w") as f:
        f.write(QML)
    qw = QtQuickWidgets.QQuickWidget()
    qw.setMinimumSize(320, 170)
    qw.setResizeMode(QtQuickWidgets.QQuickWidget.ResizeMode.SizeRootObjectToView)
    qw.statusChanged.connect(lambda s: note(f"QQuickWidget statut {s.name}"))
    qw.setSource(QtCore.QUrl.fromLocalFile(chemin))
    colonne.addWidget(qw)
    ACTIFS.append(qw)
    note(f"QQuickWidget statut {qw.status().name}, erreurs {[e.toString() for e in qw.errors()]}")

    def controle():
        image = qw.grabFramebuffer()
        rouge = sum(1 for x in range(0, image.width(), 5) for y in range(0, image.height(), 5)
                    if QtGui.QColor(image.pixel(x, y)).red() > 180 and QtGui.QColor(image.pixel(x, y)).green() < 80) \
            if not image.isNull() else 0
        ok = qw.status() == QtQuickWidgets.QQuickWidget.Status.Ready and rouge > 10
        verdict("quick", ok, f"QQuickWidget statut={qw.status().name}, framebuffer {image.width()}x{image.height()}, "
                             f"{rouge} points rouges, {time.monotonic() - t:.2f} s depuis l'import")
    QtCore.QTimer.singleShot(2500, lambda: essayer("quick", controle))


essayer("charts", charts)
QtCore.QTimer.singleShot(1500, lambda: essayer("multimedia", multimedia))
SANS = js.location.search if WEB else ""  # ?sans=quick : isoler un contrôle (diagnostic)
if "sans=quick" in SANS:
    QtCore.QTimer.singleShot(4000, lambda: verdict("quick", False, "non lancé (?sans=quick)"))
else:
    QtCore.QTimer.singleShot(4000, lambda: essayer("quick", quick))
app.exec()
