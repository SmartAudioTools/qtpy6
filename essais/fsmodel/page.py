"""Essai page (item 10 du TODO Portage, W550) : la fenêtre d'erreur fugitive de l'explorateur de Spyder, réduite à
l'essentiel. Un QTreeView sur un QFileSystemModel, le délégué de Spyder (``initStyleOption`` lit ``index.model().isDir``),
``directoryLoaded`` → ``resizeColumnToContents(0)`` comme ``explorer.py:1008``, tri activé, puis un sous-dossier déplié.
Toute exception d'un slot est notée avec sa pile.
W578 (17/11) : montage depuis un slot (le relais y exécute sur place), un sous-dossier ``tot`` déjà listé
(``setRootPath``, sans ``fetchMore``) et déplié pendant que la mise en page attend : c'est la condition qui reproduit
l'erreur du professeur (``fetchMore`` dans ``QTreeViewPrivate::layout``, lignes suivantes encore vides). 5 ECHEC sur 5
depuis HEAD, 5 OK sur 5 avec les slots de ``directoryLoaded`` reportés (``qtpy6_essais/equipe/w578/``). Verdict « VERDICT fsmodel : OK/ECHEC <détail> », état « essai_fini ».

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
os.makedirs(os.path.join(DOSSIER, "tot", "plus"))  # W578 : déplié avant la première mise en page (état restauré de Spyder)
open(os.path.join(DOSSIER, "tot", "f.py"), "w").write("z\n")
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
    pile = "<".join(c.name for c in reversed(traceback.extract_stack()[:-1]))  # W578 : appelé sur place ou reporté
    note(f"directoryLoaded {chemin} : {modele.rowCount(modele.index(chemin))} lignes ; pile {pile}")


modele.directoryLoaded.connect(charge)
modele.directoryLoaded.connect(lambda: vue.resizeColumnToContents(0))
vue.setAnimated(False)
vue.setSortingEnabled(True)
vue.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)


def montage():
    """W578 : monté depuis un slot (tâche reportée par le relais, ``_actif``), comme le changement de dossier de Spyder :
    là, le relais exécute ``directoryLoaded`` sur place, au milieu de la mise en page de la vue qui l'a provoqué."""
    modele.setRootPath(os.path.join(DOSSIER, "tot"))  # ses lignes connues, mais fetchMore jamais appelé (canFetchMore vrai)
    vue.setRootIndex(modele.setRootPath(DOSSIER))
    vue.expand(modele.index(os.path.join(DOSSIER, "tot")))  # mise en page encore en attente : dépliage seulement noté
    vue.resize(500, 300)
    vue.show()
    vue.resizeColumnToContents(0)  # une mise en page forcée depuis le slot (Spyder : resizeColumnToContents, scrollTo…)
    QtCore.QTimer.singleShot(1500, deplier)


def deplier():
    vue.expand(modele.index(os.path.join(DOSSIER, "sous")))
    QtCore.QTimer.singleShot(1500, fin)


def fin():
    ok = not ERREURS and len(CHARGES) >= 2
    note(f"VERDICT fsmodel : {'OK' if ok else 'ECHEC'} chargés {len(CHARGES)}, erreurs {ERREURS[:3]}")
    if WEB:
        js.window.etat = "essai_fini"
    BOUCLE.quit()


QtCore.QTimer.singleShot(0, montage)
BOUCLE.exec()  # le script reste suspendu, comme celui de Spyder : les slots de Qt passent par le relais reporté
