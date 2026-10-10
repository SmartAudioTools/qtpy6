// Pyodide-Qt, Qt en modules dynamiques (qtpy6/wasm/construire.sh, phase dynamique) : le Pyodide amont est pyodide-base.mjs ;
// cette enveloppe, dans une PAGE seulement, charge pyside_agrege.so (Qt + PySide6 : Core, Gui, Widgets, Svg, SvgWidgets)
// par le chargeur JS d'emscripten, en asynchrone, puis retire le fichier du FS : le dlopen C de Python n'y trouve rien à
// recopier dans le tas (+25 Mo sinon, dynlink.c ne libère jamais file_data) et retrouve la bibliothèque déjà chargée par
// son nom. Les autres modules (un pyside_Qt<M>.so chacun, DEMANDE) ne sont téléchargés et chargés qu'au PREMIER
// import, de la même façon, depuis un contexte suspendable (le script lancé par qtpy6.web.lancer, un slot) : le
// chargement est asynchrone, Chrome interdit de compiler du wasm en synchrone sur le fil principal. Tous partagent une
// même table de symboles (global : les exports d'un module rejoignent ceux du module principal, un module chargé ensuite les résout
// AU CHARGEMENT, sans stub JS ; un stub JS sur la pile interdirait toute suspension JSPI en dessous). Un worker (pas de document) n'en
// charge rien : les modules qui y tournent n'importent pas Qt.
import { loadPyodide as base, version } from "./pyodide-base.mjs";
export { version };
const SO = "/lib/pyside_agrege.so";
const MODULES = ["shiboken6.Shiboken", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtSvg", "PySide6.QtSvgWidgets"];
// Les modules à la demande, dans l'ordre : un module qui contient une bibliothèque Qt (Network, Qml, Quick, Multimedia...)
// l'exporte à ceux qui la LIENT, et wasm résout ses imports AU CHARGEMENT, pas à l'appel : un module se charge donc après
// ceux dont il importe les symboles. DEPENDANCES le dit (construire.sh, phase dynamique : symboles.py croises).
const DEPENDANCES = { Qml: ["Network"], Quick: ["Qml", "OpenGL"], QuickWidgets: ["Quick"], QuickControls2: ["Quick"],
                      Multimedia: ["Network"], MultimediaWidgets: ["Multimedia"], Charts: ["OpenGLWidgets"],
                      WebSockets: ["Network"], Quick3D: ["Quick"], Graphs: ["Quick3D"], GraphsWidgets: ["Graphs", "QuickWidgets"] };
const DEMANDE = Object.fromEntries(["PrintSupport", "Network", "Sql", "Xml", "Concurrent", "OpenGL", "OpenGLWidgets", "Test",
                                    "Qml", "Quick", "QuickWidgets", "QuickControls2", "Multimedia", "MultimediaWidgets", "Charts",
                                    "WebSockets", "Quick3D", "Graphs", "GraphsWidgets"]
                                   .map(m => [`PySide6.Qt${m}`, `/lib/pyside_Qt${m}.so`]));
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
  const dossier = options.indexURL ? new URL(options.indexURL, location.href) : import.meta.url;
  async function charger(py, chemin, recus = octets(new URL(chemin.slice("/lib/".length), dossier))) {
    py.FS.writeFile(chemin, new Uint8Array(await recus));
    await py._module.loadDynamicLibrary(chemin, { loadAsync: true, global: true, nodelete: true });
    py.FS.unlink(chemin);
  }
  const recus = octets(new URL("pyside_agrege.so", dossier));
  recus.catch(() => {});  // rejet relevé par l'await plus bas, pas en « non géré » pendant loadPyodide
  const py = await base(options);
  await charger(py, SO, recus);
  // Un seul chargement par module ; un échec (réseau) laisse la place à un nouvel essai. Une page peut charger d'avance
  // (await charger(chemin) du module Python _pyodide_qt) ; un module chargé ne suspend plus rien à l'import.
  const charges = new Map(), faits = new Set();
  const nom_de = chemin => chemin.slice("/lib/pyside_Qt".length, -".so".length);
  // Les dépendances d'abord, une à une (leur ordre est celui du lien), puis le module lui-même.
  const avec_dependances = async chemin => {
    for (const d of DEPENDANCES[nom_de(chemin)] ?? []) await charge(`/lib/pyside_Qt${d}.so`);
    await charger(py, chemin);
  };
  const charge = chemin => {
    if (!charges.has(chemin)) charges.set(chemin, avec_dependances(chemin).then(() => faits.add(chemin),
                                                                                   e => { charges.delete(chemin); throw e; }));
    return charges.get(chemin);
  };
  py.registerJsModule("_pyodide_qt", { deja: chemin => faits.has(chemin), charger: charge });
  py.runPython(`def _poser():
    import sys, importlib.machinery as m
    class QtAgrege:  # les six modules de l'agrégat, servis par le même fichier ; les autres chargés au premier import
        NOMS = frozenset(${JSON.stringify(MODULES)})
        DEMANDE = ${JSON.stringify(DEMANDE)}
        @classmethod
        def find_spec(cls, nom, chemin=None, cible=None):
            if nom in cls.NOMS:
                so = "${SO}"
            elif nom in cls.DEMANDE:
                so = cls.DEMANDE[nom]
                from _pyodide_qt import charger, deja
                if not deja(so):
                    from pyodide.ffi import run_sync
                    try:
                        run_sync(charger(so))
                    except RuntimeError as e:  # pas de suspension possible ici
                        raise ImportError(f"{nom} se charge au premier import, depuis le script lancé par "
                                          f"qtpy6.web.lancer ou un slot ({e})", name=nom) from None
            else:
                return None
            return m.ModuleSpec(nom, m.ExtensionFileLoader(nom, so), origin=so)
    sys.meta_path.insert(0, QtAgrege)
_poser()
del _poser`);
  return py;
}
