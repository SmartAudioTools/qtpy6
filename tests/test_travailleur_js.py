"""``travailleur.js`` sous node, avec un faux Pyodide : un Pyodide mort dans le Worker (``fatal_error`` → ``_api.on_fatal``)
doit finir le processus ({fin}) avec sa cause sur stderr, et fermer le Worker. Sans cela (12/11/2026, professeur, %runfile) :
le noyau meurt en silence et la WebLoop enchaîne « Cannot enter a promising task from inside another running promising
task » à chaque minuterie (W568)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).parent.parent / "qtpy6" / "web" / "js" / "travailleur.js"

FAUX_PYODIDE = """
export async function loadPyodide() {
  const py = { _api: {}, setStdout() {}, setStderr() {}, loadPackage: async () => {}, unpackArchive() {},
               runPython: () => () => null, pyimport: () => ({}) };
  globalThis.fauxPy = py;
  return py;
}
"""

HARNAIS = """
const vm = require("vm"), fs = require("fs"), url = require("url");
const [js, index, mode] = process.argv.slice(2);
const messages = [];
let ferme = false;
globalThis.self = globalThis;
globalThis.postMessage = m => messages.push(m);
globalThis.close = () => { ferme = true; };
vm.runInThisContext(fs.readFileSync(js, "utf8"), { filename: js, importModuleDynamically: vm.constants.USE_MAIN_CONTEXT_DEFAULT_LOADER });
onmessage({ data: mode === "init" ? { init: { indexURL: index, archives: [], module: "m", cwd: "/" } }
                                  : { prechauffer: { indexURL: index } } });
setTimeout(() => {
  const on_fatal = globalThis.fauxPy && globalThis.fauxPy._api.on_fatal;
  if (on_fatal) on_fatal(new Error("index out of bounds"));
  setTimeout(() => console.log(JSON.stringify({ charge: !!globalThis.fauxPy, pose: !!on_fatal, messages, ferme })), 50);
}, 200);
"""


@pytest.fixture(scope="module", params=["prechauffer", "init"])
def resultat(request, tmp_path_factory) -> dict:
    if shutil.which("node") is None:
        pytest.skip("node absent")
    d = tmp_path_factory.mktemp("travailleur")
    (d / "pyodide.mjs").write_text(FAUX_PYODIDE, encoding="utf-8")
    (d / "harnais.cjs").write_text(HARNAIS, encoding="utf-8")
    sortie = subprocess.run(["node", str(d / "harnais.cjs"), str(JS), d.as_uri() + "/", request.param], capture_output=True, text=True,
                            timeout=60, check=True).stdout
    return dict(json.loads(sortie.strip().splitlines()[-1]), mode=request.param)


def test_pyodide_mort_finit_le_processus(resultat: dict) -> None:
    assert resultat["charge"], "le faux Pyodide n'a pas été chargé (harnais)"
    assert resultat["pose"], "on_fatal n'est pas posé sur le Pyodide du Worker"
    if resultat["mode"] == "init":  # mode appels, hors de tout appel : {erreur} SANS id (« le worker est tombé »)
        erreurs = [m for m in resultat["messages"] if "erreur" in m]
        assert erreurs and "id" not in erreurs[-1] and "index out of bounds" in erreurs[-1]["erreur"]
        assert resultat["ferme"]
        return
    fins = [m["fin"] for m in resultat["messages"] if "fin" in m]
    assert fins and fins[0] != 0
    erreurs = "".join(m.get("sortie_erreur", "") for m in resultat["messages"])
    assert "index out of bounds" in erreurs and "mort" in erreurs
    assert resultat["ferme"]
