// Harnais de test_run_sync_refuse.py : le vrai Pyodide (site/pyodide-qt, sans Qt) sous bun (JavaScriptCore) ou node (V8),
// avec ou sans `boucles_qt` (qtpy6web.js), qui met l'aiguilleur de syncifyHandler. Python appelle un rappel JS qui rentre
// dans le wasm sans passer par une entrée de Pyodide (comme Qt-WASM ou embind) : can_run_sync l'y croit suspendable, et
// run_sync suspend avec une frame JS entre lui et l'entrée promettante. Écrit en JSON : mort (erreur fatale), retour du
// rappel, ce que Python a noté, une suspension ordinaire (sans frame JS) qui doit passer, Pyodide encore vivant, refus comptés.
const [, , chemin_js, dossier, mode] = process.argv;
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: () => null, setItem() {} },
  window: globalThis,
});
const m = await import(chemin_js);
if (mode !== "sans") m.boucles_qt();
const { loadPyodide } = await import(new URL("pyodide.mjs", dossier).href);
const py = await loadPyodide({ indexURL: new URL(dossier).pathname, stdout: () => {}, stderr: () => {} });
m.suspension.M = py._module;
let mort = null;
py._api.on_fatal = e => { mort = String(e && e.message); };
globalThis.attendre = () => new Promise(r => setTimeout(r, 0));
globalThis.rappel = () => {
  // mode « import » : le refus arrive dans un chercheur de sys.meta_path pendant un import (la Pause de qtpy6.web.importer,
  // élève sur iPhone du 25/11/2026, W1027) ; l'import doit aboutir.
  const M = py._module, ptr = M.stringToNewUTF8(mode === "import" ? `
from pyodide.ffi import run_sync, can_run_sync, JsException
import js, sys
note.append(can_run_sync())
class Pause:
    @staticmethod
    def find_spec(*_):
        try:
            run_sync(js.attendre())
        except JsException:
            note.append("refus")
        return None
sys.meta_path.insert(0, Pause)
try:
    import fractions
    note.append("importé")
except BaseException as e:
    note.append("échec " + type(e).__name__)
finally:
    sys.meta_path.remove(Pause)` : `
from pyodide.ffi import run_sync, can_run_sync, JsException
import js
note.append(can_run_sync())
try:
    run_sync(js.attendre())
    note.append("suspendu")
except JsException as e:
    note.append("refus")`);
  try { return M._PyRun_SimpleString(ptr); } finally { M._free(ptr); }
};
const f = py.runPython(`
import js
note = []
def f():
    return js.rappel()
def g():
    from pyodide.ffi import run_sync
    run_sync(js.attendre())
    return "suspendu"
f`), g = py.globals.get("g");
const res = { normal: null, mort: null, retour: null, note: null, vivant: null, refus_sync: 0 };
try { res.retour = await f.callPromising(); } catch (e) { res.retour = "erreur " + String(e && e.message).slice(0, 200); }
try { res.normal = await g.callPromising(); } catch (e) { res.normal = "erreur " + String(e && e.message).slice(0, 200); }
res.mort = mort;
try { res.note = py.runPython("str(note)"); res.vivant = py.runPython("1 + 1") === 2; } catch (e) { res.vivant = false; }
res.refus_sync = m.suspension.refus_sync ?? null;
console.log(JSON.stringify(res));
