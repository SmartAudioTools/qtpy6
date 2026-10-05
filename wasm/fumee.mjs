// Test de fumée, sous node : le Pyodide de construire.sh importe PySide6 et fait circuler un signal, sa bibliothèque
// standard est en .pyc, et qtpy6 s'y charge en mode paresseux.
//   node wasm/fumee.mjs [dossier]      (le paquet de phase_paquet dépaqueté ; modèle : scripts/smoke-test.mjs de Pyodide-Qt)
// QApplication et les widgets veulent un navigateur (DOM) : la sonde de qtpy6.web, pas d'ici.
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const dist = resolve(process.argv[2] || "/DATA/Python/outils_wasm/pyside6/build/dynamique/dist") + "/";
// L'enveloppe pyodide.mjs (pyodide-qt.mjs) ne charge l'agrégat de Qt que dans une page : on s'en donne l'air, fetch lisant
// le disque (sans jumeaux compressés ici : elle se rabat sur le fichier lui-même, comme en développement).
globalThis.document = {};
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
