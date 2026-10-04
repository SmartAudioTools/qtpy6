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
// l'avancement de 0 à 1, en phases (`avancement`) : les octets reçus de chaque fichier (une copie de la réponse est lue à côté :
// celle que Pyodide reçoit reste intacte, et le navigateur garde son cache de code compilé), le moteur, le dépaquetage et les
// roues, puis `module`, s'il est donné : le module de l'application, importé en rendant la main à la page entre deux de ses
// modules (qtpy6.web.importer), pour que l'avancement reste vivant ; `py.pyimport(module)` le trouve ensuite tout prêt. Le total
// attendu : `tailles` ({nom: octets décompressés}, que la page connaît), compté dès le départ ; un fichier hors de `tailles` pèse
// son Content-Length (juste s'il n'est pas compressé) une fois commencé. L'avancement ne recule jamais. `brotli` : les noms
// (dernier segment de l'adresse) d'autres fichiers servis aussi compressés en Brotli (NOM.br), comme pyodide.asm.wasm et
// python_stdlib.zip de Pyodide-Qt (hebergement/telecharger.sh) : voir `en_brotli`.
const t0 = performance.now();
export const journal = [];
let ecouter = () => {};

// L'avancement de `preparer`, en quatre phases qui se suivent : les octets (des fichiers de `tailles`), le moteur (sa
// compilation et le démarrage de Python, les octets reçus), les archives et les roues, le module de l'application (`module`).
// Chacune a sur le cercle une part à la mesure de sa durée à la visite précédente (localStorage, DUREES à défaut) et y
// avance de 1 − (1 − r)·e^(−t/τ) : r, sa fraction réelle quand elle en a une (octets reçus, modules importés sur ceux de la
// dernière fois), t le temps passé dans la phase, τ sa durée attendue (triplée quand r existe : c'est lui qui mène). Ainsi
// l'avancement ne s'arrête jamais tant que la page vit, ralentit quand une phase dure plus que prévu, et ne recule jamais
// (demande de l'utilisateur, 04/10/2026 : « ne jamais s'arrêter complètement si des choses avancent »). `progres` est
// appelé toutes les 100 ms et à chaque fraction réelle.
const PHASES = ["octets", "moteur", "archives", "module"], DUREES = { octets: 8, moteur: 3, archives: 1, module: 3 };
const MEMOIRE = "qtpy6web.avancement";
function avancement(progres) {
  let memoire = {};
  try { memoire = JSON.parse(localStorage.getItem(MEMOIRE)) || {}; } catch {}  // stockage refusé (navigation privée…)
  const attendu = PHASES.map(p => Math.max(0.2, memoire.durees?.[p] ?? DUREES[p]));
  const total = attendu.reduce((a, b) => a + b), parts = attendu.map(d => d / total);
  const durees = {}, reels = PHASES.map(() => null);
  let courante = 0, depart = performance.now(), haut = 0;
  const maj = () => {
    const t = (performance.now() - depart) / 1000, r = reels[courante];
    const dans = 1 - (1 - (r ?? 0)) * Math.exp(-t / (attendu[courante] * (r === null ? 1 : 3)));
    haut = Math.max(haut, parts.slice(0, courante).reduce((a, b) => a + b, 0) + parts[courante] * Math.min(1, dans));
    progres(haut);
  };
  const minuterie = setInterval(maj, 100);
  const debut = nom => {
    const i = PHASES.indexOf(nom);
    if (i <= courante) return;
    durees[PHASES[courante]] = (performance.now() - depart) / 1000;
    PHASES.slice(courante + 1, i).forEach(p => durees[p] = 0);  // une phase sautée : son temps est dans la précédente
    [courante, depart] = [i, performance.now()];
    maj();
  };
  return {
    debut,
    reel: (nom, r) => { const i = PHASES.indexOf(nom); if (i === courante) { reels[i] = Math.min(1, r); maj(); } },
    fin: modules => {
      debut("module");
      durees.module = (performance.now() - depart) / 1000;
      clearInterval(minuterie);
      progres(1);
      try { localStorage.setItem(MEMOIRE, JSON.stringify({ durees, modules })); } catch {}
    },
    modules: memoire.modules,
  };
}

// Le canevas de chaque fenêtre Qt (qt-window-canvas) est créé avec willReadFrequently : tenu en mémoire et non sur la carte
// graphique, il reçoit l'image que Qt-WASM envoie à chaque peinture (putImageData) en 1,5 ms au lieu de 8,3 à 1800 px
// (Intel HD, mesuré par SmartTeacher le 02/10/2026). Les autres canevas (pdf.js) restent accélérés. ?lecture=0 dans
// l'adresse rend le comportement d'origine, pour comparer.
if (new URLSearchParams(location.search).get("lecture") !== "0") {
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function(type, attrs) {
    return getContext.call(this, type, type === "2d" && this.classList.contains("qt-window-canvas")
                                        ? { ...attrs, willReadFrequently: true } : attrs);
  };
}

export function print(m) {
  const l = `${((performance.now() - t0) / 1000).toFixed(2)}s ${m}`;
  journal.push(l); console.log(l); ecouter(l);
}

function telecharger(url) {
  return fetch(url).then(r => { if (!r.ok) throw new Error(`${url} : ${r.status}`); return r.arrayBuffer(); });
}

// Un fichier dont l'hôte sert un jumeau Brotli (NOM.br) : celui-ci est demandé d'abord, décompressé dans la page en flux
// (DecompressionStream, qui ne retarde pas la compilation en flux du moteur). GitHub Pages ne compresse qu'en gzip : 11,3 Mo du
// moteur, 8,0 en Brotli, soit 0,5 s de moins à 50 Mbit/s (mesuré le 02/10/2026 sous Firefox). Rend undefined, d'où la demande
// du fichier lui-même, sans Brotli dans le navigateur (Firefox 155 l'a, sous le nom "brotli") ou sans jumeau (en
// développement). Une réponse marquée DECOMPRESSE vient du service worker d'une page (celui de SmartTeacher), qui la range
// décompressée : la décompresser à chaque ouverture coûterait 0,15 à 0,3 s de calcul.
export const DECOMPRESSE = "X-Qtpy6-Decompresse";
const BROTLI = (() => { try { new DecompressionStream("brotli"); return true; } catch { return false; } })();
async function en_brotli(fetch_origine, adresse) {
  if (!BROTLI) return;
  const br = new URL(adresse);
  br.pathname += ".br";
  const reponse = await fetch_origine(br).catch(() => undefined);
  if (!reponse?.ok) return;
  if (reponse.headers.has(DECOMPRESSE)) return reponse;
  return new Response(reponse.body.pipeThrough(new DecompressionStream("brotli")),  // application/wasm : compileStreaming l'exige
    { headers: { "Content-Type": adresse.pathname.endsWith(".wasm") ? "application/wasm" : "application/octet-stream" } });
}

// Les octets reçus pendant `preparer` : chaque réponse de fetch lue en double (clone), son nom (dernier segment de l'adresse)
// pesé par `tailles` ; et ceux de `brotli` demandés par en_brotli. Rend `prelancer(url)`, qui commence un téléchargement
// tout de suite et le garde pour la première demande de la même adresse, et `retablir()`, qui remet le fetch d'origine.
function compter(tailles, brotli, signaler) {
  const fetch_origine = window.fetch;
  const fichiers = Object.fromEntries(Object.entries(tailles).map(([nom, total]) => [nom, { recu: 0, total }]));
  let haut = 0;
  const avancer = () => {
    const f = Object.values(fichiers);
    haut = Math.max(haut, f.reduce((s, x) => s + Math.min(x.recu, x.total), 0) / Math.max(1, f.reduce((s, x) => s + x.total, 0)));
    signaler(haut);
  };
  const obtenir = async (...args) => {
    const adresse = new URL(String(args[0]?.url ?? args[0]), location.href), nom = adresse.pathname.split("/").pop();
    const reponse = brotli.includes(nom) && await en_brotli(fetch_origine, adresse) || await fetch_origine(...args);
    if (!reponse.ok || !reponse.body) return reponse;
    const fichier = fichiers[nom] = { recu: 0, total: tailles[nom] || +reponse.headers.get("Content-Length") || 1 };
    const lecteur = reponse.clone().body.getReader();
    (async () => {
      for (let r; !(r = await lecteur.read()).done;) { fichier.recu += r.value.byteLength; avancer(); }
      fichier.total = fichier.recu; avancer();
    })().catch(() => {});
    return reponse;
  };
  const prelances = new Map();
  window.fetch = (...args) => {
    const adresse = new URL(String(args[0]?.url ?? args[0]), location.href).href, reponse = prelances.get(adresse);
    prelances.delete(adresse);  // une seule fois : le corps d'une réponse ne se lit qu'une fois
    return reponse || obtenir(...args);
  };
  return {
    prelancer: url => { const p = obtenir(url); p.catch(() => {}); prelances.set(new URL(url, location.href).href, p); },
    retablir: () => { window.fetch = fetch_origine; },
  };
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
                                            tailles = {}, brotli = [], module } = {}) {
  if (sur_ligne) ecouter = sur_ligne;
  const avance = avancement(progres);
  const { prelancer, retablir } = compter(tailles, ["pyodide.asm.wasm", "python_stdlib.zip", ...brotli], f => {
    avance.reel("octets", f);
    if (f >= 1) avance.debut("moteur");
  });
  window.journal = journal;
  indexURL = new URL(indexURL.endsWith("/") ? indexURL : indexURL + "/", location.href).href;
  // Les gros fichiers demandés dès maintenant : sinon le moteur attendait pyodide.mjs puis pyodide.asm.js (1,2 Mo), deux
  // allers-retours de plus, et chaque roue le démarrage entier de Pyodide. Pyodide et loadPackage les reçoivent ensuite.
  ["pyodide.asm.wasm", "python_stdlib.zip"].forEach(n => prelancer(indexURL + n));
  roues.forEach(r => prelancer(r));
  const zips = archives.map(a => telecharger(a.url));  // en parallèle du chargement de Pyodide
  const { loadPyodide } = await import(indexURL + "pyodide.mjs");
  const [py, ...donnees] = await Promise.all([loadPyodide({ indexURL, stdout: print, stderr: print }), ...zips]);
  print(`Pyodide-Qt ${py.version} chargé${donnees.length ? " ; archives " + donnees.map(d => (d.byteLength / 1024) | 0).join(", ") + " Kio" : ""}`);
  avance.debut("archives");
  archives.forEach((a, i) => py.unpackArchive(donnees[i], "zip", { extractDir: a.dossier }));
  // loadPackage, et non unpackArchive, pour une roue : il précharge ses .so de façon asynchrone
  for (const roue of roues) {
    if (!roue.endsWith(".whl")) throw new Error(`roue ${roue} : l'adresse doit finir par .whl (pas de requête), Pyodide y lit le nom du paquet`);
    await py.loadPackage(new URL(roue, location.href).href);
  }
  retablir();
  py._module.qtContainerElements = [conteneur];  // l'API privée de Qt-WASM, isolée ici : l'élément qui sert d'écran à Qt
  molette(conteneur);
  window.qtpy6Conteneur = conteneur;  // ce que qtpy6.web.pdf lit pour caler ses <div> sur les widgets
  window.qtpy6Js = import.meta.url;  // d'où qtpy6.web.pdf charge pdf.js quand l'archive ne l'a pas (assembler, exclure)
  py.runPython(`import json, os, sys
os.environ.update(json.loads(${JSON.stringify(JSON.stringify(env))}))
sys.path[:0] = json.loads(${JSON.stringify(JSON.stringify(archives.map(a => a.dossier)))})`);
  // La version attendue : versions.json de qtpy6.web, lu dans l'archive (find_spec n'importe rien). Un fetch relatif au
  // chargeur ne la trouvait qu'en développement (js/ sous qtpy6/web/) : publié, qtpy6web.js est à la racine du site, 404.
  const attendue = py.runPython(`import importlib.util, pathlib
s = importlib.util.find_spec("qtpy6")
f = s and pathlib.Path(s.submodule_search_locations[0], "web", "versions.json")
f.read_text() if f and f.exists() else "null"`), versions = JSON.parse(attendue);
  if (versions && versions.pyodide_qt.version !== py.version)
    print(`attention : Pyodide-Qt ${py.version} là où qtpy6.web attend ${versions.pyodide_qt.version} (roues ${versions.pyodide_qt.abi})`);
  let modules;
  if (module) {
    avance.debut("module");
    const t = performance.now();
    await py.pyimport("qtpy6.web").importer.callPromising(module, n => { modules = n; if (avance.modules) avance.reel("module", n / avance.modules); });
    print(`${module} importé en ${((performance.now() - t) / 1000).toFixed(2)} s (${modules} modules)`);
  }
  avance.fin(modules);
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
