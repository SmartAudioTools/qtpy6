"""Le même plantage sans qtpy6 : PySide6 seul, un Signal accessible sous un second nom de classe, masqué par une méthode
du sous-type, puis connecté : core dump (09/10/2026, PySide6 6.11.1). Le snake_case officiel de PySide6 (``from __feature__
import snake_case``) ne pose aucun attribut de classe ni d'instance pour les signaux (``text_changed`` n'existe pas,
``textChanged`` reste) : il n'a donc pas ce défaut. Lancer : ``QT_QPA_PLATFORM=offscreen python alias_signal_pyside6.py``."""
from PySide6.QtCore import QObject, Signal
class Base(QObject):
    changed = Signal(str)
    alias = changed                      # le même signal sous un second nom, comme le fait qtpy6
class Fils(Base):
    def __init__(self):
        super().__init__()
        self.changed.connect(self.alias)  # slot qui porte le nom de l'alias
    def alias(self, texte):
        print("slot :", texte)
f = Fils(); f.changed.emit("abc"); print("pas de plantage")
