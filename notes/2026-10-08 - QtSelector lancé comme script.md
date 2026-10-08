# QtSelector lancé comme script : import relatif → absolu

## Demande
Traceback collé par l'utilisateur (« SmartPython QtSelector ») :
`ImportError: attempted relative import with no known parent package` à la ligne
`from . import API_NAMES, QtGui, QtWidgets, get_env, set_env` de `qtpy6/QtSelector.py`.

## Cause
Le module était exécuté sans son paquet (fichier lancé seul, ou `python -m QtSelector` depuis
`qtpy6/qtpy6/`) : `__package__` est vide, l'import relatif ne peut pas se résoudre.
`python -m qtpy6.QtSelector` et le point d'entrée `qtselector` marchaient déjà.

## Correctif
`from . import …` → `from qtpy6 import …`, comme le font déjà `erreurs.py`, `paresse.py` et
`QtSelector_demo.py`. qtpy6 est installé en mode éditable dans tous les SmartPython, donc
l'import absolu se résout aussi quand le fichier est lancé seul.

Écarté : un repli `if not __package__: sys.path.insert(...)` — plus de code pour un cas que
l'installation éditable couvre déjà.

## Niveau de preuve
Testé avec le Python SmartPython : `import QtSelector` depuis `qtpy6/qtpy6/` échoue avec
l'ancienne version (même ImportError) et réussit avec la nouvelle ; `import qtpy6.QtSelector`
reste bon. Fenêtre non ouverte (pas de lancement graphique depuis le bac à sable).

Hors périmètre, à signaler : le lanceur `SmartOS/Commun/scripts/QtSelector.sh` appelle
encore `python -m qtpy.QtSelector` (ancien nom du paquet).

Question de l'utilisateur : « absolu : on ne pourra pas déplacer le dossier ? » - si : l'import
vise le nom du paquet, le chemin n'est que dans le `.pth` de l'installation éditable
(`/DATA/Python/qtpy6`), à refaire après un déplacement quel que soit le style d'import. Seul un
renommage du paquet casserait l'import absolu, et `erreurs.py`, `paresse.py` en dépendent déjà.
