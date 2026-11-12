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
