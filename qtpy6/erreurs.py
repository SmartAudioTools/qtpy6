"""Une exception non rattrapée s'affiche dans une boîte de dialogue, en plus de la console.

``installer()`` remplace ``sys.excepthook`` et ``threading.excepthook`` (celui d'un ``threading.Thread``) :
l'exception passe d'abord au crochet en place (la trace en console reste), puis sa trace s'affiche dans une
``QMessageBox`` critique au texte sélectionnable, pour la copier. Levée dans un autre fil, elle traverse un signal
jusqu'au fil de l'objet relais, celui qui a appelé ``installer()`` (le fil principal) : un widget ne se crée que là.
Levée dans ce fil-là, le signal est livré directement, la boîte s'ouvre aussitôt. Sans ``QApplication``, la boîte en
crée une. ``SystemExit`` dans un fil reste muet, comme ``threading`` le fait.

Repris de SmartFramework (``ui/exceptionDialog.py``, qui l'installait à l'import, et sa variante sans signal
``exceptionDialog_mono_thread.py``, que celle-ci couvre)."""

import sys
import threading
import traceback

from qtpy6.QtCore import QObject, Qt, Signal
from qtpy6.QtWidgets import QApplication, QMessageBox

_relais = None


def boite(message):
    """La boîte affichée pour ``message`` (la trace), pas encore ouverte."""
    b = QMessageBox(QMessageBox.Icon.Critical, "Critical Error", "An unexpected Exception has occured!\n" + message)
    b.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
    return b


class _Relais(QObject):
    message = Signal(str)

    def __init__(self):
        super().__init__()
        self.precedent, self.precedent_fil = sys.excepthook, threading.excepthook
        self.message.connect(self.montrer)

    def montrer(self, message):
        if QApplication.instance() is None:
            QApplication(sys.argv)
        boite(message).exec()

    def crochet(self, exc_type, exc_value, exc_traceback):
        self.precedent(exc_type, exc_value, exc_traceback)
        self.emettre(exc_type, exc_value, exc_traceback)

    def crochet_fil(self, args):
        self.precedent_fil(args)
        if args.exc_type is not SystemExit:  # la sortie normale d'un fil, que threading tait aussi
            self.emettre(args.exc_type, args.exc_value, args.exc_traceback)

    def emettre(self, exc_type, exc_value, exc_traceback):
        try:
            self.message.emit("\n".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        except RuntimeError:  # relais détruit : un fil qui lève pendant la fermeture de l'interpréteur
            pass


def installer():
    """Affiche désormais les exceptions non rattrapées ; à appeler depuis le fil principal. Un second appel ne change
    rien."""
    global _relais
    if _relais is None or sys.excepthook != _relais.crochet:
        _relais = _Relais()
        sys.excepthook, threading.excepthook = _relais.crochet, _relais.crochet_fil
