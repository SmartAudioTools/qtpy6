"""Hors navigateur, qtpy6.web s'importe et se tient tranquille : rien ne touche à ``js``, QProcess est celui de Qt, la
feuille tactile ne remplace rien, les dispositions se replient. Les doublures du navigateur se vérifient ici en forçant
``sys.platform`` dans un interpréteur neuf ; ce que le navigateur fait vraiment se mesure avec ``python -m qtpy6.web.sonde``
sur ``exemple/`` (web.md)."""

import io
import json
import os
import subprocess
import sys
import textwrap
import time
import zipfile
from pathlib import Path

import pytest
from qtpy6 import QtCore, QtGui, QtWidgets

import qtpy6
from qtpy6 import web
from qtpy6.web import assembler, dispositions, stockage, tactile, travailleur

RACINE = Path(__file__).resolve().parents[1]
POLICE_FIXE = Path("/usr/share/fonts/liberation/LiberationMono-Regular.ttf")


def test_inerte_en_natif():
    assert not web.navigateur()
    assert "js" not in sys.modules or sys.platform == "emscripten"
    assert QtCore.QProcess is not travailleur.ProcessusWeb
    assert not hasattr(QtGui, "_application_families")  # systemFont est celui de Qt
    assert not tactile.detecte()


def test_application_offscreen(app):
    assert QtWidgets.QApplication.instance() is app
    assert web.application() is app  # idempotente


def test_tactile_detecte_en_natif(app, monkeypatch):
    """Un écran tactile parmi les périphériques de Qt : détecté ; une souris et un pavé tactile : non (sans écran branché ici,
    les périphériques sont simulés)."""
    D = QtGui.QInputDevice.DeviceType
    appareils = lambda *types: [type("Appareil", (), {"type": lambda _, t=t: t})() for t in types]  # noqa: E731
    monkeypatch.setattr(QtGui.QInputDevice, "devices", lambda: appareils(D.Mouse, D.TouchPad))
    assert not tactile.detecte()
    monkeypatch.setattr(QtGui.QInputDevice, "devices", lambda: appareils(D.Mouse, D.TouchScreen))
    assert tactile.detecte()


def test_feuille_tactile_concatenee(app):
    app.set_style_sheet("QLabel { color: red; }")
    try:
        assert tactile.marge() == 2
        tactile.activer(app, cible=44)
        assert tactile.ACTIF and app.style_sheet().startswith("QLabel { color: red; }")
        assert "min-height: 44px" in app.style_sheet()
        assert tactile.marge() == (44 - 26) // 2
    finally:
        tactile.ACTIF = False
        app.set_style_sheet("")


def test_rangee_se_replie(app):
    zone = QtWidgets.QWidget()
    rangee = dispositions.Rangee(6)
    zone.set_layout(rangee)
    for i in range(6):
        rangee.add_widget(QtWidgets.QPushButton("Bouton %d" % i))
    assert rangee.heightForWidth(200) > rangee.heightForWidth(1000)  # étroite : plusieurs lignes (camelCase : le
    # snake_case de PySide6 appelle ici la méthode de base, qui rend -1)
    boutons = zone.find_children(QtWidgets.QPushButton)
    fixe = boutons[0].sizeHint().width()
    for b in boutons[1:]:
        b.set_size_policy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    rangee.setGeometry(QtCore.QRect(0, 0, 1000, 100))
    largeurs = [b.geometry().width() for b in boutons]
    assert largeurs[0] == fixe and len(set(largeurs[1:-1])) == 1, largeurs  # parts égales, le reste au dernier
    assert boutons[-1].geometry().right() == 999, "les extensibles n'occupent pas toute la ligne"


def test_rangee_ressort_et_espacement(app):
    """Qt tient tout QSpacerItem pour vide : la rangée ne doit pas les sauter pour autant."""
    zone = QtWidgets.QWidget()
    rangee = dispositions.Rangee(6)
    zone.set_layout(rangee)
    a, b, c = (QtWidgets.QPushButton(t) for t in "abc")
    rangee.add_widget(a)
    rangee.addStretch()
    rangee.add_widget(b)
    rangee.addSpacing(20)
    rangee.add_widget(c)
    rangee.setGeometry(QtCore.QRect(0, 0, 1000, 100))
    assert a.geometry().x() == 0 and c.geometry().right() == 999, "le ressort ne pousse pas la suite à droite"
    assert c.geometry().x() - b.geometry().right() - 1 == 6 + 20 + 6, "l'espacement fixe est ignoré"


def test_rangee_recalcule_apres_changement(app):
    """La hauteur par largeur est gardée en cache : un item caché ou qui s'élargit doit la faire recalculer."""
    zone = QtWidgets.QWidget()
    rangee = dispositions.Rangee(6)
    zone.set_layout(rangee)
    boutons = [QtWidgets.QPushButton("B") for _ in range(4)]
    for b in boutons:
        rangee.add_widget(b)
    une_ligne = rangee.heightForWidth(400)
    for b in boutons:
        b.set_text("Un bouton bien plus large")
    assert rangee.heightForWidth(400) > une_ligne, "le texte élargi ne replie pas la rangée : cache périmé"
    for b in boutons[1:]:
        b.hide()
    assert rangee.heightForWidth(400) == une_ligne, "les boutons cachés comptent encore : cache périmé"

def test_rangee_elargir(app):
    """``elargir`` : les extensibles gardent leur largeur et reçoivent chacun la même part de la place libre (celle
    qu'un ressort entre deux leur aurait laissée entre eux) ; un item non extensible garde la sienne."""
    zone = QtWidgets.QWidget()
    rangee = dispositions.Rangee(6, elargir=True)
    zone.set_layout(rangee)
    boutons = [QtWidgets.QPushButton(t) for t in ("A", "Un bouton large", "B")]
    for b in boutons:
        b.set_size_policy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        rangee.add_widget(b)
    fixe = QtWidgets.QLabel("fixe")
    rangee.add_widget(fixe)
    rangee.setGeometry(QtCore.QRect(0, 0, 1000, 100))
    ajouts = [b.geometry().width() - b.sizeHint().width() for b in boutons]
    assert max(ajouts) - min(ajouts) <= 1 and min(ajouts) > 100, ajouts
    assert fixe.geometry().width() == fixe.sizeHint().width() and fixe.geometry().right() == 999


def test_versions_json():
    v = json.loads((RACINE / "qtpy6" / "web" / "versions.json").read_text())
    assert {"pyodide_qt", "pyodide"} <= set(v) and v["pyodide_qt"]["abi"].startswith("cp")


def test_assembler(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    zip_ = tmp_path / "app.zip"
    assembler.assembler(zip_, fichiers={"a.py": tmp_path / "a.py"}, paquets=("qtpy6",))
    noms = zipfile.ZipFile(zip_).namelist()
    assert "a.py" in noms and "qtpy6/web/js/travailleur.js" in noms and "qtpy6/web/versions.json" in noms
    assert "qtpy6/web/js/pdfjs/pdf.min.mjs" in noms and "qtpy6/web/js/pdfjs/pdf.worker.min.mjs" in noms
    assert not any("__pycache__" in n for n in noms)



def test_construire_avec_une_roue(tmp_path):
    from qtpy6.web.construire import construire
    (tmp_path / "app").mkdir()
    (tmp_path / "app/app.py").write_text("x = 1\n")
    roue = tmp_path / "ext-1.0-cp313-cp313-pyemscripten_2025_0_wasm32.whl"
    roue.write_bytes(b"PK")
    construire(tmp_path / "app/app.py", tmp_path / "site", roues=[roue])
    page = (tmp_path / "site/index.html").read_text()
    assert f'roues: ["./{roue.name}"],' in page and (tmp_path / "site" / roue.name).read_bytes() == b"PK"
    construire(tmp_path / "app/app.py", tmp_path / "site2")
    assert "roues: []," in (tmp_path / "site2/index.html").read_text()

def test_stockage_hors_navigateur():
    with pytest.raises(ModuleNotFoundError):  # le module s'importe en natif ; ses fonctions, elles, veulent le navigateur
        stockage.lire("cle")


def en_navigateur(code):
    """``code`` dans un interpréteur neuf où ``sys.platform`` est celui de Pyodide AVANT l'import de qtpy6 : ce que voient
    les doublures de QtCore et QtGui (le reste de Qt est celui de la machine). Rend la sortie."""
    entete = "import sys\nsys.platform = 'emscripten'\n"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API=qtpy6.API,  # la liaison des tests, dans le sous-processus aussi
               PYTHONPATH=os.pathsep.join(filter(None, [str(RACINE), os.environ.get("PYTHONPATH")])))
    r = subprocess.run([sys.executable, "-c", entete + textwrap.dedent(code)], env=env, capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_qprocess_doublé_dans_le_navigateur():
    sortie = en_navigateur("""
        from qtpy6.QtCore import QProcess
        from qtpy6.web.travailleur import ProcessusWeb
        print(QProcess is ProcessusWeb, hasattr(QProcess, "read_all_standard_output"))
    """)
    assert sortie == "True True"  # et le snake_case de qtpy6 lui est donné comme au vrai


def test_pdf_doublé_dans_le_navigateur():
    sortie = en_navigateur("""
        from qtpy6.QtPdf import QPdfDocument
        from qtpy6.QtPdfWidgets import QPdfView
        print(QPdfDocument.__module__, QPdfView.__module__, hasattr(QPdfView, "set_document"), "js" in sys.modules)
    """)
    assert sortie == "qtpy6.web.pdf qtpy6.web.pdf True False"  # js n'est chargé qu'à la première vue


def test_pdf_selection_en_natif(app, tmp_path):
    """Le QPdfView de qtpy6 sélectionne au glisser et copie par Ctrl+C, même en partant de la marge (le point est
    accroché à la ligne la plus proche : QPdfDocument.getSelection ne sélectionne rien entre deux points hors texte)."""
    from qtpy6.QtPdf import QPdfDocument
    from qtpy6.QtPdfWidgets import QPdfView
    from qtpy6.QtTest import QTest

    chemin = str(tmp_path / "cours.pdf")
    ecrivain = QtGui.QPdfWriter(chemin)
    peintre = QtGui.QPainter(ecrivain)
    peintre.setFont(QtGui.QFont("DejaVu Sans", 14))
    for i, ligne in enumerate(("Premiere ligne du cours", "Deuxieme ligne du cours")):
        peintre.drawText(600, 1200 + 600 * i, ligne)
    peintre.end()
    document = QPdfDocument(None)
    document.load(chemin)
    vue = QPdfView(None)
    vue.setDocument(document)
    vue.setZoomMode(QPdfView.ZoomMode.FitToWidth)
    vue.resize(400, 600)
    vue.show()
    page = vue._pages()[0]
    Bouton = QtCore.Qt.MouseButton
    QTest.mousePress(vue.viewport(), Bouton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, page.topLeft() + QtCore.QPoint(2, 2))
    QTest.mouseMove(vue.viewport(), page.topLeft() + QtCore.QPoint(page.width() - 2, page.height() // 3))
    QTest.mouseRelease(vue.viewport(), Bouton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, page.topLeft() + QtCore.QPoint(page.width() - 2, page.height() // 3))
    QTest.keyClick(vue, QtCore.Qt.Key.Key_C, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert QtWidgets.QApplication.clipboard().text().split() == "Premiere ligne du cours Deuxieme ligne du cours".split()
    vue.close()


def test_pdf_limite_de_pages_en_natif(app, tmp_path):
    """``setPageLimit`` : la barre de défilement s'arrête au bas de la dernière page montrée, et quand les pages
    montrées finissent plus haut que la vue, la suite est recouverte du fond."""
    from qtpy6.QtPdf import QPdfDocument
    from qtpy6.QtPdfWidgets import QPdfView

    chemin = str(tmp_path / "cours.pdf")
    ecrivain = QtGui.QPdfWriter(chemin)
    peintre = QtGui.QPainter(ecrivain)
    for i in range(4):
        if i:
            ecrivain.newPage()
        peintre.fillRect(0, 0, 9000, 13000, QtGui.QColor("red"))  # des pages rouges : un pixel rouge est une page vue
    peintre.end()
    document = QPdfDocument(None)
    document.load(chemin)
    vue = QPdfView(None)
    vue.setDocument(document)
    vue.setPageMode(QPdfView.PageMode.MultiPage)
    vue.setZoomMode(QPdfView.ZoomMode.FitToWidth)
    vue.resize(300, 400)
    vue.show()
    app.processEvents()
    barre = vue.verticalScrollBar()
    toutes = barre.maximum()
    vue.setPageLimit(2)
    app.processEvents()
    assert 0 < barre.maximum() < toutes
    barre.setValue(barre.maximum())
    assert vue._pages()[1].bottom() + 1 + vue.documentMargins().bottom() == vue.viewport().height()
    vue.resize(300, 390)  # Qt refait la mise en page, et la plage de la barre : elle reste bornée
    app.processEvents()
    barre.setValue(barre.maximum())
    assert vue._pages()[1].bottom() + 1 + vue.documentMargins().bottom() == vue.viewport().height()
    vue.setPageLimit(1)
    vue.resize(300, 1000)  # la première page finit plus haut que la vue : la deuxième, dessous, est recouverte
    app.processEvents()
    bas, attente = vue._pages()[0].bottom(), QtCore.QDeadlineTimer(10000)
    while not attente.hasExpired():  # les pages se dessinent dans un fil à part : on attend la première
        app.processEvents()
        image = vue.viewport().grab().toImage()
        rouges = [y for y in range(image.height()) if image.pixelColor(150, y).red() > 200 and image.pixelColor(150, y).green() < 80]
        if rouges:
            break
    assert rouges and max(rouges) <= bas  # la première page est dessinée, la suivante recouverte
    vue.setPageLimit(None)
    app.processEvents()
    assert barre.maximum() == 0 or barre.maximum() >= toutes - 1
    vue.close()


def test_pdf_lien_seul_sur_sa_ligne(app, tmp_path):
    """Un lien interne seul sur sa ligne se suit d'un clic n'importe où sur la ligne (un sommaire), pas seulement sur
    son texte ; deux liens sur une même ligne gardent chacun le leur."""
    from qtpy6.QtPdf import QPdfDocument
    from qtpy6.QtPdfWidgets import QPdfView

    chemin = str(tmp_path / "sommaire.pdf")
    texte = QtGui.QTextDocument()
    texte.set_html('<p><a href="#c">Court</a></p><p><a href="#c">Un</a> et <a href="#c">deux</a></p>'
                   + "<p>x</p>" * 80 + '<p><a name="c">Cible</a></p>' + "<p>x</p>" * 80)
    texte.print_(QtGui.QPdfWriter(chemin)) if hasattr(texte, "print_") else texte.print(QtGui.QPdfWriter(chemin))
    document = QPdfDocument(None)
    document.load(chemin)
    vue = QPdfView(None)
    vue.setDocument(document)
    vue.setPageMode(QPdfView.PageMode.MultiPage)
    vue.setZoomMode(QPdfView.ZoomMode.FitToWidth)
    vue.resize(400, 500)
    vue.show()
    app.processEvents()
    page = vue._pages()[0]
    echelle = page.width() / document.pagePointSize(0).width()
    largeur = document.pagePointSize(0).width()
    liens = [r for _, r, _ in vue._link_areas(0)]
    assert len(liens) == 3, liens
    court, un, deux = sorted(liens, key=lambda r: (r.top(), r.left()))

    def lien(x, rectangle):
        return vue._link(page.topLeft() + QtCore.QPoint(round(x * echelle), round(rectangle.center().y() * echelle)))

    assert lien(court.center().x(), court) is not None, "le texte du lien n'est plus cliquable"
    assert lien(largeur - court.left() - 2, court) is not None, "le bout de la ligne d'un lien seul n'est pas cliquable"
    assert lien(largeur - un.left() - 2, deux) is None, "deux liens sur une ligne : le bout de la ligne est devenu cliquable"
    assert lien(un.center().x(), un) is not None and lien(deux.center().x(), deux) is not None
    cible = lien(court.center().x(), court)
    vue._follow(cible)
    haut = vue._pages()[cible.page()].top() + cible.location().y() * echelle  # la destination, dans la vue
    assert abs(haut - QPdfView.LINK_MARGIN * echelle) <= 1, f"la destination est à {haut} px du haut de la vue"
    vue.verticalScrollBar().setValue(0)

    def plus_sombre():  # le pixel le plus sombre du texte de « Court »
        image = vue.viewport().grab().toImage()
        return min(image.pixelColor(page.left() + round(x * echelle), page.top() + round(court.center().y() * echelle)).lightness()
                   for x in range(round(court.left()), round(court.right())))

    fin = time.monotonic() + 10  # QPdfView rend ses pages en arrière-plan
    while (avant := plus_sombre()) > 250 and time.monotonic() < fin:
        app.processEvents()
    vue.setPageLimit(1)  # la cible est plus loin : le lien ne se suit plus, et un voile blanc l'éclaircit
    app.processEvents()
    assert {page for _, _, page in vue._link_areas(0)} == {cible.page()} and cible.page() > 0
    assert lien(court.center().x(), court) is None
    assert plus_sombre() > avant + 30, (avant, plus_sombre())
    vue.close()


def test_pdf_document_enfant_de_la_vue(tmp_path):
    """Un document enfant de sa vue ne fait plus planter la sortie (Qt 6.10 : ~QPdfView atteint le document déjà
    détruit) ; dans un processus à part, le plantage emportant tout."""
    chemin = tmp_path / "cours.pdf"
    code = f"""
        from qtpy6 import QtGui, QtWidgets
        app = QtWidgets.QApplication([])
        from qtpy6.QtPdf import QPdfDocument
        from qtpy6.QtPdfWidgets import QPdfView
        ecrivain = QtGui.QPdfWriter({str(chemin)!r})
        peintre = QtGui.QPainter(ecrivain)
        peintre.drawText(600, 1200, "Cours")
        peintre.end()
        vue = QPdfView()
        document = QPdfDocument(vue)
        document.load({str(chemin)!r})
        vue.setDocument(document)
        vue.show()
        app.processEvents()
        print(document.pageCount())
    """
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], env=env, capture_output=True, text=True,
                       timeout=60)
    assert (r.returncode, r.stdout.strip()) == (0, "1"), r.stderr


def test_subprocess_run_doublé_dans_le_navigateur():
    sortie = en_navigateur("""
        import subprocess
        from qtpy6 import QtCore
        from qtpy6.web import sous_processus
        for lancer in (subprocess.run, subprocess.check_call):  # check_call passe par call, doublé aussi
            try:
                lancer(["hg", "id"])
            except FileNotFoundError as e:
                print(e.filename, end=" ")
        print(subprocess.run is sous_processus.run)
    """)
    assert sortie == "hg hg True"  # seul Python se lance ; un autre programme est « absent », comme sur un bureau


def test_zipper_chemins_depuis_la_racine_sans_doublon(tmp_path):
    import zipfile  # noqa: PLC0415

    from qtpy6.web.travailleur import _zipper  # noqa: PLC0415

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"")
    (tmp_path / "sous").mkdir()
    (tmp_path / "vide").mkdir()  # le dossier temporaire que le parent crée pour l'enfant
    (tmp_path / "a.py").write_text("")
    (tmp_path / "sous" / "b.txt").write_text("")
    noms = zipfile.ZipFile(io.BytesIO(_zipper([tmp_path, tmp_path / "sous"]))).namelist()
    racine = os.path.relpath(tmp_path, "/")
    assert sorted(noms) == [f"{racine}/", f"{racine}/a.py", f"{racine}/sous/", f"{racine}/sous/b.txt", f"{racine}/vide/"]


@pytest.mark.skipif(not POLICE_FIXE.exists(), reason="Liberation Mono absente")
def test_police_fixe_dans_le_navigateur():
    sortie = en_navigateur(f"""
        import types
        # application() branche Ctrl+V sur la page (_coller) : js et pyodide.ffi réduits à ce qu'il en touche
        sys.modules["js"] = types.SimpleNamespace(document=types.SimpleNamespace(addEventListener=lambda *a: None),
                                                  setInterval=lambda *a: 0,  # la pompe de QtCore, inerte ici
                                                  Function=types.SimpleNamespace(new=lambda *a: lambda *b: None))  # _dessiner_aussitot
        sys.modules["pyodide"], sys.modules["pyodide.ffi"] = types.ModuleType("pyodide"), types.SimpleNamespace(create_proxy=lambda f: f)
        from qtpy6.QtGui import QFontDatabase
        from qtpy6.web import application
        app = application(defaut=("Noto Sans", 9))  # sans dossier : aucune police chargée
        avant = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        QFontDatabase.addApplicationFont("/usr/share/fonts/noto/NotoSans-Regular.ttf")  # pas à chasse fixe : sautée
        QFontDatabase.add_application_font({str(POLICE_FIXE)!r})
        police = QFontDatabase.system_font(QFontDatabase.SystemFont.FixedFont)
        print(avant != "Liberation Mono", police.family(), police.point_size())
    """)
    assert sortie == "True Liberation Mono 9"



def test_coller_passe_par_qt():
    """Le collage du navigateur passe par un Ctrl+V de Qt : un filtre d'événements de l'application le voit, et peut
    l'interdire (il insérait le texte directement : SmartTeacher, 02/10/2026)."""
    sortie = en_navigateur("""
        import types
        ecouteurs = {}
        sys.modules["js"] = types.SimpleNamespace(
            document=types.SimpleNamespace(addEventListener=lambda nom, f, *a: ecouteurs.setdefault(nom, f)),
            setInterval=lambda *a: 0, Function=types.SimpleNamespace(new=lambda *a: lambda *b: None))
        sys.modules["pyodide"], sys.modules["pyodide.ffi"] = types.ModuleType("pyodide"), types.SimpleNamespace(create_proxy=lambda f: f)
        from qtpy6.QtCore import QEvent, QObject
        from qtpy6.QtGui import QKeySequence
        from qtpy6.QtWidgets import QLineEdit
        from qtpy6.web import application
        app = application()
        champ = QLineEdit()
        champ.show()
        champ.activateWindow()
        champ.setFocus()
        app.processEvents()

        def coller(texte):
            evenement = types.SimpleNamespace(clipboardData=types.SimpleNamespace(getData=lambda _: texte),
                                              preventDefault=lambda: None, stopPropagation=lambda: None)
            ecouteurs["paste"](evenement)
            return champ.text()

        class Garde(QObject):
            def eventFilter(self, objet, evenement):
                return evenement.type() == QEvent.Type.KeyPress and evenement.matches(QKeySequence.StandardKey.Paste)

        print(coller("a"), end=" ")
        garde = Garde()
        app.installEventFilter(garde)
        print(coller("b"))
    """)
    assert sortie == "a a"

# --- Les doublures bloquantes, hors navigateur ------------------------------------------------------------------------
# JSPI n'existe pas ici : les primitives Pyodide de ``bloquant`` sont remplacées par des greenlets, qui suspendent
# une pile d'appels Python et la reprennent plus tard dans le même ordre que JSPI (pas en pile, comme des boucles
# QEventLoop imbriquées). Une entrée « promettante » (le script principal, une tâche asyncio) est un greenlet ; la boucle
# Qt tourne dans le greenlet principal, où rien ne peut suspendre. ``can_run_sync`` y ment comme dans le navigateur :
# True partout dès qu'une pile est suspendue.

SIMULATION = """
    import greenlet, time
    from %s.QtCore import QEventLoop as _Boucle, QCoreApplication as _App, QEvent as _Evt  # la liaison des tests, avant les doublures de qtpy6
    from qtpy6.web import bloquant
    _page, _en_attente, _taches = greenlet.getcurrent(), [], []

    def _entree(f):
        g = greenlet.greenlet(f, parent=_page)
        g.switch()
        return g

    def _pyodide_suspendre(brancher):
        g = greenlet.getcurrent()
        assert g is not _page, "run_sync hors entrée promettante : dans le navigateur, il ne reprendrait jamais"
        fait = []
        def resoudre(v=None):
            if not fait:
                fait.append(v)
                _taches.append(lambda: g.switch(v))
        brancher(resoudre)
        _en_attente.append(g)
        try:
            return _page.switch()
        finally:
            _en_attente.remove(g)

    bloquant._pyodide_peut = lambda: greenlet.getcurrent() is not _page or bool(_en_attente)
    bloquant._pyodide_suspendre = _pyodide_suspendre
    bloquant._pyodide_plus_tard = _taches.append

    def _vivre(fin):  # la page qui vit, comme la pompe du navigateur (_pyodide_pomper) : Qt tourne par processEvents,
        # les deleteLater passent hors de toute pile suspendue, et les tâches asyncio (reprise d'une entrée suspendue,
        # _plus_tard) passent ENTRE deux tours de Qt, jamais depuis un de ses rappels : c'est là que JSPI les reprend
        while not fin():
            _App.processEvents(_Boucle.ProcessEventsFlag.AllEvents, 10)
            if not _en_attente:  # comme la pompe du navigateur (_pyodide_pomper) : les deleteLater, hors de toute boucle exec()
                _App.sendPostedEvents(None, _Evt.Type.DeferredDelete)
            while _taches:
                _entree(_taches.pop(0))
            time.sleep(0.001)

    def tourner(ms=100):  # la page qui vit, hors de toute entrée promettante
        fin = time.monotonic() + ms / 1000
        _vivre(lambda: time.monotonic() >= fin)

    def principal(f):  # le script principal, lancé par runPythonAsync : la page vit jusqu'à ce qu'il rende
        retour = []
        g = _entree(lambda: retour.append(f()))
        _vivre(lambda: g.dead)
        return retour[0]

    from qtpy6.QtWidgets import QApplication
    app = QApplication([])
"""


greenlet_seul = pytest.mark.skipif(not __import__("importlib.util").util.find_spec("greenlet"), reason="greenlet imite JSPI")


def simule(code):
    return en_navigateur(textwrap.dedent(SIMULATION % qtpy6.API_NAME) + textwrap.dedent(code))


@greenlet_seul
def test_slot_reporte_garde_expediteur_et_arguments():
    sortie = simule("""
        from qtpy6.QtCore import QObject, Signal
        class A(QObject):
            s = Signal(int, str)
        class B(QObject):
            def recu(self, n):  # un argument sur deux : PyQt tronque, le relais aussi
                print("recu", n, self.sender() is a)
        a, b = A(), B()
        a.s.connect(b.recu)
        vus = []
        a.s.connect(lambda *args: vus.append(args))
        a.s.emit(1, "x")  # émis hors entrée promettante : reporté
        print("apres emit", vus)
        tourner()
        print(vus)
        a.s.disconnect(b.recu)
        a.s.emit(2, "y")
        tourner()
    """)
    assert sortie.splitlines() == ["apres emit []", "recu 1 True", "[(1, 'x')]"]


@greenlet_seul
def test_slot_direct_garde_expediteur():
    # Émis dans une entrée promettante, le slot est appelé tout de suite : sender() y vaut aussi, sinon un slot partagé par
    # deux boutons (les flèches « question non traitée » de SmartTeacher) ne sait pas lequel a été cliqué.
    sortie = simule("""
        from qtpy6.QtCore import QObject, Signal
        class A(QObject):
            s = Signal()
        class B(QObject):
            def recu(self):
                print("recu", "a1" if self.sender() is a1 else "a2" if self.sender() is a2 else self.sender())
        a1, a2, b = A(), A(), B()
        a1.s.connect(b.recu)
        a2.s.connect(b.recu)
        principal(lambda: (a1.s.emit(), a2.s.emit()))
    """)
    assert sortie.splitlines() == ["recu a1", "recu a2"]


@greenlet_seul
def test_animation_par_image_survit_au_slot_reporte():
    # Lancée hors entrée promettante, le « Running » de start() atteint _etat après la pause intérieure : l'animation doit
    # quand même aller au bout (la descente vers une question de SmartTeacher restait figée à 0).
    sortie = simule("""
        from qtpy6.QtCore import QPropertyAnimation
        from qtpy6.QtWidgets import QScrollBar
        barre = QScrollBar()
        barre.setRange(0, 1000)
        barre.show()
        a = QPropertyAnimation(barre, b"value", duration=50, startValue=0, endValue=800)
        a.start()
        tourner(400)
        print(barre.value(), a.state().name)
    """)
    assert sortie.strip() == "800 Stopped"


@greenlet_seul
def test_un_coup_de_minuterie_est_un_slot():
    sortie = simule("""
        from qtpy6.QtCore import QTimer
        from qtpy6.QtWidgets import QMessageBox
        def question():
            b = QMessageBox(QMessageBox.Icon.Question, "Q", "?", QMessageBox.StandardButton.Yes)
            QTimer.singleShot(30, lambda: b.done(7))
            print("rendu", b.exec())
        QTimer.singleShot(0, question)
        tourner(300)
    """)
    assert sortie.strip() == "rendu 7"


@greenlet_seul
def test_relais_comme_une_connexion_native():
    sortie = simule("""
        import gc, weakref
        from qtpy6.QtCore import QObject, QTimer, Qt, Signal
        from qtpy6.QtWidgets import QMenu
        class O(QObject):
            s = Signal()
        class Gros: pass
        # le relais vit tant que la connexion, pas plus : la lambda meurt avec l'expéditeur
        g, n = Gros(), []
        temoin = weakref.ref(g)
        o = O()
        o.s.connect(lambda g=g: n.append(1))
        del g
        gc.collect()
        principal(o.s.emit)
        o.deleteLater(); del o; tourner(); gc.collect()
        print("vivant puis libere", n, temoin() is None)
        # un doublon (UniqueConnection) a le sort que la liaison lui fait en natif : refusé (PyQt6 : TypeError),
        # ou ignoré (PySide6 : une seule connexion, et aucune pour une fonction), pour une méthode comme pour une lambda
        from qtpy6.web import bloquant
        class R(QObject):
            def g(self): n.append(2)
        def doublon(connecter, slot):
            o, n[:] = O(), []
            try:
                for _ in range(2):
                    connecter(o.s, slot, Qt.ConnectionType.UniqueConnection)
            except TypeError as e:
                return str(e)
            o.s.emit(); tourner(10)  # le relais diffère l'appel
            return len(n)
        natif, relaye, r = bloquant._connect_qt[0], type(O().s).connect, R()
        print("doublon comme en natif", [doublon(relaye, s) == doublon(natif, s) for s in (lambda: n.append(1), r.g)],
              repr(doublon(natif, lambda: n.append(1))), repr(doublon(natif, r.g)))
        # un menu qui resert n'empile pas ses connexions
        m = QMenu(); m.addAction("a")
        def ouvrir():
            QTimer.singleShot(30, m.hide); m.exec()
        for _ in range(3):
            principal(ouvrir)
        from qtpy6 import PYQT6
        print("aboutToHide", m.receivers(m.aboutToHide if PYQT6 else "2aboutToHide()"))
    """)
    doublons = {"pyqt6": "'connection is not unique' 'connection is not unique'", "pyside6": "0 1"}[qtpy6.API]
    assert sortie.splitlines() == ["vivant puis libere [1] True", f"doublon comme en natif [True, True] {doublons}", "aboutToHide 0"]


@greenlet_seul
def test_boites_suspendues_dans_un_slot():
    sortie = simule("""
        from qtpy6.QtCore import QTimer
        from qtpy6.QtWidgets import QDialog, QInputDialog, QMenu, QMessageBox, QPushButton
        B = QMessageBox.StandardButton
        def modale():
            return QApplication.activeModalWidget()
        def clic():
            QTimer.singleShot(30, lambda: modale().button(B.No).click())
            print("question", QMessageBox.question(None, "t", "Continuer ?") == B.No)
            def saisir():
                modale().setTextValue("abc")
                modale().accept()
            QTimer.singleShot(30, saisir)
            print("texte", QInputDialog.getText(None, "t", "Nom"))
            QTimer.singleShot(30, lambda: modale().reject())
            print("entier", QInputDialog.getInt(None, "t", "n", 7))
            d = QDialog()
            QTimer.singleShot(30, lambda: d.done(5))
            print("dialogue", d.exec())
            menu = QMenu()
            un, deux = menu.addAction("un"), menu.addAction("deux")
            def choisir():
                deux.trigger()
                menu.hide()
            QTimer.singleShot(30, choisir)
            print("menu", menu.exec(bouton.pos()) is deux)
        bouton = QPushButton()
        bouton.clicked.connect(clic)
        def main():  # le clic arrive pendant que app.exec() est suspendu : can_run_sync y ment
            QTimer.singleShot(0, bouton.click)
            QTimer.singleShot(1000, app.quit)
            return app.exec()
        principal(main)
        print("hors slot", QDialog().exec())
    """)
    assert sortie.splitlines() == ["question True", "texte ('abc', True)", "entier (7, False)", "dialogue 5",
                                   "menu True", "hors slot 0"]


@greenlet_seul
def test_exec_de_l_application_et_lancer(tmp_path):
    script = tmp_path / "app.py"
    script.write_text(textwrap.dedent("""
        import sys
        from qtpy6.QtCore import QTimer
        from qtpy6.QtWidgets import QApplication, QLabel
        app = QApplication.instance() or QApplication(sys.argv)
        app.aboutToQuit.connect(lambda: print("aboutToQuit"))
        fenetre = QLabel("bonjour")
        fenetre.show()
        QTimer.singleShot(50, lambda: app.exit(3))
        sys.exit(app.exec())
    """))
    sortie = simule(f"""
        from qtpy6.web import lancer
        print("code", principal(lambda: lancer({str(script)!r}, ["-v"], pret=lambda: print("pret"))))
        import sys
        print(sys.argv)
    """)
    assert sortie.splitlines() == ["pret", "aboutToQuit", "code 3", f"[{str(script)!r}, '-v']"]


def test_point_d_entree(tmp_path):
    from qtpy6.web.lanceur import point_d_entree

    def zip_(nom, *fichiers):
        d = tmp_path / nom
        for f in fichiers:
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            (d / f).write_text("")
        try:
            script, module = point_d_entree(d, nom)
            return str(script.relative_to(d)), module
        except ValueError as e:
            return str(e).split(" :")[0]

    assert zip_("a", "__main__.py", "p/__main__.py") == ("__main__.py", None)
    assert zip_("b", "p/__init__.py", "p/__main__.py", "outil.py") == ("p/__main__.py", "p")
    assert zip_("c", "depot-main/p/__init__.py", "depot-main/p/__main__.py") == ("depot-main/p/__main__.py", "p")
    assert zip_("d", "jeu/jeu.py", "jeu/images/fond.png") == ("jeu/jeu.py", None)
    assert zip_("e", "e.py", "outils.py") == ("e.py", None)
    assert zip_("f", "seul.py", "LISEZMOI.md") == ("seul.py", None)
    assert zip_("g", "p/__main__.py", "q/__main__.py") == "plusieurs points d'entrée possibles"
    assert zip_("p", "p/__main__.py", "q/__main__.py") == ("p/__main__.py", "p")  # le nom du zip départage
    assert zip_("h", "un.py", "deux.py") == "aucun point d'entrée"


@greenlet_seul
def test_lanceur_zip_de_paquet(tmp_path):
    archive = tmp_path / "depot.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("depot-main/monpaquet/__init__.py", "MESSAGE = 'relatif'\n")
        z.writestr("depot-main/monpaquet/__main__.py", textwrap.dedent("""
            import sys
            from . import MESSAGE
            from qtpy6.QtCore import QTimer
            from qtpy6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            print(__name__, __package__, MESSAGE, sys.argv[1:], sys.argv[0].endswith("monpaquet/__main__.py"))
            QTimer.singleShot(0, app.quit)
            sys.exit(app.exec())
        """))
    sortie = simule(f"""
        from qtpy6.web.lanceur import executer
        print("code", principal(lambda: executer({str(archive)!r}, ["donnees.txt"])))
    """)
    assert sortie.splitlines() == ["point d'entrée : -m monpaquet", "__main__ monpaquet relatif ['donnees.txt'] True",
                                   "code 0"]


@greenlet_seul
def test_fils_cooperatifs():
    sortie = simule("""
        from qtpy6.QtCore import QObject, Signal
        from qtpy6.web import fils
        ns = {"QObject": QObject, "Signal": Signal}
        fils.doubler(ns)  # Qt natif a les siens : ceux du navigateur, à part
        QThread, QThreadPool, QRunnable = ns["QThread"], ns["QThreadPool"], ns["QRunnable"]
        QMutex, QMutexLocker, QSemaphore, QWaitCondition = ns["QMutex"], ns["QMutexLocker"], ns["QSemaphore"], ns["QWaitCondition"]
        journal = []

        class Travail(QObject):
            fini = Signal(int)
            def calculer(self):
                for i in range(3):
                    journal.append(f"t{i}")
                    QThread.msleep(20)
                self.fini.emit(42)

        def main():
            fil, travail = QThread(), Travail()
            fil.started.connect(travail.calculer)
            travail.fini.connect(lambda n: (journal.append(f"fini {n}"), fil.quit()))
            fil.start()
            for i in range(3):
                journal.append(f"m{i}")
                QThread.msleep(20)
            print("wait", fil.wait(2000), fil.isFinished())
            pool = QThreadPool.globalInstance()
            for k in range(3):
                pool.start(QRunnable.create(lambda k=k: (QThread.msleep(10), journal.append(f"p{k}"))))
            print("pool", pool.waitForDone(2000), pool.activeThreadCount())
            m, cond, pret = QMutex(), QWaitCondition(), []
            def attendeur():
                with QMutexLocker(m):
                    while not pret:
                        cond.wait(m)
                    journal.append("reveil")
            QThreadPool.globalInstance().start(attendeur)
            QThread.msleep(30)
            with QMutexLocker(m):
                pret.append(1)
                cond.wakeAll()
            QThreadPool.globalInstance().waitForDone(1000)
        principal(main)
        print(journal)
        for bloque in (QSemaphore(0).acquire, QMutexLocker(QMutex()).mutex().lock):  # le verrou, pris deux fois
            try:
                bloque()
            except RuntimeError:
                print("interblocage signalé")
    """)
    lignes = sortie.splitlines()
    assert lignes[:2] == ["wait True True", "pool True 0"]
    journal = eval(lignes[2])  # noqa: S307
    assert journal.index("t1") < journal.index("m2") and journal.index("m1") < journal.index("t2")  # entrelacés
    assert {"fini 42", "p0", "p1", "p2", "reveil"} <= set(journal) and journal[-1] == "reveil"
    assert lignes[3:] == ["interblocage signalé"] * 2


def test_accept_du_selecteur_de_fichiers():
    from qtpy6.web.bloquant import _accept
    assert _accept("Images (*.png *.jpg);;Textes (*.txt)") == ".png,.jpg,.txt"
    assert _accept("Images (*.png);;Tout (*)") == ""
    assert _accept("") == ""
    assert _accept("*.tar.gz") == ".tar.gz"
