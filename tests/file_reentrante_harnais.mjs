// Harnais de test_file_reentrante.py (le Pyodide-Qt de construire.sh, sous node). QWasmSuspendResumeControl::sendPendingEvents compte la file une fois, puis fait shift() autant de fois ; un
// processEvents imbriqué (un slot qui l'appelle) vide la file entre-temps et la boucle externe lit event["index"] sur
// undefined (« undefined is not an object (evaluating 'handle[key]') » sous Safari).
// Écrit en JSON : mort (le message de l'exception) ou null, slots imbriqués, événements restés en file.
//   node file_reentrante_harnais.mjs [dist]
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const dist = resolve(process.argv[2] || "/DATA/Python/outils_wasm/pyside6/build/dynamique/dist") + "/";
globalThis.document = {};
globalThis.window = globalThis;
globalThis.location = { href: pathToFileURL(dist).href };
globalThis.fetch = async u => readFile(fileURLToPath(String(u))).then(o => new Response(o), () => new Response(null, { status: 404 }));
const { loadPyodide } = await import(pathToFileURL(dist + "pyodide.mjs").href);
const py = await loadPyodide({ indexURL: dist });
py.runPython(`
from PySide6 import QtCore
import pyodide_js
app = QtCore.QCoreApplication([])
imbrique = []
def slot():
    # un événement du navigateur livré pendant le slot (WebKit en livre de synchrones) : son handler JS rappelle
    # qtSendPendingEvents, qui vide la file que la boucle externe a déjà comptée
    imbrique.append(1)
    pyodide_js._module.qtSendPendingEvents()
QtCore.QTimer.singleShot(0, slot)
`);
const M = py._module, ctrl = M.qtSuspendResumeControl;
const ids = Object.keys(ctrl.eventHandlers).map(Number);
ctrl.pendingEvents.push(...ids.flatMap(i => [{ index: i, arg: null }, { index: i, arg: null }]));
let mort = null;
try { M.qtSendPendingEvents(); } catch (e) { mort = String(e.message || e); }
console.log(JSON.stringify({ mort, slots: py.runPython("len(imbrique)"), reste: ctrl.pendingEvents.length }));
