// Test de fumée de l'étape 4, sous node : le Pyodide relié par construire.sh importe PySide6 et fait circuler un signal.
//   node wasm/fumee.mjs [dossier dist]      (modèle : scripts/smoke-test.mjs de la recette Pyodide-Qt)
// QApplication et les widgets veulent un navigateur (DOM) : ils relèvent de l'étape 5, pas d'ici.
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const dist = resolve(process.argv[2] || "/DATA/Python/outils_wasm/pyside6/sources/pyodide/dist") + "/";
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
f"PySide6 {PySide6.__version__} Qt {QtCore.qVersion()} signal={recu} valide={shiboken6.isValid(e)}"
`);
console.log(sortie);
if (!sortie.includes("signal=[42] valide=True")) { console.error("ÉCHEC"); process.exit(1); }

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
