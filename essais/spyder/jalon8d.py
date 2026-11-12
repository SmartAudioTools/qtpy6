"""Jalon 8d du portage de SmartPythonEditor dans le navigateur (notes/2026-10-11 - Doublure zmq, plan.md, « Compléments » :
« je souhaite le couvrir ») : le client LSP de Spyder (`LSPClient`, plugins/completion/providers/languageserver/client.py)
tel quel. Il lance pylsp (`python -m pylsp --tcp`, QProcess) et sa passerelle (`transport/main.py`, QProcess, TCP vers
pylsp, sockets zmq PAIR vers le client), puis lit le FD zmq par un `QSocketNotifier`. Étapes : initialize, diagnostic d'un
document ouvert, complétion `os.pa` → `path`, arrêt. Le même script sur le bureau (offscreen) et dans la page
(construire_site.py, sonde) ; seule l'instrumentation (témoin d'état de la page, mémoire) sait où elle tourne.
État de la page : « jalon8d » pendant le travail, « fini » à la fin, « erreur » sinon."""

import os
import sys
import tempfile
import time
import traceback

os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="jalon8d-")
# Les enfants (pylsp, passerelle) importent spyder et pylsp : pylsp n'est pas dans le Python des essais, on prend les
# paquets purs de l'environnement installé de SmartPythonEditor (liens dans un dossier jetable, pour ne pas masquer le
# reste de son site). Dans la page, ce dossier n'existe pas : le site embarque les paquets (construire_site.py).
_SITE_SPE = "/DATA/Python/SmartPython/CachyOS/versions/SmartPythonEditor-6.1.5/lib/python3.12/site-packages"
_liens = tempfile.mkdtemp(prefix="jalon8d-pylsp-")
# Avec les dist-info : pylsp charge ses greffons (pyflakes, jedi_completion…) par les points d'entrée « pylsp » de
# python_lsp_server-*.dist-info (pylsp/config/config.py:90, load_setuptools_entrypoints) ; sans eux, aucun greffon,
# diagnostics et complétions vides.
import glob  # noqa: E402
for _nom in ("pylsp", "pylsp_jsonrpc", "pluggy", "docstring_to_markdown") + tuple(
        os.path.basename(d) for d in glob.glob(os.path.join(_SITE_SPE, "python_lsp_server-*.dist-info"))):
    if os.path.isdir(os.path.join(_SITE_SPE, _nom)):
        os.symlink(os.path.join(_SITE_SPE, _nom), os.path.join(_liens, _nom))
os.environ["PYTHONPATH"] = os.pathsep.join(["/DATA/Python/FORKS/SmartPythonEditor", _liens])
from preparer import T0, etape  # noqa: E402

WEB = sys.platform == "emscripten"
if WEB:
    import js  # noqa: E402 - instrumentation : témoin de phase
    js.window.etat = "jalon8d"
    from qtpy6.web import travailleur  # noqa: E402 - le Pyodide-Qt du site pour les Workers (sans réseau dans la sonde)
    travailleur.configurer("./pyodide-qt/")
DELAI = 180  # s : pylsp et la passerelle démarrent à froid (deux Workers, jedi)
SOURCE = "import os\nos.pa\nx = (\n"  # ligne 1 : complétion ; ligne 2 : erreur de syntaxe


def memoire():
    """Mio du tas wasm de la page, RSS sur le bureau (instrumentation ; les Workers ne sont pas comptés)."""
    if WEB:
        import pyodide_js
        return pyodide_js._module.HEAPU8.length / 1048576
    with open("/proc/self/status") as f:
        for ligne in f:
            if ligne.startswith("VmRSS:"):
                return int(ligne.split()[1]) / 1024


def fin(etat):
    if WEB:
        js.window.etat = etat


verdicts = {}  # contrôle → (bon, détail)


def verdict(nom, bon, detail=""):
    """Imprimé dès qu'il est posé : la page peut geler à l'étape suivante."""
    verdicts[nom] = (bool(bon), detail)
    print(f"8d {'passe' if bon else 'CASSE'} : {nom} {detail} ({time.monotonic() - T0:.1f} s)", flush=True)


client = None
try:
    from qtpy6.QtCore import QEventLoop, QObject, QTimer
    from qtpy6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    def attendre(condition, delai=DELAI):
        """Fait tourner la boucle Qt jusqu'à `condition()` ou `delai` secondes ; rend `condition()`."""
        boucle, minuterie, debut = QEventLoop(), QTimer(), time.monotonic()

        def regarder():
            if condition() or time.monotonic() - debut > delai:
                boucle.quit()
        minuterie.timeout.connect(regarder)
        minuterie.start(50)
        if not condition():
            boucle.exec()
        minuterie.stop()
        return condition()

    etape("import du client LSP")
    from spyder.plugins.completion.api import CompletionRequestTypes as R
    from spyder.plugins.completion.providers.languageserver.client import LSPClient

    class Gestionnaire(QObject):
        """Ce que le fournisseur LSP de Spyder est pour le client : son parent, rien n'y est appelé."""

    class Editeur:
        """Ce que `CodeEditor` est pour le client : le destinataire des réponses d'un document."""
        def __init__(self):
            self.recus = {}

        def handle_response(self, methode, params):
            self.recus[methode] = params

    dossier = tempfile.mkdtemp(prefix="jalon8d-projet-")
    fichier = os.path.join(dossier, "essai.py")
    with open(fichier, "w") as f:
        f.write(SOURCE)
    reglages = {  # ceux que `generate_python_config` (provider.py) donne par défaut
        "cmd": "pylsp", "args": "--host {host} --port {port} --tcp --check-parent-process",
        "host": "127.0.0.1", "port": 2087, "external": False, "stdio": False, "configurations": {},
    }
    capacites = []
    m0, t = memoire(), time.monotonic()
    client = LSPClient(Gestionnaire(), reglages, folder=dossier, language="python")
    client.sig_initialize.connect(lambda caps, langue: capacites.append(caps))
    client.start()
    for _nom, _p in (("serveur", client.server), ("passerelle", client.transport)):  # instrumentation : leurs sorties
        for _canal in ("Output", "Error"):
            getattr(_p, f"readyReadStandard{_canal}").connect(
                lambda n=_nom, p=_p, c=_canal: print(f"8d [{n}] " + bytes(getattr(p, f"readAllStandard{c}")()).decode(
                    errors="replace").rstrip()[-2000:], flush=True))
    verdict("lancement", client.transport is not None and client.server is not None,
            f"serveur {client.server_args[:4]}")

    etape("initialize")
    ok = attendre(lambda: client.initialized)
    verdict("initialize", ok, f"en {time.monotonic() - t:.1f} s, capacités : {sorted(capacites[0])[:4] if capacites else None}")
    if not ok:  # instrumentation : l'état des deux processus
        print(f"8d états : serveur {client.server.state()}, passerelle {client.transport.state()}", flush=True)
    if ok:
        client.send_configurations({})  # le fournisseur l'envoie après sig_initialize (provider.py)

        etape("diagnostic")
        editeur = Editeur()
        client.perform_request(R.DOCUMENT_DID_OPEN, {
            "file": fichier, "language": "python", "version": 1, "text": SOURCE, "codeeditor": editeur,
            "requires_response": False})
        ok = attendre(lambda: editeur.recus.get(R.DOCUMENT_PUBLISH_DIAGNOSTICS), 60)
        diags = (editeur.recus.get(R.DOCUMENT_PUBLISH_DIAGNOSTICS) or {}).get("params") or []
        verdict("diagnostic", ok and any(d["range"]["start"]["line"] >= 2 for d in diags),
                f"{[(d['range']['start']['line'], d['message'][:30]) for d in diags][:3]}")

        etape("complétion")
        reponses = []
        t = time.monotonic()
        client.perform_request(R.DOCUMENT_COMPLETION, {
            "file": fichier, "line": 1, "column": 5, "offset": len("import os\nos.pa"),
            "selection_start": 0, "selection_end": 0, "current_word": "pa",
            "requires_response": True, "response_callback": lambda req, rep: reponses.append(rep)})
        ok = attendre(lambda: reponses, 60)
        etiquettes = [c.get("label") for c in (reponses[0].get("params") or [])] if ok else []
        verdict("complétion", "path" in etiquettes, f"en {time.monotonic() - t:.2f} s, {etiquettes[:5]}")

    etape("arrêt")
    t = time.monotonic()
    client.stop()
    arretes = attendre(lambda: not client.is_transport_alive() and not client.is_server_alive(), 10)
    verdict("arrêt", arretes, f"en {time.monotonic() - t:.2f} s")
    client = None
    print(f"8d mémoire : {m0:.0f} → {memoire():.0f} Mio", flush=True)
except Exception:
    traceback.print_exc()
    verdict("exception", False, traceback.format_exc().splitlines()[-1])
finally:
    if client is not None:
        try:
            client.stop()
        except Exception:
            pass

bons = sum(bon for bon, _ in verdicts.values())
print(f"8d bilan : {bons}/{len(verdicts)} en {time.monotonic() - T0:.1f} s", flush=True)
fin("fini" if bons == len(verdicts) else "erreur")
