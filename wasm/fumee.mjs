// Test de fumée, sous node : le Pyodide de construire.sh importe PySide6 et fait circuler un signal, sa bibliothèque
// standard est en .pyc, les dix-neuf modules Qt à la demande se chargent au premier import (sqlite, DOM, QTest...), et qtpy6
// s'y charge en mode paresseux.
//   node wasm/fumee.mjs [dossier]      (le paquet de phase_paquet dépaqueté ; modèle : scripts/smoke-test.mjs de Pyodide-Qt)
// QApplication et les widgets veulent un navigateur (DOM) : la sonde de qtpy6.web, pas d'ici.
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const dist = resolve(process.argv[2] || "/DATA/Python/outils_wasm/pyside6/build/dynamique/dist") + "/";
// L'enveloppe pyodide.mjs (pyodide-qt.mjs) ne charge l'agrégat de Qt que dans une page : on s'en donne l'air, fetch lisant
// le disque (sans jumeaux compressés ici : elle se rabat sur le fichier lui-même, comme en développement).
globalThis.document = {};
globalThis.window = globalThis;  // le répartiteur d'événements de Qt programme ses réveils par window.setTimeout (QQmlEngine en poste)
globalThis.location = { href: pathToFileURL(dist).href };
globalThis.fetch = async u => readFile(fileURLToPath(String(u))).then(o => new Response(o), () => new Response(null, { status: 404 }));
const { loadPyodide } = await import(pathToFileURL(dist + "pyodide.mjs").href);
const py = await loadPyodide({ indexURL: dist });
const sortie = py.runPython(`
import PySide6, shiboken6
from PySide6 import QtCore, QtGui, QtWidgets, QtSvg, QtSvgWidgets

class Emetteur(QtCore.QObject):
    valeur = QtCore.Signal(int)

app = QtCore.QCoreApplication([])
recu = []
e = Emetteur()
e.valeur.connect(recu.append)
e.valeur.emit(42)
app.processEvents()  # pas exec() : sans ASYNCIFY, Qt-WASM ne bloque pas (c'est le rôle de qtpy6.web.bloquant)
import json
f"PySide6 {PySide6.__version__} Qt {QtCore.qVersion()} signal={recu} valide={shiboken6.isValid(e)} pyc={json.__file__.endswith('.pyc')}"
`);
console.log(sortie);
if (!sortie.includes("signal=[42] valide=True")) { console.error("ÉCHEC"); process.exit(1); }
if (!sortie.endsWith("pyc=True")) console.error("ATTENTION : bibliothèque standard en sources .py (pas le paquet de phase_paquet)");

// Les modules à la demande : chacun téléchargé et chargé au premier import, depuis un contexte suspendable (run_sync,
// JSPI : node l'a depuis la version 24 ; runPythonAsync entre par callPromising, runPython non et le finder lève alors
// ImportError). QtOpenGLWidgets tire QtOpenGL. Sans QGuiApplication ici (pas de DOM) : QPrinter, QOpenGLWidget et le GET
// de QNetworkAccessManager sont pour la sonde de qtpy6.web.
const demande = await py.runPythonAsync(`
from PySide6 import QtPrintSupport, QtNetwork, QtSql, QtXml, QtConcurrent, QtOpenGLWidgets, QtOpenGL, QtTest
base = QtSql.QSqlDatabase.addDatabase("QSQLITE"); base.setDatabaseName(":memory:"); base.open()
r = QtSql.QSqlQuery(base); r.exec("create table t (n int)"); r.exec("insert into t values (42)"); r.exec("select n from t"); r.next()
sql = r.value(0)
d = QtXml.QDomDocument(); d.setContent("<a><b>texte</b></a>")
xml = d.documentElement().firstChildElement("b").text()
t = QtCore.QElapsedTimer(); t.start(); QtTest.QTest.qWait(20)
f"sqlite={sql} dom={xml} qWait={t.elapsed() >= 20} hote={QtNetwork.QHostAddress('127.0.0.1').toString()} " \
f"imprimantes={QtPrintSupport.QPrinterInfo.availablePrinterNames()} concurrent={len([n for n in dir(QtConcurrent) if not n.startswith('_')])}"
`);
console.log(demande);
if (!demande.startsWith("sqlite=42 dom=texte qWait=True hote=127.0.0.1")) { console.error("ÉCHEC modules à la demande"); process.exit(1); }

// Qt Quick, Multimedia, Charts : chacun son .so au premier import, Qml après Network, Quick après Qml (DEPENDANCES de
// pyodide-qt.mjs). Sans DOM ni QGuiApplication : le moteur QML évalue (QJSEngine, puis un QQmlComponent qui instancie
// un QtObject), les types des autres existent et les classes sans fenêtre se construisent.
const quick = await py.runPythonAsync(`
from PySide6 import QtQml, QtQuick, QtQuickWidgets, QtQuickControls2, QtMultimedia, QtMultimediaWidgets, QtCharts
js = QtQml.QJSEngine().evaluate("6 * 7").toInt()
moteur = QtQml.QQmlEngine()
c = QtQml.QQmlComponent(moteur)
c.setData(b"import QtQml\\nQtObject { property int x: 6 * 7 }", QtCore.QUrl())
objet = c.create()
qml = objet.property("x") if objet else c.errorString()
audio = QtMultimedia.QAudioFormat(); audio.setSampleRate(44100); audio.setChannelCount(2)
format = QtMultimedia.QMediaFormat()
serie = QtCharts.QLineSeries(); serie.append(1.0, 2.0); serie.append(3.0, 4.0)
f"js={js} qml={qml} audio={audio.sampleRate()}/{audio.channelCount()} fichiers={len(format.supportedFileFormats(QtMultimedia.QMediaFormat.ConversionMode.Decode)) >= 0} serie={serie.count()} " \\
f"item={hasattr(QtQuick, 'QQuickItem')} widget={hasattr(QtQuickWidgets, 'QQuickWidget')} controles={hasattr(QtQuickControls2, 'QQuickStyle')} " \\
f"video={hasattr(QtMultimediaWidgets, 'QVideoWidget')}"
`);
console.log(quick);
if (!quick.startsWith("js=42 qml=42 audio=44100/2")) { console.error("ÉCHEC Quick, Multimedia, Charts"); process.exit(1); }

// WebSockets, Quick3D, Graphs, GraphsWidgets (10/10/2026) et les greffons d'images de qtimageformats dans l'agrégat :
// un QWebSocket se construit sans réseau, les types existent, et QImageReader connaît les nouveaux formats.
const quatre = await py.runPythonAsync(`
from PySide6 import QtWebSockets, QtQuick3D, QtGraphs, QtGraphsWidgets
ws = QtWebSockets.QWebSocket(); ws.setMaxAllowedIncomingFrameSize(1024)
formats = sorted(bytes(f).decode() for f in QtGui.QImageReader.supportedImageFormats())
f"ws={ws.maxAllowedIncomingFrameSize()} q3d={hasattr(QtQuick3D, 'QQuick3DGeometry')} graphs={hasattr(QtGraphs, 'QLineSeries')} " \\
f"gw={hasattr(QtGraphsWidgets, 'Q3DBarsWidgetItem')} images={all(x in formats for x in ('tga', 'wbmp', 'tiff', 'webp', 'icns'))}"
`);
console.log(quatre);
if (quatre !== "ws=1024 q3d=True graphs=True gw=True images=True") { console.error("ÉCHEC WebSockets, Quick3D, Graphs, images"); process.exit(1); }

// qtpy6 sur ce build : le mode paresseux de qtpy6._binding (crochet de shiboken). Les doublures du navigateur lisent
// des noms par ns["…"] à l'import : un nom absent de la liste `needed` de _binding.load fait échouer ce qui suit.
py.FS.mkdir("/qtpy6");
py.FS.mount(py.FS.filesystems.NODEFS, { root: resolve(import.meta.dirname, "..") }, "/qtpy6");
const qtpy6 = py.runPython(`
import os, sys
sys.path.insert(0, "/qtpy6")
os.environ["QT_API"] = "pyside6"
from qtpy6 import QtCore, QtGui, QtWidgets, _binding
etoiles = {}
for m in ("QtCore", "QtGui", "QtWidgets"):
    exec(f"from qtpy6.{m} import *", etoiles)
jamais_nomme = type(QtCore.QObject().meta_object())  # créée par Qt, aucun code ne l'a nommée : le crochet l'a finie
f"paresseux={_binding.LAZY} noms={len(etoiles)} alias={hasattr(jamais_nomme, 'class_name')}"
`);
console.log(qtpy6);
if (!qtpy6.startsWith("paresseux=True") || !qtpy6.endsWith("alias=True")) { console.error("ÉCHEC qtpy6"); process.exit(1); }
console.log("fumée : OK");
process.exit(0);  // la fausse page laisse la boucle de node vivante : sans cela, il attendrait indéfiniment
