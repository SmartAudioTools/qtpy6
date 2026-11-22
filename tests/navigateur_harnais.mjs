// Harnais de test_navigateur_sans_jspi.py : `preparer` (qtpy6web.js) sous node, WebAssembly.Suspending retiré (un navigateur
// trop ancien) : il doit refuser par une erreur NavigateurSansJSPI AVANT tout téléchargement ; et `navigateur` sur des
// agents réels. Écrit en JSON la mesure, sur la dernière ligne.
const [, , chemin] = process.argv;
const demandes = [];
Object.assign(globalThis, {
  location: { pathname: "/page.html", search: "", href: "https://hote/page.html" },
  HTMLCanvasElement: class { getContext() {} },
  localStorage: { getItem: () => null, setItem() {} },
  document: { visibilityState: "visible", fullscreenElement: null, addEventListener() {} },
  window: globalThis,
  addEventListener() {},
  fetch: async u => { demandes.push(String(u)); throw new Error("hors ligne"); },
});
Object.defineProperty(globalThis, "navigator", {
  value: { userAgent: "Mozilla/5.0 (iPad; CPU OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1", maxTouchPoints: 5 },
  configurable: true,
});
const m = await import(chemin);
const mesure = {};
const S = WebAssembly.Suspending;
delete WebAssembly.Suspending;
try {
  await m.preparer({}, { indexURL: "https://hote/pyodide-qt/" });
  mesure.refus = "passe sans erreur";
} catch (e) {
  mesure.refus = { nom: e.name, navigateur: e.navigateur, message: e.message };
}
WebAssembly.Suspending = S;
mesure.demandes = demandes;
const agents = {
  chrome_windows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  edge: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
  firefox: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
  safari_mac: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Safari/605.1.15",
  chrome_iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 26_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/140.0.0.0 Mobile/15E148 Safari/604.1",
};
navigator.maxTouchPoints = 0;
mesure.navigateurs = Object.fromEntries(Object.entries(agents).map(([k, a]) => [k, m.navigateur(a)]));
console.log(JSON.stringify(mesure));
process.exit(0);
