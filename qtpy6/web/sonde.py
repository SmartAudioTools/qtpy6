"""La page dans Firefox (ou Chromium) sans interface, pour vérifier une application sans écran ni clic : sert un dossier en local,
ouvre la page, attend qu'elle pose ``window.etat`` (l'état attendu, ou "erreur"), imprime son ``window.journal``, capture
l'écran, puis écrit chaque image de ``window.captures`` (``{suffixe: png_en_base64}`` : le ``grab()`` d'une fenêtre
Qt, par exemple) en ``<capture>_<suffixe>.png``. Le code de retour dit si l'état attendu a été atteint.

    python -m qtpy6.web.sonde page.html?param=x capture.png [--racine DIR] [--delai 120] [--etat fini]
                             [--taille 1000x900] [--zoom 2] [--tactile] [--visible] [--chromium]
                             [--glisser X1,Y1,X2,Y2]

``page`` est relative à ``--racine`` (le dossier de la page par défaut), servie par http.server : une page ouverte en
file:// n'a ni modules ni fetch. ``--taille`` : la fenêtre en pixels CSS (Firefox ne descend pas sous 500 de large : une
largeur de téléphone se mesure en natif hors écran, ou avec ``--zoom``) ; ``--zoom`` : le zoom du navigateur ou l'écran
HiDPI (``layout.css.devPixelsPerPx``, la capture en est multipliée) ; ``--tactile`` : un écran au doigt (le seul pointeur
est « coarse », ce que ``tactile.detecte`` voit, et les événements touch sont activés) ; ``--visible`` : une vraie fenêtre
sur l'écran, avec son compositeur et sa synchronisation verticale, pour mesurer la fluidité (hors écran, Firefox cadence
ses images seul). ``--glisser`` : une fois l'état atteint, un glissé souris réel (enfoncé en X1,Y1, dix déplacements,
relâché en X2,Y2, en pixels CSS de la fenêtre), puis la capture : un défaut de glisser-déposer propre à un navigateur.

Firefox par défaut, parce que Chromium n'ouvre pas sans socket Unix (son verrou d'instance unique,
``process_singleton_posix``), ce qu'un bac à sable peut interdire. ``--chromium`` passe par QtWebEngine, le même moteur
Blink sans ce verrou (Chrome 140 pour Qt 6.11) : un Python qui a ``PyQt6.QtWebEngineWidgets`` (celui de la sonde, sinon
``/usr/bin/python3``) ouvre la page hors écran, et la sonde la pilote par le protocole DevTools en TCP (websocket-client).
Ni zoom, ni tactile, ni fenêtre visible dans ce mode."""

import argparse
import base64
import http.server
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("page")
    a.add_argument("capture")
    a.add_argument("--racine", help="le dossier servi (celui de la page par défaut)")
    a.add_argument("--delai", type=float, default=120, help="secondes avant d'abandonner")
    a.add_argument("--etat", default="fini", help="la valeur de window.etat attendue")
    a.add_argument("--taille", default="1000x900")
    a.add_argument("--zoom")
    a.add_argument("--tactile", action="store_true")
    a.add_argument("--visible", action="store_true", help="une vraie fenêtre sur l'écran, pas hors écran")
    a.add_argument("--chromium", action="store_true", help="le moteur Blink de QtWebEngine au lieu de Firefox")
    a.add_argument("--glisser", help="X1,Y1,X2,Y2 : un glissé souris une fois l'état atteint")
    o = a.parse_args(argv)
    if o.chromium and (o.zoom or o.tactile or o.visible):
        a.error("--chromium : ni --zoom, ni --tactile, ni --visible")

    chemin, _, requete = o.page.partition("?")
    racine = Path(o.racine).resolve() if o.racine else Path(chemin).resolve().parent
    relatif = Path(chemin).resolve().relative_to(racine) if o.racine else Path(chemin).name

    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")  # comme GitHub Pages : un cadre isolé charge en CORS
            super().end_headers()

    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *args: Silencieux(*args, directory=str(racine)))
    threading.Thread(target=serveur.serve_forever, daemon=True).start()

    url = f"http://127.0.0.1:{serveur.server_port}/{relatif}{'?' + requete if requete else ''}"
    largeur, hauteur = o.taille.split("x")
    navigateur = Blink(url, int(largeur), int(hauteur)) if o.chromium else firefox(o, largeur, hauteur, url)
    try:
        debut = time.time()
        while time.time() - debut < o.delai:
            etat = navigateur.execute_script("return window.etat")
            if etat in (o.etat, "erreur"):
                break
            time.sleep(0.5)
        else:
            etat = "délai dépassé"
        if o.glisser and etat == o.etat:
            glisser(navigateur, *map(float, o.glisser.split(",")))
        print("\n".join(navigateur.execute_script("return window.journal || []")))
        print("état :", etat, "; fenêtre", *navigateur.execute_script("return [innerWidth, innerHeight, devicePixelRatio]"),
              "; tactile" if navigateur.execute_script("return matchMedia('(any-pointer: coarse)').matches") else "; souris",
              "; " + navigateur.execute_script("return navigator.userAgent").split(") ")[-1])
        navigateur.save_screenshot(o.capture)
        for suffixe, b64 in (navigateur.execute_script("return window.captures || {}") or {}).items():
            Path(o.capture).with_stem(Path(o.capture).stem + "_" + suffixe).write_bytes(base64.b64decode(b64))
    finally:
        navigateur.quit()
        serveur.shutdown()
    return etat == o.etat


def firefox(o, largeur, hauteur, url):
    from selenium import webdriver  # noqa: PLC0415 - la dépendance optionnelle [sonde]

    options = webdriver.FirefoxOptions()
    if not o.visible:
        options.add_argument("--headless")
    options.add_argument(f"--width={largeur}")
    options.add_argument(f"--height={hauteur}")
    if o.zoom:
        options.set_preference("layout.css.devPixelsPerPx", o.zoom)
    if o.tactile:
        for pref in ("ui.primaryPointerCapabilities", "ui.allPointerCapabilities"):
            options.set_preference(pref, 1)  # 1 = coarse, sans hover : ce que répondent les media queries pointer/any-pointer
        options.set_preference("dom.w3c_touch_events.enabled", 1)
    navigateur = webdriver.Firefox(options=options)
    navigateur.get(url)
    return navigateur


def glisser(navigateur, x1, y1, x2, y2, pas=10):
    """Enfoncé en (x1, y1), `pas` déplacements, relâché en (x2, y2) : de vrais événements souris du navigateur."""
    points = [(x1 + (x2 - x1) * k / pas, y1 + (y2 - y1) * k / pas) for k in range(1, pas + 1)]
    if isinstance(navigateur, Blink):
        souris = navigateur.cdp
        souris("Input.dispatchMouseEvent", type="mouseMoved", x=x1, y=y1)
        souris("Input.dispatchMouseEvent", type="mousePressed", x=x1, y=y1, button="left", buttons=1, clickCount=1)
        for x, y in points:
            souris("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y, button="left", buttons=1)
            time.sleep(0.03)
        souris("Input.dispatchMouseEvent", type="mouseReleased", x=x2, y=y2, button="left", buttons=0, clickCount=1)
    else:
        from selenium.webdriver.common.action_chains import ActionBuilder  # noqa: PLC0415

        actions = ActionBuilder(navigateur, duration=30)
        actions.pointer_action.move_to_location(x1, y1).pointer_down()
        for x, y in points:
            actions.pointer_action.move_to_location(round(x), round(y))
        actions.pointer_action.pointer_up()
        actions.perform()
    navigateur.execute_script("return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    time.sleep(0.3)  # Qt-WASM traite l'événement dans sa boucle, puis repeint : deux images et un peu plus


HOTE = """
import sys
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
app = QApplication(sys.argv[:1])
vue = QWebEngineView()
vue.resize(int(sys.argv[2]), int(sys.argv[3]))
vue.setUrl(QUrl(sys.argv[1]))
vue.show()
app.exec()
"""


class Blink:
    """La page dans QtWebEngine hors écran, pilotée par le protocole DevTools : les trois méthodes de Selenium dont la
    sonde se sert (execute_script, save_screenshot, quit), plus `cdp` pour le reste."""

    def __init__(self, url, largeur, hauteur):
        import websocket  # noqa: PLC0415 - websocket-client, la dépendance de Selenium

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        python = sys.executable if importlib.util.find_spec("PyQt6.QtWebEngineWidgets") else "/usr/bin/python3"
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QTWEBENGINE_DISABLE_SANDBOX="1",
                   QTWEBENGINE_CHROMIUM_FLAGS="--no-zygote --disable-gpu",  # le zygote et le GPU veulent des sockets
                   QTWEBENGINE_REMOTE_DEBUGGING=f"127.0.0.1:{port}")
        self.processus = subprocess.Popen([python, "-c", HOTE, url, str(largeur), str(hauteur)], env=env,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sans_mandataire = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(120):
            try:
                cibles = json.load(sans_mandataire.open(f"http://127.0.0.1:{port}/json"))
                page = next(c for c in cibles if c["type"] == "page")
                break
            except (OSError, StopIteration):
                if self.processus.poll() is not None:
                    raise RuntimeError(f"{python} : QtWebEngine n'a pas démarré (PyQt6-WebEngine installé ?)") from None
                time.sleep(0.5)
        else:
            raise RuntimeError("QtWebEngine : pas de page DevTools en 60 s")
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], suppress_origin=True)
        self.n = 0

    def cdp(self, methode, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": methode, "params": params}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.n:
                if "error" in r:
                    raise RuntimeError(f"{methode} : {r['error']}")
                return r["result"]

    def execute_script(self, code):
        r = self.cdp("Runtime.evaluate", expression=f"(async () => {{ {code} }})()", awaitPromise=True,
                     returnByValue=True)
        return r["result"].get("value")

    def save_screenshot(self, chemin):
        Path(chemin).write_bytes(base64.b64decode(self.cdp("Page.captureScreenshot", format="png")["data"]))

    def quit(self):
        self.ws.close()
        self.processus.terminate()
        self.processus.wait()


if __name__ == "__main__":
    sys.exit(not main())
