# Signaux manquants de la doublure QWebEngine (W558, 12/11/2026)

## Demande

Item 2 bis du TODO Portage (relevé par W551) ; brief W558 : « Le greffon `spyder_python_tutor` (`main_widget.py:385`)
fait `page.renderProcessTerminated.connect` : AttributeError à la première trace. Doublure : un `Signal` sous le nom Qt
dans `moteur_web.py`, jamais émis […], avec la signature Qt. Vérifie en même temps par `grep` […] quels AUTRES attributs
de `QWebEngineView`/`QWebEnginePage` sont appelés et manquent à la doublure. » Ordre du professeur (12/11 14:04) : « mets
des workers sur tous les items qui peuvent être traités indépendamment ».

## FAIT

- `qtpy6/web/moteur_web.py` : énumération `QWebEnginePage.RenderProcessTerminationStatus` (Normal, Abnormal, Crashed,
  Killed, valeurs 0-3 comme Qt) ; signal `renderProcessTerminated(RenderProcessTerminationStatus, int)` sur la page,
  jamais émis ; le même sur la vue, relayé depuis la page par `_SIGNAUX` comme les sept autres (Qt 6 le porte aussi sur
  `QWebEngineView`). Aucune ligne dans le greffon.
- `tests/test_doublures.py` : `test_moteur_web_render_process_terminated` — page et vue branchées comme le tuteur,
  émission à la main, la page et la vue reçoivent (statut, code).
- Relevé des autres attributs : `/DATA/Python/qtpy6_essais/w558/releve_attributs.py` (sortie `releve.txt`). Méthode :
  noms `.x(` et `.x.connect` des fichiers du fork (`spyder/`) et des greffons de `SmartPythonEditorPlugins` (quinze dossiers) qui
  citent WebEngine, retenus s'ils sont dans le `dir()` du vrai PySide6 (View, Page, Settings, Profile) et absents de la
  classe de la doublure (AST), hors noms de `QWidget`. Résultat, outre `renderProcessTerminated` :
  - `mainFrame` (`spyder/widgets/browser.py:280`) : branche `if not WEBENGINE` (QtWebKit), morte en Qt 6 — rien à doubler ;
  - `QWebEngineProfile.settings` (`browser.py:237, 301`) : faux positif, l'appel est `self.page().settings()`, doublé ;
  - énumérations employées (`FontFamily.*`, `FontSize.*`, `WebAction.Back/Copy/Forward/InspectElement/Reload/SelectAll/
    Stop`) : toutes présentes dans la doublure ;
  - méthodes SURCHARGÉES par le tuteur (`_DebugPage.javaScriptConsoleMessage`, `javaScriptAlert`) : existent sans être
    appelées par la doublure — pas d'AttributeError, mais `alert()` de pytutor.js ouvrirait le dialogue du navigateur au
    lieu de passer par `javaScriptAlert` (le commentaire du greffon le dit essentiel ; W546 a vu un gel par `alert()`).
    Inscrit au TODO Portage (item 2 ter), non fait : hors de l'appel qui plantait, et demande d'intercepter
    `window.alert`/`console` de l'iframe.

## POURQUOI

Le signal sous le nom Qt suffit : un navigateur n'a pas de processus de rendu séparé pour une iframe ; la doublure ne
peut rien observer à émettre. Signature Qt gardée (statut énuméré, int) pour que le lambda à deux arguments du tuteur
reste juste si un jour on l'émet.

Existant : `_SIGNAUX` de la vue relaie déjà les signaux de la page ; ajouté à la liste, pas de mécanisme neuf.

Alternative écartée : `getattr(page, "renderProcessTerminated", None)` dans le greffon — c'est la branche que la règle
CLAUDE.md interdit.

## VÉRIFIÉ

- Mesuré : le test échoue sans le correctif (`AttributeError: 'QWebEnginePage' object has no attribute
  'renderProcessTerminated'`, `git stash` de `moteur_web.py` seul) et passe avec ; `tests/test_doublures.py` 3 passés.
  Le double `navigateur_double()` n'a pas de `document.createElement` : le test lui passe `document=MagicMock()`.
- Site construit (`construire_site.py --sortie /DATA/Python/qtpy6_essais/w558/site`, sortie 0, app.zip 36955 Kio) ;
  sonde Firefox `index.html?script=greffons.py` : les sept greffons listés (tuteur INSCRIT, 41,6 s) puis plus rien
  jusqu'au délai de garde (590 s) — même arrêt que l'item 14 (W551) : l'action « Lancer » n'est pas atteinte. Le chemin
  du tuteur (`_ensure_web`, l. 342-385) n'est donc PAS mesuré dans la page : niveau « lu dans les sources + test
  unitaire ». Trace réelle demandée au professeur (sonde `--visible`).
- Règle : `grep -n "emscripten\|qtpy6\.web\|import js\b\|pyodide"` sur le greffon : aucune ligne ajoutée (aucune
  modification du greffon).
- Essai à la main du professeur (sonde `--visible`, 15:05, journal `/DATA/Python/qtpy6_essais/w558/capture_main.console.log`) :
  aucune trace Python après le démarrage, mais « Lancer » du tuteur non observé (professeur : « je n'ai pas fait
  attention »). Le dialogue d'erreur au démarrage est l'ImportError `QNetworkInterface` de `spyder_collab/network.py:43`
  (19,06 s, connu, item 14). « J'ai essayé de lancer le script qui était ouvert, et ça a tourné dans le vide en cherchant
  les variables d'environnement » : Exécuter de Spyder, hors de cet item, signalé au Superviseur.
