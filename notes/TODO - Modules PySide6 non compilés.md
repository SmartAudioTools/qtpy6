# TODO : modules PySide6 pas encore compilés en wasm (quand il reste des tokens avant une remise à zéro)

Demande de l'utilisateur, 11/10/2026 : « arrête, on ne compile que ce qui sert », puis « tu peux laisser les autres
modules dans un TODO que je ferais quand j'aurais des tokens à finir avant un reset ». Aucune application qtpy6
(SmartPythonEditor, SmartTeacher) ne les importe au 11/10/2026. Contexte, recette et pièges :
`notes/2026-10-10 - Modules Qt à la demande.md`.

## Plausibles en wasm, par dépôt Qt 6.10.2 à télécharger

Le shell n'a pas le réseau : ajouter le dépôt à la boucle Qt de `wasm/telecharger_sources.sh`, que l'utilisateur lance.
Puis `qt_wasm` (et `qt_hote` s'il faut un outil hôte) dans `wasm/construire.sh`, le module dans `MODULES_DEMANDE`, et
`DEPENDANCES`/`DEMANDE` dans `wasm/pyodide-qt.mjs`. Vérifier : `symboles.py verifier` vert, `fumee.mjs`, puis la sonde.

- [ ] **QtUiTools** (qttools) : `QUiLoader`, charger un `.ui` à l'exécution. Le plus utile de la liste.
- [ ] **QtHelp** (qttools) : à vérifier, il dépend de Sql (déjà compilé).
- [ ] **QtStateMachine**, **QtScxml** (qtscxml) : sans doute l'outil hôte `qscxmlc` (non vérifié).
- [ ] **QtWebChannel** (qtwebchannel).
- [ ] **QtNetworkAuth** (qtnetworkauth) : OAuth via QNetworkAccessManager, donc fetch, avec les limites CORS.
- [ ] **QtRemoteObjects** (qtremoteobjects) : sans doute l'outil hôte `repc` (non vérifié).
- [ ] **QtDataVisualization** (qtdatavis3d) : obsolète au profit de QtGraphs, déjà compilé.
- [ ] **Qt3DCore, Qt3DRender, Qt3DInput, Qt3DLogic, Qt3DAnimation, Qt3DExtras** (qt3d) : WebGL nécessaire.

## Libs Qt déjà construites, seule la liaison PySide manque

- [ ] **QtQuickTest** : `libQt6QuickTest.a` est déjà dans qt-wasm.
- [ ] **QtSpatialAudio** : `libQt6SpatialAudio.a` est déjà dans qt-wasm.

## Écartés

- Impossibles en wasm : WebEngine (×3), WebView, Pdf (×2), DBus, Bluetooth, Nfc, SerialPort, SerialBus, Sensors,
  Positioning, Location, TextToSpeech, HttpServer.
- Sans objet : Designer.
- Absents : Qt5Compat n'a pas de liaison PySide6 ; QtCanvasPainter n'existe qu'à partir de Qt 6.11.
