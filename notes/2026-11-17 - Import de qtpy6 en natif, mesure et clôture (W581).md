# Import de qtpy6 en natif : mesure et clôture de l'item 21 (W581, 17/11/2026)

## Demandes
- Item 21 du TODO Portage (W567, 12/11) : `import qtpy.QtCore, QtGui, QtWidgets, QtWebEngineWidgets` 760 ms par
  l'alias qtpy6 contre 165 ms par le vrai qtpy ; ~0,5 s d'énumérations PySide6 attribuées à `_binding._pyside6_class`.
- Le professeur, 12/11 19:42 : « le profilage ne devra se faire que cette nuit à un moment où le CPU n'est pas utilisé
  et en concertation avec les autres sessions » (d'où : seulement des imports ×10, pas de cProfile de jour).
- 17/11 09:51, après la mesure : « peut tu chercher encore à accelerer ? » ; 10:16 : « le gain sûr seul » ; 10:19,
  le gain sûr s'étant révélé nul : « oui, clos l'item ».

## FAIT
1. **Mesure de référence** (banc `qtpy6_essais/equipe/w581/mesurer_import.py`, 10 processus, médiane, charge 12,8-13,3).
   Le venv a le `.pth` de qtpy6 déployé : la référence retire ce relais de `sys.meta_path`.

   | variante | série 1 | série 2 |
   |---|---|---|
   | vrai qtpy 2.4.3 | 228 ms | 223 ms |
   | qtpy6 HEAD | 267 ms | 231 ms |
   | qtpy6 avant 4174b11 (copie `w581/avant_4174b11/`) | 244,5 ms | 223,5 ms |

   Ratio 1,04 à 1,17 : la cible de l'item (≤ 2) était déjà tenue. 4174b11 (W577, alias en cache par classe) : sans
   effet mesurable à l'import, ce qui concorde avec son diff, qui ne touche que l'accès aux alias.
2. **Décomposition** (`w581/surcout.py` : PySide6 importé d'abord, puis qtpy chronométré ; `-X importtime`).
   PySide6 seul ≈ 100 ms. Ce que qtpy ajoute : 103-110 ms pour le vrai qtpy, 120-139 ms pour qtpy6. Sur ces ~120 ms :
   ≈ 75 ms servent à créer tous les types PySide6 (getattr de chaque nom : QtCore 26, QtGui 24, QtWidgets 23 ms), que
   le vrai qtpy paie aussi par `import *`, ≈ 11 ms vont à `finish` (alias de 714 classes) et ≈ 7 ms à QtWebEngineWidgets.
   Les seuls imports propres à qtpy6 hors Qt sont `importlib.abc` (4,5 ms, que `importlib.metadata` de Spyder charge
   déjà) et `shlex` (0,7 ms).
3. **Aucun code changé.** Ajout de `tests/test_import_natif.py`, une garde contre les régressions : import de qtpy6
   ≤ 2 × `from PySide6.QtXxx import *` (la référence est ce que fait le vrai qtpy, sans dépendre de qtpy, qui est
   absent du venv de test). Ratio mesuré 1,27 à 1,29 (3 essais, 153-169 ms contre 194-215 ms).

## POURQUOI on clôt sans code
- Les 760 ms de W567 ne se reproduisent pas : même PySide6 6.11.1 (installé le 16/08), `.pyc` présents (22/22).
  Hypothèse supposée, invérifiable : charge 28-35 ce soir-là et `.pyc` pas encore écrits juste après le déploiement
  de 19:35 (import à froid mesuré aujourd'hui : 426-525 ms) ; et le cProfile gonfle les petits appels.
- Le « gain sûr » des imports différés, que j'avais estimé à ~20 ms, est en fait d'environ 1 ms dans SmartPythonEditor,
  sous le bruit des médianes (±20 ms). Je me suis trompé une fois : `re`, `zipfile` et `importlib.resources` sont
  importés par shibokensupport de toute façon.

## Alternative écartée (décision du professeur, 10:16)
L'espace de noms paresseux en natif (PEP 562, comme le mode LAZY du web) ferait gagner ≈ 85 ms. Il est écarté parce
que PySide6 livré n'a pas le crochet de création de types (`Shiboken.setTypeCreationHook`, propre à notre build
WebAssembly) : une classe que Qt renvoie sans que le code l'ait jamais nommée (un événement, une option de style)
n'aurait pas ses alias snake_case (lu dans `_binding.py`, docstring et `load`, non mesuré). Sur un démarrage de Spyder
qui prend plusieurs secondes, ces 85 ms ne se voient pas.

## VÉRIFIÉ
- Mesures ci-dessus : mesuré (médianes de 10, processus neufs, machine chargée, charge notée).
- Cause des 760 ms de W567 : supposée.
- `tests/test_import_natif.py` : vert (pytest, SmartPython-3.12.13). C'est une garde : sans code changé, il ne peut
  pas y avoir de rouge avant.
- Aucun cProfile de nuit nécessaire.
