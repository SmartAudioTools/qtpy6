"""Essai page : la doublure ``QWebEngineView`` de qtpy6 (``qtpy6/web/moteur_web.py``), seule, hors de Spyder.
Une page posée par ``setHtml`` (titre, image locale en MEMFS devenue ``blob:``), un clic sur un lien local intercepté par
``acceptNavigationRequest`` puis suivi, retour arrière, ``findText``, ``SelectAll`` + ``selectedText``, ``toPlainText``,
``runJavaScript`` et ``setZoomFactor``. Verdict « VERDICT moteur_web : OK/ECHEC <détail> » ; état « essai_fini ».

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "Moteur web : doublure"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 90 --etat essai_fini > sonde.log 2>&1
"""

import base64
import os
import sys
import tempfile
import time

from qtpy6 import QtCore, QtWidgets
from qtpy6.QtWebEngineCore import QWebEnginePage
from qtpy6.QtWebEngineWidgets import QWebEngineView
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==")
DOSSIER = tempfile.mkdtemp()
with open(os.path.join(DOSSIER, "point.png"), "wb") as f:
    f.write(PNG)
with open(os.path.join(DOSSIER, "suite.html"), "w", encoding="utf-8") as f:
    f.write("<html><head><title>Suite</title></head><body><p>Deuxième page</p></body></html>")
ACCUEIL = ("<html><head><title>Accueil</title></head><body><p id=t>Bonjour le monde, bonjour Qt</p>"
           "<img id=i src='point.png'><a id=l href='suite.html'>suite</a></body></html>")


class Page(QWebEnginePage):
    def __init__(self, *args):
        super().__init__(*args)
        self.demandes = []

    def acceptNavigationRequest(self, url, type_, isMainFrame):
        self.demandes.append((url.fileName(), type_ == self.NavigationType.NavigationTypeLinkClicked))
        return True


app = application()
fenetre = QtWidgets.QWidget()
disposition = QtWidgets.QVBoxLayout(fenetre)
journal = QtWidgets.QLabel("…")
journal.setWordWrap(True)
vue = QWebEngineView()
page = Page(vue)
vue.setPage(page)
disposition.addWidget(journal)
disposition.addWidget(vue, 1)
fenetre.resize(600, 400)
fenetre.show()
FINIS, TITRES, RELEVES = [], [], {}
vue.loadFinished.connect(FINIS.append)
vue.titleChanged.connect(TITRES.append)


def note(texte):
    print(texte)
    journal.setText(journal.text() + "\n" + texte)


def verdict(ok, detail):
    note(f"VERDICT moteur_web : {'OK' if ok else 'ECHEC'} {detail} ({time.monotonic() - T0:.2f} s)")
    if WEB:
        js.window.etat = "essai_fini"


def apres(ms, f):
    QtCore.QTimer.singleShot(ms, f)


def etape1():
    vue.setHtml(ACCUEIL, QtCore.QUrl.fromLocalFile(os.path.join(DOSSIER, "accueil.html")))
    apres(800, etape2)


def etape2():
    page.toPlainText(lambda t: RELEVES.__setitem__("texte", t.split(chr(10))[0]))
    page.runJavaScript("document.getElementById('i').naturalWidth + ' ' + document.getElementById('i').src.slice(0, 5)",
                       lambda r: RELEVES.__setitem__("image", r))
    vue.findText("bonjour")
    RELEVES["trouvé"] = vue.selectedText()
    vue.triggerPageAction(QWebEnginePage.WebAction.SelectAll)
    RELEVES["tout"] = vue.selectedText().strip()[:13]
    vue.setZoomFactor(1.5)
    page.runJavaScript("document.documentElement.style.zoom", lambda r: RELEVES.__setitem__("zoom", r))
    RELEVES["géométrie"] = vue.width() > 0 and vue.height() > 0
    page.runJavaScript("document.getElementById('l').click()")
    apres(800, etape3)


def etape3():
    RELEVES["après clic"] = (vue.title(), vue.url().fileName())
    vue.back()
    apres(800, fin)


def fin():
    RELEVES["après retour"] = vue.title()
    attendu = {
        "texte": "Bonjour le monde, bonjour Qt",
        "image": "1 blob:",
        "trouvé": "Bonjour",
        "tout": "Bonjour le mo",
        "zoom": "1.5",
        "géométrie": True,
        "après clic": ("Suite", "suite.html"),
        "après retour": "Accueil",
    }
    ecarts = {k: (RELEVES.get(k), v) for k, v in attendu.items() if RELEVES.get(k) != v}
    ok = (not ecarts and page.demandes == [("suite.html", True)] and FINIS[:3] == [True, True, True]
          and TITRES[:3] == ["Accueil", "Suite", "Accueil"])
    verdict(ok, f"écarts={ecarts}, demandes={page.demandes}, loadFinished={FINIS}, titres={TITRES}")


apres(300, etape1)
app.exec()
