"""Jalon 1 du portage de SmartPythonEditor dans le navigateur (notes/2026-10-09 - Portage de SmartPythonEditor…) :
le CodeEditor de Spyder (coloration, numéros, pliage, indentation) dans une fenêtre qtpy6, le même script sur le bureau
et dans la page (qtpy6.web.construire). Mesure : durée de chaque étape (import de spyder, import du CodeEditor,
fenêtre montrée) et, dans la page, le tas WebAssembly (index.html). Rien d'autre que l'éditeur : ni plugin, ni LSP, ni
console. Le fork est pris tel quel ; les modules absents du navigateur (psutil…) reçoivent une doublure minimale."""

import os
import sys

from preparer import ICI, etape  # noqa: F401 - doublures et chemins posés à l'import

if sys.platform == "emscripten":  # spyder/locale (6 Mo) est hors de l'archive ; Spyder ne fait que le lister (base.py, get_available_translations)
    os.makedirs(os.path.join(ICI, "spyder", "locale"), exist_ok=True)
import spyder  # noqa: E402
etape("import spyder")
from qtpy.QtGui import QFont  # noqa: E402
from qtpy.QtWidgets import QMainWindow  # noqa: E402
etape("import qtpy")
from spyder.plugins.editor.widgets.codeeditor import CodeEditor  # noqa: E402
etape("import CodeEditor")


import qtpy6.web  # noqa: E402

# La QApplication de qtpy6 : dans la page, elle charge les polices de app.zip (Qt n'en a aucune) ; en natif, rien de plus.
app = qtpy6.web.application(polices=os.path.join(ICI, "polices"), defaut=("DejaVu Sans", 10))
fenetre = QMainWindow()
editeur = CodeEditor(fenetre)
editeur.setup_editor(linenumbers=True, language="Python", markers=True, tab_mode=False, font=QFont("DejaVu Sans Mono", 10),
                     show_blanks=False, color_scheme="spyder/dark", wrap=False, edge_line=True, filename=__file__)
editeur.set_text_from_file(os.path.abspath(__file__))
fenetre.setCentralWidget(editeur)
fenetre.setWindowTitle("CodeEditor de Spyder dans qtpy6")
etape("CodeEditor créé")
if sys.platform == "emscripten":
    fenetre.showFullScreen()
else:
    fenetre.resize(900, 700)
    fenetre.show()
etape("fenêtre montrée")
if "--capture" in sys.argv:  # bureau : une image, pour comparer au rendu de la page
    from qtpy.QtCore import QTimer
    def capturer():
        fenetre.grab().save(os.path.join(ICI, "capture_bureau.png"))
        etape("capture faite")
        app.quit()
    QTimer.singleShot(500, capturer)
sys.exit(app.exec())
