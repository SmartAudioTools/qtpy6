"""Jalon 8b du portage de SmartPythonEditor dans le navigateur (notes/2026-10-11 - Doublure zmq, plan.md) : ce que
Spyder suppose du noyau, au-delà de la preuve de voie (jalon8a.py). Le noyau lancé par `KernelHandler.new_from_spec`
comme dans Spyder, puis :
- le comm de Spyder (`KernelComm.open_comm`, ouvert par le KernelHandler) : « comm_ready » reçu (l'état
  « SpyderKernelReady » attend en plus le kernel_info que demande la console, absente ici), et un appel distant
  bloquant (`get_syspath`, un des `@comm_handler` du noyau) ;
- le battement de cœur pendant un calcul de 3 s qui ne rend jamais la main (`while`) : ni le client Qt de Spyder ni un
  client bloquant ne doivent le croire mort ;
- `input()` : `input_request` sur le canal stdin, réponse du client ;
- deux noyaux en même temps, chacun ses variables ;
- l'interruption (`interrupt_kernel`) d'un calcul en cours, puis le redémarrage (`restart_kernel`) : le noyau répond
  ensuite, ses variables oubliées.
Le même script sur le bureau (offscreen) et dans la page (construire_site.py, sonde). État de la page : « jalon8b »
pendant le travail, « fini » à la fin, « erreur » sinon."""

import os
import queue
import sys
import tempfile
import time
import traceback

os.environ["SPYDER_CONFDIR"] = tempfile.mkdtemp(prefix="jalon8b-")
os.environ["JUPYTER_RUNTIME_DIR"] = tempfile.mkdtemp(prefix="jalon8b-runtime-")  # fichiers de connexion
from preparer import T0, etape  # noqa: E402

WEB = sys.platform == "emscripten"
if WEB:
    import js  # noqa: E402 - instrumentation : témoin de phase
    js.window.etat = "jalon8b"
    from qtpy6.web import travailleur  # noqa: E402 - le Pyodide-Qt du site pour le Worker (sans réseau dans la sonde)
    travailleur.configurer("./pyodide-qt/")
DELAI = 120  # s : démarrage du noyau (à froid dans un Worker : chargement de Pyodide et des roues)


def fin(etat):
    if WEB:
        js.window.etat = etat


def attendre_signal(signal, delai, fait=lambda: False):
    """Tourne la boucle Qt jusqu'au signal (ou `fait()`), au plus `delai` secondes."""
    from qtpy6.QtCore import QEventLoop, QTimer
    if fait():
        return
    boucle = QEventLoop()
    signal.connect(boucle.quit)
    QTimer.singleShot(int(delai * 1000), boucle.quit)
    boucle.exec()
    signal.disconnect(boucle.quit)


def reponses(client, msg_id, pendant=None):
    """Les messages iopub de la requête `msg_id`, jusqu'au statut « idle » ; `pendant()` appelé à chaque attente."""
    vus, limite = [], time.monotonic() + DELAI
    while time.monotonic() < limite:
        try:
            msg = client.get_iopub_msg(timeout=0.25)
        except queue.Empty:
            if pendant:
                pendant()
            continue
        if msg["parent_header"].get("msg_id") != msg_id:
            continue
        vus.append(msg)
        if msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle":
            return vus
    raise TimeoutError(f"pas de statut idle pour {msg_id}")


def executer(client, code, **k):
    """(texte de stdout, résultats text/plain, erreurs) d'une exécution."""
    vus = reponses(client, client.execute(code, **k))
    return ("".join(m["content"]["text"] for m in vus if m["msg_type"] == "stream" and m["content"]["name"] == "stdout"),
            [m["content"]["data"]["text/plain"] for m in vus if m["msg_type"] == "execute_result"],
            [m["content"]["ename"] for m in vus if m["msg_type"] == "error"])


def lancer():
    """Un noyau comme Spyder le lance, prêt (comm ouvert), et un client bloquant de son gestionnaire."""
    handler = KernelHandler.new_from_spec(SpyderKernelSpec())
    for fil, nom in ((handler._stdout_thread, "stdout"), (handler._stderr_thread, "stderr")):
        if fil is not None:  # journal au fil de l'eau, même si la page gèle ensuite
            fil.sig_out.connect(lambda texte, nom=nom: print(f"[noyau {nom}] {texte.rstrip()}"))
    handlers.append(handler)
    attendre_signal(handler.kernel_comm.sig_comm_ready, DELAI, lambda: handler._comm_ready_received)
    client = handler.kernel_manager.blocking_client()
    client.start_channels()
    client.wait_for_ready(timeout=DELAI)
    return handler, client


class Verdicts(dict):
    """contrôle → (bon, détail), imprimé dès qu'il est posé : la page peut geler ensuite."""

    def __setitem__(self, nom, verdict):
        super().__setitem__(nom, verdict)
        print(f"  {nom:24} {'passe' if verdict[0] else 'CASSE':6} {verdict[1]}")


verdicts = Verdicts()
handlers = []
try:
    from qtpy6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)  # les StdThread de KernelHandler sont des QThread
    from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler
    from spyder.plugins.ipythonconsole.utils.kernelspec import SpyderKernelSpec
    etape("imports")

    t = time.monotonic()
    handler, client = lancer()
    verdicts["comm Spyder"] = (handler._comm_ready_received, f"comm_ready {handler._comm_ready_received}, "
                                                              f"{time.monotonic() - t:.2f} s")
    etape("noyau 1 prêt")
    try:
        chemins = handler.kernel_comm.remote_call(blocking=True, timeout=DELAI).get_syspath()
    except Exception as e:  # noqa: BLE001
        chemins = e
    verdicts["appel distant"] = (isinstance(chemins, list) and bool(chemins),
                                 f"get_syspath → {len(chemins) if isinstance(chemins, list) else chemins!r}")
    etape("appel distant")

    # Battement de cœur : le client Qt de Spyder (hb_channel du KernelHandler) et le client bloquant, relevés pendant
    # un calcul qui ne rend jamais la main.
    morts = []
    handler.kernel_client.hb_channel.kernel_died.connect(lambda depuis: morts.append(depuis))
    releves = []
    t = time.monotonic()
    vus = reponses(client, client.execute("import time\nt = time.time()\nwhile time.time() - t < 3: pass\n'fini'"),
                   lambda: releves.append((client.hb_channel.is_beating(), handler.kernel_client.hb_channel.is_beating())))
    verdicts["battement (calcul 3 s)"] = (all(a and b for a, b in releves) and not morts and len(releves) >= 6,
                                          f"{len(releves)} relevés, {sum(not (a and b) for a, b in releves)} arrêtés, "
                                          f"kernel_died {len(morts)}, {time.monotonic() - t:.1f} s")
    etape("battement")

    # input() : le noyau demande sur stdin, le client répond.
    msg_id = client.execute("x = input('nom ? ')", allow_stdin=True)
    try:
        demande = client.get_stdin_msg(timeout=DELAI)
        invite = demande["content"].get("prompt")
        client.input("Ada")
        reponses(client, msg_id)
        sortie, _, erreurs = executer(client, "print(x)")
    except Exception as e:  # noqa: BLE001
        invite, sortie, erreurs = None, repr(e), []
    verdicts["input()"] = (invite == "nom ? " and sortie == "Ada\n" and not erreurs, f"{invite!r} → {sortie!r} {erreurs}")
    etape("input")

    # Deux noyaux : le second ne voit pas les variables du premier.
    t = time.monotonic()
    handler2, client2 = lancer()
    _, resultat2, _ = executer(client2, "'x' in dir(), 1+2")
    _, resultat1, _ = executer(client, "'x' in dir()")
    verdicts["deux noyaux"] = (resultat2 == ["(False, 3)"] and resultat1 == ["True"],
                               f"noyau 2 {resultat2}, noyau 1 {resultat1}, {time.monotonic() - t:.2f} s")
    etape("deux noyaux")

    # Interruption d'un calcul en cours, comme le bouton de Spyder sur un noyau local (signal SIGINT).
    t = time.monotonic()
    msg_id = client.execute("import time\nwhile True: time.sleep(0.05)")
    time.sleep(1)
    handler.kernel_manager.interrupt_kernel()
    try:
        vus = reponses(client, msg_id)
        erreurs = [m["content"]["ename"] for m in vus if m["msg_type"] == "error"]
    except Exception as e:  # noqa: BLE001
        erreurs = [repr(e)]
    vivant = handler.kernel_manager.is_alive()
    verdicts["interruption"] = (erreurs == ["KeyboardInterrupt"] and vivant,
                                f"{erreurs}, noyau {'vivant' if vivant else 'mort'}, {time.monotonic() - t:.2f} s")
    etape("interruption")

    # Redémarrage : nouveau processus, mêmes ports, variables oubliées.
    t = time.monotonic()
    pid = handler.kernel_manager.provisioner.process.pid
    handler.kernel_manager.restart_kernel(now=True)
    client.wait_for_ready(timeout=DELAI)
    _, resultat, _ = executer(client, "'x' in dir(), 1+1")
    pid2 = handler.kernel_manager.provisioner.process.pid
    verdicts["redémarrage"] = (resultat == ["(False, 2)"] and pid2 != pid,
                               f"{resultat}, pid {pid} → {pid2}, {time.monotonic() - t:.2f} s")
    etape("redémarrage")

    for c in (client, client2):
        c.stop_channels()
    for h in handlers:
        h.kernel_manager.shutdown_kernel(now=True)
        h.close()
    etape("arrêt")

    for nom, (bon, detail) in verdicts.items():
        print(f"  {nom:24} {'passe' if bon else 'CASSE':6} {detail}")
    print(f"verdicts : {sum(b for b, _ in verdicts.values())}/{len(verdicts)} passent ; {time.monotonic() - T0:.1f} s")
    fin("fini" if all(b for b, _ in verdicts.values()) else "erreur")
except Exception:
    traceback.print_exc()
    for nom, (bon, detail) in verdicts.items():
        print(f"  {nom:24} {'passe' if bon else 'CASSE':6} {detail}")
    for h in handlers:
        try:
            h.kernel_manager.shutdown_kernel(now=True)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    fin("erreur")
    raise
