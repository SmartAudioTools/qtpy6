// Harnais de test_boite_noire_js.py : la boîte noire de qtpy6web.js sous node, horloges et page simulées. Rejoue les
// scénarios des boîtes noires des élèves (06-09/11/2026) et écrit en JSON les lignes notées par chacun.
const [, , chemin] = process.argv;
let maintenant = 1_000_000, intervalle = null;
const ecoutes = { document: {}, window: {} };
const ecouter = cible => (nom, f) => { (ecoutes[cible][nom] ||= []).push(f); };
const emettre = (cible, nom, e = {}) => (ecoutes[cible][nom] || []).forEach(f => f(e));
const stockage = new Map();
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: k => stockage.get(k) ?? null, setItem: (k, v) => stockage.set(k, v) },
  document: { visibilityState: "visible", fullscreenElement: null, addEventListener: ecouter("document") },
  window: { addEventListener: ecouter("window") },
  setInterval: f => { intervalle = f; return 1; },
});
Object.defineProperty(globalThis, "performance", { value: { now: () => maintenant }, configurable: true });
Date.now = () => maintenant;
const m = await import(chemin);
m.ouvrir_boite_noire();
const avancer = (s, { qt = true, tics = true } = {}) => {  // s secondes ; Qt bat chaque seconde si qt, la page tique si tics
  for (let i = 0; i < s; i++) { maintenant += 1000; if (qt) m.battement_qt(); if (tics) intervalle(); }
};
const montrer = vu => { document.visibilityState = vu ? "visible" : "hidden"; emettre("document", "visibilitychange"); };
const lignes = () => { const b = JSON.parse(stockage.get("qtpy6.boite_noire:/page.html")); return [b.lignes.map(l => l.replace(/^\S+ /, "")), b.fin]; };
const resultat = {};
const scenario = (nom, f) => { const debut = lignes()[0].length; f(); const [l, fin] = lignes(); resultat[nom] = { lignes: l.slice(debut), fin }; };

avancer(5);
// Onglet caché, page figée AVANT le tic suivant (aucun tic ni battement de Qt pendant 300 s), puis montré.
scenario("onglet_cache", () => { montrer(false); avancer(300, { qt: false, tics: false }); montrer(true); avancer(1, { qt: false }); avancer(5); });
// Retour arrière : pagehide, page figée 300 s dans le cache, pageshow persisted.
scenario("cache_navigateur", () => {
  emettre("window", "pagehide"); montrer(false); avancer(300, { qt: false, tics: false });
  montrer(true); emettre("window", "pageshow", { persisted: true }); avancer(1, { qt: false }); avancer(5);
});
// Retour du cache sans aucun visibilitychange (seuls pagehide et pageshow persisted).
scenario("cache_sans_visibilite", () => {
  emettre("window", "pagehide"); avancer(300, { qt: false, tics: false });
  emettre("window", "pageshow", { persisted: true }); avancer(1, { qt: false }); avancer(5);
});
// Un vrai gel, onglet visible : le fil bloqué 10 s (aucun tic, aucun battement), puis la page repart.
scenario("fil_bloque", () => { avancer(10, { qt: false, tics: false }); avancer(5); });
// La boucle de Qt arrêtée seule, la page tique toujours : 10 s sans battement, puis Qt repart.
scenario("qt_arretee", () => { avancer(10, { qt: false }); avancer(2); });
console.log(JSON.stringify(resultat));
