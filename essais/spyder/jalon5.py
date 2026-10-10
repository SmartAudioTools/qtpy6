"""Jalon 5 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) : les
fichiers de l'élève — écrits, retrouvés après un rechargement de la page, ouverts depuis son disque, enregistrés vers son
disque — par les appels mêmes de Spyder (`spyder.utils.encoding.read/write`, ce qu'appellent EditorStack.load/save, et
`QFileDialog.getOpenFileName/getSaveFileName`). Même script sur le bureau et dans la page (construire_site.py, puis la
sonde avec --pilote, deux gestes de plus : « fichier » et « recharger »).

Deux phases. 1 : le dossier de l'élève (`DOSSIER`, dans la page monté dans IndexedDB par qtpy6), deux fichiers écrits puis
persistés, une retouche persistée, et le rechargement de la page (sur le bureau, la phase 2 suit dans le même processus).
2 : les fichiers retrouvés et relus à l'identique, l'un posé dans le CodeEditor (capture « relu ») ; un clic réel ; «
ouvrir » (dans la page, qtpy6 ouvre le sélecteur de fichiers du navigateur, que la sonde remplit ; sur le bureau, le dialogue
Qt est accepté par une minuterie) ; « enregistrer sous » (dans la page, qtpy6 demande le nom — Entrée tapée — puis télécharge
le fichier dès qu'il est écrit ; mesuré par un espion sur `stockage.telecharger`). Capture « fin ».

Rien n'est propre au web ici hors instrumentation (état de la page, journal, captures, témoin de phase) depuis la doublure
`application(persistant=DOSSIER)` (10/10/2026) : elle remplace `dossier_persistant` et `persister`, les deux branches du
premier jet (le manque de qtpy6, chiffré au jalon : montage 15 ms, copie 2–3 ms). État de la
page : « jalon5 » pendant le travail, « fini » à la fin (ou « erreur » : l'exception est dans le journal)."""

import base64
import gc
import os
import sys
import tempfile
import time
import traceback

from preparer import ICI, T0, etape

if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
import spyder  # noqa: E402
from qtpy.QtCore import QBuffer, QByteArray, QIODevice, QTimer  # noqa: E402
from qtpy.QtGui import QFont  # noqa: E402
from qtpy.QtWidgets import QApplication, QFileDialog, QLineEdit, QMainWindow  # noqa: E402
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
from spyder.utils import encoding  # noqa: E402
import qtpy6.web  # noqa: E402

etape("imports")
WEB = sys.platform == "emscripten"
LIGNES = 2000
DOSSIER = os.path.join(tempfile.gettempdir(), "jalon5")  # le dossier de l'élève
DISQUE = os.path.join(tempfile.gettempdir(), "jalon5_disque")  # sur le bureau, « son disque » : d'où vient le fichier ouvert
TELEVERSE = ("televerse.py", "def televerse():\n    return 'é'\n")  # le fichier que l'élève ouvre
RENDU = "rendu.py"  # le fichier qu'il enregistre sous
RETOUCHE = "# retouche\n"
JOURNAL = []  # ce que la phase 1 a dit, à faire passer par-dessus le rechargement (window.journal repart vide)
telechargements = []
if WEB:
    import js  # noqa: E402
    from pyodide.ffi import to_js  # noqa: E402
    from qtpy6.web import stockage  # noqa: E402 - instrumentation (témoin de phase, espion) et manque de qtpy6 (plus bas)
    js.window.etat = "jalon5"  # sinon la page pose « fini » dès le premier rendu
    _telecharger = stockage.telecharger

    def espion(nom, contenu, *a, **k):
        telechargements.append((nom, len(contenu)))
        _telecharger(nom, contenu, *a, **k)

    stockage.telecharger = espion


def dire(*mots):
    ligne = " ".join(str(m) for m in mots)
    print(ligne)
    JOURNAL.append(ligne)


def tas():
    if not WEB:
        return ""
    import pyodide_js  # noqa: PLC0415
    return f" ; tas {pyodide_js._module.HEAPU8.length // 1048576} Mio"


def mesure(nom, debut):
    dire(f"{nom} : {(time.monotonic() - debut) * 1000:.0f} ms{tas()}")


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
        image.save(os.path.join(ICI, f"capture_jalon5_bureau_{suffixe}.png"))  # la sonde écrit capture_jalon5_<suffixe>.png


# --- L'éditeur. Le dossier de l'élève survit à la fermeture : qtpy6 s'en charge (`persistant`), l'éditeur n'en sait rien. ---

t = time.monotonic()
app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10), persistant=DOSSIER)
mesure(f"application prête, dossier de l'élève : {len(os.listdir(DOSSIER))} fichiers retrouvés", t)
fenetre = QMainWindow()
editeur = CodeEditor(fenetre)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename="exercice1.py")
source = os.path.join(os.path.dirname(spyder.__file__), "plugins", "editor", "widgets", "codeeditor", "codeeditor.py")
with open(source, encoding="utf-8") as f:
    TEXTE = "\n".join(f.read().splitlines()[:LIGNES]) + "\n"
FICHIERS = {"exercice1.py": TEXTE, "notes.txt": "Notes de l'élève : é à ù — ligne 1\nligne 2\n"}
ATTENDU = {**FICHIERS, "exercice1.py": TEXTE + RETOUCHE}  # après la retouche de la phase 1
fenetre.setCentralWidget(editeur)
fenetre.setWindowTitle("Jalon 5 : fichiers dans qtpy6")
if WEB:
    fenetre.showFullScreen()
else:
    fenetre.resize(1000, 900)
    fenetre.show()

_activite = [time.monotonic()]  # le dernier événement utile : le chien de garde arrête l'essai après 30 s sans rien
ETAPE = ["début"]


def vivant(nom=None):
    _activite[0] = time.monotonic()
    if nom:
        ETAPE[0] = nom


def chien_de_garde():
    if time.monotonic() - _activite[0] > 30:
        dire(f"BLOQUÉ : état {js.window.etat!r}, étape {ETAPE[0]!r}")
        js.window.etat = "erreur"


def geste(nom, **valeurs):
    """Demande un geste réel à la sonde (--pilote) et rend le moment de la demande ; `attendre` guette `<nom>_fait`."""
    for cle, v in valeurs.items():
        setattr(js.window, cle, to_js(v, dict_converter=js.Object.fromEntries))
    dire(f"geste « {nom} » demandé")
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
        js.window.etat = "jalon5"
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


def accepter(chemin, essais=50):
    """Sur le bureau : le dialogue de fichiers de Qt (modal, hors écran) reçoit `chemin` et est accepté — ce que la sonde fait
    dans la page par les gestes « fichier » et « taper »."""
    d = QApplication.activeModalWidget()
    if isinstance(d, QFileDialog):
        d.setDirectory(os.path.dirname(chemin))  # selectFile() ne remplit pas le champ quand il a le focus (code de Qt) :
        d.findChild(QLineEdit, "fileNameEdit").setText(os.path.basename(chemin))  # le champ, comme l'utilisateur
    if isinstance(d, QFileDialog) and d.selectedFiles() == [chemin]:
        d.accept()
    elif essais:
        QTimer.singleShot(100, lambda: accepter(chemin, essais - 1))
    else:
        dire(f"ÉCART : pas de QFileDialog modal avec {chemin} sélectionné (actif : {d!r})")


if WEB:  # le chien de garde : 30 s sans événement, l'essai s'arrête en « erreur » avec un diagnostic
    chien = QTimer()
    chien.timeout.connect(garde(chien_de_garde))
    chien.start(5000)
PHASE = 2 if WEB and stockage.lire("jalon5") else 1


# --- Phase 1 : écrire, persister, recharger. ---

@garde
def ecrire():
    for nom in os.listdir(DOSSIER):  # un essai précédent (le dossier lui-même reste : dans la page, c'est le montage)
        os.remove(os.path.join(DOSSIER, nom))
    for nom, texte in FICHIERS.items():
        t = time.monotonic()
        encoding.write(texte, os.path.join(DOSSIER, nom))
        mesure(f"{nom} écrit ({len(texte)} caractères)", t)
    t = time.monotonic()
    encoding.write(ATTENDU["exercice1.py"], os.path.join(DOSSIER, "exercice1.py"))
    mesure("exercice1.py retouché", t)
    if WEB:
        stockage.ecrire("jalon5", "\n".join(JOURNAL))  # le témoin de phase, et le journal par-dessus le rechargement
        geste("recharger")
    else:
        relire()


# --- Phase 2 : retrouver, ouvrir, enregistrer. ---

@garde
def reprise():
    for ligne in stockage.lire("jalon5").splitlines():
        print("phase 1 |", ligne)
    stockage.effacer("jalon5")
    relire()


@garde
def relire():
    dire("fichiers retrouvés :", sorted(os.listdir(DOSSIER)))
    for nom, attendu in ATTENDU.items():
        t = time.monotonic()
        texte, codage = encoding.read(os.path.join(DOSSIER, nom))
        mesure(f"{nom} relu ({codage})", t)
        dire(f"{nom} :", "ok" if texte == attendu else f"ÉCART, {len(texte)} caractères au lieu de {len(attendu)}")
    t = time.monotonic()
    editeur.set_text(encoding.read(os.path.join(DOSSIER, "exercice1.py"))[0])
    fenetre.grab()
    mesure("exercice1.py posé dans l'éditeur, rendu", t)
    capturer("relu")
    centre = editeur.viewport().mapToGlobal(editeur.viewport().rect().center())
    if WEB:  # c'est le clic réel qui donne le focus clavier au canevas de Qt dans la page (l'Entrée de « enregistrer sous »)
        t = geste("cliquer", clic=[centre.x(), centre.y()])
        attendre("cliquer", lambda: (mesure("clic réel", t), ouvrir()))
    else:
        ouvrir()


@garde
def ouvrir():
    """« Ouvrir » : QFileDialog.getOpenFileName, l'appel de Spyder ; dans la page, le sélecteur de fichiers du navigateur
    (doublure de qtpy6), que la sonde remplit ; sur le bureau, le dialogue Qt, accepté sur le fichier du « disque »."""
    nom, texte = TELEVERSE
    if WEB:
        geste("fichier", fichier={"nom": nom, "texte": texte})
    else:
        os.makedirs(DISQUE, exist_ok=True)
        encoding.write(texte, os.path.join(DISQUE, nom))
        QTimer.singleShot(200, lambda: accepter(os.path.join(DISQUE, nom)))
    t = time.monotonic()
    chemin, _ = QFileDialog.getOpenFileName(fenetre, "Ouvrir", DOSSIER, "Python (*.py)",
                                            options=QFileDialog.Option.DontUseNativeDialog)
    mesure(f"ouvrir : {chemin!r}", t)
    lu, _ = encoding.read(chemin)
    dire("ouvert :", "ok" if lu == texte else f"ÉCART, {lu!r}")
    editeur.set_text(lu)
    if WEB:  # la page reprend sur l'événement du sélecteur, AVANT que la sonde n'ait répondu « fichier_fait » : l'attendre,
        attendre("fichier", enregistrer)  # sinon cette réponse écraserait le geste suivant
    else:
        enregistrer()


@garde
def enregistrer():
    """« Enregistrer sous » : QFileDialog.getSaveFileName puis encoding.write, l'appel de Spyder ; dans la page, qtpy6 demande
    le nom (Entrée : celui proposé) et télécharge le fichier dès qu'il est écrit ; sur le bureau, le dialogue Qt accepté."""
    texte = editeur.toPlainText() + "# enregistré\n"
    propose = os.path.join(DOSSIER, RENDU)
    if WEB:
        geste("taper", texte="\n")
    else:
        QTimer.singleShot(200, lambda: accepter(propose))
    t = time.monotonic()
    chemin, _ = QFileDialog.getSaveFileName(fenetre, "Enregistrer sous", propose, "Python (*.py)",
                                            options=QFileDialog.Option.DontUseNativeDialog)
    mesure(f"enregistrer sous : {chemin!r}", t)
    if WEB:  # même attente que pour « fichier » : l'Entrée tapée a fermé le dialogue avant la réponse « taper_fait »
        attendre("taper", lambda: ecrire_rendu(chemin, texte))
    else:
        ecrire_rendu(chemin, texte)


@garde
def ecrire_rendu(chemin, texte):
    t = time.monotonic()
    encoding.write(texte, chemin)
    des_que(lambda: telechargements or not WEB, lambda: telecharge(t, chemin, texte), "téléchargement attendu")


@garde
def telecharge(t, chemin, texte):
    if WEB:
        nom, taille = telechargements[0]
        mesure(f"téléchargé : {nom} ({taille} octets)", t)
        dire("téléchargement :", "ok" if (nom, taille) == (RENDU, len(texte.encode())) else "ÉCART")
    else:
        dire("téléchargement : sans objet sur le bureau, le fichier est sur le disque")
    lu, _ = encoding.read(chemin)
    dire("enregistré :", "ok" if lu == texte else "ÉCART")
    fin()


def fin():
    t = time.monotonic()
    gc.collect()
    mesure("gc", t)
    capturer("fin")
    dire(f"durée totale du script : {time.monotonic() - T0:.1f} s{tas()}")
    if WEB:
        js.window.captures = to_js(captures, dict_converter=js.Object.fromEntries)
        js.window.etat = "fini"
    else:
        app.quit()


QTimer.singleShot(0, ecrire if PHASE == 1 else reprise)
sys.exit(app.exec())
