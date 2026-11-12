"""Essai page (item 10 du TODO Portage, W550) : la fenêtre d'erreur fugitive de l'explorateur de Spyder, réduite à
l'essentiel. Un QTreeView sur un QFileSystemModel, le délégué de Spyder (``initStyleOption`` lit ``index.model().isDir``),
``directoryLoaded`` → ``resizeColumnToContents(0)`` comme ``explorer.py:1008``, tri activé, puis un sous-dossier déplié.
Toute exception d'un slot est notée avec sa pile. Verdict « VERDICT fsmodel : OK/ECHEC <détail> », état « essai_fini ».

    $P -m qtpy6.web.construire page.py /DATA/Python/qtpy6_essais/w550/fsmodel_site --pyodide ./pyodide-qt/ --titre fsmodel
    $P -m qtpy6.web.sonde /DATA/Python/qtpy6_essais/w550/fsmodel_site/index.html capture.png --racine /DATA/Python/qtpy6_essais/w550/fsmodel_site --delai 120 --etat essai_fini
"""

import os
import sys
import tempfile
import time
import traceback

from qtpy6 import QtCore, QtWidgets
from qtpy6.web import application

WEB = sys.platform == "emscripten"  # instrumentation : l'état de la page pour la sonde
if WEB:
    import js
T0 = time.monotonic()
ERREURS = []


def note(texte):
    print(f"[{time.monotonic() - T0:6.2f}] {texte}", flush=True)


def crochet(type_, valeur, pile):
    ERREURS.append(f"{type_.__name__}: {valeur}")
    note("EXCEPTION d'un slot :\n" + "".join(traceback.format_exception(type_, valeur, pile)))


sys.excepthook = crochet

DOSSIER = tempfile.mkdtemp(prefix="fsmodel-")
for nom in ("a.py", "b.txt", "c.py"):
    open(os.path.join(DOSSIER, nom), "w").write("x\n")
os.makedirs(os.path.join(DOSSIER, "sous", "plus"))
for nom in ("d.py", "e.py"):
    open(os.path.join(DOSSIER, "sous", nom), "w").write("y\n")


class Delegue(QtWidgets.QStyledItemDelegate):  # spyder/plugins/explorer/widgets/explorer.py:169
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if isinstance(option, QtWidgets.QStyleOptionViewItem):
            model = index.model()
            if model is None:
                note(f"initStyleOption : index sans modèle (valide {index.isValid()}, ligne {index.row()})")
            model.isDir(index)


app = application()
BOUCLE = QtCore.QEventLoop()
modele = QtWidgets.QFileSystemModel()
modele.setNameFilterDisables(False)
vue = QtWidgets.QTreeView()
vue.setItemDelegate(Delegue(vue))
vue.setModel(modele)
CHARGES = []


def charge(chemin):
    CHARGES.append(chemin)
    note(f"directoryLoaded {chemin} : {modele.rowCount(modele.index(chemin))} lignes")


modele.directoryLoaded.connect(charge)
modele.directoryLoaded.connect(lambda: vue.resizeColumnToContents(0))
vue.setAnimated(False)
vue.setSortingEnabled(True)
vue.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
vue.setRootIndex(modele.setRootPath(DOSSIER))
vue.resize(500, 300)
vue.show()


def deplier():
    vue.expand(modele.index(os.path.join(DOSSIER, "sous")))
    QtCore.QTimer.singleShot(1500, fin)


def fin():
    ok = not ERREURS and len(CHARGES) >= 2
    note(f"VERDICT fsmodel : {'OK' if ok else 'ECHEC'} chargés {len(CHARGES)}, erreurs {ERREURS[:3]}")
    if WEB:
        js.window.etat = "essai_fini"
    BOUCLE.quit()


QtCore.QTimer.singleShot(1500, deplier)
BOUCLE.exec()  # le script reste suspendu, comme celui de Spyder : les slots de Qt passent par le relais reporté
