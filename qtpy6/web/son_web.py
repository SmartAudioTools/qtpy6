"""Le son d'une bibliothèque compilée qui tourne dans un Web Worker (Pyxel, par SDL2 d'emscripten) : un Worker n'a pas
d'``AudioContext``, SDL y renonce (« Failed to initialize audio device ») et le jeu tourne muet. Le code du jeu ne
change pas : c'est ``AudioContext`` qui est doublé dans le Worker, et la page joue ce qu'il produit.

Ce que SDL2 en emploie (lu dans ``pyxel_binding.abi3.so``, roue 2.9.9) : ``new AudioContext()``, ``sampleRate``,
``state``, ``createScriptProcessor(n, 0, canaux)`` avec ``onaudioprocess`` / ``connect`` / ``disconnect``, et ``close``.
- Worker (``doubler()``, appelé avant ``pyxel.init``) : un ``AudioContext`` minimal, toujours ``running``, à
  ``DEBIT`` Hz. Son ``ScriptProcessorNode`` est POMPÉ par un crochet du moteur de ``memoire_partagee`` (sa minuterie de
  4 ms, qui ne passe que pendant que Python est suspendu par JSPI, et ``reconcilier()`` autour d'un sommeil bloquant),
  cadencé sur l'horloge murale comme une vraie carte : le mixeur de Pyxel avance au rythme du temps, que la page écoute
  ou non. ``onaudioprocess`` n'appelle que du wasm (le mixeur Rust de Pyxel, par ``dynCall``), jamais Python.
- Anneau : un ``SharedArrayBuffer`` créé par la page (``preparer_page()``, depuis ``memoire_partagee.installer()``),
  transmis à chaque Worker comme un segment (``enregistrer_worker``) : en-tête ``Int32`` (``_EN_TETE``) puis
  ``TRAMES`` trames de deux ``Float32`` entrelacés (le mono occupe la première). Plein : la trame est perdue (compteur).
- Page : rien tant qu'aucun Worker ne joue (aucun ``AudioContext`` créé : une application sans son ne voit que
  l'anneau). À la première demande, un ``AudioContext`` et un ``AudioWorklet`` qui lit l'anneau, rééchantillonne
  linéairement si le navigateur n'a pas donné ``DEBIT`` Hz, garde la latence près de la cible (saute en avant au-delà
  du double) et rend du silence quand l'anneau est vide. Un navigateur ne joue qu'après un geste de l'utilisateur :
  le contexte reprend à la première touche, au premier clic ; ce qui est produit avant est perdu.
Un seul anneau par page : deux jeux qui sonnent en même temps se mélangeraient mal (un jeu par noyau, non requis)."""

from __future__ import annotations

from typing import Any

NOM = "qtpy6_son"  # le segment, dans self.qtpy6_memoires
DEBIT = 48000
TRAMES = 16384  # puissance de deux : ≈ 340 ms à 48 kHz
LATENCE = 0.05  # s, cible minimale du remplissage de l'anneau ; au moins deux tampons de SDL, et une fois et demie
# l'écart entre deux pompes (sans JSPI, le sommeil bloque et la pompe ne passe qu'autour de lui)
_EN_TETE = ("ECR", "LEC", "CANAUX", "DEBIT", "CIBLE", "DEMANDE", "ETAT", "NON_NULS", "LUES", "VIDES", "PERDUES",
            "SAUTS", "NIVEAU", "POMPES")  # mots Int32 ; ETAT : 0 rien, 1 suspendu (geste attendu), 2 joue
_OCTETS_EN_TETE = 64
assert len(_EN_TETE) * 4 <= _OCTETS_EN_TETE

_COMMUN = "const I = {" + ", ".join(f"{n}: {i}" for i, n in enumerate(_EN_TETE)) + f"""}};
const TRAMES = {TRAMES}, M = TRAMES - 1, OCTETS = {_OCTETS_EN_TETE}, DEBIT = {DEBIT};
"""

_WORKER = _COMMUN + f"""
if (!self.qtpy6_son) {{
  const S = self.qtpy6_son = {{ noeuds: new Set(), dans_pompe: false }};
  const sab = () => self.qtpy6_memoires?.get("{NOM}");
  class Noeud {{
    constructor(n, entrees, canaux) {{
      this.n = n; this.canaux = Math.min(canaux, 2); this.onaudioprocess = null;
      const c = this.c = Array.from({{ length: canaux }}, () => new Float32Array(n));
      this.tampon = {{ numberOfChannels: canaux, length: n, sampleRate: DEBIT, getChannelData: i => c[i] }};
    }}
    connect() {{ S.noeuds.add(this); }}
    disconnect() {{ S.noeuds.delete(this); }}
  }}
  class AudioContext {{
    constructor() {{ this.sampleRate = DEBIT; this.state = "running"; this.destination = {{}}; }}
    get currentTime() {{ return performance.now() / 1000; }}
    createScriptProcessor(n, entrees, canaux) {{ return new Noeud(n, entrees, canaux); }}
    createBuffer(canaux, n, debit) {{
      const c = Array.from({{ length: canaux }}, () => new Float32Array(n));
      return {{ numberOfChannels: canaux, length: n, sampleRate: debit, getChannelData: i => c[i] }};
    }}
    resume() {{ return Promise.resolve(); }}
    suspend() {{ return Promise.resolve(); }}
    close() {{ this.state = "closed"; S.noeuds.clear(); return Promise.resolve(); }}
  }}
  self.AudioContext ??= AudioContext;

  const ecrire = (noeud, cible) => {{
    const b = sab();
    if (!b) return;
    const H = new Int32Array(b, 0, OCTETS / 4), D = new Float32Array(b, OCTETS, TRAMES * 2), n = noeud.n;
    Atomics.store(H, I.CANAUX, noeud.canaux); Atomics.store(H, I.DEBIT, DEBIT); Atomics.store(H, I.CIBLE, cible);
    Atomics.add(H, I.POMPES, 1);
    if (Atomics.compareExchange(H, I.DEMANDE, 0, 1) === 0) Atomics.notify(H, I.DEMANDE);
    const e = Atomics.load(H, I.ECR), l = Atomics.load(H, I.LEC);
    if (((e - l) | 0) + n > TRAMES) {{ Atomics.add(H, I.PERDUES, n); return; }}
    for (let k = 0; k < noeud.canaux; k++) {{
      const c = noeud.c[k];
      for (let j = 0; j < n; j++) D[((e + j) & M) * 2 + k] = c[j];
    }}
    Atomics.store(H, I.ECR, (e + n) | 0);
  }};
  let t0 = null, produites = 0, derniere = null, ecart = 0;
  S.pomper = sommet => {{  // le crochet du moteur de memoire_partagee
    const [noeud] = S.noeuds;  // SDL n'en ouvre qu'un pour la sortie
    if (!noeud || !noeud.onaudioprocess) {{ t0 = derniere = null; return; }}
    const maintenant = performance.now();
    ecart = Math.max(derniere === null ? 0 : maintenant - derniere, ecart * 0.98); derniere = maintenant;  // ms entre deux pompes, maximum glissant
    const cible = Math.min(TRAMES >> 1, Math.round(Math.max(2 * noeud.n, DEBIT * {LATENCE}, 1.5 * ecart * DEBIT / 1000)));
    if (t0 === null || (maintenant - t0) * DEBIT / 1000 - produites > TRAMES) {{ t0 = maintenant; produites = 0; }}  // départ, ou Python a calculé longtemps sans dormir : on ne rattrape pas
    while (produites < (maintenant - t0) * DEBIT / 1000 + cible) {{
      // Entrée au sommet (minuterie) : une pile JSPI peut être suspendue, sa pile C laissée en place sous le pointeur ;
      // Pyodide ne la met à l'abri que dans enterTask(), à chacune de ses entrées : sans lui, le mixeur l'écrase
      // (mesuré : « index out of bounds » puis « indirect call to null » au réveil de Python). Imbriquée : rien à faire.
      if (sommet) S.module?.enterTask?.();
      S.dans_pompe = true;
      try {{ noeud.onaudioprocess({{ outputBuffer: noeud.tampon }}); }} finally {{ S.dans_pompe = false; }}
      produites += noeud.n;
      ecrire(noeud, cible);
    }}
  }};
}}
self.qtpy6_son
"""

_PROCESSEUR = _COMMUN + """
registerProcessor("qtpy6-son", class extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const b = options.processorOptions.sab;
    this.H = new Int32Array(b, 0, OCTETS / 4); this.D = new Float32Array(b, OCTETS, TRAMES * 2); this.f = 0;
  }
  process(entrees, sorties) {
    const H = this.H, D = this.D, s = sorties[0], n = s[0].length;
    const c = Atomics.load(H, I.CANAUX) || 1, pas = (Atomics.load(H, I.DEBIT) || DEBIT) / sampleRate;
    const e = Atomics.load(H, I.ECR), cible = Atomics.load(H, I.CIBLE) || 2400;
    let l = Atomics.load(H, I.LEC), non_nuls = 0, vides = 0;
    if (((e - l) | 0) > 2 * cible) { l = (e - cible) | 0; this.f = 0; Atomics.add(H, I.SAUTS, 1); }
    for (let j = 0; j < n; j++) {
      if (((e - l) | 0) < 2) { for (const canal of s) canal[j] = 0; vides++; continue; }
      const i0 = (l & M) * 2, i1 = ((l + 1) & M) * 2;
      for (let k = 0; k < s.length; k++) {
        const q = Math.min(k, c - 1), v = D[i0 + q] + (D[i1 + q] - D[i0 + q]) * this.f;
        s[k][j] = v;
        if (v !== 0) non_nuls++;
      }
      this.f += pas;
      const avance = Math.floor(this.f);
      l = (l + avance) | 0; this.f -= avance;
    }
    Atomics.store(H, I.LEC, l); Atomics.store(H, I.NIVEAU, (e - l) | 0);
    Atomics.add(H, I.NON_NULS, non_nuls); Atomics.add(H, I.LUES, n); Atomics.add(H, I.VIDES, vides);
    return true;
  }
});
"""

_PAGE = _COMMUN + """
(processeur => {
  if (self.qtpy6_son_page) return self.qtpy6_son_page;
  const sab = new SharedArrayBuffer(OCTETS + TRAMES * 2 * 4), H = new Int32Array(sab, 0, OCTETS / 4);
  const P = self.qtpy6_son_page = { sab, H, I, contexte: undefined };
  const demarrer = async () => {
    let ctx;
    try { ctx = new AudioContext({ sampleRate: DEBIT }); } catch { ctx = new AudioContext(); }  // rééchantillonné par le worklet
    P.contexte = ctx;
    const url = URL.createObjectURL(new Blob([processeur], { type: "text/javascript" }));
    await ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const noeud = new AudioWorkletNode(ctx, "qtpy6-son",
      { numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [2], processorOptions: { sab } });
    noeud.connect(ctx.destination);
    const evenements = ["keydown", "pointerdown", "touchstart"];
    const reprendre = () => { if (ctx.state === "suspended") ctx.resume(); };
    const etat = () => {
      Atomics.store(H, I.ETAT, ctx.state === "running" ? 2 : 1);
      if (ctx.state !== "suspended") evenements.forEach(e => removeEventListener(e, reprendre, true));
    };
    ctx.onstatechange = etat;
    evenements.forEach(e => addEventListener(e, reprendre, true));
    etat();
  };
  const attendre = () => {
    if (Atomics.load(H, I.DEMANDE)) return demarrer().catch(e => console.error("qtpy6 son :", e));
    if (Atomics.waitAsync) {
      const r = Atomics.waitAsync(H, I.DEMANDE, 0);
      if (r.async) r.value.then(attendre); else attendre();
    } else setTimeout(attendre, 250);
  };
  attendre();
  return P;
})
"""


def preparer_page() -> Any:
    """Page : l'anneau (un ``SharedArrayBuffer``), et l'attente d'un Worker qui joue. ``None`` si la page n'est pas
    isolée (sans ``SharedArrayBuffer``, pas de son ; le jeu tourne muet comme avant)."""
    import js  # noqa: PLC0415
    from pyodide.code import run_js  # noqa: PLC0415

    if not hasattr(js, "SharedArrayBuffer") or not getattr(js.self, "crossOriginIsolated", False):
        return None
    return run_js(_PAGE)(_PROCESSEUR).sab


def doubler() -> None:
    """Worker : ``AudioContext`` doublé, pompé par le moteur de ``memoire_partagee``. Idempotent."""
    from pyodide.code import run_js  # noqa: PLC0415

    from qtpy6.web import memoire_partagee  # noqa: PLC0415

    import pyodide_js  # noqa: PLC0415

    son = run_js(_WORKER)
    son.module = pyodide_js._module  # enterTask, avant d'entrer dans le wasm depuis la minuterie
    memoire_partagee.ajouter_crochet(son.pomper)
