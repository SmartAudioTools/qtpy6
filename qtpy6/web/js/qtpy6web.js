// qtpy6web.js (qtpy6.web) : une application qtpy6 dans le navigateur, sous un Pyodide où Qt 6 et sa liaison Python (PyQt6 pour
// Pyodide-Qt, PySide6 sinon) sont liés en WebAssembly.
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
// et répond « No known package with name » sinon. `env` : des variables d'environnement (QT_API : la liaison, celle du Pyodide chargé par défaut). `sur_ligne` : reçoit chaque ligne du
// journal (print), qui va aussi dans window.journal (ce que lit qtpy6.web.sonde) et la console. `progres(fraction)` : reçoit
// l'avancement de 0 à 1, les octets reçus de chaque fichier jusqu'à 0,9 (une copie de la réponse est lue à côté : celle que
// Pyodide reçoit reste intacte, et le navigateur garde son cache de code compilé), puis dépaquetage, roues, 1 rendue. Le total
// attendu : `tailles` ({nom: octets décompressés}, que la page connaît), compté dès le départ ; un fichier hors de `tailles` pèse
// son Content-Length (juste s'il n'est pas compressé) une fois commencé. L'avancement ne recule jamais.
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

// Les octets reçus pendant `preparer` : chaque réponse de fetch lue en double (clone), son nom (dernier segment de l'adresse)
// pesé par `tailles`. Rend la fonction qui remet le fetch d'origine.
function compter(tailles, signaler) {
  const fetch_origine = window.fetch;
  const fichiers = Object.fromEntries(Object.entries(tailles).map(([nom, total]) => [nom, { recu: 0, total }]));
  let haut = 0;
  const avancer = () => {
    const f = Object.values(fichiers);
    haut = Math.max(haut, f.reduce((s, x) => s + Math.min(x.recu, x.total), 0) / Math.max(1, f.reduce((s, x) => s + x.total, 0)));
    signaler(haut);
  };
  window.fetch = async (...args) => {
    const reponse = await fetch_origine(...args);
    if (!reponse.ok || !reponse.body) return reponse;
    const nom = new URL(reponse.url || String(args[0]?.url ?? args[0]), location.href).pathname.split("/").pop();
    const fichier = fichiers[nom] = { recu: 0, total: tailles[nom] || +reponse.headers.get("Content-Length") || 1 };
    const lecteur = reponse.clone().body.getReader();
    (async () => {
      for (let r; !(r = await lecteur.read()).done;) { fichier.recu += r.value.byteLength; avancer(); }
      fichier.total = fichier.recu; avancer();
    })().catch(() => {});
    return reponse;
  };
  return () => { window.fetch = fetch_origine; };
}

// La molette à la mesure du bureau. Qt-WASM fait d'un pixel du navigateur un angleDelta de 1 et d'une ligne 12 ; or un
// QScrollArea défile de 60 px pour 120 (un cran, 3 lignes de 20 px) : un pixel du navigateur n'en faisait qu'un demi, et un
// cran de Firefox (3 lignes) 18 px au lieu de 60. Chaque roulement sur le conteneur est donc rejoué sur la même cible
// (le canevas, dans l'ombre de Qt) en pixels doublés : le défilement suit le doigt sur le pavé tactile comme une page web,
// une ligne vaut 20 px comme sur le bureau. Un roulement en pages (rare) passe tel quel.
function molette(conteneur) {
  const rejoues = new WeakSet();
  addEventListener("wheel", e => {
    if (rejoues.has(e) || e.deltaMode === WheelEvent.DOM_DELTA_PAGE || !e.composedPath().includes(conteneur)) return;
    const k = e.deltaMode === WheelEvent.DOM_DELTA_LINE ? 40 : 2;
    const copie = new WheelEvent("wheel", { deltaX: e.deltaX * k, deltaY: e.deltaY * k, deltaMode: WheelEvent.DOM_DELTA_PIXEL,
      clientX: e.clientX, clientY: e.clientY, screenX: e.screenX, screenY: e.screenY, buttons: e.buttons, ctrlKey: e.ctrlKey,
      shiftKey: e.shiftKey, altKey: e.altKey, metaKey: e.metaKey, bubbles: true, composed: true, cancelable: true });
    rejoues.add(copie);
    e.stopImmediatePropagation(); e.preventDefault();
    e.composedPath()[0].dispatchEvent(copie);
  }, { capture: true, passive: false });
}

export async function preparer(conteneur, { indexURL, archives = [], roues = [], env = {}, sur_ligne, progres = () => {},
                                            tailles = {} } = {}) {
  if (sur_ligne) ecouter = sur_ligne;
  const retablir = compter(tailles, f => progres(0.9 * f));
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
  retablir();
  archives.forEach((a, i) => py.unpackArchive(donnees[i], "zip", { extractDir: a.dossier }));
  progres(0.93);
  // loadPackage, et non unpackArchive, pour une roue : il précharge ses .so de façon asynchrone
  for (const roue of roues) {
    if (!roue.endsWith(".whl")) throw new Error(`roue ${roue} : l'adresse doit finir par .whl (pas de requête), Pyodide y lit le nom du paquet`);
    await py.loadPackage(new URL(roue, location.href).href);
  }
  progres(0.97);
  py._module.qtContainerElements = [conteneur];  // l'API privée de Qt-WASM, isolée ici : l'élément qui sert d'écran à Qt
  molette(conteneur);
  window.qtpy6Conteneur = conteneur;  // ce que qtpy6.web.pdf lit pour caler ses <div> sur les widgets
  window.qtpy6Js = import.meta.url;  // d'où qtpy6.web.pdf charge pdf.js quand l'archive ne l'a pas (assembler, exclure)
  py.runPython(`import json, os, sys
os.environ.update(json.loads(${JSON.stringify(JSON.stringify(env))}))
sys.path[:0] = json.loads(${JSON.stringify(JSON.stringify(archives.map(a => a.dossier)))})`);
  progres(1);
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
