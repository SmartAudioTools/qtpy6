// W576 (17/11/2026) : reproduction minimale, Pyodide nu sous Node, piles JSPI entrelacées + GC jeune agressif.
// Usage : node gcnu.mjs [variante] [fils] [tours]
//   variante : "entrelace" (défaut) N entrées promettantes simultanées, chacune suspend par run_sync ;
//              "imbrique"  une entrée promettante qui, pendant sa suspension, en relance une autre (pompe) ;
//              "seul"      témoin : une seule entrée à la fois (pas d'entrelacement).
// Témoins (variables d'environnement) : GC=0 laisse les seuils par défaut ; GC=off coupe le GC automatique ;
// GC=jeune|incr|plein : GC automatique coupé, gc.collect(0|1|2) explicite à chaque tour (discrimine la passe en cause) ;
// SUSP=0 remplace la suspension par un appel sans bascule.
// Le Pyodide chargé est celui du site : ../site/pyodide/ (314.0.7).
const dossier = process.env.PYODIDE || "../site/pyodide/";  // pyodide_patche/ : correctif c. émulé (CORRIGE=1)
const { loadPyodide } = await import(dossier + "pyodide.mjs");
import { fileURLToPath } from "node:url";
import path from "node:path";

const ici = path.dirname(fileURLToPath(import.meta.url));
const variante = process.argv[2] || "entrelace";
const fils = +(process.argv[3] || 4);
const tours = +(process.argv[4] || 200);

const py = await loadPyodide({ indexURL: path.join(ici, dossier) });
console.log("GC", process.env.GC || "1", "SUSP", process.env.SUSP || "1", "pyodide", py.version, "node", process.version, "variante", variante, "fils", fils, "tours", tours);

py.globals.set("GC_MODE", process.env.GC || "1");
py.globals.set("SUSP", process.env.SUSP || "1");
py.runPython(`
import gc, sys
from pyodide.ffi import run_sync
import js

if GC_MODE == "1": gc.set_threshold(1, 1, 1)
elif GC_MODE != "0": gc.disable()
PASSE = {"jeune": 0, "incr": 1, "plein": 2}.get(GC_MODE)
fini = []

class Noeud:
    def __init__(s, p): s.p = p; s.moi = s; s.l = [s, p, {"k": s}]

def attendre_js(ms):
    # Une suspension JSPI : la pile Python de ce fil est mise de côté, la boucle JS reprend la main.
    if SUSP == "0": return None
    return run_sync(js.Promise.new(lambda ok, ko: js.setTimeout(ok, ms)))

def fil(n, tours, relance=None):
    racine = None
    for t in range(tours):
        racine = Noeud(racine)            # cycles : la passe jeune a du travail
        if t % 7 == 0: racine = None
        lst = [Noeud(None) for _ in range(5)]
        if relance is not None and t == 3:
            relance()                      # une autre entrée promettante démarre PENDANT notre vie
        if PASSE is not None: gc.collect(PASSE)
        attendre_js((n + t) % 3)           # bascule
        del lst
    fini.append(n)
`);

const fil = py.globals.get("fil");
const t0 = Date.now();
try {
  if (variante === "seul") {
    for (let n = 0; n < fils; n++) await fil.callPromising(n, tours);
  } else if (variante === "imbrique") {
    // Chaque fil relance le suivant de l'intérieur (comme pomper → callPromising pendant une attente).
    const promesses = [];
    const lancer = (n) => () => { if (n < fils) promesses.push(fil.callPromising(n, tours, lancer(n + 1))); };
    promesses.push(fil.callPromising(0, tours, lancer(1)));
    while (promesses.length < fils) await new Promise((r) => setTimeout(r, 5));
    await Promise.all(promesses);
  } else {
    await Promise.all(Array.from({ length: fils }, (_, n) => fil.callPromising(n, tours)));
  }
  console.log("OK fini", py.globals.get("fini").toJs(), "en", Date.now() - t0, "ms");
} catch (e) {
  console.log("PLANTAGE", String(e && e.stack || e));
  process.exitCode = 1;
}
if (py._module.W576stats) console.log("SONDE", JSON.stringify(py._module.W576stats));
process.exit();  // Pyodide garde des poignées ouvertes sous Node : sortir explicitement
