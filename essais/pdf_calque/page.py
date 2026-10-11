"""Essai page : la doublure ``QPdfView`` après son passage sur ``Calque`` (``qtpy6/web/calque.py``, 11/10/2026). Un PDF
d'une page écrit par ``QPdfWriter`` en MEMFS, affiché sous une étiquette ; la place transmise à pdf.js doit suivre le
widget, et la vue désactivée doit cacher son élément. Verdict « VERDICT pdf_calque : OK/ECHEC <détail> » ; état
« essai_fini ».

    $P -m qtpy6.web.construire page.py site --pyodide ./pyodide-qt/ --titre "PDF : Calque"
    $P ../modules_demande/sonde_console.py site/index.html capture.png --racine site --delai 90 --etat essai_fini > sonde.log 2>&1
"""

import os
import sys
import tempfile
import time

from qtpy6 import QtCore, QtGui, QtWidgets
from qtpy6.QtPdf import QPdfDocument
from qtpy6.QtPdfWidgets import QPdfView
from qtpy6.web import application

WEB = sys.platform == "emscripten"
if WEB:
    import js
T0 = time.monotonic()
CHEMIN = os.path.join(tempfile.mkdtemp(), "essai.pdf")

app = application()
ecrivain = QtGui.QPdfWriter(CHEMIN)
peintre = QtGui.QPainter(ecrivain)
peintre.setFont(QtGui.QFont("DejaVu Sans", 40))
peintre.drawText(400, 1000, "Page PDF de l'essai")
peintre.end()

fenetre = QtWidgets.QWidget()
disposition = QtWidgets.QVBoxLayout(fenetre)
journal = QtWidgets.QLabel("…")
journal.setWordWrap(True)
journal.setMinimumHeight(120)
document = QPdfDocument(fenetre)
vue = QPdfView(fenetre)
vue.setDocument(document)
disposition.addWidget(journal)
disposition.addWidget(vue, 1)
fenetre.resize(600, 500)
fenetre.show()
RELEVES = {}


def note(texte):
    print(texte)
    journal.setText(journal.text() + "\n" + texte)


def verdict(ok, detail):
    note(f"VERDICT pdf_calque : {'OK' if ok else 'ECHEC'} {detail} ({time.monotonic() - T0:.2f} s)")
    if WEB:
        js.window.etat = "essai_fini"


def etape1():
    document.load(CHEMIN)
    QtCore.QTimer.singleShot(1500, etape2)


def etape2():
    RELEVES["statut"] = (document.status().name, document.pageCount())
    x, y, largeur, hauteur, visible = vue._place
    RELEVES["place"] = (largeur, hauteur, visible) == (vue.width(), vue.height(), True) and y > journal.height()
    vue.setEnabled(False)
    QtCore.QTimer.singleShot(300, etape3)


def etape3():
    RELEVES["désactivée"] = vue._place[4]
    vue.setEnabled(True)
    QtCore.QTimer.singleShot(300, fin)


def fin():
    RELEVES["réactivée"] = vue._place[4]
    attendu = {"statut": ("Ready", 1), "place": True, "désactivée": False, "réactivée": True}
    verdict(RELEVES == attendu, f"relevés={RELEVES}, place={vue._place}")


QtCore.QTimer.singleShot(300, etape1)
app.exec()
