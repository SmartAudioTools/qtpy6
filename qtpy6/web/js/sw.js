// qtpy6.web : le service worker d'une page déployée (qtpy6web.service_worker l'enregistre). Il sert depuis le Cache Storage ce
// que la page lui a confié, sans requête : un hôte statique sert avec un max-age court (GitHub Pages : 600 s), passé lequel
// chaque fichier de Pyodide-Qt et de l'application est revalidé (un aller-retour par fichier, 304 sans corps) à chaque visite.
// Servi depuis le dossier de la page (qtpy6.web.construire.deposer l'y met) : un service worker ne contrôle que son dossier
// et ce qui est en dessous.
// La page envoie, une fois prête, la liste des adresses à garder (postMessage, `garder`) : le service worker les relit dans le
// cache HTTP (« force-cache » : sans réseau, la page vient de les télécharger) et les range. Un cache par requête
// d'enregistrement (?v=… de la page, cache=… : le nom de l'application, p=… : le Pyodide des workers) ; à l'activation, les
// caches du même nom d'application et d'une autre requête sont effacés. Le Pyodide des workers (p=…, passé à
// l'enregistrement car le service worker ne lit pas les constantes de la page) : un worker neuf demande les fichiers BRUTS
// (pyodide.asm.wasm…) que la page n'a chargés que par leurs jumeaux (qtpy6web.js, en_jumeau) ; il les reçoit de l'entrée du
// jumeau, sinon du réseau, rangés au premier passage — sans quoi chaque worker referait un aller-retour par fichier, et rien
// hors ligne. Le reste (la page, les données de l'application) passe au réseau tel quel.
// Venu de SmartTeacher le 05/10/2026 : ses deux moitiés (la page qui enregistre et range, ce fichier qui sert) vivaient dans
// deux dépôts, et la régression de SmartTeacher rév. 546 (le jumeau .gz du moteur servi brut au worker) n'était vue par aucun
// des deux ; tests/test_web.py, test_service_worker, la voit dans Blink et Firefox.
const REQUETE = new URLSearchParams(location.search);
const NOM = REQUETE.get("cache") || "qtpy6";
const CACHE = NOM + location.search;
const PYODIDE = REQUETE.get("p") || "";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(Promise.all([self.clients.claim(),  // contrôler dès la première visite :
  // sans claim, les workers de cette visite-là échapperaient au cache, qui ne se remplirait qu'à la seconde
  caches.keys().then(cles => Promise.all(
    cles.filter(c => c.startsWith(NOM + "?") && c !== CACHE).map(c => caches.delete(c))))])));
// Un jumeau Brotli ou gzip (NOM.br, NOM.gz, que qtpy6web.js demande à la place de NOM) est rangé DÉCOMPRESSÉ, marqué de
// l'en-tête que qtpy6web.js reconnaît (DECOMPRESSE) : sinon la page le décompresserait à chaque ouverture (0,15 à 0,3 s pour le moteur).
self.addEventListener("message", e => e.waitUntil(caches.open(CACHE).then(cache => Promise.all(e.data.map(async url => {
  if (await cache.match(url)) return;
  let reponse = await fetch(url, { cache: "force-cache" });
  if (!reponse.ok) return;
  const nom = new URL(url).pathname;
  const format = { br: "brotli", gz: "gzip" }[nom.split(".").pop()];
  if (format)
    reponse = new Response(reponse.body.pipeThrough(new DecompressionStream(format)), { headers: {
      "Content-Type": /\.wasm\.\w+$/.test(nom) ? "application/wasm" : "application/octet-stream", "X-Qtpy6-Decompresse": "1" } });
  await cache.put(url, reponse);
})))));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(caches.open(CACHE).then(async cache => {
    const garde = await cache.match(e.request);
    if (garde) return garde;
    if (PYODIDE && e.request.url.startsWith(PYODIDE)) {
      // un worker demande l'URL BRUTE d'un fichier que la page n'a chargé que par son jumeau (pyodide.asm.wasm.br…) :
      // l'entrée du jumeau, rangée décompressée (message), est la bonne réponse — sans elle, retéléchargement brut
      const jumeau = await cache.match(e.request.url + ".br") || await cache.match(e.request.url + ".gz");
      if (jumeau) return jumeau;
    }
    const reponse = await fetch(e.request);
    if (PYODIDE && e.request.url.startsWith(PYODIDE) && reponse.ok && ["basic", "cors"].includes(reponse.type)
        && !/\.(br|gz)$/.test(new URL(e.request.url).pathname))
      // jamais une réponse opaque ou en erreur ; jamais un jumeau, que seul « message » range, décompressé : rangé brut
      // ici (la page le demande dès qu'elle est contrôlée, quand p=… est le Pyodide-Qt de la page), « message » le
      // trouvait déjà là, et le worker recevait pour pyodide.asm.wasm du gzip (« Incorrect response MIME type »).
      // L'écriture hors de la chaîne de réponse : un stockage plein ou refusé (QuotaExceededError, navigation privée)
      // ne doit pas transformer une réponse reçue en erreur réseau
      e.waitUntil(cache.put(e.request, reponse.clone()).catch(() => {}));
    return reponse;
  }));
});
