// Pyodide-Qt, Qt en module dynamique (qtpy6/wasm/construire.sh, phase dynamique) : le Pyodide amont est pyodide-base.mjs ;
// cette enveloppe, dans une PAGE seulement, charge pyside_agrege.so (Qt + PySide6) par le chargeur JS d'emscripten, en
// asynchrone, puis retire le fichier du FS : le dlopen C de Python n'y trouve rien à recopier dans le tas (+25 Mo sinon,
// dynlink.c ne libère jamais file_data) et retrouve la bibliothèque déjà chargée par son nom. Un worker (pas de document)
// n'en charge rien : les modules qui y tournent n'importent pas Qt.
import { loadPyodide as base, version } from "./pyodide-base.mjs";
export { version };
const SO = "/lib/pyside_agrege.so";
const MODULES = ["shiboken6.Shiboken", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtSvg", "PySide6.QtSvgWidgets"];
// Les jumeaux compressés de l'hébergement (NOM.br, NOM.gz : hebergement/telecharger.sh), comme en_jumeau de qtpy6web.js :
// le meilleur que le navigateur décompresse, le fichier lui-même à défaut (en développement). Une réponse marquée
// X-Qtpy6-Decompresse vient du service worker d'une page, qui la range décompressée.
const JUMEAU = [[".br", "brotli"], [".gz", "gzip"]].find(([, format]) => {
  try { new DecompressionStream(format); return true; } catch { return false; } });
async function octets(url) {
  if (JUMEAU) {
    const r = await fetch(url + JUMEAU[0]).catch(() => undefined);
    if (r?.ok) return new Response(r.headers.has("X-Qtpy6-Decompresse") ? r.body
                                   : r.body.pipeThrough(new DecompressionStream(JUMEAU[1]))).arrayBuffer();
  }
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} : ${r.status}`);
  return r.arrayBuffer();
}
export async function loadPyodide(options = {}) {
  if (typeof document === "undefined") return base(options);
  const url = new URL("pyside_agrege.so", options.indexURL ? new URL(options.indexURL, location.href) : import.meta.url);
  const recus = octets(url);
  recus.catch(() => {});  // rejet relevé par l'await plus bas, pas en « non géré » pendant loadPyodide
  const py = await base(options);
  py.FS.writeFile(SO, new Uint8Array(await recus));
  await py._module.loadDynamicLibrary(SO, { loadAsync: true, global: false, nodelete: true }, {});
  py.FS.unlink(SO);
  py.runPython(`def _poser():
    import sys, importlib.machinery as m
    class QtAgrege:  # les six modules de l'agrégat, tous servis par le même fichier
        NOMS = frozenset(${JSON.stringify(MODULES)})
        @classmethod
        def find_spec(cls, nom, chemin=None, cible=None):
            if nom in cls.NOMS:
                return m.ModuleSpec(nom, m.ExtensionFileLoader(nom, "${SO}"), origin="${SO}")
    sys.meta_path.insert(0, QtAgrege)
_poser()
del _poser`);
  return py;
}
