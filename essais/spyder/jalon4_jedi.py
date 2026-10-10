"""Le moteur de complétion du jalon 4 : jedi en direct, sans serveur de langage, dans le format qu'attend
``CodeEditor.handle_response(DOCUMENT_COMPLETION)`` de Spyder (``label``, ``insertText``, ``kind``…).

Importé par jalon4.py (moteur A : dans l'interpréteur de l'éditeur), ou lancé en serveur (moteur B : un Worker de la page,
un processus SmartPython sur le bureau) : ``{"pret": ms}`` sur stdout une fois jedi importé, puis une ligne JSON par
requête lue sur stdin ``{"id", "code", "ligne", "colonne"}`` (ligne à partir de 1, colonne de 0, comme jedi) → une ligne
``{"id", "items", "ms"}``. ``InterpreterEnvironment`` : jedi ne lance pas de sous-processus pour inspecter l'environnement
(il n'y en a pas dans Pyodide), il regarde l'interpréteur courant."""

import json
import sys
import time

for _m in ("PySide2", "shiboken2", "PyQt5", "PyQt6"):  # jedi IMPORTE les modules compilés qu'il rencontre (ici qtpy nomme
    sys.modules.setdefault(_m, None)  # les quatre liaisons) ; sur le bureau PySide2 plante le processus (core dump) : ImportError plutôt
_t = time.monotonic()
import jedi  # noqa: E402

IMPORT_MS = round((time.monotonic() - _t) * 1000)
GENRES = {"module": 9, "class": 7, "instance": 6, "function": 3, "param": 6, "path": 17, "keyword": 14, "property": 10,
          "statement": 6}  # jedi Completion.type → CompletionItemKind de LSP (celui du widget de Spyder) ; 1 = Text sinon
ENVIRONNEMENT = jedi.InterpreterEnvironment()


def completer(code: str, ligne: int, colonne: int, nom: str = "eleve.py") -> list[dict]:
    script = jedi.Script(code, path=nom, environment=ENVIRONNEMENT)
    try:
        propositions = script.complete(ligne, colonne)
    except Exception as e:  # jedi suit les imports du fichier dans l'interpréteur même : une liaison compilée inattendue
        print(f"jedi : {e!r}", file=sys.stderr, flush=True)  # (PySide6 de Pyodide-Qt, dans la page) le fait tomber
        return []
    return [{"label": c.name, "insertText": c.name, "filterText": c.name, "kind": GENRES.get(c.type, 1), "detail": c.type,
             "documentation": "", "provider": "jedi", "sortText": ("z" if c.name.startswith("_") else "a") + c.name}
            for c in propositions]


if __name__ == "__main__":
    print(json.dumps({"pret": IMPORT_MS}), flush=True)
    for brute in sys.stdin:
        if not brute.strip():
            continue
        d = json.loads(brute)
        t = time.monotonic()
        items = completer(d["code"], d["ligne"], d["colonne"])
        print(json.dumps({"id": d["id"], "items": items, "ms": round((time.monotonic() - t) * 1000)}), flush=True)
