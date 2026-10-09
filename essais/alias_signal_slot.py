"""Reproduction d'un plantage de qtpy6 (09/10/2026) : PySide6 fait un segfault quand une classe fille définit une méthode
(un slot, PEP 8) du nom de l'alias snake_case qu'un signal reçoit de qtpy6 (_binding._pyside6_class) et la connecte à ce
signal. Trouvé en portant Spyder (cursor_position_changed, plugins/editor/widgets/base.py), reproduit ici sans Spyder.

    QT_QPA_PLATFORM=offscreen $P essais/alias_signal_slot.py          # plante (core dump), aucune exception
    QT_QPA_PLATFORM=offscreen $P essais/alias_signal_slot.py --sans   # sans qtpy6 : « slot : abc », pas de plantage

Doit cesser de planter le jour où qtpy6 n'aliasse plus les signaux (ou les protège) : c'est le test qui échoue sans le
correctif. Note : notes/2026-10-09 - Portage de SmartPythonEditor…, « Points ouverts »."""
import sys

if "--sans" not in sys.argv:
    import qtpy6  # noqa: F401  pose text_changed (alias du signal textChanged) sur QLineEdit
from PySide6.QtWidgets import QApplication, QLineEdit


class Champ(QLineEdit):
    def __init__(self):
        super().__init__()
        self.textChanged.connect(self.text_changed)

    def text_changed(self, texte):  # slot nommé comme le signal, en snake_case : le nom naturel en PEP 8
        print("slot :", texte)


app = QApplication([])
champ = Champ()
champ.setText("abc")
print("pas de plantage")
