"""Jalon 3 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) :
l'exécution du programme de l'élève et la console. Le même script sur le bureau (un vrai QProcess sur SmartPython) et
dans la page (`qtpy6.QtCore.QProcess`, c'est-à-dire `ProcessusWeb` : un Web Worker Pyodide par programme, le Pyodide-Qt
du site en guise d'interpréteur), lancé par `site/index.html?script=jalon3.py` et la sonde avec --pilote.

La fenêtre : le CodeEditor de Spyder (le programme de l'élève) au-dessus, le widget console de Spyder (`ShellBaseWidget`,
celui de la console interne : ANSI, invite, historique) en dessous, relié au processus comme un terminal : ce que le
programme imprime s'y écrit (stderr en rouge), ce que l'élève y tape après une invite part sur son stdin.

Trois programmes, chacun chronométré (et, dans la page, le tas WebAssembly) :
  1. à froid : prints, deux `input()` (réponses tapées au clavier dans la console, par la sonde dans la page), 1 000 lignes,
     une seconde de calcul (la page doit rester réactive : un QTimer de 50 ms mesure son plus long silence), une
     exception (traceback sur stderr) ; mesures : premier octet (boot du worker), aller-retour d'un input, fin ;
  2. préchauffé (`travailleur.prechauffer`, le worker suivant charge Pyodide pendant le calme) : une boucle infinie, tuée
     au bout d'une seconde (`kill`), le seul « Arrêter » du navigateur ; mesures : premier octet, délai du `finished` ;
  3. dans l'interpréteur de la page (`exec`, sans input) : le même programme ; mesure : durée, et la page figée pendant.
État de la page : « jalon3 » pendant le travail, « fini » à la fin (ou « erreur » : l'exception est dans le journal)."""

import base64
import gc
import io
import os
import sys
import tempfile
import time
import traceback

from preparer import ICI, T0, etape

if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
from qtpy.QtCore import QBuffer, QByteArray, QEvent, QIODevice, Qt, QTimer  # noqa: E402
from qtpy.QtGui import QFont, QKeyEvent  # noqa: E402
from qtpy.QtWidgets import QApplication, QMainWindow, QSplitter  # noqa: E402
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
from spyder.plugins.console.widgets.shell import ShellBaseWidget  # noqa: E402
import qtpy6.web  # noqa: E402
from qtpy6.QtCore import QProcess  # noqa: E402  - ProcessusWeb dans la page, le QProcess de Qt sur le bureau

etape("imports")
WEB = sys.platform == "emscripten"
DOSSIER = os.path.join(tempfile.gettempdir(), "jalon3")  # le dossier de l'élève : le seul recopié dans le worker (filtre)
os.makedirs(DOSSIER, exist_ok=True)
PROGRAMME = '''\
import math
print("Bonjour !")
nom = input("Ton nom ? ")
n = int(input("Un entier ? "))
print(f"{nom}, la racine de {n} vaut {math.sqrt(n):.3f}")
for i in range(1000):
    print("ligne", i)
total = sum(i * i for i in range(5_000_000))  # un calcul d'une seconde dans la page : la page doit rester réactive
print("somme", total)


def inverse(x):
    return 1 / x


print(inverse(0))
'''
BOUCLE = 'print("je tourne")\nwhile True:\n    pass\n'
REPONSES = ["Alice", "16"]
if WEB:
    import js  # noqa: E402
    from pyodide.ffi import to_js  # noqa: E402
    from qtpy6.web import travailleur  # noqa: E402
    js.window.etat = "jalon3"  # sinon la page pose « fini » dès le premier rendu
    travailleur.configurer("./pyodide-qt/", filtre=lambda chemin: chemin.startswith(DOSSIER))  # le Pyodide-Qt du site, déjà en cache


def tas():
    if not WEB:
        return ""
    import pyodide_js  # noqa: PLC0415
    return f" ; tas {pyodide_js._module.HEAPU8.length // 1048576} Mio"


def mesure(nom, debut):
    print(f"{nom} : {(time.monotonic() - debut) * 1000:.0f} ms{tas()}")


def touche(widget, c):
    """Une touche sur le bureau : le QKeyEvent qu'un clavier aurait produit (code Qt = ASCII majuscule, Entrée = Return)."""
    cle, texte = (Qt.Key_Return, "\r") if c == "\n" else (Qt.Key(ord(c.upper())), c)
    for genre in (QEvent.KeyPress, QEvent.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(genre, cle, Qt.NoModifier, texte))


class Console(ShellBaseWidget):
    """Le widget console de Spyder en terminal d'un processus : les touches qui, dans la console interne, ouvrent l'aide ou
    la complétion insèrent ici le caractère ; Entrée envoie la ligne tapée (`on_enter`) sur le stdin du processus."""
    INITHISTORY = ["# -*- coding: utf-8 -*-", "# jalon 3"]
    SEPARATOR = f"{os.linesep * 2}##---({time.ctime()})---"

    def __init__(self, parent):
        super().__init__(parent, os.path.join(DOSSIER, "historique.py"))
        self.processus = None

    def on_enter(self, command):
        self.add_to_history(command)
        self.new_input_line = True
        if self.processus is not None:
            self.processus.write((command + "\n").encode())

    def _key_other(self, text):
        pass

    def _key_backspace(self, cursor_position):
        if self.has_selected_text():
            self.check_selection()
            self.remove_selected_text()
        elif self.current_prompt_pos != cursor_position and self.is_cursor_on_last_line():
            self.stdkey_backspace()

    def _key_tab(self):
        self.stdkey_tab()

    def _key_ctrl_space(self):
        pass

    _key_pageup = _key_pagedown = _key_escape = _key_ctrl_space

    def _key_question(self, text):
        self.insert_text(text)

    _key_parenleft = _key_period = _key_question


captures = {}


def capturer(suffixe):
    image = fenetre.grab()
    if WEB:
        octets = QByteArray()
        tampon = QBuffer(octets)
        tampon.open(QIODevice.WriteOnly)
        image.save(tampon, "PNG")
        captures[suffixe] = base64.b64encode(bytes(octets)).decode()
    else:
        image.save(os.path.join(ICI, f"capture_jalon3_bureau_{suffixe}.png"))  # la sonde écrit capture_jalon3_<suffixe>.png


app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))
fenetre = QMainWindow()
partage = QSplitter(Qt.Vertical, fenetre)
editeur = CodeEditor(partage)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename="eleve.py")
editeur.set_text(PROGRAMME)
t = time.monotonic()
console = Console(partage)
console.set_font(QFont("DejaVu Sans Mono", 10))
console.setMaximumBlockCount(5000)  # la console interne de Spyder ne garde que 300 lignes (max_line_count) : trop peu pour la mesure
mesure("console de Spyder créée", t)
partage.addWidget(editeur)
partage.addWidget(console)
partage.setSizes([450, 450])
fenetre.setCentralWidget(partage)
fenetre.setWindowTitle("Jalon 3 : exécution et console dans qtpy6")
if WEB:
    fenetre.showFullScreen()
else:
    fenetre.resize(1000, 900)
    fenetre.show()
t = time.monotonic()
fenetre.grab()
mesure("premier rendu", t)

# La réactivité de la page : un tic toutes les 50 ms, et le plus long silence entre deux.
ecarts, _dernier = [], [time.monotonic()]


def tic():
    t = time.monotonic()
    ecarts.append(t - _dernier[0])
    _dernier[0] = t


horloge = QTimer()
horloge.timeout.connect(tic)
horloge.start(50)


def silence(nom):
    print(f"{nom} : plus long silence de la page {max(ecarts, default=0) * 1000:.0f} ms sur {len(ecarts)} tics")
    del ecarts[:]
    _dernier[0] = time.monotonic()


_activite = [time.monotonic()]  # le dernier événement utile : le chien de garde arrête l'essai après 20 s sans rien


def vivant():
    _activite[0] = time.monotonic()


def chien_de_garde():
    if time.monotonic() - _activite[0] > 20:
        print(f"BLOQUÉ : état {js.window.etat!r}, programme {getattr(L, 'nom', None)}, réponses restantes "
              f"{getattr(L, 'reponses', None)}, fin de la sortie {getattr(L, 'sortie', '')[-60:]!r}")
        js.window.etat = "erreur"


def geste(nom, **valeurs):
    """Demande un geste réel à la sonde (--pilote) et rend le moment de la demande ; `attendre` guette `<nom>_fait`.
    Un seul geste à la fois : l'appelant ne demande le suivant qu'une fois l'état revenu à « jalon3 » (voir `repondre`)."""
    for cle, v in valeurs.items():
        setattr(js.window, cle, to_js(v))
    print(f"geste « {nom} » demandé (état {js.window.etat!r} avant)")
    js.window.etat = nom
    vivant()
    return time.monotonic()



def garde(f):
    """Une étape lancée depuis la boucle d'événements : son exception finit dans le journal et pose l'état « erreur »."""
    def g(*a):
        try:
            f(*a)
        except Exception:
            traceback.print_exc()
            if WEB:
                js.window.etat = "erreur"
            else:
                app.quit()
    return g


@garde
def attendre(nom, suite):
    if js.window.etat == f"{nom}_fait":
        js.window.etat = "jalon3"
        vivant()
        suite()
    else:
        QTimer.singleShot(100, lambda: attendre(nom, suite))


if WEB:  # le chien de garde : 20 s sans événement, l'essai s'arrête en « erreur » avec un diagnostic
    chien = QTimer()
    chien.timeout.connect(garde(chien_de_garde))
    chien.start(5000)


class Lancement:
    """Un programme de l'élève lancé dans un processus relié à la console ; `fini(code)` est appelé à sa fin."""

    def __init__(self, nom, source, fini):
        self.nom, self.fini, self.sortie, self.erreurs = nom, fini, "", ""
        self.reponses = list(REPONSES)
        self.t_input = None
        self.script = os.path.join(DOSSIER, f"{nom}.py")
        with open(self.script, "w", encoding="utf-8") as f:
            f.write(source)
        self.p = QProcess(fenetre)
        self.p.setWorkingDirectory(DOSSIER)
        self.p.readyReadStandardOutput.connect(garde(self.lire))
        self.p.readyReadStandardError.connect(garde(self.lire_erreurs))
        self.p.finished.connect(garde(self.termine))
        console.processus = self.p
        self.t0 = time.monotonic()
        self.p.start(sys.executable, ["-u", self.script])

    def lire(self):
        texte = bytes(self.p.readAllStandardOutput()).decode("utf-8", "replace")
        if not self.sortie:
            mesure(f"{self.nom} : premier octet", self.t0)
        if self.t_input is not None:
            mesure(f"{self.nom} : réponse à input() revenue", self.t_input)
            self.t_input = None
        self.sortie += texte
        console.write(texte)
        vivant()
        if self.reponses:  # tant qu'une saisie est attendue, chaque morceau reçu est journalisé
            print(f"{self.nom} : reçu {texte[-40:]!r}")
        # Dans la page, deux écritures rapprochées du programme (« Bonjour ! », puis l'invite) donnent deux readyRead
        # dont le second ne lit plus rien, comme QProcess peut le faire : un morceau vide n'est jamais une invite neuve.
        if texte and self.sortie.endswith("? ") and self.reponses:
            console.flush()
            QTimer.singleShot(0, garde(self.repondre))

    def lire_erreurs(self):
        texte = bytes(self.p.readAllStandardError()).decode("utf-8", "replace")
        self.erreurs += texte
        console.write_error(texte)

    def repondre(self):
        if WEB and js.window.etat != "jalon3":  # la sonde n'a pas encore acquitté le geste précédent (« taper_fait »
            QTimer.singleShot(50, garde(self.repondre))  # arrive après l'invite suivante) : un seul geste à la fois
            return
        reponse = self.reponses.pop(0)
        self.t_input = time.monotonic()
        if WEB:  # un vrai clic dans la console (le focus), puis la réponse au clavier
            centre = console.viewport().mapToGlobal(console.viewport().rect().center())
            t = geste("cliquer", clic=[centre.x(), centre.y()])
            attendre("cliquer", lambda: (mesure("clic réel", t), geste("taper", texte=reponse + "\n"),
                                         attendre("taper", lambda: None)))  # consomme « taper_fait » : état « jalon3 »
        else:
            console.setFocus()
            for c in reponse + "\n":
                touche(console, c)

    def termine(self, code, *_):
        console.flush()
        vivant()
        mesure(f"{self.nom} : fini (code {code})", self.t0)
        self.fini(code)


@garde
def programme1():
    global L
    L = Lancement("eleve", PROGRAMME, programme1_fini)


def programme1_fini(code):
    silence("programme 1")
    texte = console.toPlainText()
    print("sortie :", "ok" if "Alice, la racine de 16 vaut 4.000" in L.sortie and "ligne 999" in L.sortie
          else f"ÉCART : {L.sortie[:200]!r}")
    print("traceback :", "ok" if "ZeroDivisionError" in L.erreurs and "line 13" in L.erreurs else f"ÉCART : {L.erreurs!r}")
    print(f"console : {texte.count('ligne ')} lignes « ligne », {len(texte.splitlines())} lignes en tout")
    print("saisies dans la console :", "ok" if "Ton nom ? Alice" in texte and "Un entier ? 16" in texte else "ÉCART")
    if WEB:
        travailleur.prechauffer()
        QTimer.singleShot(4000, garde(programme2))  # le moment calme : le worker de réserve charge son Pyodide
    else:
        programme2()


def programme2():
    global L
    console.write("\n")
    L = Lancement("boucle", BOUCLE, programme2_fini)
    QTimer.singleShot(1000, garde(arreter))


def arreter():
    print("boucle : sortie reçue :", "ok" if "je tourne" in L.sortie else f"ÉCART {L.sortie!r}")
    L.t_kill = time.monotonic()
    L.p.kill()


def programme2_fini(code):
    mesure("boucle : finished après kill", L.t_kill)
    silence("programme 2")
    programme3()


def programme3():
    console.write("\n--- dans l'interpréteur de la page ---\n")
    tampon = io.StringIO()
    t = time.monotonic()
    ancien, sys.stdout = sys.stdout, tampon
    try:
        exec(compile(PROGRAMME.replace("input(", "(lambda q: '16')("), "eleve.py", "exec"), {"__name__": "__main__"})
    except ZeroDivisionError:
        tampon.write(traceback.format_exc())
    finally:
        sys.stdout = ancien
    console.write(tampon.getvalue(), flush=True)
    mesure("programme 3 (exec dans la page)", t)
    silence("programme 3")
    fin()


def fin():
    t = time.monotonic()
    gc.collect()
    mesure("gc", t)
    console.set_cursor_position("eof")
    capturer("fin")
    print(f"durée totale du script : {time.monotonic() - T0:.1f} s{tas()}")
    if WEB:
        js.window.captures = to_js(captures, dict_converter=js.Object.fromEntries)
        js.window.etat = "fini"
    else:
        app.quit()


L = None
QTimer.singleShot(0, programme1)
sys.exit(app.exec())
