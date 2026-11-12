# qtpy6 comme qtpy dans SmartPythonEditor natif (W567)

Demande (brief W567, reste de W559) : « SmartPythonEditor natif […] n'emploie pas encore qtpy6 comme alias de `qtpy` :
il faut qtpy6 dans ce venv, `_qtpy.installer()` avant le PREMIER import de `qtpy` […] choisis le point d'entrée qui ne
modifie pas le code de Spyder […] puis un démarrage complet mesuré ». Le professeur a demandé que ce reste soit confié
à un worker, sans question.

## FAIT

- **Point d'entrée : un `.pth` paresseux dans le venv**, écrit une fois par `python -m qtpy6._qtpy`
  (`_qtpy.ecrire_pth()`, fichier `qtpy6_qtpy.pth`). C'est une ligne que `site` exécute et qui n'importe rien : elle
  pose en tête de `sys.meta_path` un chercheur qui, au premier `import qtpy` ou `qtpy.X`, se retire, appelle
  `installer()` et rend la spec de `_Chercheur`. `qtpy6` n'est jamais intercepté (test sur `n.partition('.')[0]`).
- **qtpy6 dans le venv** `SmartPythonEditor-6.1.5` (Python 3.12.14, PySide6 6.11.1) : `pip install --no-deps`.
  Pendant l'essai, l'installation était éditable ; une fois le commit fait, elle est remplacée par un instantané de
  ce commit (voir « Déploiement »).
- **Défaut trouvé au premier démarrage, corrigé dans `_binding._Alias._qt`** : Spyder appelle `inspect.signature`
  sur chaque membre `create_*` de `CompletionConfigPage` (`spyder/plugins/completion/plugin.py:577`). L'alias
  `create_win_id` de `createWinId`, une méthode native de PySide6 sans signature, levait `ValueError`, et le
  démarrage s'arrêtait après 3 greffons. Désormais, une méthode du binding lue PAR LA CLASSE et dépourvue de
  signature est rendue enveloppée dans un `_Signe`, qui porte la signature honnête `(*args, **kwargs)`. La lecture
  par l'instance ne change pas.
  - Pourquoi un `_Signe` et non une fonction : une première version en fonction cassait
    `test_qtpy6.py::test_alias_follows_override` (`QWidget.find_children == QWidget.findChildren`).
  - Le `_Signe` reste égal à la méthode Qt (`==`, `hash`), s'appelle et se lie (`__get__`) comme elle.
- Relecteur, remarques acceptées sans correction :
  - Les doublures Python statiques sous PyQt6 (`QFileDialog.get_open_file_name`) suivent `__wrapped__` jusqu'au
    builtin sip et restent sans signature : ce n'est pas le cas de Spyder sous PySide6.
  - Une course entre le retrait du chercheur paresseux et `installer()` n'est possible qu'au premier `import qtpy`
    fait en parallèle par deux fils : jamais observée.
- **Défaut latent de W555, corrigé dans `_qtpy._corriger`** : `QtGui.Qt.mightBeRichText` était lu sans condition.
  Or `qtpy6.QtGui` n'a pas de `Qt` sous PyQt6, si bien que tout `import qtpy.QtCore` par l'alias plantait sous PyQt6.

## POURQUOI le `.pth`, et les alternatives écartées

- **Le lanceur** (`SmartPythonEditor.sh`, `python -c "installer(); runpy…"`) : écarté. Le redémarrage de Spyder
  (`spyder/app/restart.py:234-236`) relance `sys.executable spyder/app/start.py` sans passer par le lanceur, et
  `restart.py` importe lui-même qtpy. Avec le lanceur, le processus redémarré aurait donc tourné sur le vrai qtpy.
- **`spyder/app/start.py`** : écarté, car c'est du code de Spyder.
- **Un `.pth` direct** (`import qtpy6._qtpy; installer()`) : écarté après mesure. `import qtpy6._qtpy` coûte de
  0,5 à 1 s (qtpy6 importe QtCore et QtWidgets) dans CHAQUE processus du venv, pylsp compris.
- **Même code natif et web** : rien n'est ajouté à l'application. Dans la page, `qtpy6.web.lancer()` appelle
  `installer()` ; en natif, c'est le `.pth`, un réglage posé une fois sur le venv.

## VÉRIFIÉ

- Tests (`tests/test_doublures.py`, section W567) :
  - `test_alias_qtpy_pth_paresseux` : rouge avant (`AttributeError`), puis vert. Il vérifie que le `.pth` n'importe
    ni qtpy6 ni PySide6 au démarrage, que `qtpy.__file__` est `_qtpy.py` et que le chercheur s'est retiré.
  - `test_alias_methode_signature_par_la_classe` : rouge avant (`ValueError`, PyQt6), puis vert.
  - Ces deux tests passent aussi sous PySide6, dans le venv : mesuré.
- **Démarrage complet**, hors écran, configuration séparée, chronomètre `SMARTOS_STARTUP_TRACE`, banc
  `/DATA/Python/qtpy6_essais/w567/mesurer_demarrage.py`, sans et avec alias en alternance (mesuré) :
  - le repère `editeur_utilisable` est atteint ;
  - 47 greffons, dans le même ordre, avec et sans alias ;
  - `qtpy` est bien servi par `qtpy6/_qtpy.py` ;
  - les stderr sont identiques (mêmes 2 traces préexistantes, même `RuntimeWarning` libpyside de
    `ipythonconsole/main_widget.py:1663`), À L'EXCEPTION de 3 `SignalAliasMasked` (voir RESTE).
- **Temps** :
  - Le démarrage complet n'est pas comparable : charge machine de 28 à 35, de 11 à 37 s des deux côtés.
  - L'import isolé (`qtpy.QtCore`, `QtGui`, `QtWidgets`, `QtWebEngineWidgets`, 10 essais alternés) est comparable :
    médiane ~165 ms avec le vrai qtpy, ~760 ms avec l'alias, soit **+0,6 s environ** (mesuré).
  - Le profil (cProfile) attribue ~0,5 s à la création d'environ 700 énumérations PySide6, que déclenche le
    parcours des classes par `_binding._pyside6_class`. C'est un coût de qtpy6 en général, pas de l'alias.
    Signalé au Superviseur, hors de cet item.

## RESTE

- **3 `SignalAliasMasked`**, tous dans le fork : `TextEditBaseWidget.cursor_position_changed`
  (`editor/widgets/base.py`), `ArrayTable.cell_changed` (`widgets/arraybuilder.py`),
  `ProfilerDataTree.item_expanded` (`profiler/widgets/profiler_data_tree.py`). C'est l'item 3 du TODO : le
  renommage du générateur du fork a été perdu, et D1 garde l'avertissement. Le zéro dépend du propriétaire du fork
  (demandé au Superviseur).
- **Durabilité** : `installation_SmartPythonEditor.sh` (SmartOS) ne connaît ni qtpy6 ni le `.pth`. Un venv
  reconstruit perd l'alias. À ajouter par la session SmartOS : `pip install --no-deps <qtpy6>` puis
  `python -m qtpy6._qtpy`.
- **Vérification visuelle** des fenêtres par le professeur sur sa machine : demandée une fois, en fin d'item.
