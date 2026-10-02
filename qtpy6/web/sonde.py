"""La page dans Firefox sans interface, pour vérifier une application sans écran ni clic : sert un dossier en local,
ouvre la page, attend qu'elle pose ``window.etat`` (l'état attendu, ou "erreur"), imprime son ``window.journal``, capture
l'écran, puis écrit chaque image de ``window.captures`` (``{suffixe: png_en_base64}`` : le ``grab()`` d'une fenêtre
Qt, par exemple) en ``<capture>_<suffixe>.png``. Le code de retour dit si l'état attendu a été atteint.

    python -m qtpy6.web.sonde page.html?param=x capture.png [--racine DIR] [--delai 120] [--etat fini]
                             [--taille 1000x900] [--zoom 2] [--tactile] [--visible]

``page`` est relative à ``--racine`` (le dossier de la page par défaut), servie par http.server : une page ouverte en
file:// n'a ni modules ni fetch. ``--taille`` : la fenêtre en pixels CSS (Firefox ne descend pas sous 500 de large : une
largeur de téléphone se mesure en natif hors écran, ou avec ``--zoom``) ; ``--zoom`` : le zoom du navigateur ou l'écran
HiDPI (``layout.css.devPixelsPerPx``, la capture en est multipliée) ; ``--tactile`` : un écran au doigt (le seul pointeur
est « coarse », ce que ``tactile.detecte`` voit, et les événements touch sont activés) ; ``--visible`` : une vraie fenêtre
sur l'écran, avec son compositeur et sa synchronisation verticale, pour mesurer la fluidité (hors écran, Firefox cadence
ses images seul). Firefox parce que Chromium
n'ouvre pas sans socket Unix, ce qu'un bac à sable peut interdire."""

import argparse
import base64
import http.server
import sys
import threading
import time
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
    o = a.parse_args(argv)
    from selenium import webdriver  # noqa: PLC0415 - la dépendance optionnelle [sonde]

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

    options = webdriver.FirefoxOptions()
    if not o.visible:
        options.add_argument("--headless")
    largeur, hauteur = o.taille.split("x")
    options.add_argument(f"--width={largeur}")
    options.add_argument(f"--height={hauteur}")
    if o.zoom:
        options.set_preference("layout.css.devPixelsPerPx", o.zoom)
    if o.tactile:
        for pref in ("ui.primaryPointerCapabilities", "ui.allPointerCapabilities"):
            options.set_preference(pref, 1)  # 1 = coarse, sans hover : ce que répondent les media queries pointer/any-pointer
        options.set_preference("dom.w3c_touch_events.enabled", 1)
    navigateur = webdriver.Firefox(options=options)
    try:
        navigateur.get(f"http://127.0.0.1:{serveur.server_port}/{relatif}{'?' + requete if requete else ''}")
        debut = time.time()
        while time.time() - debut < o.delai:
            etat = navigateur.execute_script("return window.etat")
            if etat in (o.etat, "erreur"):
                break
            time.sleep(0.5)
        else:
            etat = "délai dépassé"
        print("\n".join(navigateur.execute_script("return window.journal || []")))
        print("état :", etat, "; fenêtre", *navigateur.execute_script("return [innerWidth, innerHeight, devicePixelRatio]"),
              "; tactile" if navigateur.execute_script("return matchMedia('(any-pointer: coarse)').matches") else "; souris")
        navigateur.save_screenshot(o.capture)
        for suffixe, b64 in (navigateur.execute_script("return window.captures || {}") or {}).items():
            Path(o.capture).with_stem(Path(o.capture).stem + "_" + suffixe).write_bytes(base64.b64decode(b64))
    finally:
        navigateur.quit()
        serveur.shutdown()
    return etat == o.etat


if __name__ == "__main__":
    sys.exit(not main())
