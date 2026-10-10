"""Autour du jalon 5 (notes/2026-10-09 - Portage de SmartPythonEditor…) : le dossier de l'élève sur SON DISQUE, autorisé par
lui — File System Access de Chrome (`showDirectoryPicker`, handle gardé dans IndexedDB, permission redemandée ou mémorisée
au rechargement) monté dans Pyodide par `pyodide.mountNativeFS` (NATIVEFS_ASYNC : les écritures restent en mémoire jusqu'à
`syncfs()`). Demande de l'utilisateur, 10/10/2026 : « les postes du lycée sont sous Chrome, mesure l'option dossier autorisé ».

Page seule, dans le Chrome de l'utilisateur (le sélecteur exige un clic réel, et Chromium ne démarre pas dans le bac à
sable) : index.html?script=jalon5_dossier.py. Deux phases, comme jalon5.py. A : bouton « Choisir le dossier », sélecteur,
montage, les mêmes fichiers que jalon5 écrits par `encoding.write` puis `syncfs`, une retouche puis `syncfs`, le journal
écrit dans le dossier, rechargement. B : handle retrouvé, permission lue (mémorisée → montage sans clic ; sinon bouton
« Réautoriser ») ; fichiers retrouvés, relus à l'identique, posé dans le CodeEditor ; journal complet écrit dans
`jalon5_dossier.log` du dossier choisi — que la session lit depuis le dépôt (essais/spyder/jalon5_dossier/).

Tout ce qui est propre au web ici est l'objet de la mesure (la doublure, un troisième emplacement de
`application(persistant=chemin)` dans qtpy6, se note, ne se code pas) : `js`, `pyodide_js` et `bloquant._suspendre`
sont donc partout, et le script ne tourne pas sur le bureau."""

import gc
import os
import sys
import time
import traceback

from preparer import ICI, T0, etape

os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)  # comme jalon5.py : hors de l'archive, seulement listé
import js  # noqa: E402
import pyodide_js  # noqa: E402
import spyder  # noqa: E402
from pyodide.ffi import create_once_callable  # noqa: E402
from qtpy.QtCore import QTimer  # noqa: E402
from qtpy.QtGui import QFont  # noqa: E402
from qtpy.QtWidgets import QMainWindow  # noqa: E402
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
from spyder.utils import encoding  # noqa: E402
import qtpy6.web  # noqa: E402
from qtpy6.web import bloquant, stockage  # noqa: E402

etape("imports")
LIGNES = 2000
DOSSIER = "/home/pyodide/jalon5_dossier"  # le point de montage : doit être vide ou absent (mountNativeFS le crée)
LOG = "jalon5_dossier.log"  # écrit dans le dossier choisi, lu par la session depuis le dépôt
TEMOIN = "jalon5_dossier"  # localStorage : la phase A faite, et son journal par-dessus le rechargement
RETOUCHE = "# retouche\n"
JOURNAL = []
PATIENCE = 180  # s sans événement avant « BLOQUÉ » : le temps de trouver le dossier dans le sélecteur
js.window.etat = "jalon5_dossier"
nfs = None  # ce que rend mountNativeFS : {syncfs()}

# Le côté JS : IndexedDB pour le handle, le bouton (le clic réel), le sélecteur et la permission. Chaque fonction rend
# une promesse, attendue côté Python par `attendre_js`.
js.eval("""
window.jalon5dossier = {
  bd() { return new Promise((ok, ko) => { const r = indexedDB.open("jalon5_dossier", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("h");
    r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error); }); },
  async ecrire(h) { const bd = await this.bd(); await new Promise((ok, ko) => { const t = bd.transaction("h", "readwrite");
    if (h) t.objectStore("h").put(h, "eleve"); else t.objectStore("h").delete("eleve");
    t.oncomplete = ok; t.onerror = () => ko(t.error); }); },
  async lire() { const bd = await this.bd(); return await new Promise((ok, ko) => { const r = bd.transaction("h").objectStore("h").get("eleve");
    r.onsuccess = () => ok(r.result || null); r.onerror = () => ko(r.error); }); },
  bouton(texte) { return new Promise(ok => { const b = document.createElement("button"); b.textContent = texte;
    b.style.cssText = "position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:1000;font-size:20px;padding:12px 24px;cursor:pointer";
    b.onclick = () => { b.remove(); ok(performance.now()); }; document.body.appendChild(b); }); },
  async choisir() {  // phase A : le clic, le sélecteur, le handle gardé
    const t0 = await this.bouton("Choisir le dossier essais/spyder/jalon5_dossier");
    const h = await showDirectoryPicker({ mode: "readwrite", id: "jalon5_dossier" });
    const t1 = performance.now(); await this.ecrire(h);
    return { nom: h.name, choix: t1 - t0, garde: performance.now() - t1 }; },
  async reprendre() {  // phase B : le handle retrouvé, la permission lue, redemandée au besoin (clic)
    const h = await this.lire(); if (!h) throw new Error("aucun handle en IndexedDB");
    const lue = await h.queryPermission({ mode: "readwrite" }); let etat = lue, clic = 0;
    if (etat !== "granted") { const t0 = await this.bouton("Réautoriser le dossier"); etat = await h.requestPermission({ mode: "readwrite" }); clic = performance.now() - t0; }
    return { nom: h.name, lue, etat, clic }; },
  async oublier() { await this.ecrire(null); },
};
""")
jd = js.window.jalon5dossier


class Echec(Exception):
    pass


def attendre_js(promesse):
    """Suspend jusqu'à la promesse JS ; rend sa valeur, ou lève `Echec` avec le message du rejet."""
    res = bloquant._suspendre(lambda resoudre: promesse.then(
        create_once_callable(resoudre),
        create_once_callable(lambda e: resoudre(Echec(str(getattr(e, "message", e)))))))
    if isinstance(res, Echec):
        raise res
    return res


def dire(*mots):
    ligne = " ".join(str(m) for m in mots)
    print(ligne)
    JOURNAL.append(ligne)


def tas():
    return f" ; tas {pyodide_js._module.HEAPU8.length // 1048576} Mio"


def mesure(nom, debut):
    dire(f"{nom} : {(time.monotonic() - debut) * 1000:.0f} ms{tas()}")


def synchroniser(nom):
    """Après des écritures : `syncfs()` du montage natif, ce qui pousse réellement les fichiers sur le disque."""
    t = time.monotonic()
    attendre_js(nfs.syncfs())
    mesure(f"syncfs après {nom}", t)


def journaliser():
    """Le journal (les deux phases) dans le dossier choisi, poussé sur le disque : ce que la session lit."""
    if nfs is None:
        return
    with open(os.path.join(DOSSIER, LOG), "w", encoding="utf-8") as f:
        f.write("\n".join(JOURNAL) + "\n")
    attendre_js(nfs.syncfs())


# --- L'éditeur, comme jalon5.py. ---

app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))
fenetre = QMainWindow()
editeur = CodeEditor(fenetre)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename="exercice1.py")
source = os.path.join(os.path.dirname(spyder.__file__), "plugins", "editor", "widgets", "codeeditor", "codeeditor.py")
with open(source, encoding="utf-8") as f:
    TEXTE = "\n".join(f.read().splitlines()[:LIGNES]) + "\n"
FICHIERS = {"exercice1.py": TEXTE, "notes.txt": "Notes de l'élève : é à ù — ligne 1\nligne 2\n"}
ATTENDU = {**FICHIERS, "exercice1.py": TEXTE + RETOUCHE}
fenetre.setCentralWidget(editeur)
fenetre.setWindowTitle("Jalon 5 : dossier autorisé (File System Access)")
fenetre.showFullScreen()

_activite = [time.monotonic()]
ETAPE = ["début"]


def vivant(nom=None):
    _activite[0] = time.monotonic()
    if nom:
        ETAPE[0] = nom


def chien_de_garde():
    if time.monotonic() - _activite[0] > PATIENCE:
        dire(f"BLOQUÉ : étape {ETAPE[0]!r}")
        js.window.etat = "erreur"
        journaliser()


def garde(f):
    """Une étape lancée depuis la boucle d'événements : son exception finit dans le journal (et dans le dossier, s'il est
    monté) et pose l'état « erreur »."""
    def g(*a):
        try:
            f(*a)
        except Exception:
            dire("ERREUR :\n" + traceback.format_exc())
            js.window.etat = "erreur"
            afficher()  # le journal à l'écran : si l'erreur précède le montage, rien n'a pu atteindre le dossier
            try:
                journaliser()
            except Exception:
                traceback.print_exc()
    return g


def afficher():
    pre = js.document.createElement("pre")
    pre.style.cssText = "position:fixed;top:0;left:0;right:0;max-height:60%;overflow:auto;z-index:1000;background:#fff;color:#000;padding:8px;font-size:12px"
    pre.textContent = "\n".join(JOURNAL)
    js.document.body.appendChild(pre)


def monter(handle):
    global nfs
    t = time.monotonic()
    nfs = attendre_js(pyodide_js.mountNativeFS(DOSSIER, handle))
    mesure(f"montage natif, {len(os.listdir(DOSSIER))} fichiers retrouvés", t)


chien = QTimer()
chien.timeout.connect(garde(chien_de_garde))
chien.start(5000)
PHASE = "B" if stockage.lire(TEMOIN) else "A"


# --- Phase A : choisir, monter, écrire, pousser, recharger. ---

@garde
def phase_a():
    vivant("choix du dossier (clic attendu)")
    dire(f"Chrome : {js.navigator.userAgent}")
    dire("File System Access :", "présent" if hasattr(js.window, "showDirectoryPicker") else "ABSENT")
    choix = attendre_js(jd.choisir())
    vivant("montage")
    dire(f"dossier choisi : {choix.nom!r} ; sélecteur (du clic au handle) {choix.choix:.0f} ms ; handle gardé en IndexedDB "
         f"{choix.garde:.0f} ms")
    monter(attendre_js(jd.lire()))
    for nom, texte in FICHIERS.items():
        t = time.monotonic()
        encoding.write(texte, os.path.join(DOSSIER, nom))
        mesure(f"{nom} écrit ({len(texte)} caractères)", t)
    synchroniser("deux fichiers")
    t = time.monotonic()
    encoding.write(ATTENDU["exercice1.py"], os.path.join(DOSSIER, "exercice1.py"))
    mesure("exercice1.py retouché", t)
    synchroniser("une retouche")
    dire(f"phase A : {time.monotonic() - T0:.1f} s depuis le chargement{tas()}")
    journaliser()
    stockage.ecrire(TEMOIN, "\n".join(JOURNAL))
    dire("rechargement de la page")
    js.location.reload()


# --- Phase B : retrouver, relire, poser dans l'éditeur. ---

@garde
def phase_b():
    for ligne in stockage.lire(TEMOIN).splitlines():
        JOURNAL.append("phase A | " + ligne)
    stockage.effacer(TEMOIN)
    vivant("permission (clic si elle n'est pas mémorisée)")
    t = time.monotonic()
    rep = attendre_js(jd.reprendre())
    vivant("montage")
    dire(f"après rechargement : handle {rep.nom!r} retrouvé ; permission lue {rep.lue!r}"
         + (f", redemandée au clic ({rep.clic:.0f} ms) : {rep.etat!r}" if rep.clic else " (mémorisée, sans clic)")
         + f" ; {(time.monotonic() - t) * 1000:.0f} ms en tout")
    if rep.etat != "granted":
        raise Echec(f"permission {rep.etat!r}")
    monter(attendre_js(jd.lire()))
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
    t = time.monotonic()
    gc.collect()
    mesure("gc", t)
    attendre_js(jd.oublier())
    dire(f"durée totale du script : {time.monotonic() - T0:.1f} s{tas()}")
    journaliser()
    js.window.etat = "fini"


QTimer.singleShot(0, phase_a if PHASE == "A" else phase_b)
sys.exit(app.exec())
