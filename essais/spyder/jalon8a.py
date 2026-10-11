"""Jalon 8a du portage de SmartPythonEditor dans le navigateur (notes/2026-10-11 - Doublure zmq, plan.md) : preuve de
voie du noyau. Le vrai noyau de Spyder (`spyder_kernels.console`) lancé par le chemin de Spyder lui-même
(`KernelHandler.new_from_spec`, donc `SpyderKernelManager.start_kernel` → `subprocess.Popen`), puis interrogé par un
client bloquant du gestionnaire (jupyter_client) : `kernel_info_reply`, `execute` → un `stream` stdout et `execute_result` « 2 », temps au
premier message, mémoire, arrêt. Le même script sur le bureau (offscreen) et dans la page (construire_site.py, sonde) ;
seule l'instrumentation (témoin d'état de la page, mémoire) sait où elle tourne. Configuration de Spyder dans un dossier
jetable (SPYDER_CONFDIR), fichiers de connexion aussi (JUPYTER_RUNTIME_DIR). État de la page : « jalon8a » pendant le travail, « fini » à la fin, « erreur » sinon."""

import os
import sys
import tempfile
import time
import traceback

os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="jalon8a-")
os.environ["JUPYTER_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="jalon8a-runtime-")  # fichiers de connexion
from preparer import T0, etape  # noqa: E402

WEB = sys.platform == "emscripten"
if WEB:
    import js  # noqa: E402 - instrumentation : témoin de phase
    js.window.etat = "jalon8a"
    from qtpy6.web import travailleur  # noqa: E402 - le Pyodide-Qt du site pour le Worker (sans réseau dans la sonde)
    travailleur.configurer("./pyodide-qt/")
DELAI = 120  # s : démarrage du noyau (à froid dans un Worker : chargement de Pyodide et des roues)


def memoire():
    """Mio du tas wasm de la page, RSS sur le bureau (instrumentation ; le Worker n'est pas compté)."""
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


def reponses(client, msg_id):
    """Les messages iopub de la requête `msg_id`, jusqu'au statut « idle »."""
    vus = []
    while True:
        msg = client.get_iopub_msg(timeout=DELAI)
        if msg["parent_header"].get("msg_id") != msg_id:
            continue
        vus.append(msg)
        if msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle":
            return vus


verdicts = {}  # contrôle → (bon, détail)
handler = None
try:
    from qtpy6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)  # les StdThread de KernelHandler sont des QThread
    from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler
    from spyder.plugins.ipythonconsole.utils.kernelspec import SpyderKernelSpec
    etape("imports")
    m0 = memoire()

    t = time.monotonic()
    handler = KernelHandler.new_from_spec(SpyderKernelSpec())
    etape("noyau lancé (Popen)")
    for fil, nom in ((handler._stdout_thread, "stdout"), (handler._stderr_thread, "stderr")):  # au fil de l'eau : journal
        if fil is not None:  # (et console de la sonde) même si la page gèle ensuite
            fil.sig_out.connect(lambda texte, nom=nom: print(f"[noyau {nom}] {texte.rstrip()}"))
    verdicts["lancement"] = (True, f"{time.monotonic() - t:.2f} s, pid {handler.kernel_manager.provisioner.process.pid}")

    # Le client bloquant du gestionnaire : sa vie se juge sur le processus (poll), pas sur le battement de cœur, dont
    # le premier relevé tombe avant le premier battement quand le client vit hors du gestionnaire (« Kernel died »).
    client = handler.kernel_manager.blocking_client()
    client.start_channels()
    t = time.monotonic()
    client.wait_for_ready(timeout=DELAI)  # kernel_info jusqu'à la première réponse
    verdicts["premier message"] = (True, f"{time.monotonic() - t:.2f} s après start_channels")
    etape("noyau prêt")

    msg_id = client.kernel_info()
    info = client.get_shell_msg(timeout=DELAI)
    while info["parent_header"].get("msg_id") != msg_id:
        info = client.get_shell_msg(timeout=DELAI)
    verdicts["kernel_info_reply"] = (info["msg_type"] == "kernel_info_reply" and info["content"]["status"] == "ok",
                                     f"{info['content'].get('implementation')} "
                                     f"{info['content'].get('language_info', {}).get('version')}")

    t = time.monotonic()
    msg_id = client.execute("print('bonjour'); 1+1")
    vus = reponses(client, msg_id)
    flux = "".join(m["content"]["text"] for m in vus
                   if m["msg_type"] == "stream" and m["content"]["name"] == "stdout")
    resultat = [m["content"]["data"]["text/plain"] for m in vus if m["msg_type"] == "execute_result"]
    verdicts["stream stdout"] = (flux == "bonjour\n", repr(flux))
    verdicts["execute_result"] = (resultat == ["2"], f"{resultat!r}, {time.monotonic() - t:.2f} s")
    etape("execute")
    client.stop_channels()

    processus = handler.kernel_manager.provisioner.process
    t = time.monotonic()
    handler.kernel_manager.shutdown_kernel(now=False)
    verdicts["arrêt"] = (processus.poll() is not None, f"code {processus.poll()}, {time.monotonic() - t:.2f} s")
    handler.close_std_threads()
    etape("arrêt")

    for nom, (bon, detail) in verdicts.items():
        print(f"  {nom:18} {'passe' if bon else 'CASSE':6} {detail}")
    print(f"verdicts : {sum(b for b, _ in verdicts.values())}/{len(verdicts)} passent ; "
          f"mémoire {m0:.0f} → {memoire():.0f} Mio, {time.monotonic() - T0:.1f} s")
    fin("fini" if all(b for b, _ in verdicts.values()) else "erreur")
except Exception:
    traceback.print_exc()
    for nom, (bon, detail) in verdicts.items():
        print(f"  {nom:18} {'passe' if bon else 'CASSE':6} {detail}")
    if handler is not None:
        processus = handler.kernel_manager.provisioner.process
        if processus is not None:  # ce qu'il a écrit : les StdThread de Spyder l'ont lu dans _init_stdout/_init_stderr
            print(f"noyau {'vivant' if processus.poll() is None else f'mort (code {processus.returncode})'} ; "
                  f"stdout :\n{handler._init_stdout}\nstderr :\n{handler._init_stderr}")
        try:
            handler.kernel_manager.shutdown_kernel(now=True)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    fin("erreur")
    raise
