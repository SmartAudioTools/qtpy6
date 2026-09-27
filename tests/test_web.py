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

def test_versions_json():
    v = json.loads((RACINE / "qtpy6" / "web" / "versions.json").read_text())
    assert {"pyodide_qt", "pyodide"} <= set(v) and v["pyodide_qt"]["abi"].startswith("cp")


def test_assembler(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    zip_ = tmp_path / "app.zip"
    assembler.assembler(zip_, fichiers={"a.py": tmp_path / "a.py"}, paquets=("qtpy6",))
    noms = zipfile.ZipFile(zip_).namelist()
    assert "a.py" in noms and "qtpy6/web/js/travailleur.js" in noms and "qtpy6/web/versions.json" in noms
    assert not any("__pycache__" in n for n in noms)


def test_stockage_hors_navigateur():
    with pytest.raises(ModuleNotFoundError):  # le module s'importe en natif ; ses fonctions, elles, veulent le navigateur
        stockage.lire("cle")


def en_navigateur(code):
    """``code`` dans un interpréteur neuf où ``sys.platform`` est celui de Pyodide AVANT l'import de qtpy6 : ce que voient
    les doublures de QtCore et QtGui (le reste de Qt est celui de la machine). Rend la sortie."""
    entete = "import sys\nsys.platform = 'emscripten'\n"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
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


# --- Les doublures bloquantes, hors navigateur ------------------------------------------------------------------------
# JSPI n'existe pas ici : les primitives Pyodide de ``bloquant`` sont remplacées par des greenlets, qui suspendent
# une pile d'appels Python et la reprennent plus tard dans le même ordre que JSPI (pas en pile, comme des boucles
# QEventLoop imbriquées). Une entrée « promettante » (le script principal, une tâche asyncio) est un greenlet ; la boucle
# Qt tourne dans le greenlet principal, où rien ne peut suspendre. ``can_run_sync`` y ment comme dans le navigateur :
# True partout dès qu'une pile est suspendue.

SIMULATION = """
    import os
    os.environ["QT_API"] = "pyqt6"  # quelle que soit la liaison des tests : Pyodide-Qt est PyQt6
    import greenlet
    from PyQt6.QtCore import QEventLoop as _Boucle, QTimer as _Minuteur, QCoreApplication as _App
    _exec, _quit, _un_coup = _Boucle.exec, _Boucle.quit, _Minuteur.singleShot  # avant les doublures de qtpy6
    from qtpy6.web import bloquant
    _page, _en_attente = greenlet.getcurrent(), []

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
                _un_coup(0, lambda: g.switch(v))
        brancher(resoudre)
        _en_attente.append(g)
        try:
            return _page.switch()
        finally:
            _en_attente.remove(g)

    bloquant._pyodide_peut = lambda: greenlet.getcurrent() is not _page or bool(_en_attente)
    bloquant._pyodide_suspendre = _pyodide_suspendre
    bloquant._pyodide_plus_tard = lambda f: _un_coup(0, lambda: _entree(f))

    def tourner(ms=100):  # la page qui vit, hors de toute entrée promettante
        boucle = _Boucle()
        _un_coup(ms, lambda: _quit(boucle))
        _exec(boucle)

    def principal(f):  # le script principal, lancé par runPythonAsync : la page vit jusqu'à ce qu'il rende
        retour = []
        g = _entree(lambda: retour.append(f()))
        while not g.dead:
            _App.processEvents(_Boucle.ProcessEventsFlag.WaitForMoreEvents)
        return retour[0]

    from qtpy6.QtWidgets import QApplication
    app = QApplication([])
"""


pyqt6_seul = pytest.mark.skipif(not all(__import__("importlib.util").util.find_spec(m) for m in ("PyQt6", "greenlet")),
                                reason="Pyodide-Qt est PyQt6 : les doublures ne sont posées que là ; greenlet imite JSPI")


def simule(code):
    return en_navigateur(textwrap.dedent(SIMULATION) + textwrap.dedent(code))


@pyqt6_seul
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


@pyqt6_seul
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


@pyqt6_seul
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
        # un doublon est refusé comme en natif
        o, f = O(), lambda: None
        o.s.connect(f, Qt.ConnectionType.UniqueConnection)
        try:
            o.s.connect(f, Qt.ConnectionType.UniqueConnection)
        except TypeError as e:
            print(e)
        # un menu qui resert n'empile pas ses connexions
        m = QMenu(); m.addAction("a")
        def ouvrir():
            QTimer.singleShot(30, m.hide); m.exec()
        for _ in range(3):
            principal(ouvrir)
        print("aboutToHide", m.receivers(m.aboutToHide))
    """)
    assert sortie.splitlines() == ["vivant puis libere [1] True", "connection is not unique", "aboutToHide 0"]


@pyqt6_seul
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


@pyqt6_seul
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


@pyqt6_seul
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


@pyqt6_seul
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
