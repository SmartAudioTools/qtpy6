"""``qtpy6.doublures`` : le navigateur doublé le temps d'un bloc, puis ``sys.modules`` rendu tel quel."""

import sys

import pytest

from qtpy6.doublures import MODULES, navigateur_double


def test_modules_rendus_tels_quels():
    """Un nom absent le redevient, un nom présent retrouve son module, même quand le bloc lève."""
    sentinelle = object()
    sys.modules.pop("js", None)
    sys.modules["pyodide"] = sentinelle
    avant = {nom: sys.modules.get(nom, "absent") for nom in MODULES}
    try:
        with pytest.raises(RuntimeError), navigateur_double(titre="essai") as js:
            from js import document, titre
            from pyodide.ffi import create_proxy, jsnull
            assert sys.modules["js"] is js and titre == "essai"
            assert document.addEventListener("visibilitychange", create_proxy(print)) is None
            assert create_proxy(print) is print and jsnull is not None and not jsnull
            raise RuntimeError
        assert {nom: sys.modules.get(nom, "absent") for nom in MODULES} == avant
    finally:
        sys.modules.pop("pyodide")


# --- W556 : application(persistant=…, disque=True), le dossier autorisé de Chrome --------------------------------------
def test_disque_sans_effet_en_natif(tmp_path):
    """En natif, ``disque`` ne change rien : le dossier persistant est un dossier du disque, créé au besoin, et aucun
    montage n'est noté (``stockage`` n'importe ``js`` qu'à l'appel)."""
    from qtpy6.web import application, stockage

    dossier = tmp_path / "eleve"
    application(persistant=dossier, disque=True)
    assert dossier.is_dir() and not stockage._montes and not stockage._natifs


# --- W558 : renderProcessTerminated de la doublure QWebEngine (greffon spyder_python_tutor, main_widget.py:385) ----------
def test_moteur_web_render_process_terminated(app):
    """Le tuteur branche ``page.renderProcessTerminated`` (statut, code de sortie) : le signal existe sous le nom et la
    signature Qt sur la page et sur la vue, qui le relaie comme les autres ; jamais émis par la doublure (l'iframe meurt
    avec la page)."""
    from unittest.mock import MagicMock

    with navigateur_double(document=MagicMock(), window=MagicMock()):
        from qtpy6.web.moteur_web import QWebEnginePage, QWebEngineView

        vue = QWebEngineView()
        page = QWebEnginePage(vue)
        vue.setPage(page)
        recus = []
        page.renderProcessTerminated.connect(lambda statut, code: recus.append(("page", statut, code)))
        vue.renderProcessTerminated.connect(lambda statut, code: recus.append(("vue", statut, code)))
        crash = QWebEnginePage.RenderProcessTerminationStatus.CrashedTerminationStatus
        page.renderProcessTerminated.emit(crash, 11)
        assert sorted(recus) == [("page", crash, 11), ("vue", crash, 11)]


# --- W560 : alert() et console.* de l'iframe vers javaScriptAlert / javaScriptConsoleMessage (tuteur, _DebugPage) --------
def _page_relais(app, classe_page=None):
    from qtpy6.web.moteur_web import QWebEnginePage, QWebEngineView

    vue = QWebEngineView()
    page = (classe_page or QWebEnginePage)(vue)
    vue.setPage(page)
    return vue, page


def test_moteur_web_relais_alert_console(app):
    """Le tuteur surcharge ``javaScriptAlert`` et ``javaScriptConsoleMessage`` (``main_widget.py:372-380``) : la page
    posée par ``setHtml`` porte, avant tout autre script et après le doctype, le relais qui remplace ``alert`` et
    ``console.*`` de l'iframe ; le relais appelle les méthodes surchargées avec la signature Qt."""
    from unittest.mock import MagicMock

    with navigateur_double(document=MagicMock(), window=MagicMock()):
        from qtpy6.web.moteur_web import QWebEnginePage

        recus = []

        class _DebugPage(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, line, source):
                recus.append((level.name, message, line, source))

            def javaScriptAlert(self, origin, msg):
                recus.append(("alert", origin.toString(), msg))

        vue, page = _page_relais(app, _DebugPage)
        page.setHtml("<!DOCTYPE html><html><head><script>alert(1)</script></head></html>")
        srcdoc = str(page._cadre.srcdoc)
        assert srcdoc.startswith("<!DOCTYPE html><html><head><script>")
        assert srcdoc.index("qtpy6_relais") < srcdoc.index("alert(1)")
        relais = page._cadre.qtpy6_relais
        relais("alert", "Assertion Failure", 0, "")
        relais("error", "boum", 12, "viz.js")
        relais("warn", "attention", 3, "viz.js")
        relais("log", "info", 0, "")
        assert recus == [("alert", page.url().toString(), "Assertion Failure"),
                         ("ErrorMessageLevel", "boum", 12, "viz.js"),
                         ("WarningMessageLevel", "attention", 3, "viz.js"),
                         ("InfoMessageLevel", "info", 0, "")]


def test_moteur_web_alert_par_defaut(app):
    """Sans surcharge, ``javaScriptAlert`` ouvre une QMessageBox comme Qt, sans ``exec()`` (le relais est appelé par
    le navigateur, entrée non suspendable : ``open()`` ne bloque pas) ; ``javaScriptConsoleMessage`` ne fait rien."""
    from unittest.mock import MagicMock

    from qtpy6.QtWidgets import QMessageBox

    with navigateur_double(document=MagicMock(), window=MagicMock()):
        vue, page = _page_relais(app)
        page.setHtml("<p>x</p>")
        page._cadre.qtpy6_relais("error", "boum", 1, "")
        page._cadre.qtpy6_relais("alert", "Bonjour", 0, "")
        boites = [b for b in vue.findChildren(QMessageBox) if b.text() == "Bonjour"]
        assert len(boites) == 1 and boites[0].isVisible()
        boites[0].close()


# --- W562 : l'alias snake_case d'un SIGNAL cède au nom de l'application (Spyder, TextEditBaseWidget) ---------------------
def test_alias_signal_cede_au_mixin(app):
    """``class TextEditBaseWidget(QPlainTextEdit, BaseEditMixin)`` : la méthode ``BaseEditMixin.cursor_position_changed``
    vient après Qt dans la MRO ; un alias-attribut du signal ``cursorPositionChanged`` la masquait, et
    ``cursorPositionChanged.connect(self.cursor_position_changed)`` (spyder/plugins/editor/widgets/base.py:76) connectait
    le signal à lui-même : ``setPlainText`` récursait sans fin (jalon 5, « too much recursion » dans la page)."""
    from qtpy6.QtWidgets import QPlainTextEdit

    class Mixin:
        def cursor_position_changed(self):
            self.appels += 1

    class Editeur(QPlainTextEdit, Mixin):
        appels = 0

    e = Editeur()
    assert e.cursor_position_changed.__func__ is Mixin.cursor_position_changed
    e.cursorPositionChanged.connect(e.cursor_position_changed)
    e.setPlainText("a\nb\n")
    e.moveCursor(e.textCursor().MoveOperation.End)
    assert e.appels >= 1
    nu = QPlainTextEdit()  # sans nom de l'application, l'alias reste le signal
    vus = []
    nu.cursor_position_changed.connect(lambda: vus.append(1))
    nu.setPlainText("x\n")
    nu.moveCursor(nu.textCursor().MoveOperation.End)
    assert vus


# --- W547 : alias snake_case des signaux (D1, item 3 du TODO Portage) -----------------------------------------------------
def test_alias_signal_et_slot_homonyme(app):
    """L'alias ``text_changed`` est le signal ``textChanged`` (objet et classe) ; une méthode homonyme d'une sous-classe,
    connectée au signal, le masque sans planter (avant D1 : code 139, ``essais/alias_signal_slot.py``) et qtpy6 le dit
    à la définition de la classe."""
    import warnings

    from qtpy6._binding import SignalAliasMasked
    from qtpy6.QtWidgets import QLineEdit

    assert QLineEdit.text_changed is QLineEdit.textChanged
    recus = []
    with warnings.catch_warnings(record=True) as avertis:
        warnings.simplefilter("always")

        class Champ(QLineEdit):
            def __init__(self):
                super().__init__()
                self.textChanged.connect(self.text_changed)

            def text_changed(self, texte):
                recus.append(("slot", texte))

    from qtpy6 import PYSIDE6
    assert [a.category for a in avertis] == ([SignalAliasMasked] if PYSIDE6 else [])  # PyQt6 : pas d'avertissement
    champ, autre = Champ(), QLineEdit()
    autre.text_changed.connect(lambda t: recus.append(("alias", t)))
    champ.setText("abc")
    autre.setText("xyz")
    assert recus == [("slot", "abc"), ("alias", "xyz")]
