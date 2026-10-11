"""Essai page : une connexion WebSocket RÉELLE depuis le navigateur (point ouvert de notes/2026-10-10 - Modules Qt à la
demande.md : seule l'erreur sur un port fermé avait été vue). QtWebSockets importé depuis un slot, QWebSocket ouvert sur
le serveur d'écho de `serveur.py` (127.0.0.1:8765), un message texte puis un binaire envoyés, leurs échos attendus, puis
fermeture. Verdict « VERDICT websocket : OK/ECHEC <détail> » ; état de la page « essai_fini ».

    $P serveur.py 8765 300 > serveur.log 2>&1 &
    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "WebSocket : écho"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 90 --etat essai_fini > sonde.log 2>&1
"""

import sys
import time

from qtpy6 import QtCore, QtWidgets
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
TEXTE, BINAIRE = "bonjour é ✓", bytes([0, 1, 127, 128, 255])

app = application()
journal = QtWidgets.QLabel("…")
journal.setWordWrap(True)
journal.resize(520, 300)
journal.show()
ACTIFS, EVENEMENTS, ECHOS = [], [], {}


def note(texte):
    print(texte)
    journal.setText(journal.text() + "\n" + texte)


def verdict(ok, detail):
    note(f"VERDICT websocket : {'OK' if ok else 'ECHEC'} {detail} ({time.monotonic() - T0:.2f} s)")
    if WEB:
        js.window.etat = "essai_fini"


def essai():
    t = time.monotonic()
    from PySide6 import QtWebSockets
    note(f"import QtWebSockets : {time.monotonic() - t:.2f} s")
    ws = QtWebSockets.QWebSocket()
    ACTIFS.append(ws)
    ws.stateChanged.connect(lambda s: EVENEMENTS.append(f"état {s.name}"))
    ws.errorOccurred.connect(lambda e: EVENEMENTS.append(f"erreur {e.name} {ws.errorString()!r}"))

    def connecte():
        EVENEMENTS.append("connecté")
        ws.sendTextMessage(TEXTE)
        ws.sendBinaryMessage(QtCore.QByteArray(BINAIRE))

    def recu(cle, valeur):
        ECHOS[cle] = valeur
        if len(ECHOS) == 2:
            ws.close()

    ws.connected.connect(connecte)
    ws.textMessageReceived.connect(lambda m: recu("texte", m))
    ws.binaryMessageReceived.connect(lambda m: recu("binaire", bytes(m)))
    ws.disconnected.connect(lambda: EVENEMENTS.append("déconnecté"))
    ws.open(QtCore.QUrl("ws://127.0.0.1:8765/essai"))

    def fin():
        ok = ECHOS.get("texte") == TEXTE and ECHOS.get("binaire") == BINAIRE and "déconnecté" in EVENEMENTS
        verdict(ok, f"échos={ECHOS}, événements={EVENEMENTS}")
    QtCore.QTimer.singleShot(4000, fin)


QtCore.QTimer.singleShot(300, essai)
app.exec()
