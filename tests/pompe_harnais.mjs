// Harnais de test_pompe_pile_js.py : la pompe promettante de qtpy6web.js (`pomper`) sous node, avec un module Emscripten
// simulé dont chaque callPromising laisse 16 octets de pile C, comme Pyodide 0.29.3 (B1, W744, 17/11/2026). Écrit en JSON
// la descente de la pile après N tours, sans et avec un cadre vivant d'une autre entrée posé pendant un tour.
const [, , chemin] = process.argv;
let intervalle = null;
const stockage = new Map();
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: k => stockage.get(k) ?? null, setItem: (k, v) => stockage.set(k, v) },
  document: { visibilityState: "visible", fullscreenElement: null, addEventListener() {} },
  window: { addEventListener() {} },
  setInterval: f => { intervalle = f; return 1; },
  clearInterval: () => { intervalle = null; },
});
const m = await import(chemin);
let sp = 5_000_000;
const M = { qtSuspendResumeControl: {}, stackSave: () => sp, stackRestore: v => { sp = v; } };
m.suspension.M = M;
let autre = 0;  // octets qu'une autre entrée pose (et garde) pendant le prochain tour
const tour = () => {};
tour.callPromising = () => { sp -= 16; sp -= autre; autre = 0; return Promise.resolve(); };
m.pomper(tour, 10);
const tours = async n => { for (let i = 0; i < n; i++) { intervalle(); await new Promise(r => setTimeout(r, 0)); } };
const depart = sp;
await tours(1000);
const seule = depart - sp;
const avant = sp;
autre = 64;
await tours(1);
const cadre_vivant = avant - sp;
console.log(JSON.stringify({ seule, cadre_vivant }));
