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
