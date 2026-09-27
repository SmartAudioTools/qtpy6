// qtpy6web.js (qtpy6.web) : une application qtpy6 (PyQt6) dans le navigateur, sous Pyodide-Qt (Qt 6 et PyQt6 en WebAssembly).
//
//   const py = await preparer(conteneur, { indexURL, archives, roues, env, sur_ligne });
//   py.pyimport("mon_application").demarrer();
//
// `conteneur` est l'élément où Qt dessine, son « écran » : il doit AVOIR SA TAILLE au moment de l'appel (Qt la prend au
// démarrage ; un élément en display:none donne une fenêtre de 0 px, préférer visibility:hidden). `indexURL` : le dossier
// de Pyodide-Qt (pyodide.mjs, pyodide.asm.wasm, python_stdlib.zip ; à côté de la page ou sur un autre hôte avec CORS).
// `archives` : [{url, dossier}], des zip dépaquetés dans le système de fichiers de Pyodide et mis dans sys.path (le code
// de l'application, qtpy6, ses données, ses polices : qtpy6.web.assembler les construit). `roues` : des roues
// WebAssembly (.whl) chargées par URL, pour les extensions compilées (le lock de Pyodide-Qt est vide : ni loadPackage("nom")
// ni micropip) ; une adresse qui FINIT par .whl, sans requête « ?v=… » : Pyodide y lit le nom du paquet (uriToPackageData),
// et répond « No known package with name » sinon. `env` : des variables d'environnement, QT_API=pyqt6 par défaut. `sur_ligne` : reçoit chaque ligne du
// journal (print), qui va aussi dans window.journal (ce que lit qtpy6.web.sonde) et la console.
const t0 = performance.now();
export const journal = [];
let ecouter = () => {};

export function print(m) {
  const l = `${((performance.now() - t0) / 1000).toFixed(2)}s ${m}`;
  journal.push(l); console.log(l); ecouter(l);
}

function telecharger(url) {
  return fetch(url).then(r => { if (!r.ok) throw new Error(`${url} : ${r.status}`); return r.arrayBuffer(); });
}

export async function preparer(conteneur, { indexURL, archives = [], roues = [], env = {}, sur_ligne } = {}) {
  if (sur_ligne) ecouter = sur_ligne;
  env = { QT_API: "pyqt6", ...env };  // qtpy6 prendrait PySide6 sinon, absent de Pyodide-Qt
  window.journal = journal;
  indexURL = new URL(indexURL.endsWith("/") ? indexURL : indexURL + "/", location.href).href;
  const attendu = fetch(new URL("../versions.json", import.meta.url)).then(r => r.ok ? r.json() : null).catch(() => null);
  const zips = archives.map(a => telecharger(a.url));  // en parallèle du chargement de Pyodide
  const { loadPyodide } = await import(indexURL + "pyodide.mjs");
  const [py, ...donnees] = await Promise.all([loadPyodide({ indexURL, stdout: print, stderr: print }), ...zips]);
  print(`Pyodide-Qt ${py.version} chargé${donnees.length ? " ; archives " + donnees.map(d => (d.byteLength / 1024) | 0).join(", ") + " Kio" : ""}`);
  const versions = await attendu;
  if (versions && versions.pyodide_qt.version !== py.version)
    print(`attention : Pyodide-Qt ${py.version} là où qtpy6.web attend ${versions.pyodide_qt.version} (roues ${versions.pyodide_qt.abi})`);
  archives.forEach((a, i) => py.unpackArchive(donnees[i], "zip", { extractDir: a.dossier }));
  // loadPackage, et non unpackArchive, pour une roue : il précharge ses .so de façon asynchrone
  for (const roue of roues) {
    if (!roue.endsWith(".whl")) throw new Error(`roue ${roue} : l'adresse doit finir par .whl (pas de requête), Pyodide y lit le nom du paquet`);
    await py.loadPackage(new URL(roue, location.href).href);
  }
  py._module.qtContainerElements = [conteneur];  // l'API privée de Qt-WASM, isolée ici : l'élément qui sert d'écran à Qt
  py.runPython(`import json, os, sys
os.environ.update(json.loads(${JSON.stringify(JSON.stringify(env))}))
sys.path[:0] = json.loads(${JSON.stringify(JSON.stringify(archives.map(a => a.dossier)))})`);
  return py;
}

// Exécute un script écrit pour le bureau (qtpy6.web.lancer : `sys.exit(app.exec())` y suspend au lieu de bloquer la page).
// `pret` est tenue quand l'application entre dans exec() (sa fenêtre est montrée), `fin` au retour du script (son code).
export function lancer(py, script, args = []) {
  let signaler;
  const pret = new Promise(r => signaler = r);
  const fin = py.pyimport("qtpy6.web").lancer.callPromising(script, py.toPy(args), () => signaler());
  fin.then(() => signaler(), () => signaler());
  return { pret, fin };
}

// Trois images : ce qu'il faut pour que la fenêtre Qt soit dessinée avant une capture ou un `window.etat`.
export async function rendu(images = 3) {
  for (let i = 0; i < images; i++) await new Promise(r => requestAnimationFrame(r));
}
