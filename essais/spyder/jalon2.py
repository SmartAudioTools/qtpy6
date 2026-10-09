"""Jalon 2 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) : la
frappe et l'édition réelle dans la page, sur un fichier de 2 000 lignes (les 2 000 premières de codeeditor.py du fork),
et la mémoire après usage. Le même script sur le bureau et dans la page (construire_site.py, puis la sonde avec --pilote,
qui fait les gestes réels que la page demande : un clic dans l'éditeur, puis la saisie au clavier). Sur le bureau, les
touches sont des QKeyEvent envoyés à l'éditeur, ce qui donne le coût propre de Spyder, à comparer à la page.

Étapes, chacune chronométrée (et, dans la page, le tas WebAssembly) : texte posé, premier rendu, clic réel, saut à la
fin, frappe de trois lignes (indentation automatique et fermeture des parenthèses de Spyder comprises), annulation,
sélection de tout puis au clavier (Maj+Bas × 50), pliage (plages calculées par `ast`, là où Spyder les reçoit du serveur
de langage : `_update_folding_info`) d'une classe, puis gc et tas final. Deux captures : « plie » et « fin ».
État de la page : « jalon2 » pendant le travail, « fini » à la fin (ou « erreur » : l'exception est dans le journal)."""

import ast
import base64
import gc
import os
import sys
import time
import traceback

from preparer import ICI, T0, etape

if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
import spyder  # noqa: E402
from qtpy.QtCore import QBuffer, QByteArray, QEvent, QIODevice, Qt, QTimer  # noqa: E402
from qtpy.QtGui import QFont, QKeyEvent, QTextCursor  # noqa: E402
from qtpy.QtWidgets import QApplication, QMainWindow  # noqa: E402
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
import qtpy6.web  # noqa: E402

etape("imports")
WEB = sys.platform == "emscripten"
LIGNES = 2000
SAISIE = "\ndef jalon2(x):\nreturn x * 2\n"  # après « : » + Entrée, Spyder indente seul ; « ( » ferme seul, « ) » le remplace
ATTENDU = ["def jalon2(x):", "    return x * 2"]
if WEB:
    import js  # noqa: E402
    from pyodide.ffi import to_js  # noqa: E402
    js.window.etat = "jalon2"  # sinon la page pose « fini » dès le premier rendu


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


def plis(texte):
    """Les plages de pliage qu'un serveur de langage enverrait (LSP foldingRange, lignes à partir de 0) : chaque bloc
    composé de plus d'une ligne, par `ast`."""
    arbre = ast.parse(texte)
    return [{"startLine": n.lineno - 1, "endLine": n.end_lineno - 1} for n in ast.walk(arbre)
            if hasattr(n, "body") and hasattr(n, "lineno") and n.end_lineno > n.lineno]


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
        image.save(os.path.join(ICI, f"capture_jalon2_bureau_{suffixe}.png"))  # la sonde écrit capture_jalon2_<suffixe>.png


app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))
fenetre = QMainWindow()
editeur = CodeEditor(fenetre)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename="codeeditor.py")
source = os.path.join(os.path.dirname(spyder.__file__), "plugins", "editor", "widgets", "codeeditor", "codeeditor.py")
with open(source, encoding="utf-8") as f:
    TEXTE = "\n".join(f.read().splitlines()[:LIGNES]) + "\n"
t = time.monotonic()
editeur.set_text(TEXTE)
mesure(f"texte de {LIGNES} lignes posé", t)
fenetre.setCentralWidget(editeur)
fenetre.setWindowTitle("Jalon 2 : édition dans qtpy6")
changements = []
editeur.textChanged.connect(lambda: changements.append(time.monotonic()))
if WEB:
    fenetre.showFullScreen()
else:
    fenetre.resize(1000, 900)
    fenetre.show()
t = time.monotonic()
editeur.grab()
mesure("premier rendu", t)
editeur.setFocus()


def geste(nom, **valeurs):
    """Demande un geste réel à la sonde (--pilote) et rend le moment de la demande ; `attendre` guette `<nom>_fait`."""
    for cle, v in valeurs.items():
        setattr(js.window, cle, to_js(v))
    js.window.etat = nom
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
        js.window.etat = "jalon2"
        suite()
    else:
        QTimer.singleShot(100, lambda: attendre(nom, suite))


def clic():
    """Un vrai clic au milieu de l'éditeur : c'est lui qui donne le focus clavier au canevas de Qt dans la page."""
    centre = editeur.viewport().mapToGlobal(editeur.viewport().rect().center())
    if WEB:
        t = geste("cliquer", clic=[centre.x(), centre.y()])
        attendre("cliquer", lambda: (mesure("clic réel", t), saut()))
    else:
        saut()


def saut():
    t = time.monotonic()
    editeur.moveCursor(QTextCursor.End)
    editeur.ensureCursorVisible()
    editeur.grab()
    mesure("saut à la fin, rendu", t)
    frappe()


def frappe():
    del changements[:]
    if WEB:
        t = geste("taper", texte=SAISIE)
        attendre("taper", lambda: frappe_finie(t))
    else:
        t = time.monotonic()
        for c in SAISIE:
            touche(editeur, c)
        frappe_finie(t)


def frappe_finie(t):
    mesure(f"frappe de {len(SAISIE)} touches ({len(changements)} textChanged)", t)
    lignes = editeur.toPlainText().splitlines()[-3:]
    print("dernières lignes :", lignes)
    print("frappe :", "ok" if lignes[-2:] == ATTENDU else f"ÉCART, attendu {ATTENDU}")
    t = time.monotonic()
    n = 0
    while editeur.document().isUndoAvailable() and editeur.toPlainText() != TEXTE and n < 100:
        editeur.undo()
        n += 1
    mesure(f"annulation ({n} pas)", t)
    print("annulation :", "ok" if editeur.toPlainText() == TEXTE else "ÉCART, le texte diffère")
    selection()


def selection():
    t = time.monotonic()
    editeur.selectAll()
    editeur.grab()
    mesure("tout sélectionné, rendu", t)
    editeur.moveCursor(QTextCursor.Start)
    t = time.monotonic()
    for _ in range(50):
        for genre in (QEvent.KeyPress, QEvent.KeyRelease):
            QApplication.sendEvent(editeur, QKeyEvent(genre, Qt.Key_Down, Qt.ShiftModifier))
    editeur.grab()
    n = editeur.textCursor().selectedText().count(" ") + 1
    mesure(f"Maj+Bas × 50 ({n} lignes sélectionnées), rendu", t)
    editeur.moveCursor(QTextCursor.Start)
    pliage()


def pliage():
    t = time.monotonic()
    plages = plis(TEXTE)
    editeur._update_folding_info(plages)
    editeur._finish_update_folding()
    mesure(f"{len(plages)} plis calculés et posés", t)
    panneau = editeur.folding_panel
    # Les plis sont indexés par le numéro de ligne (à partir de 1) du « class » ; toggle_fold_trigger attend le PREMIER bloc
    # à cacher, celui dont blockNumber vaut ce numéro (codefolding.py, mouseMoveEvent → find_parent_scope → toggle).
    n = next(i for i, l in enumerate(TEXTE.splitlines()) if l.startswith("class ")) + 1
    editeur.setTextCursor(QTextCursor(editeur.document().findBlockByNumber(n - 1)))
    editeur.centerCursor()  # la classe à l'écran, sinon le pli ne se voit pas sur la capture
    bloc = editeur.document().findBlockByNumber(n)
    t = time.monotonic()
    panneau.toggle_fold_trigger(bloc)
    editeur.grab()
    mesure(f"classe de la ligne {n} repliée, rendu", t)
    print("pli :", "ok" if panneau.folding_status.get(n) else f"ÉCART, ligne {n} non pliée")
    capturer("plie")
    panneau.toggle_fold_trigger(bloc)
    fin()


def fin():
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


QTimer.singleShot(0, garde(clic))
sys.exit(app.exec())
