# qtpy6

*PySide6's API, in snake_case, on top of PySide6 or PyQt6 — documentation in French below.*

Écrire du code Qt une seule fois, avec **l'API exacte de PySide6** —
`Signal`/`Slot`/`Property`, `exec()` sans tiret bas,
`QFileDialog.get_open_file_name(dir=…)`, énumérations scopées ou non — et en
**snake_case**, puis le faire tourner tel quel sur PySide6 ou PyQt6.

```python
from qtpy6 import QtCore, QtWidgets

class Compteur(QtWidgets.QWidget):
    changed = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        self.set_window_title('Compteur')
        bouton = QtWidgets.QPushButton('+1', self)
        bouton.clicked.connect(lambda: self.changed.emit(1))

app = QtWidgets.QApplication([])
Compteur().show()
app.exec()
```

Dérivé de [QtPy](https://github.com/spyder-ide/qtpy) (licence MIT), qui
harmonise dans l'autre sens, sur l'API de PyQt5 en camelCase, et du fork
`/DATA/Python/FORKS/qtpy` dont il reprend les réglages de session (voir plus bas).

## Installation

```bash
pip install qtpy6[pyside6]   # ou qtpy6[pyqt6], ou qtpy6 seul si un binding est déjà là
```

Python ≥ 3.10, Qt ≥ 6.4 (énumérations Python). Aucune dépendance obligatoire :
qtpy6 prend le binding qu'il trouve.

## Choix du binding

Dans l'ordre :

1. le binding **déjà importé** dans le processus (un processus ne peut pas en
   changer : c'est ce qui fait fonctionner qtpy6 dans Spyder ou sous pyqtgraph) ;
2. le réglage **`QT_API`** — `pyside6`, `pyqt6` ou `auto` — lu dans
   l'environnement, sinon dans la session de bureau (registre Windows, ou
   `~/.config/plasma-workspace/env/QtEnvironment.sh` sous KDE) ;
3. le premier **installé**, PySide6 avant PyQt6.

Le choix est ensuite écrit dans `os.environ['QT_API']` pour que qtpy, pyqtgraph
et matplotlib prennent le même. `qtpy6.API`, `API_NAME`, `PYSIDE6`, `PYQT6`,
`QT_VERSION`, `PYQT_VERSION`, `PYSIDE_VERSION` disent ce qui a été choisi.
`QT_VERSION` est la version de la bibliothèque Qt **chargée** (`qVersion()`),
pas celle contre laquelle le binding a été compilé : les roues PyQt6 6.11
embarquent Qt 6.11.1 tout en déclarant 6.11.0. Un `QT_API` invalide lève
`ValueError` ; aucun binding installé lève `qtpy6.QtBindingsNotFoundError`.

Les bindings Qt5 (PySide2, PyQt5) ne sont pas pris en charge : PySide2 s'arrête
à Python 3.10, et les deux sont défaillants sous Wayland.

## Mécanisme

Trois passes sur chaque module du binding, dans `qtpy6/_binding.py` :

- **`load`** — copie les noms publics du module homonyme du binding.
- **les correctifs du module** (`QtCore.py`, `QtGui.py`, `QtWidgets.py`) —
  `pyqtSignal`→`Signal` et consorts (les noms PyQt disparaissent),
  `QtCore.__version__`, `QTimer.single_shot(msec, receiver, slot)` (forme à trois
  arguments de PySide6, absente de PyQt6), mot-clé `dir` **et** `directory` sur les fonctions
  statiques de `QFileDialog`, `mode=` de `QTextCursor.move_position` sur
  PySide6, police de `QApplication`.
- **`finish`** — sur chaque classe : `exec`/`print` pour `exec_`/`print_`,
  membres d'énumération non scopés (`Qt.AlignLeft`) sur PyQt6 qui n'a que les
  scopés, et un **alias snake_case de chaque méthode, méthode statique et
  signal** camelCase, selon la règle exacte de shiboken (`snake_case`) : pas de
  conversion sous trois caractères, ni pour `gl` + majuscule, ni quand deux
  majuscules se touchent (`isOK`, `setDPI`). Les alias sont **additifs** : le
  camelCase reste, parce que les objets sont ceux du binding et que les
  bibliothèques tierces (pyqtgraph, matplotlib…) continuent de les appeler par
  leurs noms d'origine. Un alias posé sur une classe suit sa redéfinition
  (`QWidget.set_parent` est bien le `setParent` de QWidget, pas de QObject).

Les modules sans fichier propre (`qtpy6.QtNetwork`, `qtpy6.QtTest`,
`qtpy6.QtMultimedia`…) sont servis par un **finder** (`sys.meta_path`) qui
applique `load` puis `finish` au module homonyme du binding — tout module que le
binding sait importer existe donc dans qtpy6, sans rien à déclarer.

Coût mesuré : `import qtpy6` (QtCore + QtWidgets, ~4 800 alias dans QtWidgets)
~75 ms sur PyQt6, ~125 ms sur PySide6 ; ~10 ms par module supplémentaire.

## Réglages de session (repris du fork qtpy)

Lus par `qtpy6.get_env`, écrits par `qtpy6.set_env` — dans le registre sous
Windows (`setx`), dans `QtEnvironment.sh` sous KDE Plasma — de sorte qu'un
changement vaut pour le prochain programme Qt lancé, sans se reconnecter :

| Réglage | Valeurs | Effet |
|---|---|---|
| `QT_API` | `auto`, `PySide6`, `PyQt6` | binding (voir ci-dessus) |
| `QT_SCALE` | `auto` (DPI logique du premier écran / 192) ou un facteur | `qtpy6.scaled(x)` : entier, flottant, `QRect`, `QSize`, `QMargins`, tuple, liste ; `scaled(a, b)` rend un tuple. La mise à l'échelle de Qt est désactivée (`QT_ENABLE_HIGHDPI_SCALING=0`, `QT_USE_PHYSICAL_DPI=1`) |
| `QT_FONT` | `default` ou une famille | police de `QApplication` |
| `QT_FONT_SIZE` | `default`, des points (`10`, `10.5`) ou `12 pixels` | taille de police de `QApplication` |

Sous Windows, l'import rend aussi le processus « DPI aware ».

`qtpy6.QtSelector` (widgets `QtApiSelector`, `QtScaleSelector`, `QtFontSelector`,
`QtFontSizeSelector`, `QtSelector`) règle les quatre depuis une fenêtre :
`python -m qtpy6.QtSelector` ou, une fois installé, `qtselector` ;
`python -m qtpy6.QtSelector_demo` montre ce qu'un programme reçoit.

## Ce qui n'est pas harmonisé

- Les fonctions de module gardent leur nom (`qInstallMessageHandler`) : PySide6
  fait pareil.
- Les méthodes propres à un binding (`QSize.toTuple()` de PySide6,
  `pyqtConfigure` de PyQt6) restent propres à ce binding.
- `qtpy6.QtStateMachine` n'existe que si le binding sait l'importer : les roues
  PyQt6 livrent le module sans `libQt6StateMachine`.

## Dans le navigateur

Le même code tourne dans une page web, sous un Pyodide où Qt 6 et PySide6 sont liés en WebAssembly (LGPL v3, recette
`wasm/` ; PyQt6 en repli) :
`python -m qtpy6.web.construire app.py site/` en fait un site statique, `sys.exit(app.exec())` compris. Ce que Qt-WASM
n'a pas et qui a un nom Qt, qtpy6 le double sous ce nom, dans le navigateur seulement : les `exec()` et boîtes statiques
(`QMessageBox.question`, `QFileDialog.getOpenFileName`…) attendent leur réponse, `QThread` et ses verrous deviennent des
fils coopératifs, `QtCore.QProcess` un Web Worker Pyodide, `QFontDatabase.systemFont(FixedFont)` la police fixe que
l'application a chargée. Le reste (chargeur de la page, polices, tactile, stockage, archive, sonde Firefox) est dans
`qtpy6.web` : voir [web.md](web.md), qui dit aussi ce qui diffère encore du bureau.

## Référence

| Nom | Rôle |
|---|---|
| `qtpy6.QtCore`, `QtGui`, `QtWidgets`, et tout `qtpy6.QtXxx` du binding | les modules Qt, API de PySide6 + alias snake_case |
| `API`, `API_NAME`, `PYSIDE6`, `PYQT6` | binding choisi : `'pyside6'`/`'pyqt6'`, `'PySide6'`/`'PyQt6'`, deux booléens |
| `QT_VERSION`, `PYQT_VERSION`, `PYSIDE_VERSION` | versions ; celle de l'autre binding vaut `None` |
| `QtBindingsNotFoundError` | levée à l'import si aucun binding n'est installé |
| `get_env(key, default=None)`, `set_env(key, value)` | réglages de session (environnement, puis registre ou `QtEnvironment.sh`) |
| `QT_SCALE`, `QT_FONT`, `QT_FONT_SIZE` | valeurs lues à l'import (`QT_SCALE` : flottant, ou `None` tant que `auto` n'est pas résolu) |
| `scaled(obj, *more)` | `obj × QT_SCALE`, résout `auto` au premier appel (il faut une `QApplication`) |
| `qtpy6.QtSelector` | les widgets de réglage et `main()` (point d'entrée `qtselector`) |
| `qtpy6.animation.AnimationParImage(cible, propriete, parent, duree, courbe)` | une `QPropertyAnimation` menée par les images de l'écran (`QWindow.requestUpdate` : rappel du compositeur sur Wayland, `requestAnimationFrame` dans le navigateur) au lieu de la minuterie de 16 ms de Qt ; `setStartValue`, `setEndValue`, `start`, `stop`, `finished` |
| `qtpy6.web` | le navigateur : `navigateur()`, `application()`, `lancer()`, `construire`, `bloquant`, `fils`, `tactile`, `dispositions`, `travailleur`, `stockage`, `assembler`, `sonde` ([web.md](web.md)) |

## Tests et niveau de preuve

- **PySide6 6.11.1 et PyQt6 6.11 (Qt 6.11.1) : testés** — 76 tests, verts sur
  les deux (sur Python 3.12, 3.13 et 3.14 avant la fusion du navigateur, 3.13 seul depuis). `tests/test_qtpy6.py` tourne dans le
  processus de test (un binding par lancement) ; `tests/test_process.py` lance
  des interpréteurs neufs et couvre, pour chaque binding installé, la sélection
  (environnement, fichier de session, binding déjà importé, valeur invalide,
  aucun binding), les réglages de police et d'échelle, `QtSelector` et sa démo.
- **Le navigateur : testé en direct dans Firefox sans interface** (Pyodide 0.29.3, Qt 6.10.2,
  sous PyQt6 puis sous PySide6, où le lecteur d'épreuves de SmartTeacher a aussi été ouvert, défilé et
  animé) : une application de bureau construite telle quelle (`construire`) a enchaîné
  `QMessageBox.question`, `QInputDialog`, un `QMenu.exec`, un `QThread` attendu par `wait()`, l'ouverture et
  l'enregistrement d'un fichier, puis `quit()` jusqu'au code de sortie. `tests/test_web.py` (18 tests)
  rejoue en natif la mécanique de suspension, `greenlet` y tenant le rôle de JSPI : il prouve la
  logique, pas le comportement de Qt-WASM.
- **La branche Windows de `_env.py` n'a tourné que contre des doublures**
  (`tests/test_env_windows.py` : `winreg`, `nt`, `ctypes.windll` et `setx`
  simulés). Cela prouve que le code s'exécute et prend les bonnes branches,
  pas que Windows se comporte comme les doublures.
- **Couverture de lignes : 100 %** de `qtpy6/`, en cumulant les deux bindings
  et les interpréteurs lancés par les tests. Un seul `pytest --cov` n'en voit
  qu'une partie (un binding, un processus : 79 %) ; le cumul demande
  `coverage` en mode sous-processus (`COVERAGE_PROCESS_START`) et un lancement
  par binding, ou le traceur maison qui a servi ici.
- Le `mode=` de `move_position` est bien nécessaire : PySide6 6.11.1 refuse
  encore ce mot-clé.

```bash
QT_QPA_PLATFORM=offscreen QT_API=pyqt6 python -m pytest tests
QT_QPA_PLATFORM=offscreen QT_API=pyside6 python -m pytest tests --cov=qtpy6 --cov-report=term-missing
# Dans un environnement SmartPython, dont le pytest charge un greffon typeguard cassé sur 3.14 :
QT_QPA_PLATFORM=offscreen QT_API=pyside6 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /DATA/Python/SmartPython/CachyOS/versions/3.14.6/envs/SmartPython-3.14.6_2026-07-26/bin/python \
  -m pytest tests
```

## Publication sur PyPI

Le nom `qtpy6` est libre sur PyPI (vérifié le 18/09/2026). La version est lue
dans `qtpy6/__init__.py` (`__version__`) ; les changements vont dans
`CHANGELOG.md`.

```bash
python -m pip install --upgrade build twine
python -m build                       # dist/qtpy6-X.Y.Z.tar.gz et .whl
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*   # répétition, sur test.pypi.org
python -m twine upload dist/*         # jeton API PyPI dans ~/.pypirc ou TWINE_PASSWORD
```

Vérifié ici : `python -m build` produit la sdist et la roue (avec les deux SVG),
la roue s'installe dans un environnement neuf, `qtselector` y est exécutable et
les tests passent depuis un autre dossier. L'envoi lui-même demande un compte
PyPI et le réseau ; `twine` n'est pas installé sur cette machine.

## Différences avec le fork qtpy d'origine

- Sélection : « binding déjà importé » remplace le cas particulier Spyder ;
  PySide2 et PyQt5 ne sont plus proposés.
- `get_env` sous Plasma : valeurs avec espaces ou `=` lues et écrites correctement
  (`shlex`), dossier créé s'il manque.
- `set_env` Windows : `OpenKey` au lieu de `CreateKey` (une lecture ne crée plus
  de clé).
- `scaled(tuple)` rend un tuple, plus un générateur ; `QT_FONT_SIZE` accepte
  des points non entiers.
- `QtSelector` : une classe de base commune aux trois combos ; plus de `setFont`
  redéfini sur `QtFontSelector` (il masquait `QWidget.setFont`).
