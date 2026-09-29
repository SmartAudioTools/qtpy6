"""QtPdf et QtPdfWidgets dans le navigateur, où Qt-WASM ne les a pas (QtPdf repose sur PDFium, construit avec
QtWebEngine) : ``QPdfDocument`` et ``QPdfView`` sous les mêmes noms, dessinés par pdf.js (``js/pdfjs/``, vendu, aucun
réseau) dans un ``<div>`` de la page que la vue cale sur son widget. Le texte y est sélectionnable et copiable, comme
dans le lecteur PDF du navigateur. ``qtpy6.QtPdf`` et ``qtpy6.QtPdfWidgets`` les chargent sous Pyodide.

Le ``<div>`` est au-dessus du canevas de Qt : il n'est montré que quand le widget se voit, est activé (un widget
désactivé cache son PDF : un rideau posé par ``setEnabled(False)`` le couvre) et qu'aucune boîte modale ni menu
n'est ouvert, que Qt dessinerait dessous. Seul le sous-ensemble utile de l'API est doublé : ``QPdfDocument.load``
(chemin ou QIODevice), ``status``, ``pageCount`` et leurs signaux ; ``QPdfView.setDocument`` et les modes, la page
étant toujours ajustée à la largeur, les pages les unes sous les autres. Le chargement est asynchrone : ``load`` rend
``Error.None_`` avec ``status() == Loading``, puis ``statusChanged(Ready)``."""

import enum
import importlib.resources

from qtpy6.QtCore import QObject, QPoint, QTimer, Signal
from qtpy6.QtWidgets import QApplication, QWidget

_JS = None


def _js():
    """Les fonctions de ``js/pdf_vue.js``, chargées au premier usage (rien n'importe ``js`` au chargement du module)."""
    global _JS
    if _JS is None:
        import js  # noqa: PLC0415
        from pyodide.code import run_js  # noqa: PLC0415

        dossier = importlib.resources.files(__package__).joinpath("js")

        def url(nom):
            source = dossier.joinpath(nom).read_text(encoding="utf-8")
            return js.URL.createObjectURL(js.Blob.new([source], type="text/javascript"))

        _JS = run_js(dossier.joinpath("pdf_vue.js").read_text(encoding="utf-8"))(
            url("pdfjs/pdf.min.mjs"), url("pdfjs/pdf.worker.min.mjs"))
    return _JS


class QPdfDocument(QObject):
    class Status(enum.Enum):
        Null, Loading, Ready, Unloading, Error = range(5)

    class Error(enum.Enum):
        None_, Unknown, DataNotYetAvailable, FileNotFound, InvalidFileFormat, IncorrectPassword, \
            UnsupportedSecurityScheme = range(7)

    statusChanged = Signal(object)
    pageCountChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status, self._erreur, self._pages, self._promesse = self.Status.Null, self.Error.None_, 0, None

    def status(self):
        return self._status

    def error(self):
        return self._erreur

    def pageCount(self):
        return self._pages

    def load(self, source):
        if isinstance(source, str):
            try:
                with open(source, "rb") as f:
                    octets = f.read()
            except OSError:
                self._erreur = self.Error.FileNotFound
                self._statut(self.Status.Error)
                return self._erreur
        else:
            octets = bytes(source.readAll())
        from pyodide.ffi import create_once_callable, to_js  # noqa: PLC0415

        self.close()
        self._erreur = self.Error.None_
        self._statut(self.Status.Loading)
        promesse = self._promesse = _js().ouvrir(to_js(octets))

        def pret(doc):
            if promesse is self._promesse:
                self._pages = doc.numPages
                self.pageCountChanged.emit(self._pages)
                self._statut(self.Status.Ready)

        def echec(raison):
            if promesse is self._promesse:
                self._erreur = (self.Error.IncorrectPassword if "Password" in str(raison.name)
                                else self.Error.InvalidFileFormat)
                self._statut(self.Status.Error)

        promesse.then(create_once_callable(pret), create_once_callable(echec))
        return self.Error.None_

    def close(self):
        if self._promesse is not None:
            self._promesse, self._pages = None, 0
            self.pageCountChanged.emit(0)
            self._statut(self.Status.Null)

    def _statut(self, statut):
        if statut != self._status:
            self._status = statut
            self.statusChanged.emit(statut)


class QPdfView(QWidget):
    class PageMode(enum.Enum):
        SinglePage, MultiPage = range(2)

    class ZoomMode(enum.Enum):
        Custom, FitToWidth, FitInView = range(3)

    documentChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._document, self._mode_page, self._mode_zoom = None, self.PageMode.SinglePage, self.ZoomMode.Custom
        self._vue = vue = _js().vue()
        self._place = None
        self.destroyed.connect(lambda *_: vue.detruire())
        # Le filet : ce qu'aucun événement du widget ne signale (un ancêtre qui bouge, une boîte modale, un menu)
        self._minuterie = QTimer(self, interval=100, timeout=self._synchroniser)
        self._minuterie.start()

    def document(self):
        return self._document

    def setDocument(self, document):
        if self._document is not None:
            self._document.statusChanged.disconnect(self._afficher)
        self._document = document
        if document is not None:
            document.statusChanged.connect(self._afficher)
        self._afficher()
        self.documentChanged.emit(document)

    def _afficher(self, *_):
        prete = self._document is not None and self._document.status() == QPdfDocument.Status.Ready
        self._vue.afficher(self._document._promesse if prete else None)

    def pageMode(self):
        return self._mode_page

    def setPageMode(self, mode):
        self._mode_page = mode

    def zoomMode(self):
        return self._mode_zoom

    def setZoomMode(self, mode):
        self._mode_zoom = mode

    def _synchroniser(self):
        import js  # noqa: PLC0415

        modale = QApplication.activeModalWidget()
        visible = (self.isVisible() and self.isEnabled() and QApplication.activePopupWidget() is None
                   and modale in (None, self.window()))
        coin = self.mapToGlobal(QPoint(0, 0)) - self.screen().geometry().topLeft()
        boite = js.window.qtpy6Conteneur.getBoundingClientRect()
        place = (coin.x() + boite.left, coin.y() + boite.top, self.width(), self.height(), visible)
        if place != self._place:
            self._place = place
            self._vue.placer(*place)

    def showEvent(self, evenement):
        super().showEvent(evenement)
        self._synchroniser()

    def hideEvent(self, evenement):
        super().hideEvent(evenement)
        self._synchroniser()

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        self._synchroniser()

    def changeEvent(self, evenement):
        super().changeEvent(evenement)
        self._synchroniser()
