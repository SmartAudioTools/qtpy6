"""L'exemple de qtpy6.web : le Compteur du README, plus un worker « écho » (un Web Worker Pyodide, ce qui tient
lieu de sous-processus dans le navigateur). ``demarrer()`` est appelé par index.html une fois Pyodide-Qt prêt."""

from qtpy6 import QtCore, QtGui, QtWidgets
from qtpy6.web import application, navigateur
from qtpy6.web.travailleur import Travailleur


class Compteur(QtWidgets.QWidget):
    changed = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        self.set_window_title("Compteur")
        self.total = 0
        self.bouton = QtWidgets.QPushButton("+1")
        self.affichage = QtWidgets.QLabel("0")
        self.echo = QtWidgets.QPlainTextEdit()  # pas d'arguments nommés de propriétés : PyQt6 ne les connaît pas
        self.echo.set_read_only(True)
        self.echo.set_placeholder_text("ce que dit le worker…")
        self.echo.set_font(QtGui.QFontDatabase.system_font(QtGui.QFontDatabase.SystemFont.FixedFont))  # Liberation Mono dans le navigateur
        colonne = QtWidgets.QVBoxLayout(self)
        colonne.add_widget(self.bouton)
        colonne.add_widget(self.affichage)
        colonne.add_widget(self.echo)
        self.bouton.clicked.connect(lambda: self.changed.emit(1))
        self.changed.connect(self.ajouter)

    def ajouter(self, n):
        self.total += n
        self.affichage.set_text(str(self.total))


FENETRE = WORKER = None
PYODIDE_WORKER = "pyodide/"  # le Pyodide du worker, relatif à la page ; « pyodide-qt/ » sous ?sw (index.html)


def dire(texte):
    """Ce qui vient du worker : dans la fenêtre, et dans le journal de la page (sortie sans retour à la ligne comprise)."""
    FENETRE.echo.insert_plain_text(texte)
    print(f"worker : {texte!r}")


def demarrer():
    global FENETRE, WORKER
    app = application(polices="polices", defaut=("Noto Sans", 10))  # les polices d'app.zip : Qt-WASM n'en a aucune
    FENETRE = Compteur()
    if navigateur():
        FENETRE.show_full_screen()  # tout le conteneur de la page
        WORKER = Travailleur(PYODIDE_WORKER, [("app.zip", "/home/pyodide/app")], "echo", parent=FENETRE)  # URL relatives à la page
        WORKER.pret.connect(lambda: dire("worker prêt\n"))
        WORKER.sortie.connect(lambda n, texte: dire(texte))
        WORKER.termine.connect(lambda n, retour: dire(f"retour de l'appel {n} : {retour!r}\n"))
        WORKER.erreur.connect(lambda n, texte: dire(f"erreur de l'appel {n} : {texte}\n"))
        WORKER.expire.connect(lambda n: dire(f"l'appel {n} n'a pas répondu\n"))
        WORKER.appeler("echo", "bonjour", delai=60)
    else:
        FENETRE.show()
    return app


if __name__ == "__main__":  # en natif : la même fenêtre, sans worker
    demarrer().exec()
