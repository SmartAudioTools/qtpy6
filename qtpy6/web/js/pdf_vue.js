// pdf_vue.js (qtpy6.web.pdf) : un PDF dessiné par pdf.js dans un <div> de la page, que la doublure de QPdfView cale sur
// son widget. Une EXPRESSION, évaluée par run_js : (urlPdf, urlWorker) => { ouvrir, Vue }, les deux URL étant celles
// (Blob) de js/pdfjs/pdf.min.mjs et de son worker. Un <div> et pas un <iframe> : le focus reste dans la page, qui ne
// reçoit pas de `blur` (ce qu'une surveillance d'épreuve compterait comme une sortie).
//
// Chaque page : un canevas (l'image, à la densité de l'écran) et, par-dessus, la couche de texte de pdf.js (des <span>
// transparents placés sur les glyphes) : le texte se sélectionne et se copie comme dans le lecteur de Firefox.
(urlPdf, urlWorker) => {
  const MARGE = 6, ECART = 3;  // les marges et l'espacement par défaut de QPdfView
  let lib = null;

  // La partie de pdf_viewer.css (pdf.js 6.2.108) qui fait la couche de texte, plus la page et le fond de la vue.
  const CSS = `
.qtpy6-pdf { position: fixed; overflow: auto; background: #d9d9d9; z-index: 10; box-sizing: border-box; }
.qtpy6-pdf .page { position: relative; margin: 0 auto ${ECART}px; background: white; box-shadow: 0 0 2px #0006;
  --user-unit: 1; --total-scale-factor: calc(var(--scale-factor) * var(--user-unit));
  --scale-round-x: 1px; --scale-round-y: 1px; }
.qtpy6-pdf .page:first-child { margin-top: ${MARGE}px; }
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
      lib = import(urlPdf).then(m => { m.GlobalWorkerOptions.workerSrc = urlWorker; return m; });
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
    }

    async afficher(doc) {  // un PDFDocumentProxy, sa promesse (celle d'ouvrir) ou null
      const demande = this.demande = (this.demande ?? 0) + 1;
      doc = await doc;
      if (demande !== this.demande) return;  // une demande plus récente est passée pendant l'attente
      this.doc = doc;
      await this.mettreEnPage();
    }

    async mettreEnPage() {
      const generation = ++this.generation, doc = this.doc;
      const proportion = this.div.scrollHeight > 0 ? this.div.scrollTop / this.div.scrollHeight : 0;
      this.visibles.disconnect();
      this.div.replaceChildren();
      this.largeur = this.div.clientWidth;
      if (!doc || this.largeur <= 0) return;
      for (let n = 1; n <= doc.numPages; n++) {
        const page = await doc.getPage(n);
        if (generation !== this.generation) return;
        const base = page.getViewport({ scale: 1 });
        const echelle = (this.largeur - 2 * MARGE) / base.width;
        const cadre = document.createElement("div");
        cadre.className = "page";
        cadre.style.width = `${Math.floor(base.width * echelle)}px`;
        cadre.style.height = `${Math.floor(base.height * echelle)}px`;
        cadre.style.setProperty("--scale-factor", echelle);
        cadre.qtpy6 = { page, echelle, generation };
        this.div.append(cadre);
        this.visibles.observe(cadre);
      }
      this.div.scrollTop = proportion * this.div.scrollHeight;
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
      const { TextLayer } = await lib;
      await new TextLayer({ textContentSource: page.streamTextContent(), container: texte, viewport }).render();
      const fin = document.createElement("div");
      fin.className = "endOfContent";
      texte.append(fin);
    }

    // Le rectangle du widget, en pixels CSS de la page ; caché quand le widget ne doit pas se voir.
    placer(x, y, largeur, hauteur, visible) {
      Object.assign(this.div.style, { left: `${x}px`, top: `${y}px`, width: `${largeur}px`, height: `${hauteur}px`,
                                      display: visible ? "" : "none" });
    }

    detruire() {
      this.generation++;
      this.visibles.disconnect();
      this.taille.disconnect();
      document.removeEventListener("mouseup", this.relacher);
      this.div.remove();
    }
  }

  return { ouvrir, vue: () => new Vue() };
}
