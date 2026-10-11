"""QtWebEngineWidgets et QtWebEngineCore dans le navigateur, où Qt-WASM n'a pas QtWebEngine (Chromium ne se compile
pas en WebAssembly) : ``QWebEngineView`` et ``QWebEnginePage`` sous les mêmes noms, la page étant une ``<iframe>`` du
navigateur que la vue cale sur son widget (``calque.Calque``, comme ``QPdfView``). ``qtpy6.QtWebEngineWidgets`` et
``qtpy6.QtWebEngineCore`` les chargent sous Pyodide.

``setHtml(html, baseUrl)`` passe par ``srcdoc`` : la page est de même origine, son texte, sa sélection et ses liens
sont lisibles. Les ressources locales qu'elle cite (``<script src>``, ``<link href>``, ``<img src>``, relatives à
``baseUrl`` ou en ``file://``), lues dans le système de fichiers de Pyodide, deviennent des URL ``blob:`` (les ``url()``
des feuilles de style aussi) ; celles qu'un script charge lui-même ensuite (MathJax et ses extensions) ne sont pas
servies. ``load`` d'un fichier local fait de même ; ``load`` d'une URL http(s) pose ``src`` : la page est alors d'une
autre origine, et le navigateur interdit d'y lire quoi que ce soit — ``toPlainText``, ``toHtml``, ``selectedText`` et
``runJavaScript`` rendent une chaîne vide (ou None), ``findText`` ne trouve rien, et ses liens ne passent pas par
``acceptNavigationRequest``.

Un clic sur un lien d'une page de même origine appelle ``acceptNavigationRequest(url, NavigationTypeLinkClicked,
True)``, comme sur ordinateur ; un lien interne (``#ancre``) est suivi par le navigateur. Le clavier et la souris
au-dessus de l'``<iframe>`` vont au navigateur, pas à Qt : ni menu contextuel de Qt, ni raccourci de Qt quand elle a le
focus. Seul le sous-ensemble utile de l'API est doublé (celui de Spyder : ``widgets/browser.py``,
``plugins/help/widgets.py``) ; ``QWebEngineProfile`` et ``QWebEngineScript`` sont des classes vides."""

from __future__ import annotations

import enum
import mimetypes
import os
import re
from typing import Any, Callable

from qtpy6.QtCore import QObject, QUrl, Signal
from qtpy6.QtGui import QAction, QColor, QIcon
from qtpy6.QtWidgets import QApplication

from .calque import Calque


def _a_plat(classe: type) -> type:
    """Les membres des énumérations de ``classe`` posés aussi sur elle (``QWebEnginePage.FindBackward``), comme PySide6."""
    for valeur in list(vars(classe).values()):
        if isinstance(valeur, type) and issubclass(valeur, enum.Enum):
            for nom, membre in valeur.__members__.items():
                setattr(classe, nom, membre)
    return classe


@_a_plat
class QWebEngineSettings:
    """Les polices, appliquées comme défauts de la page (une feuille de style placée avant les siennes) ; les attributs
    sont gardés, sans effet."""

    class FontFamily(enum.Enum):
        StandardFont, FixedFont, SerifFont, SansSerifFont, CursiveFont, FantasyFont, PictographFont = range(7)

    class FontSize(enum.Enum):
        MinimumFontSize, MinimumLogicalFontSize, DefaultFontSize, DefaultFixedFontSize = range(4)

    class WebAttribute(enum.Enum):
        AutoLoadImages, JavascriptEnabled, JavascriptCanOpenWindows, JavascriptCanAccessClipboard, LinksIncludedInFocusChain, \
            LocalStorageEnabled, LocalContentCanAccessRemoteUrls, XSSAuditingEnabled, SpatialNavigationEnabled, \
            LocalContentCanAccessFileUrls, HyperlinkAuditingEnabled, ScrollAnimatorEnabled, ErrorPageEnabled, \
            PluginsEnabled, FullScreenSupportEnabled, ScreenCaptureEnabled, WebGLEnabled, Accelerated2dCanvasEnabled, \
            AutoLoadIconsForPage, TouchIconsEnabled, FocusOnNavigationEnabled, PrintElementBackgrounds, \
            AllowRunningInsecureContent, AllowGeolocationOnInsecureOrigins, AllowWindowActivationFromJavaScript, \
            ShowScrollBars, PlaybackRequiresUserGesture, WebRTCPublicInterfacesOnly, JavascriptCanPaste, \
            DnsPrefetchEnabled, PdfViewerEnabled, NavigateOnDropEnabled, ReadingFromCanvasEnabled, \
            ForceDarkMode = range(34)

    def __init__(self, page: QWebEnginePage | None = None):
        self._page, self._polices, self._tailles, self._attributs = page, {}, {}, {}

    def setFontFamily(self, famille: FontFamily, nom: str) -> None:
        self._polices[famille] = nom
        self._appliquer()

    def fontFamily(self, famille: FontFamily) -> str:
        return self._polices.get(famille, "")

    def setFontSize(self, genre: FontSize, taille: int) -> None:
        self._tailles[genre] = taille
        self._appliquer()

    def fontSize(self, genre: FontSize) -> int:
        return self._tailles.get(genre, 0)

    def setAttribute(self, attribut: WebAttribute, active: bool) -> None:
        self._attributs[attribut] = active

    def testAttribute(self, attribut: WebAttribute) -> bool:
        return self._attributs.get(attribut, True)

    def _appliquer(self) -> None:
        if self._page is not None:
            self._page._styler()

    def _css(self) -> str:
        """La feuille de style des défauts : ``html`` pour la police standard, ``pre, code…`` pour la fixe."""
        F, T = self.FontFamily, self.FontSize
        regles = []
        for selecteur, famille, taille in (("html", F.StandardFont, T.DefaultFontSize),
                                           ("pre, code, kbd, samp, tt", F.FixedFont, T.DefaultFixedFontSize)):
            declarations = []
            if self._polices.get(famille):
                declarations.append(f'font-family: "{self._polices[famille]}"')
            if self._tailles.get(taille):
                declarations.append(f"font-size: {self._tailles[taille]}px")
            if declarations:
                regles.append(f"{selecteur} {{ {'; '.join(declarations)} }}")
        return "\n".join(regles)


class QWebEngineProfile(QObject):
    _defaut = None

    @classmethod
    def defaultProfile(cls) -> QWebEngineProfile:
        if cls._defaut is None:
            cls._defaut = cls()
        return cls._defaut


class QWebEngineScript:
    pass


_BLOBS = {}  # (chemin, date de modification) → URL blob:, pour toute la durée de la page


def _local(lien: str, base: QUrl) -> str | None:
    """Le chemin local de ``lien`` (relatif à ``base`` ou en file://), None s'il n'est pas un fichier lisible."""
    url = base.resolved(QUrl(lien)) if base.isValid() else QUrl(lien)
    if not url.isLocalFile():
        return None
    chemin = "/" + url.toLocalFile().lstrip("/")  # file:////chemin (le gabarit de Spyder écrit file:///{{chemin absolu}})
    return chemin if os.path.isfile(chemin) else None


def _blob(chemin: str) -> str:
    """L'URL blob: du fichier ``chemin`` ; une feuille de style a ses propres ``url()`` réécrites de même."""
    cle = (chemin, os.path.getmtime(chemin))
    if cle not in _BLOBS:
        import js  # noqa: PLC0415
        from pyodide.ffi import to_js  # noqa: PLC0415

        type_ = mimetypes.guess_type(chemin)[0] or "application/octet-stream"
        if type_ == "text/css":
            with open(chemin, encoding="utf-8", errors="replace") as f:
                contenu = _urls_css(f.read(), QUrl.fromLocalFile(chemin))
        else:
            with open(chemin, "rb") as f:
                contenu = to_js(f.read())
        _BLOBS[cle] = js.URL.createObjectURL(js.Blob.new([contenu], type=type_))
    return _BLOBS[cle]


def _urls_css(css: str, base: QUrl) -> str:
    def remplacer(m):
        chemin = _local(m.group(2), base)
        return f'url("{_blob(chemin)}")' if chemin else m.group(0)

    return re.sub(r"""url\(\s*(["']?)([^"')]+)\1\s*\)""", remplacer, css)


_BALISE = re.compile(r"<(?:script|link|img|source|embed|audio|video)\b[^>]*>", re.I)
_ATTRIBUT = re.compile(r"""\b(src|href)(\s*=\s*)(["'])(.*?)\3""", re.I | re.S)


def _ressources(html: str, base: QUrl) -> str:
    """``html`` dont les ressources locales sont des URL blob: (pas les liens ``<a>`` : ils restent des liens)."""
    def attribut(m):
        chemin = _local(m.group(4), base)
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{_blob(chemin)}{m.group(3)}" if chemin else m.group(0)

    html = _BALISE.sub(lambda m: _ATTRIBUT.sub(attribut, m.group(0)), html)
    return re.sub(r"(<style\b[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + _urls_css(m.group(2), base) + m.group(3),
                  html, flags=re.I | re.S)


@_a_plat
class QWebEnginePage(QObject):
    class WebAction(enum.Enum):
        NoWebAction = -1
        Back, Forward, Stop, Reload, Cut, Copy, Paste, Undo, Redo, SelectAll, ReloadAndBypassCache, PasteAndMatchStyle, \
            OpenLinkInThisWindow, OpenLinkInNewWindow, OpenLinkInNewTab, CopyLinkToClipboard, DownloadLinkToDisk, \
            CopyImageToClipboard, CopyImageUrlToClipboard, DownloadImageToDisk, CopyMediaUrlToClipboard, \
            ToggleMediaControls, ToggleMediaLoop, ToggleMediaPlayPause, ToggleMediaMute, DownloadMediaToDisk, \
            InspectElement, ExitFullScreen, RequestClose, Unselect, SavePage, OpenLinkInNewBackgroundTab, \
            ViewSource = range(33)

    class NavigationType(enum.Enum):
        NavigationTypeLinkClicked, NavigationTypeTyped, NavigationTypeFormSubmitted, NavigationTypeBackForward, \
            NavigationTypeReload, NavigationTypeOther, NavigationTypeRedirect = range(7)

    class FindFlag(enum.IntFlag):
        FindWrapsAroundDocument = 0  # Qt 6 : toujours ; gardé pour le code écrit pour Qt 5
        FindBackward = 1
        FindCaseSensitively = 2

    loadStarted = Signal()
    loadProgress = Signal(int)
    loadFinished = Signal(bool)
    urlChanged = Signal(QUrl)
    titleChanged = Signal(str)
    iconChanged = Signal(QIcon)
    selectionChanged = Signal()

    def __init__(self, *args):
        """``QWebEnginePage(parent=None)`` ou ``QWebEnginePage(profil, parent=None)``."""
        if args and isinstance(args[0], QWebEngineProfile):
            self._profil, args = args[0], args[1:]
        else:
            self._profil = QWebEngineProfile.defaultProfile()
        super().__init__(*args)
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy  # noqa: PLC0415

        self._url, self._titre, self._zoom, self._fond = QUrl(), "", 1.0, None
        self._historique, self._position, self._en_cours = [], -1, False
        self._reglages, self._actions = QWebEngineSettings(self), {}
        self._cadre = cadre = js.document.createElement("iframe")
        cadre.className = "qtpy6-web"
        cadre.style.cssText = "position: fixed; z-index: 10; border: 0; display: none; background: white"
        self._charge_proxy = create_proxy(self._charge)
        self._clic_proxy = create_proxy(self._clic)
        cadre.addEventListener("load", self._charge_proxy)
        js.document.body.append(cadre)
        self.destroyed.connect(lambda *_: cadre.remove())

    # Contenu
    def setHtml(self, html: str, baseUrl: QUrl = QUrl()) -> None:
        self._empiler(QUrl(baseUrl), html)

    def load(self, url: QUrl | str) -> None:
        self._empiler(QUrl(url), None)

    def _empiler(self, url: QUrl, html: str | None) -> None:
        """Une entrée d'historique (url, html) : le html d'un ``setHtml``, None d'une page à charger ; Qt garde l'une
        et l'autre pour ``back()``."""
        entree = (url, html)
        if self._position < 0 or self._historique[self._position] != entree:
            del self._historique[self._position + 1:]
            self._historique.append(entree)
            self._position += 1
        self._aller(entree)

    def _poser(self, html: str, url: QUrl) -> None:
        self._url = QUrl(url)
        self._commencer()
        self._cadre.removeAttribute("src")
        self._cadre.srcdoc = _ressources(html, self._url)
        self.urlChanged.emit(QUrl(self._url))

    def _aller(self, entree: tuple[QUrl, str | None]) -> None:
        url, html = entree
        if html is not None:
            self._poser(html, url)
        elif url.isLocalFile():
            try:
                with open(url.toLocalFile(), encoding="utf-8", errors="replace") as f:
                    html = f.read()
            except OSError:
                self._echec(url)
                return
            self._poser(html, url)
        elif url.scheme() in ("http", "https", "data", "blob", "about"):
            self._url = QUrl(url)
            self._commencer()
            self._cadre.removeAttribute("srcdoc")
            self._cadre.src = url.toString()
            self.urlChanged.emit(QUrl(url))
        else:
            self._echec(url)

    def _commencer(self) -> None:
        self._en_cours = True
        self.loadStarted.emit()

    def _echec(self, url: QUrl) -> None:
        self._url = QUrl(url)
        self.urlChanged.emit(QUrl(url))
        self.loadStarted.emit()
        self.loadFinished.emit(False)

    def url(self) -> QUrl:
        return QUrl(self._url)

    def requestedUrl(self) -> QUrl:
        return QUrl(self._url)

    def title(self) -> str:
        return self._titre

    def icon(self) -> QIcon:
        return QIcon()

    def _document(self):
        """Le document de la page, None d'une autre origine (le navigateur le refuse)."""
        try:
            return self._cadre.contentDocument
        except Exception:  # noqa: BLE001
            return None

    def _charge(self, *_):
        document = self._document()
        if document is not None and str(document.URL) == "about:blank" and self._en_cours:
            return  # le about:blank initial de l'<iframe>, avant la page demandée
        if document is not None:
            document.addEventListener("click", self._clic_proxy)
            self._styler()
        titre = str(document.title) if document is not None else ""
        if titre != self._titre:
            self._titre = titre
            self.titleChanged.emit(titre)
        if self._en_cours:
            self._en_cours = False
            self.loadProgress.emit(100)
            self.loadFinished.emit(True)

    def _styler(self) -> None:
        """Polices par défaut (avant les feuilles de la page, qui l'emportent), zoom et fond."""
        document = self._document()
        if document is None or document.documentElement is None:
            return
        style = document.getElementById("qtpy6-reglages")
        if style is None:
            style = document.createElement("style")
            style.id = "qtpy6-reglages"
            tete = document.head or document.documentElement
            tete.insertBefore(style, tete.firstChild)
        style.textContent = self._reglages._css()
        document.documentElement.style.zoom = str(self._zoom)

    def _clic(self, evenement):
        lien = evenement.target.closest("a[href]") if hasattr(evenement.target, "closest") else None
        if lien is None or evenement.defaultPrevented:
            return
        cible = str(lien.getAttribute("href"))
        if cible.startswith("#"):
            return  # ancre de la page : le navigateur la suit
        evenement.preventDefault()
        url = self._url.resolved(QUrl(cible)) if self._url.isValid() else QUrl(cible)
        if self.acceptNavigationRequest(url, self.NavigationType.NavigationTypeLinkClicked, True):
            self.load(url)

    def acceptNavigationRequest(self, url: QUrl, type_: NavigationType, isMainFrame: bool) -> bool:
        return True

    def toPlainText(self, rappel: Callable[[str], Any]) -> None:
        """Rappelé tout de suite (Spyder le suppose), "" d'une page d'une autre origine."""
        document = self._document()
        rappel(str(document.body.innerText) if document is not None and document.body is not None else "")

    def toHtml(self, rappel: Callable[[str], Any]) -> None:
        document = self._document()
        rappel(str(document.documentElement.outerHTML) if document is not None and document.documentElement else "")

    def runJavaScript(self, source: str, *args) -> None:
        """``runJavaScript(source[, worldId][, rappel])`` : exécuté dans la page, le rappel reçoit le résultat (None d'une
        page d'une autre origine, ou si le script lève)."""
        rappel = args[-1] if args and callable(args[-1]) else None
        try:
            resultat = self._cadre.contentWindow.eval(source)
            resultat = resultat.to_py() if hasattr(resultat, "to_py") else resultat
        except Exception:  # noqa: BLE001
            resultat = None
        if rappel is not None:
            rappel(resultat)

    # Sélection et recherche
    def selectedText(self) -> str:
        try:
            return str(self._cadre.contentWindow.getSelection().toString())
        except Exception:  # noqa: BLE001
            return ""

    def hasSelection(self) -> bool:
        return bool(self.selectedText())

    def findText(self, texte: str, options: FindFlag = FindFlag(0), resultCallback: Callable | None = None) -> None:
        """Sélectionne l'occurrence suivante (``window.find`` du navigateur) ; un texte vide efface la sélection."""
        try:
            fenetre = self._cadre.contentWindow
            if not texte:
                fenetre.getSelection().removeAllRanges()
                return
            fenetre.find(texte, bool(options & self.FindFlag.FindCaseSensitively),
                         bool(options & self.FindFlag.FindBackward), True)
        except Exception:  # noqa: BLE001
            pass

    # Actions
    def action(self, action: WebAction) -> QAction:
        if action not in self._actions:
            qaction = self._actions[action] = QAction(action.name, self)
            qaction.triggered.connect(lambda *_: self.triggerAction(action))
        return self._actions[action]

    def triggerAction(self, action: WebAction, checked: bool = False) -> None:
        A = self.WebAction
        if action in (A.Back, A.Forward):
            position = self._position + (-1 if action == A.Back else 1)
            if 0 <= position < len(self._historique):
                self._position = position
                self._aller(self._historique[position])
        elif action in (A.Reload, A.ReloadAndBypassCache):
            if self._position >= 0:
                self._aller(self._historique[self._position])
        elif action == A.SelectAll:
            document = self._document()
            if document is not None and document.body is not None:
                self._cadre.contentWindow.getSelection().selectAllChildren(document.body)
        elif action == A.Copy:
            if self.hasSelection():
                QApplication.clipboard().setText(self.selectedText())
        elif action == A.Unselect:
            self.findText("")

    # Réglages
    def settings(self) -> QWebEngineSettings:
        return self._reglages

    def profile(self) -> QWebEngineProfile:
        return self._profil

    def setZoomFactor(self, facteur: float) -> None:
        self._zoom = facteur
        self._styler()

    def zoomFactor(self) -> float:
        return self._zoom

    def setBackgroundColor(self, couleur: QColor) -> None:
        self._fond = QColor(couleur)
        self._cadre.style.background = self._fond.name()

    def backgroundColor(self) -> QColor:
        return QColor(self._fond) if self._fond is not None else QColor("white")


class QWebEngineView(Calque):
    loadStarted = Signal()
    loadProgress = Signal(int)
    loadFinished = Signal(bool)
    urlChanged = Signal(QUrl)
    titleChanged = Signal(str)
    iconChanged = Signal(QIcon)
    selectionChanged = Signal()
    _SIGNAUX = ("loadStarted", "loadProgress", "loadFinished", "urlChanged", "titleChanged", "iconChanged",
                "selectionChanged")

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)  # coopératif : WebView(QWebEngineView, SpyderWidgetMixin) y passe class_parent
        self._page = None

    def page(self) -> QWebEnginePage:
        if self._page is None:
            self.setPage(QWebEnginePage(self))
        return self._page

    def setPage(self, page: QWebEnginePage) -> None:
        if self._page is not None:
            for nom in self._SIGNAUX:
                getattr(self._page, nom).disconnect(getattr(self, nom))
            self._page._cadre.style.display = "none"
        self._page, self._place = page, None
        for nom in self._SIGNAUX:
            getattr(page, nom).connect(getattr(self, nom))
        self._synchroniser()

    def _placer(self, x: float, y: float, largeur: int, hauteur: int, visible: bool) -> None:
        style = self.page()._cadre.style
        style.left, style.top, style.width, style.height = f"{x}px", f"{y}px", f"{largeur}px", f"{hauteur}px"
        style.display = "block" if visible else "none"

    # Ce que la vue délègue à sa page, comme QWebEngineView
    def setHtml(self, html: str, baseUrl: QUrl = QUrl()) -> None:
        self.page().setHtml(html, baseUrl)

    def load(self, url: QUrl | str) -> None:
        self.page().load(url)

    def setUrl(self, url: QUrl | str) -> None:
        self.page().load(url)

    def url(self) -> QUrl:
        return self.page().url()

    def title(self) -> str:
        return self.page().title()

    def icon(self) -> QIcon:
        return QIcon()

    def selectedText(self) -> str:
        return self.page().selectedText()

    def hasSelection(self) -> bool:
        return self.page().hasSelection()

    def findText(self, texte: str, options=QWebEnginePage.FindFlag(0), resultCallback: Callable | None = None) -> None:
        self.page().findText(texte, options, resultCallback)

    def pageAction(self, action: QWebEnginePage.WebAction) -> QAction:
        return self.page().action(action)

    def triggerPageAction(self, action: QWebEnginePage.WebAction, checked: bool = False) -> None:
        self.page().triggerAction(action, checked)

    def back(self) -> None:
        self.page().triggerAction(QWebEnginePage.WebAction.Back)

    def forward(self) -> None:
        self.page().triggerAction(QWebEnginePage.WebAction.Forward)

    def reload(self) -> None:
        self.page().triggerAction(QWebEnginePage.WebAction.Reload)

    def stop(self) -> None:
        pass

    def settings(self) -> QWebEngineSettings:
        return self.page().settings()

    def setZoomFactor(self, facteur: float) -> None:
        self.page().setZoomFactor(facteur)

    def zoomFactor(self) -> float:
        return self.page().zoomFactor()
