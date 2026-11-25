// Harnais de test_run_sync_refuse.py, test du préchargement `qt` de preparer : le vrai Pyodide-Qt DYNAMIQUE (pyodide.mjs de
// pyodide-qt.mjs, l'agrégat et pyside_QtNetwork.so) sous bun (JavaScriptCore) ou node (V8), avec `boucles_qt` (qtpy6web.js).
// `import PySide6.QtNetwork` est lancé là où run_sync est refusé (un rappel JS rentre dans le wasm hors entrée de Pyodide,
// comme le démarrage sur l'iPhone de L-61) : sans préchargement, le chercheur de Pyodide-Qt doit suspendre et l'import
// échoue ; avec (mode « avec » : _pyodide_qt.charger, ce que fait preparer pour `qt`), il aboutit. Écrit en JSON.
const [, , chemin_js, dossier, mode] = process.argv;
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "", href: "file:///" },
  document: { visibilityState: "visible" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: () => null, setItem() {} },
  window: globalThis,
});
const { readFile } = await import("node:fs/promises"), fetch_reseau = globalThis.fetch;
globalThis.fetch = async (url, ...a) => String(url).startsWith("file:")  // node ne lit pas file:// par fetch
  ? readFile(new URL(String(url))).then(o => new Response(o), () => new Response(null, { status: 404 }))
  : fetch_reseau(url, ...a);
delete globalThis.DecompressionStream;  // les fichiers eux-mêmes : un build n'a pas les jumeaux .br/.gz de l'hébergement
const m = await import(chemin_js);
m.boucles_qt();
const { loadPyodide } = await import(new URL("pyodide.mjs", dossier).href);
const py = await loadPyodide({ indexURL: new URL(dossier).pathname, stdout: () => {}, stderr: () => {} });
m.suspension.M = py._module;
let mort = null;
py._api.on_fatal = e => { mort = String(e && e.message); };
if (mode === "avec") await py.pyimport("_pyodide_qt").charger("/lib/pyside_QtNetwork.so");
globalThis.rappel = () => {
  const M = py._module, ptr = M.stringToNewUTF8(`
try:
    import PySide6.QtNetwork
    note.append("importé " + PySide6.QtNetwork.QNetworkRequest.__name__)
except BaseException as e:
    note.append("échec " + type(e).__name__)`);
  try { return M._PyRun_SimpleString(ptr); } finally { M._free(ptr); }
};
const f = py.runPython(`
import js
note = []
def f():
    return js.rappel()
f`);
const res = { mort: null, retour: null, note: null, refus_sync: 0 };
try { res.retour = await f.callPromising(); } catch (e) { res.retour = "erreur " + String(e && e.message).slice(0, 200); }
res.mort = mort;
try { res.note = py.runPython("str(note)"); } catch (e) { res.note = "Pyodide mort"; }
res.refus_sync = m.suspension.refus_sync ?? null;
console.log(JSON.stringify(res));
process.exit(0);
