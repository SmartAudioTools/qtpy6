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
// son Content-Length (juste s'il n'est pas compressé) une fois commencé. L'avancement ne recule jamais. `jumeaux` : les noms
// (dernier segment de l'adresse) d'autres fichiers servis aussi compressés à côté (NOM.br et NOM.gz), comme pyodide.asm.wasm
// et python_stdlib.zip de Pyodide-Qt (hebergement/telecharger.sh) : voir `en_jumeau`.
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

// Un fichier dont l'hôte sert des jumeaux compressés (NOM.br, NOM.gz) : le meilleur que le navigateur sait décompresser est
// demandé d'abord, décompressé dans la page en flux (DecompressionStream, qui ne retarde pas la compilation en flux du moteur).
// GitHub Pages ne compresse qu'en gzip, et pas tous les types (ni les .zip ni le JSON) : 11,3 Mo du moteur, 8,0 en Brotli, soit
// 0,5 s de moins à 50 Mbit/s (mesuré le 02/10/2026 sous Firefox). Brotli si le navigateur l'a (Firefox 155 ; pas Chromium 153,
// mesuré en ligne le 04/10/2026 : il téléchargeait 30 Mo au lieu de 13, dont la bibliothèque standard écrite sans compression
// pour Brotli, 9,8 Mo) ; sinon gzip, que tous ont. Rend undefined, d'où la demande du fichier lui-même, sans jumeau (en
// développement). Une réponse marquée DECOMPRESSE vient du service worker de la page (sw.js, `service_worker`), qui la range
// décompressée : la décompresser à chaque ouverture coûterait 0,15 à 0,3 s de calcul.
export const DECOMPRESSE = "X-Qtpy6-Decompresse";
const JUMEAU = [[".br", "brotli"], [".gz", "gzip"]].find(([, format]) => {
  try { new DecompressionStream(format); return true; } catch { return false; } });
async function en_jumeau(fetch_origine, adresse) {
  if (!JUMEAU) return;
  const [extension, format] = JUMEAU, jumeau = new URL(adresse);
  jumeau.pathname += extension;
  const reponse = await fetch_origine(jumeau).catch(() => undefined);
  if (!reponse?.ok) return;
  if (reponse.headers.has(DECOMPRESSE)) return reponse;
  return new Response(reponse.body.pipeThrough(new DecompressionStream(format)),  // application/wasm : compileStreaming l'exige
    { headers: { "Content-Type": adresse.pathname.endsWith(".wasm") ? "application/wasm" : "application/octet-stream" } });
}

// Le service worker de la page (js/sw.js, que qtpy6.web.construire.deposer met À CÔTÉ de la page : il ne contrôle que son
// dossier et ce qui est en dessous) : la visite suivante a, sans aucune requête, ce que la page lui a confié.
//   const garder = service_worker("./sw.js?v=…", { cache: "mon_appli", pyodide: "./pyodide-qt/" });
//   … une fois la page prête : garder(url => …)   (les adresses chargées, performance, que ce filtre retient)
// `cache` : le nom de l'application, début du nom de ses caches (ses autres caches, « NOM?… », sont effacés à l'activation : changer
// la requête du script, ?v=… à chaque déploiement, repart sur un cache neuf). `pyodide` : le Pyodide des workers
// (Travailleur), dont sw.js sert aux workers neufs les fichiers bruts depuis l'entrée de leur jumeau. Enregistré sur un
// navigateur qui n'en a pas (ou un contexte non sûr, http hors 127.0.0.1) : rien, et `garder` ne fait rien.
export function service_worker(script, { cache = "qtpy6", pyodide, erreur = console.error } = {}) {
  const sw = navigator.serviceWorker;
  if (!sw) return () => {};
  const url = new URL(script, location.href);
  url.searchParams.set("cache", cache);
  if (pyodide) url.searchParams.set("p", new URL(pyodide, location.href).href);
  sw.register(url).catch(erreur);
  return (filtre = () => true) => {
    const urls = performance.getEntriesByType("resource").map(r => r.name).filter(filtre);
    sw.ready.then(r => r.active?.postMessage(urls)).catch(erreur);
  };
}

// Les octets reçus pendant `preparer` : chaque réponse de fetch lue en double (clone), son nom (dernier segment de l'adresse)
// pesé par `tailles` ; et ceux de `jumeaux` demandés par en_jumeau. Rend `prelancer(url)`, qui commence un téléchargement
// tout de suite et le garde pour la première demande de la même adresse, et `retablir()`, qui remet le fetch d'origine.
function compter(tailles, jumeaux, signaler) {
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
    const reponse = jumeaux.includes(nom) && await en_jumeau(fetch_origine, adresse) || await fetch_origine(...args);
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

// Ni menu ni sélection du navigateur sur l'écran de Qt : un doigt qui s'y attarde (``tactile.AppuiLong`` saisit à 300 ms)
// ne doit pas ouvrir le menu contextuel (Android, 400 ms et plus) ni la loupe ou la bulle d'iOS. Sur le conteneur
// seulement : le reste de la page (un champ HTML) garde son menu. Le clic droit de Qt vient des pointerdown, pas de cet
// événement.
function sans_menu(conteneur) {
  conteneur.addEventListener("contextmenu", e => e.preventDefault());
  Object.assign(conteneur.style, { webkitTouchCallout: "none", webkitUserSelect: "none", userSelect: "none" });
}

// Les boucles imbriquées de Qt, QDrag.exec en tête, comme sur le bureau. Qt-WASM sait les mener en suspendant sa pile
// (QEventLoop::exec → qtSuspendJs) quand il se croit compilé avec Asyncify ; Pyodide-Qt ne l'est pas, mais la JSPI de
// Pyodide fait la même chose : la cale `Asyncify` lui fait croire (jsHaveJspi() lit globalThis.Asyncify, haveJspi() met
// la réponse en cache), et qtSuspendJs, enveloppé à l'instanciation du module, suspend par WebAssembly.Suspending. Une
// suspension n'est possible que dans une entrée « promettante » : la pompe de bloquant en est une (`pompe`), le drapeau
// `etat.promettant` le dit pendant qu'elle tourne ; une tâche de bloquant._plus_tard aussi (`tache`, que bloquant pose), où
// passe tout slot Python que Qt appelle dans la pompe : sans elle, un QTimer.timeout qui lance QDrag.exec (l'appui long
// de tactile) bouclait sans fin sur des refus (mesuré le 05/10/2026), comme tout slot qui ouvrirait une boucle de Qt. Ailleurs, refus : qtSuspendJs rend tout de suite, après avoir tiré les
// minuteries à 0 ms de Qt (sinon sa boucle d'envoi des événements natifs attend une minuterie qui ne viendrait jamais).
// PySide/PyQt rendent le GIL autour de processEvents : le reprendre pour sauver l'état de Python, le rendre pendant la
// suspension (les autres entrées en ont besoin), le reprendre et le rendre de nouveau à la reprise.
const suspension = { promettant: false, tache: false, qtEnTache: false, suspendu: false, suspensions: 0, refus: 0, M: null };
function boucles_qt() {
  globalThis.Asyncify ??= { handleAsync: f => f(), makeAsyncFunction: f => f };
  const minuteries = new Map();  // id → fonction, des setTimeout à 0 ms : le repli sans suspension en tire celles de Qt
  const st0 = setTimeout, ct0 = clearTimeout;
  window.setTimeout = (f, d, ...a) => {
    if (typeof f !== "function" || (d | 0) !== 0) return st0(f, d, ...a);
    const id = st0((...b) => { minuteries.delete(id); f(...b); }, d, ...a);
    minuteries.set(id, f);
    return id;
  };
  window.clearTimeout = id => { minuteries.delete(id); ct0(id); };
  const envelopper = imports => {
    const env = imports && imports.env;
    if (!env || !env.__asyncjs__qtSuspendJs) return imports;
    const { saveState, restoreState } = env, s = suspension;
    // Pas async : une promesse rendue hors entrée promettante serait un SuspendError
    env.__asyncjs__qtSuspendJs = new WebAssembly.Suspending(() => {
      const M = s.M, ctrl = M && M.qtSuspendResumeControl;
      let etat = null, sans_gil = false;
      const en_tache = s.tache && !s.promettant;
      if ((s.promettant || en_tache) && ctrl) {
        sans_gil = !M._PyGILState_Check();
        if (sans_gil) M._PyEval_RestoreThread(M._PyGILState_GetThisThreadState());
        etat = saveState();
        if (!(etat && etat.stackState) && sans_gil) M._PyEval_SaveThread();
      }
      if (!(etat && etat.stackState)) {
        s.refus++;
        if (ctrl) for (const [id, f] of [...minuteries])
          if (Object.values(ctrl.eventHandlers).includes(f)) { ct0(id); minuteries.delete(id); f(); }
        return;
      }
      s.suspensions++; s.promettant = false; s.suspendu = true;
      if (en_tache) s.qtEnTache = true;  // la pompe attend la fin de la tâche (bloquant), comme la sienne propre (encours)
      return new Promise(r => { ctrl.resume = r; }).then(() => {
        restoreState(etat);
        if (sans_gil) M._PyEval_SaveThread();
        s.promettant = !en_tache; s.suspendu = false;
      });
    });
    return imports;
  };
  const i0 = WebAssembly.instantiate, is0 = WebAssembly.instantiateStreaming;
  WebAssembly.instantiate = (b, imports) => i0(b, envelopper(imports));
  WebAssembly.instantiateStreaming = (r, imports) => is0(r, envelopper(imports));
  window.qtpy6Pomper = pompe;  // ce que bloquant._pyodide_pomper appelle, s'il le trouve
  window.qtpy6Suspension = suspension;  // où bloquant._pyodide_signaler pose `tache`
}

// Un événement DOM que Qt met en file pendant une suspension est traité APRÈS sa diffusion : composedPath() rend alors []
// et target est null (qwasmevent.cpp, qwasmwindow.cpp → dom::mapPoint), d'où « objHandle is null ». On les fige quand
// l'événement entre dans la file.
function figer_les_evenements(M) {
  const figer = c => {
    if (!c) return;
    c.pendingEvents.push = function (...items) {
      for (const it of items) {
        const ev = it && it.arg;
        if (!ev || typeof ev.composedPath !== "function") continue;
        const chemin = ev.composedPath();
        if (chemin.length) Object.defineProperty(ev, "composedPath", { value: () => chemin, configurable: true });
        for (const k of ["target", "currentTarget"]) { const v = ev[k]; if (v) Object.defineProperty(ev, k, { value: v, configurable: true }); }
      }
      // Un événement mis en file hors suspension est traité par le prochain processEvents, et si celui-ci n'est pas
      // promettant (un runPython de la page), le handler qui suspend tue Pyodide : celui du réveil de Qt (onWakeup →
      // processEvents(AllEvents), qeventdispatcher_wasm.cpp), mesuré le 05/10/2026. On vide la file tout de suite, en
      // promettant, avant toute autre tâche du navigateur.
      if (suspension.tourner) queueMicrotask(suspension.tourner);
      return Array.prototype.push.apply(this, items);
    };
  };
  let c = M.qtSuspendResumeControl;
  figer(c);
  Object.defineProperty(M, "qtSuspendResumeControl", { configurable: true, get: () => c, set: v => { c = v; figer(v); } });
}

// La pompe de bloquant (`_pyodide_pomper`) quand `boucles_qt` est posé, promettante : Qt peut y suspendre. Une seule à la fois ; pendant une
// suspension (un glisser en cours), c'est la boucle de Qt reprise par `ctrl.resume` qui traite les événements.
// Posée hors de l'appel de Python qui la demande (setTimeout) : créée pendant cet appel (l'import de QtCore), la première
// suspension de Qt tuait Pyodide (« handle is undefined », mesuré le 05/10/2026 ; la même pompe posée depuis la page, non).
function pompe(tour, periode) {
  setTimeout(() => pomper(tour, periode), 0);
}
function pomper(tour, periode) {
  let encours = false;
  const tourner = () => {
    // Ni pendant une tâche où Qt a suspendu : entre la reprise (`ctrl.resume`) et la suite de sa pile, une pompe glissée
    // là (queueMicrotask de figer_les_evenements) la trouvait non promettante, d'où les refus en boucle (05/10/2026).
    if (encours || suspension.qtEnTache) return;
    // Pas avant que Qt ait son contrôle de suspension (la première boucle d'événements) : appelée en promettante plus tôt,
    // Python meurt (« handle is undefined ») ; le tour ordinaire, comme sans boucles_qt.
    if (!(suspension.M && suspension.M.qtSuspendResumeControl)) return tour();
    encours = true;
    suspension.promettant = true;
    let p;
    try { p = tour.callPromising(); } finally { suspension.promettant = false; }
    p.catch(e => print("pompe : " + (e.message || e))).finally(() => { encours = false; suspension.promettant = false; });
  };
  suspension.tourner = tourner;
  setInterval(tourner, periode);
}

// Le glisser rejoué. QWasmDrag attend un glisser HTML5 (dragstart…dragend) que le navigateur ne lance pas : sous un doigt,
// Firefox n'en lance aucun ; sous la souris, l'appui que Qt a déjà consommé n'en lance pas non plus, et QDrag.exec restait
// suspendu après le relâcher (essai à la main, 05/10/2026). Pendant que Qt attend un glisser (une suspension en cours, donc
// QDrag.exec), un doigt ou une souris qui bouge sur un élément draggable (la fenêtre Qt) le rejoue : dragstart, puis
// dragover à chaque mouvement, drop et dragend au lever, sur l'élément sous le pointeur. Si le navigateur lance quand
// même son propre glisser (dragstart authentique), on le lui laisse. Qt a pris le glisser quand il pose son image
// (setDragImage) ; il refuse sinon (preventDefault), et on réessaie au mouvement suivant, 50 ms plus tard au plus tôt.
// Le pointeur pris, ses pointermove n'atteignent plus Qt ; son pointerup, si : c'est lui qui termine QDrag.exec quand le
// dépôt tombe hors de toute cible (« No drag target set »). Un pointercancel synthétique, ou un pointerup avalé, laissait
// exec suspendu jusqu'à l'appui suivant (mesuré le 05/10/2026, souris et doigt).
// Le navigateur ne dessine l'image d'un glisser que pour le sien : celle que Qt donne à setDragImage (canvas du pixmap du
// QDrag, son texte, ou le logo Qt) est recopiée dans un élément fixe qui suit le pointeur, sans souris (pointer-events),
// donc invisible à elementFromPoint ; Qt retire l'original à la fin du glisser, d'où la copie.
function glisser_rejoue(conteneur) {
  let e = null;  // { id, type, el, racine, x0, y0, dt, pris, essai }
  let image = null;  // { el, hx, hy } : la copie qui suit le pointeur
  const effacer = () => { if (image) image.el.remove(); image = null; };
  const placer = (x, y) => { if (image) image.el.style.transform = `translate(${x - image.hx}px, ${y - image.hy}px)`; };
  const copier = (src, hx, hy) => {
    let el;
    if (src instanceof HTMLCanvasElement) {
      el = document.createElement("canvas");
      [el.width, el.height] = [src.width, src.height];
      el.getContext("2d").drawImage(src, 0, 0);
      [el.style.width, el.style.height] = [src.style.width, src.style.height];
    } else el = src.cloneNode(true);
    el.removeAttribute("class");  // hidden-drag-image : Qt la cache
    Object.assign(el.style, { position: "fixed", left: "0", top: "0", margin: "0", pointerEvents: "none", opacity: "0.8",
                              zIndex: "2147483647" });
    document.body.appendChild(el);
    image = { el, hx: +hx || 0, hy: +hy || 0 };
  };
  const drag = (type, el, x, y) => el.dispatchEvent(new DragEvent(type, { dataTransfer: e.dt, clientX: x, clientY: y,
    screenX: x, screenY: y, buttons: type === "drop" || type === "dragend" ? 0 : 1, bubbles: true, cancelable: true, composed: true }));
  const sous = (x, y) => e.racine.elementFromPoint(x, y) || e.el;
  const avaler = ev => { ev.stopImmediatePropagation(); ev.preventDefault(); };
  addEventListener("pointerdown", ev => {
    e = null;
    effacer();
    if (!["touch", "mouse"].includes(ev.pointerType) || !ev.isPrimary || !ev.composedPath().includes(conteneur)) return;
    const el = ev.composedPath()[0];
    if (el && el.closest && el.closest("[draggable=true]"))
      e = { id: ev.pointerId, type: ev.pointerType, el, racine: el.getRootNode(), x0: ev.clientX, y0: ev.clientY, essai: 0 };
  }, true);
  addEventListener("pointermove", ev => {
    if (!e || ev.pointerId !== e.id) return;
    const { clientX: x, clientY: y } = ev;
    if (!e.pris && e.dt && e.dt.pris) e.pris = true;
    if (e.pris) { avaler(ev); placer(x, y); drag("dragover", sous(x, y), x, y); return; }
    const t = performance.now();
    if (!suspension.suspendu || Math.hypot(x - e.x0, y - e.y0) < 8 || t - e.essai < 50) return;
    e.essai = t;
    const dt = e.dt = new DataTransfer(), poser = dt.setDragImage.bind(dt);
    // Chrome ignore l'écriture de dropEffect sur un DataTransfer construit (Firefox la garde) : Qt y lisait « none » au
    // dragend, croyait le glisser ignoré et relançait QBasicDrag::drag, dont le relâcher déposait une seconde fois
    // (étiquette dupliquée, 05/10/2026). La valeur que Qt pose au dragover est donc gardée ici.
    let effet = "none";
    Object.defineProperty(dt, "dropEffect", { get: () => effet, set: v => { effet = v; } });
    dt.setDragImage = (el, hx, hy) => {
      dt.pris = true;
      effacer();
      try { copier(el, hx, hy); placer(x, y); } catch (err) { print("image du glisser : " + (err.message || err)); }
      try { poser(el, hx, hy); } catch {}
    };
    drag("dragstart", e.el, x, y);
  }, true);
  addEventListener("pointerup", ev => {
    if (!e || ev.pointerId !== e.id) return;
    if (e.pris) {
      const { clientX: x, clientY: y } = ev;
      drag("drop", sous(x, y), x, y);
      drag("dragend", e.el, x, y);
    }
    e = null;
    effacer();
  }, true);
  addEventListener("pointercancel", ev => {
    if (!e || ev.pointerId !== e.id || !ev.isTrusted) return;
    if (e.pris) drag("dragend", e.el, ev.clientX, ev.clientY);  // le navigateur a repris le doigt : glisser abandonné
    e = null;
    effacer();
  }, true);
  addEventListener("dragstart", ev => { if (ev.isTrusted && e && !e.dt) e = null; }, true);
}

export async function preparer(conteneur, { indexURL, archives = [], roues = [], env = {}, sur_ligne, progres = () => {},
                                            tailles = {}, jumeaux = [], module, boucles = true } = {}) {
  if (sur_ligne) ecouter = sur_ligne;
  const avance = avancement(progres);
  const { prelancer, retablir } = compter(tailles, ["pyodide.asm.wasm", "python_stdlib.zip", ...jumeaux], f => {
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
  // Sans JSPI (pas de WebAssembly.Suspending), rien n'est posé : Pyodide lui-même n'y démarre pas (web.md, QDrag.exec).
  boucles = boucles && typeof WebAssembly.Suspending === "function";
  if (boucles) boucles_qt();  // avant que Pyodide instancie son module
  const { loadPyodide } = await import(indexURL + "pyodide.mjs");
  const [py, ...donnees] = await Promise.all([loadPyodide({ indexURL, stdout: print, stderr: print }), ...zips]);
  if (boucles) { suspension.M = py._module; figer_les_evenements(py._module); }
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
  sans_menu(conteneur);
  if (boucles) glisser_rejoue(conteneur);
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
