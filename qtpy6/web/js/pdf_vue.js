// pdf_vue.js (qtpy6.web.pdf) : un PDF dessiné par pdf.js dans un <div> de la page, que la doublure de QPdfView cale sur
// son widget. Une EXPRESSION, évaluée par run_js : (urlPdf, urlWorker) => { ouvrir, Vue }, les deux URL étant celles
// (Blob) de js/pdfjs/pdf.min.mjs et de son worker. Un <div> et pas un <iframe> : le focus reste dans la page, qui ne
// reçoit pas de `blur` (ce qu'une surveillance d'épreuve compterait comme une sortie).
//
// Chaque page : un canevas (l'image, à la densité de l'écran) et, par-dessus, la couche de texte de pdf.js (des <span>
// transparents placés sur les glyphes) : le texte se sélectionne et se copie comme dans le lecteur de Firefox ; et au-dessus,
// un <a> par lien interne du PDF (un sommaire), qui fait défiler jusqu'à sa destination. Les zones masquées (setMasks) sont
// repeintes en pavés sur le canevas, et leur texte retiré de la couche de texte : ni sélection, ni copie, ni recherche.
(urlPdf, urlWorker) => {
  let lib = null;
  const MARGE_LIEN = 12;  // points laissés au-dessus de la destination d'un lien : dessus, le haut d'un titre était coupé (même marge sur ordinateur, QtPdfWidgets.py)
  const PAVE = 12;  // côté des pavés d'un masque, en points de la page : illisible à tout zoom (MASK_BLOCK sur ordinateur)
  const MARGE_RECHERCHE = 40;  // points laissés au-dessus d'un résultat de recherche atteint (SEARCH_MARGIN sur ordinateur)
  const mesure = document.createElement("canvas").getContext("2d");
  const largeur = (texte, famille) => {  // largeur d'un texte dans la famille de fonte d'un morceau pdf.js (repli sans-serif)
    mesure.font = `100px ${famille || "sans-serif"}`;
    return mesure.measureText(texte).width || texte.length;
  };

  // Les pavés d'un masque (x, y, l, h en points) sur le canevas d'une page : chacun prend la couleur moyenne de ce qu'il
  // couvre, obtenue par réductions de moitié successives (une réduction directe n'échantillonne que quelques pixels, et
  // laisserait passer des traits du texte), puis agrandi sans lissage. Pavés comptés depuis le coin du masque, en points :
  // un fort zoom ne les affine pas.
  function paver(canevas, [x, y, l, h], echelle) {
    const colonnes = Math.max(1, Math.ceil(Math.round(l) / PAVE)), rangees = Math.max(1, Math.ceil(Math.round(h) / PAVE));
    const sx = Math.round(x * echelle), sy = Math.round(y * echelle), cote = PAVE * echelle;
    let source = canevas, zone = [sx, sy, Math.round(colonnes * cote), Math.round(rangees * cote)];
    while (zone[2] > 2 * colonnes || zone[3] > 2 * rangees) {
      const etape = document.createElement("canvas");
      etape.width = Math.max(colonnes, Math.ceil(zone[2] / 2));
      etape.height = Math.max(rangees, Math.ceil(zone[3] / 2));
      etape.getContext("2d").drawImage(source, ...zone, 0, 0, etape.width, etape.height);
      source = etape;
      zone = [0, 0, etape.width, etape.height];
    }
    const pave = document.createElement("canvas");
    pave.width = colonnes;
    pave.height = rangees;
    pave.getContext("2d").drawImage(source, ...zone, 0, 0, colonnes, rangees);
    const ctx = canevas.getContext("2d");
    ctx.save();
    ctx.beginPath();
    ctx.rect(sx, sy, Math.round(l * echelle), Math.round(h * echelle));  // les derniers pavés débordent du masque : coupés
    ctx.clip();
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(pave, sx, sy, colonnes * cote, rangees * cote);
    ctx.restore();
  }

  // La partie de pdf_viewer.css (pdf.js 6.2.108) qui fait la couche de texte, plus la page et le fond de la vue.
  const CSS = `
.qtpy6-pdf { position: fixed; overflow: auto; background: #d9d9d9; z-index: 10; box-sizing: border-box;
  scrollbar-color: rgba(0 0 0 / 0.3) white; }
.qtpy6-pdf .page { position: relative; margin: 0 auto; background: white;
  --user-unit: 1; --total-scale-factor: calc(var(--scale-factor) * var(--user-unit));
  --scale-round-x: 1px; --scale-round-y: 1px; }
.qtpy6-pdf .liens { position: absolute; inset: 0; z-index: 2; pointer-events: none; }
.qtpy6-pdf .liens a { position: absolute; pointer-events: auto; cursor: pointer; }
.qtpy6-pdf .liens .voile { position: absolute; background: rgba(255 255 255 / 0.63); }
.qtpy6-pdf .trouves { position: absolute; inset: 0; z-index: 1; pointer-events: none; }
.qtpy6-pdf .trouves div { position: absolute; background: rgba(255 230 0 / 0.43); }
.qtpy6-pdf .trouves .courant { background: rgba(255 150 0 / 0.55); }
.qtpy6-pdf-bulle { position: fixed; z-index: 2147483647; pointer-events: none; max-width: 32em; padding: 4px 8px;
                   background: #ffffe1; color: #000; border: 1px solid #767676; font: 13px sans-serif; }
.qtpy6-pdf .page canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
.qtpy6-pdf .textLayer { position: absolute; text-align: initial; inset: 0; overflow: clip; opacity: 1; line-height: 1;
  text-size-adjust: none; forced-color-adjust: none; transform-origin: 0 0; caret-color: CanvasText; z-index: 0;
  --min-font-size: 1; --text-scale-factor: calc(var(--total-scale-factor) * var(--min-font-size));
  --min-font-size-inv: calc(1 / var(--min-font-size)); }
.qtpy6-pdf .textLayer :is(span, br) { color: transparent; position: absolute; white-space: pre; cursor: text;
  transform-origin: 0% 0%; user-select: text; }
.qtpy6-pdf .textLayer > :not(.markedContent), .qtpy6-pdf .textLayer .markedContent span:not(.markedContent) {
  z-index: 1; --font-height: 0; font-size: calc(var(--text-scale-factor) * var(--font-height));
  --scale-x: 1; --rotate: 0deg;
  transform: rotate(var(--rotate)) scaleX(var(--scale-x)) scale(var(--min-font-size-inv)); }
.qtpy6-pdf .textLayer .markedContent { display: contents; }
.qtpy6-pdf .textLayer span[role="img"] { user-select: none; cursor: default; }
.qtpy6-pdf .textLayer ::selection { background: rgba(0 0 255 / 0.25); }
.qtpy6-pdf .textLayer br::selection { background: transparent; }
.qtpy6-pdf .textLayer .endOfContent { display: block; position: absolute; inset: 100% 0 0; z-index: 0; cursor: default;
  user-select: none; }
.qtpy6-pdf .textLayer.selecting .endOfContent { top: 0; }`;

  function bibliotheque() {
    if (!lib) {
      const style = document.createElement("style");
      style.textContent = CSS;
      document.head.append(style);
      // pdf.js 6 appelle Map.getOrInsertComputed (ES2026), absent d'un navigateur plus ancien (Chrome 140 de QtWebEngine,
      // 05/10/2026) : sans lui, page.render échoue en silence et le PDF ne paraît jamais. Posé ici et dans le worker, que
      // charge un module Blob qui le pose avant d'importer le vrai.
      const COMPAT = `for (const C of [Map, WeakMap]) {
        C.prototype.getOrInsert ??= function (k, v) { if (!this.has(k)) this.set(k, v); return this.get(k); };
        C.prototype.getOrInsertComputed ??= function (k, f) { if (!this.has(k)) this.set(k, f(k)); return this.get(k); };
      }`;
      new Function(COMPAT)();
      const travailleur = URL.createObjectURL(new Blob([`${COMPAT}\nimport ${JSON.stringify(urlWorker)};`],
                                                       { type: "text/javascript" }));
      lib = import(urlPdf).then(m => {
        m.GlobalWorkerOptions.workerPort = new Worker(travailleur, { type: "module" });
        return m;
      });
    }
    return lib;
  }

  // Le document : une promesse de PDFDocumentProxy, que QPdfDocument garde et que chaque Vue affiche.
  async function ouvrir(octets) {
    const m = await bibliotheque();
    return m.getDocument({ data: octets, isEvalSupported: false }).promise;
  }

  class Vue {
    constructor() {
      this.div = document.createElement("div");
      this.div.className = "qtpy6-pdf";
      this.div.style.display = "none";
      this.div.tabIndex = -1;  // prend le focus au clic : Ctrl+C et Ctrl+A visent ce <div>, pas le canevas de Qt
      document.body.append(this.div);
      this.doc = null;
      this.limite = null;  // setPageLimit : les premières pages seules, les suivantes ne sont pas créées
      this.masques = new Map();  // setMasks : numéro de page (0 = la première) → [[x, y, l, h] en points, depuis le haut gauche]
      this.marges = [6, 6, 6, 6];  // setDocumentMargins (gauche, haut, droite, bas) et setPageSpacing : les défauts de QPdfView
      this.ecart = 3;
      this.largeur = 0;
      this.generation = 0;
      this.visibles = new IntersectionObserver(e => e.forEach(x => x.isIntersecting && this.dessiner(x.target)),
                                               { root: this.div, rootMargin: "300px 0px" });
      // la largeur change : on refait la mise en page (la position de lecture est gardée en proportion)
      this.taille = new ResizeObserver(() => {
        const l = this.div.clientWidth;
        if (this.doc && l > 0 && Math.abs(l - this.largeur) > 1) this.mettreEnPage();
      });
      this.taille.observe(this.div);
      // la sélection partant d'une page déborde moins en marge quand .endOfContent couvre la page (pdf_viewer)
      this.div.addEventListener("mousedown", e => e.target.closest?.(".textLayer")?.classList.add("selecting"));
      this.relacher = () => this.div.querySelectorAll(".selecting").forEach(t => t.classList.remove("selecting"));
      document.addEventListener("mouseup", this.relacher);
      this.zonesCopie = null;
      this.filtre = null;
      this.div.addEventListener("copy", e => {
        if (!this.filtre) return;
        e.clipboardData.setData("text/plain", this.filtre(document.getSelection().toString()));
        e.preventDefault();
      });
      this.cherche = "";  // setSearchText : le texte, ses résultats [[page, [[x, y, l, h] en points], …], le courant
      this.trouves = [];
      this.courant = -1;
      // Le <div> cliqué a le clavier, Qt ne le voit pas. Ctrl+F : sans ceci, le navigateur ouvrirait sa propre recherche ;
      // Ctrl+C et Ctrl+A restent au <div> (copier, tout sélectionner) ; toute autre touche part à Qt (rappelClavier),
      // comme au QPdfView natif qui a le focus (raccourcis de la fenêtre, keyPressEvent), et celle que Qt laisse passer
      // garde son effet dans la page (défilement).
      this.div.addEventListener("keydown", e => {
        const commande = (e.ctrlKey || e.metaKey) && !e.altKey ? e.key.toLowerCase() : "";
        if (commande === "f") {
          e.preventDefault();
          this.trouver?.();
        } else if (commande !== "c" && commande !== "a" && this.touche?.(e.key, e.ctrlKey, e.shiftKey, e.altKey, e.metaKey)) {
          e.preventDefault();
        }
      });
    }

    async afficher(doc) {  // un PDFDocumentProxy, sa promesse (celle d'ouvrir) ou null
      const demande = this.demande = (this.demande ?? 0) + 1;
      doc = await doc;
      if (demande !== this.demande) return;  // une demande plus récente est passée pendant l'attente
      this.doc = doc;
      await this.mettreEnPage();
      this.rechercher();
    }

    rappelsRecherche(compte, trouver) {  // le nombre de résultats, une fois connu ; Ctrl+F dans la vue
      this.compte = compte;
      this.trouver = trouver;
    }

    rappelClavier(touche) {  // (key, ctrl, maj, alt, meta) → vrai si Qt a pris la touche
      this.touche = touche;
    }

    pageCourante() {  // pageNavigator().currentPage() : la dernière page dont le haut est monté au haut de la vue
      // ou, tant que la vue n'a pas bougé, celle d'allerPage même si le bas du document l'empêche de monter (comme Qt)
      if (this.sautee && this.sautee[1] === this.div.scrollTop) return this.sautee[0];
      let n = 0;
      while (n + 1 < this.div.children.length && this.div.children[n + 1].offsetTop <= this.div.scrollTop + 1) n++;
      return n;
    }

    allerPage(n, y) {  // pageNavigator().jump : le point à y points du haut de la page n, en haut de la vue
      const cadre = this.div.children[n];
      if (!cadre) return;
      this.div.scrollTop = cadre.offsetTop + y * cadre.qtpy6.echelle;
      this.sautee = [n, this.div.scrollTop];
    }

    // setSearchText : le texte des pages montrées, lu par pdf.js (getTextContent) ; casse ignorée, un blanc vaut tout
    // blanc ; un résultat qui touche un masque n'existe pas, ni compté ni montré (même règle sur ordinateur). Chaque
    // morceau de texte donne la part de sa largeur qu'occupe le résultat, au prorata de ses caractères.
    async rechercher(texte = this.cherche) {
      this.cherche = texte ?? "";
      const tour = this.tour = (this.tour ?? 0) + 1, trouves = [], doc = this.doc;
      const mots = this.cherche.split(/\s+/).filter(Boolean);
      if (mots.length && doc) {
        const motif = new RegExp(mots.map(m => m.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+"), "giu");
        for (let n = 1; n <= this.montrees(); n++) {
          const page = await doc.getPage(n), contenu = await page.getTextContent();
          if (tour !== this.tour || doc !== this.doc) return;
          const base = page.getViewport({ scale: 1 }), morceaux = [], masques = this.masques.get(n - 1) ?? [];
          let tout = "";
          for (const item of contenu.items) {
            if (item.str === undefined) continue;
            morceaux.push([tout.length, item]);
            tout += item.str + (item.hasEOL ? "\n" : "");
          }
          for (const m of tout.matchAll(motif)) {
            const debut = m.index, fin = m.index + m[0].length, boites = [];
            for (const [origine, item] of morceaux) {
              const a = Math.max(debut, origine), b = Math.min(fin, origine + item.str.length);
              // un morceau blanc ne compte pas : pdf.js lui donne parfois toute la largeur jusqu'au mot suivant
              if (a >= b || !item.str.slice(a - origine, b - origine).trim()) continue;
              const [x, y] = base.convertToViewportPoint(item.transform[4], item.transform[5]);  // la ligne de base
              const h = item.height || Math.hypot(item.transform[2], item.transform[3]);
              // la part de largeur mesurée dans une fonte proche (pdf.js : styles[fontName]), pas comptée en lettres :
              // une lettre étroite avant le mot décalait le surlignage d'un caractère
              const part = t => largeur(t, contenu.styles?.[item.fontName]?.fontFamily) / largeur(item.str, contenu.styles?.[item.fontName]?.fontFamily);
              const boite = [x + item.width * part(item.str.slice(0, a - origine)), y - h,
                             item.width * part(item.str.slice(a - origine, b - origine)), h];
              const derniere = boites.at(-1);  // une boîte par ligne, comme sur ordinateur
              if (derniere && Math.min(derniere[1] + derniere[3], boite[1] + h) - Math.max(derniere[1], boite[1]) > 0) {
                const [g, hh, d, bb] = [Math.min(derniere[0], boite[0]), Math.min(derniere[1], boite[1]),
                                        Math.max(derniere[0] + derniere[2], boite[0] + boite[2]),
                                        Math.max(derniere[1] + derniere[3], boite[1] + h)];
                boites[boites.length - 1] = [g, hh, d - g, bb - hh];
              } else boites.push(boite);
            }
            const touche = ([x, y, l, h]) => masques.some(([mx, my, ml, mh]) => x < mx + ml && mx < x + l
                                                                                && y < my + mh && my < y + h);
            if (boites.length && !boites.some(touche)) trouves.push([n - 1, boites]);
          }
        }
      }
      if (tour !== this.tour) return;
      const avant = this.trouves.length;
      this.trouves = trouves;
      this.courant = -1;
      this.surligner();
      if (this.cherche || avant) this.compte?.(trouves.length);
    }

    surligner() {
      for (const cadre of this.div.children) this.peindreTrouves(cadre);
    }

    peindreTrouves(cadre) {  // les résultats de la page, en surbrillance, le courant plus foncé
      const { page, echelle } = cadre.qtpy6 ?? {};
      if (!page) return;
      cadre.querySelector(":scope > .trouves")?.remove();
      const calque = document.createElement("div");
      calque.className = "trouves";
      this.trouves.forEach(([numero, boites], i) => {
        if (numero !== page.pageNumber - 1) return;
        for (const [x, y, l, h] of boites) {
          const boite = document.createElement("div");
          if (i === this.courant) boite.className = "courant";
          Object.assign(boite.style, { left: `${x * echelle}px`, top: `${y * echelle}px`,
                                       width: `${l * echelle}px`, height: `${h * echelle}px` });
          calque.append(boite);
        }
      });
      if (calque.childElementCount) cadre.append(calque);
    }

    allerA(index) {  // setCurrentSearchResultIndex : le résultat devient le courant, et la vue défile jusqu'à lui
      this.courant = index;
      this.surligner();
      const trouve = this.trouves[index], cadre = trouve && this.div.children[trouve[0]];
      if (cadre) this.div.scrollTop = cadre.offsetTop + Math.max(0, trouve[1][0][1] - MARGE_RECHERCHE) * cadre.qtpy6.echelle;
    }

    async mettreEnPage() {
      const generation = ++this.generation, doc = this.doc;
      const proportion = this.div.scrollHeight > 0 ? this.div.scrollTop / this.div.scrollHeight : 0;
      this.visibles.disconnect();
      this.div.replaceChildren();
      this.largeur = this.div.clientWidth;
      if (!doc || this.largeur <= 0) return;
      const montrees = this.montrees();
      for (let n = 1; n <= montrees; n++) {
        const page = await doc.getPage(n);
        if (generation !== this.generation) return;
        const base = page.getViewport({ scale: 1 });
        const [gauche, haut, droite, bas] = this.marges;
        const echelle = (this.largeur - gauche - droite) / base.width;
        const cadre = document.createElement("div");
        cadre.className = "page";
        cadre.style.width = `${Math.floor(base.width * echelle)}px`;
        cadre.style.height = `${Math.floor(base.height * echelle)}px`;
        cadre.style.marginTop = `${n === 1 ? haut : this.ecart}px`;
        cadre.style.marginBottom = `${n === montrees ? bas : 0}px`;
        cadre.style.setProperty("--scale-factor", echelle);
        cadre.qtpy6 = { page, echelle, generation };
        this.div.append(cadre);
        this.peindreTrouves(cadre);
        this.visibles.observe(cadre);
      }
      this.div.scrollTop = proportion * this.div.scrollHeight;
    }

    montrees() {  // le nombre de pages montrées
      return Math.min(this.doc.numPages, this.limite ?? Infinity);
    }

    limiter(nombre) {
      this.limite = nombre ?? null;
      if (this.doc) this.mettreEnPage().then(() => this.rechercher());
    }

    // setCopyZones : seul le texte de ces zones se sélectionne et se copie (null : tout) ; setCopyFilter : texte → texte
    copiables(liste) {  // [[page, x, y, l, h], …] ou null
      this.zonesCopie = liste === null ? null : new Map();
      for (const [page, ...zone] of liste ?? []) this.zonesCopie.set(page, [...(this.zonesCopie.get(page) ?? []), zone]);
      if (this.doc) this.mettreEnPage();
    }

    filtrer(fonction) {
      this.filtre = fonction;
    }

    adresses(schemas, bulle, clic) {  // setUrlLinks : les liens vers ces schémas d'URL, leur infobulle et leur clic
      this.schemas = [...schemas];
      this.bulle = bulle;
      this.clic = clic;
      if (this.doc) this.mettreEnPage();
    }

    montrerBulle(adresse, e) {
      const html = this.bulle?.(adresse);
      if (!html) return;
      this.cacherBulle();
      const bulle = this.infobulle = document.createElement("div");
      bulle.className = "qtpy6-pdf-bulle";
      bulle.innerHTML = html;
      document.body.append(bulle);
      const { width, height } = bulle.getBoundingClientRect();  // près du pointeur, sans sortir de la fenêtre
      bulle.style.left = `${Math.max(0, Math.min(e.clientX + 12, innerWidth - width - 4))}px`;
      bulle.style.top = `${e.clientY + 16 + height < innerHeight ? e.clientY + 16 : Math.max(0, e.clientY - height - 8)}px`;
    }

    cacherBulle() {
      this.infobulle?.remove();
      this.infobulle = null;
    }

    masquer(liste) {  // [[page, x, y, l, h], …]
      this.masques = new Map();
      for (const [page, ...zone] of liste ?? []) this.masques.set(page, [...(this.masques.get(page) ?? []), zone]);
      if (this.doc) this.mettreEnPage().then(() => this.rechercher());
    }

    espacer(gauche, haut, droite, bas, ecart) {
      this.marges = [gauche, haut, droite, bas];
      this.ecart = ecart;
      if (this.doc) this.mettreEnPage();
    }

    // Les liens internes de la page, vers une page montrée ; ceux vers une page cachée sont voilés de blanc. Une URL
    // n'est un lien que si son schéma est dans setUrlLinks (une épreuve ne sort pas de la page) : son clic va à
    // urlActivated, son survol montre l'infobulle, sur son propre rectangle (même règle sur ordinateur). Un lien seul sur sa ligne la prend toute, large comme la page moins sa marge
    // gauche de chaque côté, et pas seulement son texte (un sommaire : la fin d'un titre court n'était pas cliquable) ;
    // même règle sur ordinateur (QtPdfWidgets.py).
    async lier(page, viewport, cadre, generation) {
      const liens = document.createElement("div");
      liens.className = "liens";
      const annotations = (await page.getAnnotations()).filter(a => a.subtype === "Link");
      const seul = a => !annotations.some(b => b !== a && Math.min(b.rect[1], b.rect[3]) < Math.max(a.rect[1], a.rect[3])
                                                         && Math.min(a.rect[1], a.rect[3]) < Math.max(b.rect[1], b.rect[3]));
      for (const a of annotations) {
        const adresse = a.dest ? null : a.url ?? a.unsafeUrl;  // pdf.js ne garde en url que les schémas qu'il sait sûrs
        if (adresse && this.schemas?.includes(adresse.split(":")[0])) {
          const [[x1, y1], [x2, y2]] = [a.rect.slice(0, 2), a.rect.slice(2)].map(([x, y]) => viewport.convertToViewportPoint(x, y));
          const lien = document.createElement("a");
          Object.assign(lien.style, { left: `${Math.min(x1, x2)}px`, top: `${Math.min(y1, y2)}px`,
                                      width: `${Math.abs(x2 - x1)}px`, height: `${Math.abs(y2 - y1)}px` });
          lien.addEventListener("click", e => { e.preventDefault(); this.cacherBulle(); this.clic?.(adresse); });
          lien.addEventListener("mouseenter", e => this.montrerBulle(adresse, e));
          lien.addEventListener("mouseleave", () => this.cacherBulle());
          liens.append(lien);
          continue;
        }
        if (!a.dest) continue;
        const dest = typeof a.dest === "string" ? await this.doc.getDestination(a.dest) : a.dest;
        if (!dest) continue;
        const cible = typeof dest[0] === "number" ? dest[0] : await this.doc.getPageIndex(dest[0]);
        const [[x1, y1], [x2, y2]] = [a.rect.slice(0, 2), a.rect.slice(2)].map(([x, y]) => viewport.convertToViewportPoint(x, y));  // pdf.js 6 n'a plus convertToViewportRectangle
        const actif = cible < this.montrees(), lien = document.createElement(actif ? "a" : "div"), gauche = Math.min(x1, x2);
        const largeur = seul(a) ? Math.max(Math.abs(x2 - x1), viewport.width - 2 * gauche) : Math.abs(x2 - x1);
        Object.assign(lien.style, { left: `${gauche}px`, top: `${Math.min(y1, y2)}px`,
                                    width: `${largeur}px`, height: `${Math.abs(y2 - y1)}px` });
        if (!actif) {  // vers une page cachée (setPageLimit) : un voile blanc, et rien à cliquer (même voile sur ordinateur)
          lien.className = "voile";
          liens.append(lien);
          continue;
        }
        lien.addEventListener("click", e => {
          e.preventDefault();
          const page = this.div.children[cible];
          const { page: proxy, echelle } = page.qtpy6;  // une destination XYZ donne son haut en points du PDF (y vers le haut)
          const haut = dest[1]?.name === "XYZ" && dest[3] != null
            ? proxy.getViewport({ scale: echelle }).convertToViewportPoint(dest[2] ?? 0, dest[3] + MARGE_LIEN)[1] : 0;
          this.div.scrollTop = page.offsetTop + Math.max(0, haut);
        });
        liens.append(lien);
      }
      if (generation === this.generation) cadre.append(liens);
    }

    async dessiner(cadre) {
      const { page, echelle, generation } = cadre.qtpy6 ?? {};
      if (!page || cadre.dataset.dessinee) return;
      cadre.dataset.dessinee = "1";
      const viewport = page.getViewport({ scale: echelle });
      const densite = window.devicePixelRatio || 1;
      const canevas = document.createElement("canvas");
      canevas.width = Math.floor(viewport.width * densite);
      canevas.height = Math.floor(viewport.height * densite);
      const texte = document.createElement("div");
      texte.className = "textLayer";
      cadre.append(canevas, texte);
      await page.render({ canvas: canevas, viewport, transform: densite === 1 ? null : [densite, 0, 0, densite, 0, 0] })
                .promise;
      if (generation !== this.generation) return;
      const masques = this.masques.get(page.pageNumber - 1) ?? [];
      for (const masque of masques) paver(canevas, masque, echelle * densite);
      const { TextLayer } = await lib;
      await new TextLayer({ textContentSource: page.streamTextContent(), container: texte, viewport }).render();
      if (masques.length) {  // le texte d'un masque : retiré, rien à sélectionner, copier ni chercher
        const origine = cadre.getBoundingClientRect();
        for (const span of texte.querySelectorAll("span")) {
          const r = span.getBoundingClientRect(), [gauche, haut] = [r.left - origine.left, r.top - origine.top];
          if (masques.some(([x, y, l, h]) => gauche < (x + l) * echelle && x * echelle < gauche + r.width
                                             && haut < (y + h) * echelle && y * echelle < haut + r.height)) span.remove();
        }
      }
      if (this.zonesCopie) {  // hors des zones de copie, le texte ne se sélectionne pas (COPY_MARGIN de QtPdfWidgets.py)
        const zones = this.zonesCopie.get(page.pageNumber - 1) ?? [], m = 3, origine = cadre.getBoundingClientRect();
        for (const span of texte.querySelectorAll("span")) {
          const r = span.getBoundingClientRect(), [gauche, haut] = [r.left - origine.left, r.top - origine.top];
          if (!zones.some(([x, y, l, h]) => (x - m) * echelle <= gauche && gauche + r.width <= (x + l + m) * echelle
                                            && (y - m) * echelle <= haut && haut + r.height <= (y + h + m) * echelle))
            span.style.userSelect = "none";
        }
      }
      const fin = document.createElement("div");
      fin.className = "endOfContent";
      texte.append(fin);
      await this.lier(page, viewport, cadre, generation);
    }

    // Le rectangle du widget, en pixels CSS de la page ; caché quand le widget ne doit pas se voir.
    placer(x, y, largeur, hauteur, visible) {
      Object.assign(this.div.style, { left: `${x}px`, top: `${y}px`, width: `${largeur}px`, height: `${hauteur}px`,
                                      display: visible ? "" : "none" });
    }

    detruire() {
      this.cacherBulle();
      this.generation++;
      this.visibles.disconnect();
      this.taille.disconnect();
      document.removeEventListener("mouseup", this.relacher);
      this.div.remove();
    }
  }

  return { ouvrir, vue: () => new Vue() };
}
