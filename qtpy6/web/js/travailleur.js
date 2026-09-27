// Le Web Worker de qtpy6.web.travailleur : Pyodide (l'ordinaire, pas Pyodide-Qt) dans un fil que la page peut terminer,
// des archives dépaquetées, un module importé ; ses appels sont traités un par un, dans l'ordre, chacun rendant la main
// avant le suivant. Lancé depuis une URL blob: : toutes les URL reçues sont absolues.
//   reçus : {init: {indexURL, archives: [{url, dossier}], module, cwd}}, {appel: {id, fonction, args}}
//   émis :  {pret}, {id, sortie} (ce que l'appel imprime, au fil de l'eau), {id, retour}, {id, erreur}, {erreur} (init)
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

onmessage = e => {
  const m = e.data;
  file = m.init ? file.then(() => demarrer(m.init)).catch(e => postMessage({ erreur: String(e) }))
                : file.then(() => traiter(m.appel));
};
