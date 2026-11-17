"""La fenêtre d'erreur fugitive de l'explorateur de Spyder dans le navigateur (item 10 du TODO Portage, W570 puis W578).

Qt wasm n'a pas de fil : le QFileInfoGatherer de QFileSystemModel émet ``directoryLoaded`` SUR PLACE, dans le
``fetchMore`` que QTreeView appelle en pleine mise en page (``QTreeViewPrivate::layout``, descente dans un dossier déplié,
les lignes suivantes encore vides). Le slot de Spyder (``resizeColumnToContents(0)``, ``explorer.py:1009``) y parcourait
ces lignes vides : son délégué recevait ``QModelIndex()``, ``index.model()`` None. En natif, le fil du gatherer le livre
en connexion différée. Ici, le ``fetchMore`` du modèle émet sur place comme celui de Qt wasm, sur le vrai QTreeView.
"""

from test_web import greenlet_seul, simule

MONTAGE = """
    import os, sys, tempfile, traceback
    from qtpy6.QtWidgets import QFileSystemModel, QStyledItemDelegate, QTreeView
    erreurs = []
    sys.excepthook = lambda t, v, p: erreurs.append(f"{t.__name__}: {v}")

    class ModeleSansFil(QFileSystemModel):  # comme Qt wasm (QT_FEATURE_thread -1) : directoryLoaded émis dans fetchMore
        def fetchMore(self, parent):
            super().fetchMore(parent)
            self.directoryLoaded.emit(self.filePath(parent))

    class Delegue(QStyledItemDelegate):  # spyder/plugins/explorer/widgets/explorer.py:177
        def initStyleOption(self, option, index):
            super().initStyleOption(option, index)
            index.model().isDir(index)

    d = tempfile.mkdtemp()
    for nom in ("tot/plus", "sous"):
        os.makedirs(os.path.join(d, nom))
    for nom in ("a.py", "b.py", "tot/f.py"):
        open(os.path.join(d, nom), "w").close()
    m, vue = ModeleSansFil(), QTreeView()
    vue.setItemDelegate(Delegue(vue))
    vue.setModel(m)
"""


@greenlet_seul
def test_directory_loaded_pendant_la_mise_en_page_ne_voit_pas_de_ligne_vide():
    # essais/fsmodel/page.py, passe essai4 de W578 : 5 échecs sur 5 sans le report, 0 sur 5 avec.
    sortie = simule(MONTAGE + """
    m.directoryLoaded.connect(lambda: vue.resizeColumnToContents(0))

    vue.setSortingEnabled(True)  # comme Spyder : dossiers d'abord, tot n'est pas la dernière ligne
    for chemin in (d, os.path.join(d, "tot")):  # lignes connues (le fil natif les liste pendant tourner), fetchMore jamais appelé
        m.setRootPath(chemin)
        tourner(500)

    def montage():  # dans une entrée promettante, comme le chdir de Spyder : sans le report, le slot passe sur place
        vue.setRootIndex(m.setRootPath(d))
        vue.expand(m.index(os.path.join(d, "tot")))  # mise en page en attente : dépliage seulement noté
        vue.resizeColumnToContents(0)  # la mise en page, qui descend dans tot et l'y charge
    principal(montage)
    tourner()
    print(erreurs)
    """)
    assert sortie == "[]"


@greenlet_seul
def test_directory_loaded_se_deconnecte_par_le_slot():
    # Spyder déconnecte restore_directory_state une fois l'état déplié rendu : le relais, qui ne fait plus le même choix
    # pour directoryLoaded, doit retrouver le sien.
    sortie = simule(MONTAGE + """
    vus = []
    def recu(chemin):
        vus.append(chemin)
    m.directoryLoaded.connect(recu)
    m.directoryLoaded.disconnect(recu)
    principal(lambda: m.directoryLoaded.emit("/x"))
    tourner()
    print(vus, erreurs)
    """)
    assert sortie == "[] []"
