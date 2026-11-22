// Harnais de test_suspension_jspi.py : le qtSuspendJs que `boucles_qt` (qtpy6web.js) donne à Qt, sous node (JSPI de V8), et
// sous la règle de JavaScriptCore (Safari) si l'argument « jsc » est donné : tout import Suspending suspend, même s'il rend
// une valeur ordinaire (WebAssemblySuspending.cpp). Qt est simulé par un module wasm dont run() appelle qtSuspendJs.
// Écrit en JSON, pour chaque cas, « passe » ou le message de l'erreur, et les compteurs de `suspension`.
const [, , chemin, regle] = process.argv;
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: () => null, setItem() {} },
  document: { visibilityState: "visible", fullscreenElement: null, addEventListener() {} },
  window: globalThis,
  addEventListener() {},
});
if (regle === "jsc") {
  const S0 = WebAssembly.Suspending;
  WebAssembly.Suspending = function (f) { return new S0((...a) => Promise.resolve(f(...a))); };
}
const m = await import(chemin);
m.boucles_qt();

// module : type () → (), les imports env.<noms> (moins de 128 octets en tout), run() les appelle dans l'ordre
const u = s => [...new TextEncoder().encode(s)];
const section = (id, c) => [id, c.length, ...c];
const appelant = (...noms) => {
  const corps = [0, ...noms.flatMap((_, i) => [16, i]), 11];
  return new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, ...section(1, [1, 96, 0, 0]),
    ...section(2, [noms.length, ...noms.flatMap(n => [3, ...u("env"), n.length, ...u(n), 0, 0])]),
    ...section(3, [1, 0]), ...section(7, [1, 3, ...u("run"), 0, noms.length]), ...section(10, [1, corps.length, ...corps])]);
};
let sauves = 0, restaures = 0, apres = 0, vides = 0, etat_vide = false, gil = [];
const env = { __asyncjs__qtSuspendJs: () => {},
              saveState: () => etat_vide ? (vides++, {}) : (sauves++, { stackState: 1 }), restoreState: () => restaures++,
              apres: () => apres++ };
const { instance } = await WebAssembly.instantiate(appelant("__asyncjs__qtSuspendJs", "apres"), { env });
const qt = instance.exports.run;
const dehors = cb => new WebAssembly.Instance(new WebAssembly.Module(appelant("cb")), { env: { cb } }).exports.run;
const ctrl = { eventHandlers: {}, resume: null };
const s = m.suspension;
s.M = { qtSuspendResumeControl: ctrl, _PyGILState_Check: () => !etat_vide, _PyGILState_GetThisThreadState: () => 7,
        _PyEval_RestoreThread: () => gil.push("pris"), _PyEval_SaveThread: () => gil.push("rendu") };

const resultat = {};
const essai = async (nom, f) => {
  try { await f(); resultat[nom] = "passe"; } catch (e) { resultat[nom] = `${e.constructor.name}: ${e.message}`; }
};
// le refus hors de toute entrée promettante (un runPython de la page)
await essai("refus_hors_promettant", () => qt());
// le refus dans une entrée promettante, une frame JS au milieu (un rappel JS → Python → Qt)
await essai("refus_frame_js", () => WebAssembly.promising(dehors(() => qt()))());
// le refus dans une entrée promettante sans frame JS, hors pompe (l'import de l'application, `preparer`) : Qt doit
// continuer sans rendre la main (aucune suspension, donc aucune autre entrée de Python pendant qu'il attend)
await essai("refus_promettant", async () => {
  const n = apres, p = WebAssembly.promising(qt)();
  resultat.refus_sans_suspendre = apres === n + 1;
  await p;
});
// le refus dans la pompe (promettante), Pyodide refusant de sauver sa pile (`saveState` sans stackState), le GIL non tenu :
// pas de suspension, le GIL pris pour saveState puis rendu, la pompe toujours promettante
await essai("refus_etat_vide", async () => {
  s.promettant = true; etat_vide = true;
  const n = apres, p = WebAssembly.promising(qt)();
  resultat.etat_vide_sans_suspendre = apres === n + 1 && vides === 1 && gil.join() === "pris,rendu" && s.promettant;
  await p;
  etat_vide = false;
});
// la vraie suspension (la pompe) : suspendue tant que Qt n'est pas repris par ctrl.resume, l'état de Pyodide restauré
await essai("suspension", async () => {
  s.promettant = true;
  let fini = false;
  const p = WebAssembly.promising(qt)().then(() => { fini = true; });
  await new Promise(r => setTimeout(r, 10));
  resultat.suspendue = !fini && typeof ctrl.resume === "function";
  ctrl.resume();
  await p;
  resultat.reprise = fini && s.promettant && !s.suspendu;
});
Object.assign(resultat, { refus: s.refus, suspensions: s.suspensions, sauves, restaures });
// la pompe promettante, une frame JS au milieu (pompe → wasm → rappel JS → Qt qui veut suspendre ; les Safari des élèves,
// W929) : decider prépare la suspension, suspendre lève un SuspendError, l'aiguilleur l'attrape et refuse (état restauré,
// minuteries de Qt tirées), la pompe reste promettante
const avant = { refus: s.refus, suspensions: s.suspensions, sauves, restaures };
await essai("pompe_frame_js", async () => {
  s.promettant = true;
  await WebAssembly.promising(dehors(() => qt()))();
});
resultat.pompe_frame_js_compteurs = [s.refus - avant.refus, s.suspensions - avant.suspensions, sauves - avant.sauves,
                                     restaures - avant.restaures, s.promettant, s.suspendu];
console.log(JSON.stringify(resultat));
