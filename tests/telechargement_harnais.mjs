// Harnais de test_telechargement_vital.py : `preparer` (qtpy6web.js) sous node, un fetch qui refuse python_stdlib.zip `refus`
// fois puis le sert (ses jumeaux .br et .gz : 404, comme en développement), et un faux pyodide.mjs qui fait comme Pyodide : la bibliothèque standard manquante
// est écrite en console et loadPyodide ne rend jamais la main. Écrit en JSON la mesure, sur la dernière ligne.
//   node telechargement_harnais.mjs <qtpy6web.js en file://> <dossier du faux Pyodide en file://> <refus>
const [, , chemin, dossier, refus] = process.argv;
let refuses = 0;
const demandes = [];
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "", href: "https://hote/page.html" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: () => null, setItem() {} },
  document: { visibilityState: "visible", fullscreenElement: null, addEventListener() {} },
  window: globalThis,
  addEventListener() {},
  fetch: async u => {
    const nom = new URL(String(u)).pathname.split("/").pop();
    demandes.push(nom);
    if (nom === "python_stdlib.zip" && refuses < +refus) { refuses++; throw new TypeError("Failed to fetch"); }
    if (nom.endsWith(".br") || nom.endsWith(".gz")) return new Response(null, { status: 404 });
    return new Response(new Uint8Array(nom === "python_stdlib.zip" ? 1234 : 10));
  },
});
Object.defineProperty(globalThis, "navigator", { value: { userAgent: "node", maxTouchPoints: 0 }, configurable: true });
const m = await import(chemin);
const debut = Date.now();
const mesure = await Promise.race([
  m.preparer({}, { indexURL: dossier, boucles: false }).then(() => ({ issue: "prêt" }),
    e => ({ issue: "erreur", nom: e.name, fichier: e.fichier, message: e.message, recu: globalThis.stdlib_recue ?? null })),
  new Promise(r => setTimeout(() => r({ issue: "bloqué" }), 15000)),
]);
mesure.duree = (Date.now() - debut) / 1000;
mesure.essais_stdlib = demandes.filter(n => n === "python_stdlib.zip").length;
console.log(JSON.stringify(mesure));
process.exit(0);
