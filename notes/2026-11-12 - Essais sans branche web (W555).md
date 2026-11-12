# Essais sans branche web (W555, 12/11/2026)

Brief : items 4 et 13 du TODO Portage (« ce que les essais font encore propre au web »). Réorienté par le professeur
après la question sur D5 (14:11) : « on ne peut pas passer tout SmartPythonEditor à qtpy6 ? », puis « je voulais dire :
on ne peut pas ne plus du tout utiliser le module qtpy, et ne faire que des import de qtpy6 dans SmartPythonEditor ? »,
puis (14:15) « fais dans un premier temps l'alias qtpy dans qtpy6 », et « à terme quel est le plus propre ? ».

## FAIT

- **`qtpy6/_qtpy.py`** (neuf) : un chercheur de `sys.meta_path` qui sert `qtpy` et `qtpy.*` par qtpy6.
  `qtpy.QtXxx` = l'espace de noms de `qtpy6.QtXxx` (doublures de la page comprises : QProcess, fils, QWebEngineView),
  plus un `__getattr__` vers lui (noms servis à la demande du mode paresseux) ; `qtpy` porte les drapeaux et les
  exceptions de qtpy (`API`, `PYSIDE2`, `QT6`, `QtModuleNotInstalledError`…) ; `qtpy.compat` les enveloppes de
  `QFileDialog` ; les correctifs de qtpy 2.4 pour Qt6 (`exec_`, `Qt.MidButton`, `QAction` dans QtWidgets,
  `QSinglePointEvent.pos/x/y`, `QFontMetrics.width`, `setTabStopWidth`, `directory`→`dir` de QFileDialog…) posés une
  fois, au premier `qtpy.Qt*`, comme qtpy les pose. `installer()` refuse si le vrai qtpy est déjà importé.
- **`qtpy6/web/__init__.py`, `lancer()`** : `_qtpy.installer()` avant le script : dans la page, toute application
  qui importe qtpy (Spyder, qtconsole, qtawesome, superqt) reçoit qtpy6. En natif, rien d'installé (étape suivante).
- **`essais/spyder/preparer.py`** : retrait du bloc qui complétait `PySide6.QtCore` et posait `PySide6.QtWebEngine*`
  (lignes 69-86) : l'alias le rend inutile (item 4a).
- **`essais/spyder/spe.py`** : retrait de `--no-web-widgets` (W546 : le gel était l'alert() de loading.html, corrigé
  dans `moteur_web.py`).

## POURQUOI, alternatives écartées

- Relevé : 345 fichiers de Spyder importent qtpy (331 `qtpy.QtCore`, 289 `QtWidgets`, 181 `QtGui`, 36 `qtpy.compat`),
  et 75 dans qtconsole, qtawesome, superqt, qdarkstyle (paquets de Jupyter, de l'équipe Spyder, de pyapp-kit : pas à
  nous, vérifié dans leurs métadonnées).
- **Écarté : compléter `PySide6.*` par qtpy6** (D5 telle que posée) : deux couches (qtpy sur PySide6 retouché), les
  doublures fuient dans l'espace de noms de PySide6.
- **Écarté pour l'instant : réécrire les imports du fork** (`qtpy` → `qtpy6`, dans le générateur) : l'alias reste
  nécessaire pour les dépendances, la réécriture n'ajouterait qu'un gros diff face à Spyder amont. Réponse donnée au
  professeur sur « le plus propre » : l'alias seul, fork intact, une seule couche (qtpy6).
- Existant : `qtpy6/_binding.py` sert déjà `qtpy6.QtXxx` sans fichier ; l'alias s'appuie dessus. Les correctifs Qt6 sont
  repris de qtpy (MIT), branches PySide6/PyQt6 seules ; non servis : `qtpy.uic` (aucun appelant), `promote_enums` PyQt6.

## VÉRIFIÉ

- **Mesuré, natif** : `/DATA/Python/qtpy6_essais/w555/importer_spyder.py` importe les 325 modules (hors tests) de Spyder
  et de ses dépendances Qt qui importent qtpy : vrai qtpy 8 échecs, alias 8 échecs, les MÊMES (qtsass, cmap, pyconify,
  pint : dépendances optionnelles absentes). Ne prouve que les imports, pas le comportement des correctifs.
- **Mesuré, page** (Firefox, site construit à part dans `/DATA/Python/qtpy6_essais/w555/site`, testeur) : jalon8c 5/5
  avec l'alias et les widgets web (noyau prêt en 16,9 s, `1+1 → Out[1]: 2`, variable dans l'explorateur, redémarrage) ;
  logs `qtpy6_essais/w555/sonde_8c.log`, `capture_8c.png`. spe.py : aucune capture rendue, cause non établie.
- Défaut trouvé et corrigé : la boîte des dépendances disait « qtpy 2.4.3 (NOK) » : Spyder
  (`programs.is_module_installed`) refuse un module sans `__file__` ; l'alias le porte désormais, vérifié en natif
  (`is_module_installed('qtpy', '>=2.4.0')` → True), pas encore dans la page.
- `QNetworkInterface` absent de `qtpy.QtNetwork` (greffon spyder_collab) : DÉJÀ présent avec le vrai qtpy
  (`essais/spyder/capture_greffons.console.log`), PySide6 WASM ne l'a pas ; pas un effet de l'alias.

- Relecture (relecteur, 14:40), corrigé : le correctif `directory`→`dir` de QFileDialog retiré (qtpy6.QtWidgets
  accepte déjà les deux mots-clés) ; le drapeau « correctifs posés » mis APRÈS eux (un échec n'est plus suivi d'imports
  silencieusement à moitié corrigés). Natif relancé : 325 modules, 8 échecs, les mêmes.
- Relecture, laissé : `QMenu.exec_(actions, pos)` STATIQUE dans la page tomberait sur `menu_exec` (bloquant.py), qui
  attend une instance — même chose avec le vrai qtpy, appel d'instance correct ; `QTimer.singleShot` à récepteur et
  `QTextDocument.print_` non repris (PyQt6 seulement) ; `qtpy.QtCore.__version__` non servi (aucun appelant dans Spyder).

## RESTE

- Natif : où installer l'alias pour SmartPythonEditor sur le bureau (point d'entrée du fork, ou `import qtpy6`).
- D4 (roues et Pyodide du Worker, `spe.py:71-73`), D6 (chardet), 4c, 4d, Interpréteur : non commencés.
