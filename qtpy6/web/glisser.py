"""Le glisser-déposer des vues d'éléments (``QListWidget``, ``QTreeView``…) dans le navigateur : ``startDrag`` sans
``QDrag.exec``.

Qt-WASM ne sait pas imbriquer une boucle d'événements, et ``QDrag.exec`` en est une (``QBasicDrag``). Mesuré
(04/10/2026, Pyodide-Qt 6.10, souris comme doigt) : le premier glisser dépose bien, mais ``exec`` ne revient jamais, si
bien que la vue de départ ne retire pas l'élément déplacé (il est COPIÉ) ; chaque glisser suivant rend la main en 3 ms
sans rien déposer. ``bloquant`` ne peut rien ici : ``startDrag`` est appelée par Qt depuis ``mouseMoveEvent``, une
entrée où JSPI ne suspend pas, et c'est le ``QDrag::exec`` C++ qui imbrique sa boucle. Des ``QDropEvent`` fabriqués
n'y suppléent pas non plus : leur ``source()`` est None (elle vient du gestionnaire de glisser de Qt), et les vues les
refusent toutes, même vue comme autre vue (mesuré en natif).

D'où ``startDrag`` ci-dessous, posée sur les classes de vues de la liaison par ``QtWidgets`` de qtpy6 sous Pyodide : elle
mène le glisser par un filtre d'application (une image de l'élément suit le pointeur, la souris est avalée jusqu'au
relâchement) et dépose par le MODÈLE, comme le fait ``QAbstractItemView`` au bout du compte : les données des éléments
choisis insérées (``insertRows``, ``setItemData``) dans la vue sous le pointeur, au rang que désigne la moitié haute ou basse de l'élément visé,
puis, pour un déplacement, ``removeRows`` des lignes de départ. Ce que la vue d'arrivée autorise est respecté
(``acceptDrops``, ``dragDropMode``, ``canDropMimeData``, éléments déplaçables), comme l'action par défaut de la vue de
départ. Pas d'indicateur de dépôt ni de défilement automatique près des bords ; pas de dépôt SUR un élément (arbre) :
entre deux éléments seulement."""

from . import navigateur

_classes = ("QAbstractItemView", "QListView", "QListWidget", "QTreeView", "QTreeWidget", "QTableView", "QTableWidget",
            "QColumnView", "QUndoView")
_avant = {}  # la startDrag de chaque classe avant la doublure


def doubler(espace):
    """Pose ``startDrag`` sur les vues de l'espace de noms de ``qtpy6.QtWidgets`` (appelé par lui sous Pyodide). Par
    le module et non l'espace : en mode paresseux, une classe n'y entre qu'au premier ``getattr``."""
    import sys  # noqa: PLC0415

    module = sys.modules[espace["__name__"]]
    for nom in _classes:
        classe = getattr(module, nom, None)
        if classe is not None:
            _avant.setdefault(classe, vars(classe).get("startDrag"))
            classe.startDrag = startDrag


def retirer():
    """Rend aux vues la ``startDrag`` de Qt (la mesure d'avant, ``sonde_lecteur`` ``?glisser=0``)."""
    for classe, methode in _avant.items():
        if methode is None:
            delattr(classe, "startDrag")
        else:
            classe.startDrag = methode


def startDrag(vue, actions):
    """La ``startDrag`` des vues dans le navigateur : rend la main tout de suite, le glisser se poursuit par
    ``_Glisser``."""
    from qtpy6.QtCore import QRect, Qt  # noqa: PLC0415 - posée pendant l'import de QtWidgets

    indexes = [i for i in vue.selectedIndexes() if i.flags() & Qt.ItemFlag.ItemIsDragEnabled]
    if not indexes:
        return
    cadre = QRect()
    for index in indexes:
        cadre = cadre.united(vue.visualRect(index))
    image = vue.viewport().grab(cadre.intersected(vue.viewport().rect()))  # peinte maintenant : l'état de glisser de la vue
    _Glisser(vue, indexes, actions, image)


class _Glisser:
    """Un glisser en cours : l'image qui suit le pointeur, puis le dépôt au relâchement."""

    def __init__(self, vue, indexes, actions, image):
        from qtpy6.QtCore import QObject, Qt  # noqa: PLC0415
        from qtpy6.QtWidgets import QApplication, QLabel  # noqa: PLC0415

        self.vue, self.actions = vue, actions
        self.lignes = sorted({index.row() for index in indexes})
        self.parent = indexes[0].parent()
        self.mime = vue.model().mimeData(indexes)
        self.etiquette = QLabel(vue.window())
        self.etiquette.setPixmap(image)
        self.etiquette.resize(image.size() / image.devicePixelRatio())
        self.etiquette.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.etiquette.hide()  # montrée au premier mouvement, centrée sous le pointeur

        glisser = self

        class Filtre(QObject):
            def eventFilter(self, objet, evenement):
                return glisser._evenement(evenement)

        self.filtre = Filtre()
        QApplication.instance().installEventFilter(self.filtre)

    def _evenement(self, evenement):
        from qtpy6.QtCore import QEvent  # noqa: PLC0415

        type_ = evenement.type()
        if type_ == QEvent.Type.MouseMove:
            point = self.etiquette.parentWidget().mapFromGlobal(evenement.globalPosition().toPoint())
            self.etiquette.move(point - self.etiquette.rect().center())
            self.etiquette.show()
            self.etiquette.raise_()
            return True
        if type_ == QEvent.Type.MouseButtonRelease:
            self._finir()
            self._deposer(evenement.globalPosition().toPoint())
            return True
        if type_ in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):  # relâchement perdu : on abandonne
            self._finir()
        return False

    def _finir(self):
        from qtpy6.QtWidgets import QApplication  # noqa: PLC0415

        QApplication.instance().removeEventFilter(self.filtre)
        self.etiquette.deleteLater()

    def _action(self, cible):
        from qtpy6.QtCore import Qt  # noqa: PLC0415

        Mode = type(self.vue.dragDropMode())
        deplacer = (self.actions & Qt.DropAction.MoveAction
                    and (self.vue.defaultDropAction() == Qt.DropAction.MoveAction
                         or self.vue.dragDropMode() == Mode.InternalMove))
        if deplacer:
            return Qt.DropAction.MoveAction
        return Qt.DropAction.CopyAction if self.actions & Qt.DropAction.CopyAction and cible is not self.vue else None

    def _cible(self, point):
        """La vue sous ``point`` (global) qui accepte ce dépôt, et le rang où il se fait ; ou (None, None)."""
        from qtpy6.QtWidgets import QAbstractItemView, QApplication  # noqa: PLC0415

        widget = QApplication.widgetAt(point)
        while widget is not None and not (isinstance(widget, QAbstractItemView)
                                          and widget.viewport().rect().contains(widget.viewport().mapFromGlobal(point))):
            widget = widget.parentWidget()
        if widget is None or not widget.acceptDrops():
            return None, None
        Mode = QAbstractItemView.DragDropMode
        mode = widget.dragDropMode()
        if mode in (Mode.NoDragDrop, Mode.DragOnly) or (mode == Mode.InternalMove and widget is not self.vue):
            return None, None
        p = widget.viewport().mapFromGlobal(point)
        index = widget.indexAt(p)
        parent = index.parent() if index.isValid() else widget.rootIndex()
        if widget is self.vue and parent != self.parent:  # un déplacement interne reste au même niveau
            return None, None
        if index.isValid():
            rang = index.row() + (p.y() > widget.visualRect(index).center().y())
        else:
            rang = widget.model().rowCount(parent)
        return widget, (rang, parent)

    def _deposer(self, point):
        cible, ou = self._cible(point)
        action = self._action(cible) if cible is not None else None
        if action is None:
            return
        rang, parent = ou
        modele, source = cible.model(), self.vue.model()
        if not modele.canDropMimeData(self.mime, action, rang, 0, parent):
            return
        meme = cible is self.vue
        if meme and len(self.lignes) == 1 and rang in (self.lignes[0], self.lignes[0] + 1):
            return  # lâché à sa place
        # Les lignes s'insèrent puis se remplissent, ce que fait ``decodeData`` de Qt au bout de ``dropMimeData`` :
        # ``QListWidget.dropMimeData`` lit, lui, la position de l'indicateur de dépôt de la vue (que seul le glisser de
        # Qt pose) et, faute de mieux, ÉCRASE l'élément visé au lieu d'insérer (mesuré).
        donnees = [[source.itemData(source.index(ligne, c, self.parent)) for c in range(_colonnes(source, self.parent))]
                   for ligne in self.lignes]
        n = len(donnees)
        if not modele.insertRows(rang, n, parent):
            return
        for k, ligne in enumerate(donnees):
            for c, valeurs in enumerate(ligne[:_colonnes(modele, parent)]):
                modele.setItemData(modele.index(rang + k, c, parent), valeurs)
        if action == action.MoveAction:
            for ligne in reversed(self.lignes):  # du bas vers le haut : les rangs restants ne bougent pas
                source.removeRows(ligne + (n if meme and ligne >= rang else 0), 1, self.parent)
            if meme:
                rang -= sum(ligne < rang for ligne in self.lignes)
        cible.setCurrentIndex(modele.index(rang, 0, parent))


def _colonnes(modele, parent):
    try:
        return modele.columnCount(parent)
    except TypeError:  # privée dans un modèle de liste (QAbstractListModel) : une colonne
        return 1


def installee():
    """La doublure est en place (dans le navigateur seulement)."""
    from qtpy6.QtWidgets import QListWidget  # noqa: PLC0415

    return navigateur() and QListWidget.startDrag is startDrag
