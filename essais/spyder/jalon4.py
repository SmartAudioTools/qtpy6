"""Jalon 4 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) : la
complétion, par jedi en direct (sans serveur de langage), dans le widget de complétion de Spyder lui-même. Même script sur le
bureau et dans la page (construire_site.py, puis la sonde avec --pilote).

Deux moteurs, le même fichier `jalon4_jedi.py` : A, jedi importé dans l'interpréteur de la page (la complétion bloque la
page le temps du calcul) ; B, jedi dans un Worker (`qtpy6.QtCore.QProcess`, ProcessusWeb dans la page, serveur JSON sur
stdin/stdout — sur le bureau, un vrai QProcess sur SmartPython). Les réponses entrent par le flux de Spyder : `do_completion`
→ `sig_perform_completion_request` → le moteur → `handle_response(DOCUMENT_COMPLETION)` → `completion_widget.show_list`.

Mesures, sur le fichier de 2 000 lignes du jalon 2 : pour A puis B, trois requêtes (os.pa : typeshed de la stdlib ;
CodeEditor.set : la classe du fichier et ses bases importées ; "".up : builtins), la première à froid puis répétée à chaud,
avec le plus long silence de la page et le tas ; le Worker à froid et préchauffé. Puis le geste réel avec B : clic dans
l'éditeur, « os.pat » tapé (la complétion automatique de Spyder se déclenche sur le « . »), la liste affichée (capture
« liste »), Entrée qui insère « path » (capture « fin »). État de la page : « jalon4 » pendant le travail, « fini » à la fin
(ou « erreur » : l'exception est dans le journal)."""

import base64
import gc
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

from preparer import ICI, T0, etape

if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
import spyder  # noqa: E402
from qtpy.QtCore import QBuffer, QByteArray, QEvent, QIODevice, Qt, QTimer  # noqa: E402
from qtpy.QtGui import QFont, QKeyEvent, QTextCursor  # noqa: E402
from qtpy.QtWidgets import QApplication, QMainWindow  # noqa: E402
from spyder.plugins.completion.api import CompletionRequestTypes  # noqa: E402
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
import qtpy6.web  # noqa: E402
from qtpy6.QtCore import QProcess  # noqa: E402  - ProcessusWeb dans la page, le QProcess de Qt sur le bureau

etape("imports")
WEB = sys.platform == "emscripten"
LIGNES = 2000
DOSSIER = os.path.join(tempfile.gettempdir(), "jalon4")  # le seul dossier recopié dans le worker (filtre) : le serveur jedi
os.makedirs(DOSSIER, exist_ok=True)
SERVEUR = shutil.copy(os.path.join(ICI, "jalon4_jedi.py"), DOSSIER)
REQUETES = [("os.pa", "path"), ("CodeEditor.set", "setup_editor"), ('"".up', "upper")]  # texte ajouté en fin de fichier, item attendu
SAISIE = "\nimport os\nos.pat"
if WEB:
    import js  # noqa: E402
    from pyodide.ffi import to_js  # noqa: E402
    from qtpy6.web import travailleur  # noqa: E402
    js.window.etat = "jalon4"  # sinon la page pose « fini » dès le premier rendu
    travailleur.configurer("./pyodide-qt/", roues=list(js.window.roues),  # le Pyodide-Qt du site ; jedi et parso, les
                           filtre=lambda chemin: chemin.startswith(DOSSIER))  # roues de la page (construire_site.py)


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
        image.save(os.path.join(ICI, f"capture_jalon4_bureau_{suffixe}.png"))  # la sonde écrit capture_jalon4_<suffixe>.png


app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))
fenetre = QMainWindow()
editeur = CodeEditor(fenetre)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename="codeeditor.py")
source = os.path.join(os.path.dirname(spyder.__file__), "plugins", "editor", "widgets", "codeeditor", "codeeditor.py")
with open(source, encoding="utf-8") as f:
    TEXTE = "\n".join(f.read().splitlines()[:LIGNES]) + "\n"
editeur.set_text(TEXTE)
fenetre.setCentralWidget(editeur)
fenetre.setWindowTitle("Jalon 4 : complétion dans qtpy6")
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


_activite = [time.monotonic()]  # le dernier événement utile : le chien de garde arrête l'essai après 30 s sans rien
ETAPE = ["début"]


def vivant(nom=None):
    _activite[0] = time.monotonic()
    if nom:
        ETAPE[0] = nom


def chien_de_garde():
    if time.monotonic() - _activite[0] > 30:
        print(f"BLOQUÉ : état {js.window.etat!r}, étape {ETAPE[0]!r}, widget de complétion visible "
              f"{editeur.completion_widget.isVisible()}, dernière ligne {editeur.toPlainText().splitlines()[-1]!r}")
        js.window.etat = "erreur"


def geste(nom, **valeurs):
    """Demande un geste réel à la sonde (--pilote) et rend le moment de la demande ; `attendre` guette `<nom>_fait`.
    Un seul geste à la fois : le suivant n'est demandé qu'une fois l'état revenu à « jalon4 » (`attendre`)."""
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
        js.window.etat = "jalon4"
        vivant()
        suite()
    else:
        QTimer.singleShot(100, lambda: attendre(nom, suite))


@garde
def des_que(condition, suite, nom):
    """Appelle `suite` dès que `condition()` est vraie (sondée toutes les 50 ms) ; le chien de garde borne l'attente."""
    vivant(nom)
    if condition():
        suite()
    else:
        QTimer.singleShot(50, lambda: des_que(condition, suite, nom))


if WEB:  # le chien de garde : 30 s sans événement, l'essai s'arrête en « erreur » avec un diagnostic
    chien = QTimer()
    chien.timeout.connect(garde(chien_de_garde))
    chien.start(5000)


class MoteurA:
    """jedi dans l'interpréteur de la page : la réponse est immédiate, et la page bloquée pendant ce temps."""
    nom = "A (page)"

    def __init__(self, pret):
        deja = "jedi" in sys.modules  # Spyder l'importe lui-même (introspection) : l'import est alors déjà payé
        t = time.monotonic()
        import jalon4_jedi  # noqa: PLC0415
        self.completer_ = jalon4_jedi.completer
        mesure(f"A : import de jalon4_jedi (jedi {'déjà importé' if deja else f'importé en {jalon4_jedi.IMPORT_MS} ms'})", t)
        QTimer.singleShot(0, pret)  # après le retour du constructeur : MOTEUR[0] est alors posé

    def completer(self, code, ligne, colonne, suite):
        t, n = time.monotonic(), len(sys.modules)
        items = self.completer_(code, ligne, colonne)
        if len(sys.modules) > n:  # le coût caché de A : jedi importe, dans l'interpréteur de l'éditeur, ce que le fichier nomme
            print(f"A : {len(sys.modules) - n} modules importés dans l'éditeur par cette complétion")
        suite(items, round((time.monotonic() - t) * 1000))

    def arreter(self):
        pass


class MoteurB:
    """jedi dans un Worker (ProcessusWeb) ou, sur le bureau, un processus SmartPython : `jalon4_jedi.py` en serveur JSON."""
    nom = "B (Worker)"

    def __init__(self, pret):
        self.pret, self.attentes, self.tampon, self.n = pret, {}, "", 0
        self.p = QProcess(fenetre)
        self.p.setWorkingDirectory(DOSSIER)
        self.p.readyReadStandardOutput.connect(garde(self.lire))
        self.p.readyReadStandardError.connect(garde(self.lire_erreurs))
        self.p.finished.connect(lambda code, *_: print(f"B : serveur fini (code {code})"))
        self.t0 = time.monotonic()
        self.p.start(sys.executable, ["-u", SERVEUR])

    def completer(self, code, ligne, colonne, suite):
        self.n += 1
        self.attentes[self.n] = suite
        self.p.write((json.dumps({"id": self.n, "code": code, "ligne": ligne, "colonne": colonne}) + "\n").encode())

    def lire(self):
        self.tampon += bytes(self.p.readAllStandardOutput()).decode("utf-8", "replace")
        *lignes, self.tampon = self.tampon.split("\n")  # une réponse peut arriver en plusieurs morceaux
        for ligne in lignes:
            if not ligne.strip():
                continue
            d = json.loads(ligne)
            vivant()
            if "pret" in d:
                mesure(f"B : serveur prêt (import de jedi {d['pret']} ms)", self.t0)
                self.pret()
            else:
                self.attentes.pop(d["id"])(d["items"], d["ms"])

    def lire_erreurs(self):
        print("B : stderr :", bytes(self.p.readAllStandardError()).decode("utf-8", "replace"))

    def arreter(self):
        self.p.kill()
        if not WEB:
            self.p.waitForFinished(1000)  # sinon Qt se plaint d'un QProcess détruit en cours de route à la sortie


# Les requêtes directes, hors widget : la même liste de trois, à froid puis à chaud, par moteur.
MOTEUR = [None]


def serie(moteur, suite):
    """Les trois requêtes de REQUETES sur `moteur`, la première jouée deux fois (froid, chaud), puis `suite`."""
    restantes = [(0, "à froid"), (0, "à chaud"), (1, ""), (2, "")]

    @garde
    def prochaine():
        if not restantes:
            silence(f"{moteur.nom} : série")
            suite()
            return
        i, etat = restantes.pop(0)
        ajout, attendu = REQUETES[i]
        code = TEXTE + ajout
        ligne, colonne = code.count("\n") + 1, len(ajout)
        vivant(f"{moteur.nom} {ajout}")
        t = time.monotonic()

        def recu(items, ms):
            noms = [x["label"] for x in items]
            print(f"{moteur.nom} : {ajout!r} {etat} : {len(items)} items en {ms} ms (aller-retour "
                  f"{(time.monotonic() - t) * 1000:.0f} ms){tas()} :", "ok" if attendu in noms else f"ÉCART, {noms[:8]}")
            QTimer.singleShot(0, prochaine)

        moteur.completer(code, ligne, colonne, recu)

    prochaine()


# Le flux de Spyder : la requête de l'éditeur part vers le moteur, la réponse revient par handle_response.
editeur.completions_available = True  # ce que start_completion_services pose : sans lui, do_completion n'émet rien
requetes_widget = []


@garde
def requete(langue, methode, params):
    if methode != CompletionRequestTypes.DOCUMENT_COMPLETION:
        return  # didOpen, didChange, symboles, pliage… : pas de serveur de langage ici
    t = time.monotonic()
    requetes_widget.append(t)

    def recu(items, ms):
        mesure(f"widget : réponse à la requête {len(requetes_widget)} ({len(items)} items, jedi {ms} ms)", t)
        editeur.handle_response(methode, {"params": items})

    MOTEUR[0].completer(editeur.toPlainText(), params["line"] + 1, params["column"], recu)


editeur.sig_perform_completion_request.connect(requete)


def liste_visible():
    w = editeur.completion_widget
    return w.isVisible() and any(x["label"] == "path" for x in w.completion_list or ())


@garde
def moteur_a():
    MOTEUR[0] = MoteurA(lambda: serie(MOTEUR[0], moteur_b_froid))


@garde
def moteur_b_froid():
    MOTEUR[0] = MoteurB(lambda: serie(MOTEUR[0], moteur_b_prechauffe))


@garde
def moteur_b_prechauffe():
    MOTEUR[0].arreter()
    if WEB:
        travailleur.prechauffer(["jedi", "parso"])
        QTimer.singleShot(6000, garde(moteur_b_2))  # le moment calme : le worker de réserve charge Pyodide, jedi et parso
    else:
        moteur_b_2()


@garde
def moteur_b_2():
    MOTEUR[0] = MoteurB(lambda: serie(MOTEUR[0], geste_reel))


@garde
def geste_reel():
    editeur.moveCursor(QTextCursor.End)  # sur le bureau ; dans la page, le clic réel qui donne le focus déplace le curseur
    centre = editeur.viewport().mapToGlobal(editeur.viewport().rect().center())
    del requetes_widget[:]
    if WEB:
        t = geste("cliquer", clic=[centre.x(), centre.y()])
        attendre("cliquer", lambda: (mesure("clic réel", t), geste("taper", texte=SAISIE), attendre("taper", liste)))
    else:
        editeur.setFocus()
        for c in SAISIE:
            touche(editeur, c)
        liste()


@garde
def liste():
    t = time.monotonic()
    des_que(liste_visible, lambda: liste_affichee(t), "liste de complétion attendue")


@garde
def liste_affichee(t):
    w = editeur.completion_widget
    mesure(f"liste affichée après la frappe ({len(requetes_widget)} requêtes, {len(w.completion_list)} items)", t)
    capturer("liste")
    if WEB:
        geste("taper", texte="\n")
        attendre("taper", insere)
    else:
        touche(w, "\n")
        insere()


@garde
def insere():
    ligne = editeur.textCursor().block().text().strip()  # le clic réel a placé le curseur où il est tombé, pas à la fin
    print("insertion :", "ok" if ligne == "os.path" else f"ÉCART, ligne du curseur {ligne!r}")
    silence("geste réel")
    fin()


def fin():
    MOTEUR[0].arreter()
    t = time.monotonic()
    gc.collect()
    mesure("gc", t)
    capturer("fin")
    print(f"durée totale du script : {time.monotonic() - T0:.1f} s{tas()}")
    if WEB:
        js.window.captures = to_js(captures, dict_converter=js.Object.fromEntries)
        js.window.etat = "fini"
    else:
        app.quit()


QTimer.singleShot(0, moteur_a)
sys.exit(app.exec())
