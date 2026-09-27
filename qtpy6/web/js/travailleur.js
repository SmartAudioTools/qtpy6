// Le Web Worker de qtpy6.web.travailleur : Pyodide (l'ordinaire, pas Pyodide-Qt) dans un fil que la page peut terminer,
// des archives dépaquetées, un module importé ; ses appels sont traités un par un, dans l'ordre, chacun rendant la main
// avant le suivant. Lancé depuis une URL blob: : toutes les URL reçues sont absolues.
//   reçus : {init: {indexURL, archives: [{url, dossier}], module, cwd}}, {appel: {id, fonction, args}}
//   émis :  {pret}, {id, sortie} (ce que l'appel imprime, au fil de l'eau), {id, retour}, {id, erreur}, {erreur} (init)
// Ou bien un processus (ProcessusWeb) : un script lancé en __main__, qui lit son stdin comme sur le bureau.
//   reçus : {lancer: {indexURL, zip, dossier, argv, cwd}}, {entree: texte} (stdin), {entree: null} (fin de fichier) ;
//           le zip porte ses chemins depuis la racine du système de fichiers, où il est dépaqueté
//   émis :  {sortie} (stdout), {sortie_erreur} (stderr), {fin: code}, {erreur} (Pyodide injoignable, JSPI absent)
let py, module, appeler, courant = 0, file = Promise.resolve();  // courant : le numéro de l'appel en cours, 0 hors de tout appel (l'import du module)
const decodeur = new TextDecoder();

function telecharger(url) {
  return fetch(url).then(r => { if (!r.ok) throw new Error(`${url} : ${r.status}`); return r.arrayBuffer(); });
}

async function demarrer({ indexURL, archives, module: nom, cwd }) {
  const zips = archives.map(a => telecharger(a.url));
  const { loadPyodide } = await import(indexURL + "pyodide.mjs");  // worker module : importScripts est refusé chez Google
  const [p, ...donnees] = await Promise.all([loadPyodide({ indexURL }), ...zips]);
  py = p;
  const sortie = { write: octets => { postMessage({ id: courant, sortie: decodeur.decode(octets, { stream: true }) }); return octets.length; } };
  py.setStdout(sortie); py.setStderr(sortie);
  archives.forEach((a, i) => py.unpackArchive(donnees[i], "zip", { extractDir: a.dossier }));
  py.runPython(`import json, os, sys
sys.path[:0] = json.loads(${JSON.stringify(JSON.stringify(archives.map(a => a.dossier)))})
os.makedirs(${JSON.stringify(cwd)}, exist_ok=True); os.chdir(${JSON.stringify(cwd)})`);
  appeler = py.runPython("def _appeler(module, fonction, args):\n    return getattr(module, fonction)(*args.to_py())\n_appeler");
  module = py.pyimport(nom);
  postMessage({ pret: true });
}

async function traiter({ id, fonction, args }) {
  courant = id;
  try {
    let r = appeler(module, fonction, args);
    if (r && typeof r.then === "function") r = await r;  // une fonction async
    if (r && typeof r.toJs === "function") { const v = r.toJs({ dict_converter: Object.fromEntries }); r.destroy(); r = v; }
    py.runPython("import sys; sys.stdout.flush(); sys.stderr.flush()");
    postMessage({ id, retour: r === undefined ? null : r });
  } catch (e) {
    postMessage({ id, erreur: String(e) });
  } finally {
    courant = 0;
  }
}

const entrees = [], attentes = [];  // stdin : ce qui est arrivé sans être lu, et les lectures qui attendent
self.prochaine_entree = () => entrees.length ? Promise.resolve(entrees.shift()) : new Promise(r => attentes.push(r));

async function lancer({ indexURL, zip, dossier, argv, cwd }) {
  const { loadPyodide } = await import(indexURL + "pyodide.mjs");
  py = await loadPyodide({ indexURL });
  const canal = cle => { const d = new TextDecoder(); return { write: o => { postMessage({ [cle]: d.decode(o, { stream: true }) }); return o.length; } }; };
  py.setStdout(canal("sortie")); py.setStderr(canal("sortie_erreur"));
  py.unpackArchive(zip, "zip", { extractDir: "/" });
  py.globals.set("_lancement", py.toPy({ argv, cwd, dossier }));
  const code = await py.runPythonAsync(`
import io, js, os, runpy, sys, traceback
from pyodide.ffi import can_run_sync, run_sync

class _Entree(io.RawIOBase):  # stdin : chaque lecture attend la prochaine écriture de la page (JSPI)
    reste = b""
    def readable(self):
        return True
    def readinto(self, b):
        sys.stdout.flush(); sys.stderr.flush()
        if not self.reste:
            texte = run_sync(js.prochaine_entree())
            if texte is None:
                return 0
            self.reste = texte.encode("utf-8")
        n = min(len(b), len(self.reste))
        b[:n], self.reste = self.reste[:n], self.reste[n:]
        return n

def _executer(argv, cwd, dossier):
    if not can_run_sync():
        raise RuntimeError("ce navigateur ne sait pas suspendre Python (JSPI) : pas de sous-processus")
    # __stdin__ aussi, comme sur un bureau : un script qui enveloppe sys.stdin.buffer puis remplace sys.stdin ne doit pas
    # voir l'ancien objet ramassé, ce qui fermerait le tampon partagé (console_enfant.py de SmartTeacher)
    sys.stdin = sys.__stdin__ = io.TextIOWrapper(io.BufferedReader(_Entree()), encoding="utf-8")
    sys.stdout.reconfigure(line_buffering=True); sys.stderr.reconfigure(line_buffering=True)
    os.makedirs(cwd, exist_ok=True); os.chdir(cwd)
    try:
        if argv[0] == "-m":
            sys.path.insert(0, cwd); sys.argv = argv[1:]
            runpy.run_module(argv[1], run_name="__main__", alter_sys=True)
        else:
            sys.path.insert(0, dossier); sys.argv = argv
            runpy.run_path(argv[0], run_name="__main__")
        code = 0
    except SystemExit as e:
        if e.code is None or isinstance(e.code, int):
            code = e.code or 0
        else:
            print(e.code, file=sys.stderr); code = 1
    except BaseException:
        traceback.print_exc(); code = 1
    sys.stdout.flush(); sys.stderr.flush()
    return code

_executer(**_lancement)
`);
  postMessage({ fin: code });
}

onmessage = e => {
  const m = e.data;
  if (m.lancer) { lancer(m.lancer).catch(e => postMessage({ erreur: String(e) })); return; }
  if ("entree" in m) { attentes.length ? attentes.shift()(m.entree) : entrees.push(m.entree); return; }
  file = m.init ? file.then(() => demarrer(m.init)).catch(e => postMessage({ erreur: String(e) }))
                : file.then(() => traiter(m.appel));
};
