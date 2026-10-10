"""La sonde de qtpy6 (``python -m qtpy6.web.sonde``), plus la console du navigateur recopiée dans ``window.journal`` :
``console.error``/``console.warn`` (les qWarning de Qt-WASM arrivent là, pas dans stderr), les erreurs JS et les rejets de
promesse. Sans elle, « WebGL context creation failed » est invisible (10/10/2026). Mêmes arguments que la sonde."""

import sys

from qtpy6.web import sonde

CROCHET = """
window.journal = window.journal || [];
const j = (p) => (...a) => { try { window.journal.push(p + " " + a.map(x => (x && x.stack) || String(x)).join(" ")); } catch (e) {} };
for (const n of ["error", "warn"]) { const o = console[n].bind(console); console[n] = (...a) => { j("console." + n)(...a); o(...a); }; }
window.addEventListener("error", e => j("window.error")(e.message, e.error && e.error.stack));
window.addEventListener("unhandledrejection", e => j("rejet")(e.reason && (e.reason.stack || e.reason)));
"""
_attendre = sonde.attendre


def attendre(navigateur, *args, **kwargs):
    navigateur.execute_script(CROCHET)
    return _attendre(navigateur, *args, **kwargs)


sonde.attendre = attendre
sys.exit(0 if sonde.main() else 1)
