# Les huit autres modules Qt de qtbase en PySide6-WASM, chargés à la demande

Note du 10/10/2026. Fait dans la session « Superviseur » (qui ne supervise plus), à la suite du jalon 6 du portage de
SmartPythonEditor (`notes/2026-10-09 - Portage de SmartPythonEditor dans le navigateur, faisabilité.md`) : là,
`QPageSetupDialog` avait dû être doublé parce que tout `PySide6.QtPrintSupport` manquait dans Pyodide-PySide6. Le niveau
de preuve est donné section par section.

## Les demandes, citées

« il faut tous les compiler et les charger à la demande », puis « oui, commence par les huit de qtbase en /plan ».
Le plan approuvé : PrintSupport, Network, Sql, Xml, Concurrent, OpenGL, OpenGLWidgets, Test — une liaison PySide6
chacun, UN fichier par module, téléchargé et chargé au PREMIER `import PySide6.QtXxx`, jamais au chargement de la page.
Les autres modules Qt (Quick, Multimedia, Charts…) viendront après. Question posée le même jour, « la lecture d'un pdf
pourrait à terme utiliser le lecteur Qt de pdf sur le web ? » : non, QtPdf est bâti sur PDFium et Qt l'exclut à la
configuration en WebAssembly ; la voie reste une doublure qtpy6 de `QPdfView` sur pdf.js ou le lecteur du navigateur.

## Ce qui a été livré

- `wasm/construire.sh` : `MODULES` passe de 5 à 13 liaisons (phase `pyside`) ; la phase `pyodide` archive les 13 cibles
  et relie le module principal avec `-sFETCH` (patch `patches/pyodide-pyside6.patch`, `QNetworkAccessManager` en WASM
  repose sur `emscripten_fetch`) ; la phase `dynamique` lie, en plus de `pyside_agrege.so`, un `pyside_Qt<M>.so` par
  module (liaison PySide + `libQt6<M>.a` + greffons : sqlite pour Sql, `certonly` pour Network, importés par un
  `greffons_<M>.cpp` généré) et vérifie les symboles ; la phase `paquet` met les huit `.so` dans
  `pyodide-pyside6-0.29.3.1.zip`.
- `wasm/metatypes_qtcore.cpp` : les huit `QMetaTypeInterfaceWrapper<T>::metaType` de QtCore, instanciés dans chaque
  module (section « Choix »).
- `wasm/symboles.py` : lit les sections import/export des `.so`, écrit `exports.rsp` (ce que l'agrégat doit exporter
  pour les huit) et `--verifier` fait échouer la phase si un import d'un `.so` n'est fourni ni par l'agrégat, ni par
  le module principal (ses exports, ses imports `env`, et sa bibliothèque JavaScript lue dans `pyodide.asm.js`), ni par
  un `.so` chargé avant.
- `wasm/patches/pyside-qtnetwork-features-absentes.patch` : la liaison QtNetwork de PySide suppose des features que
  Qt-WASM n'a pas (ssl, dnslookup…) ; le patch les retire du typesystem.
- `wasm/pyodide-qt.mjs` (copié en `pyodide.mjs` du paquet) : table `DEMANDE` (nom de module → `/lib/pyside_Qt<M>.so`),
  un objet `portee` partagé par tous les `loadDynamicLibrary` (agrégat compris, `global: false`), un module JavaScript
  `_pyodide_qt` (`charger(chemin)` : fetch avec les jumeaux br/gz, `FS.writeFile`, `loadDynamicLibrary` asynchrone,
  `FS.unlink`, une seule promesse par module ; `deja(chemin)`), et le finder Python `QtAgrege` étendu : pour un nom de
  `DEMANDE` pas encore chargé, `pyodide.ffi.run_sync(charger(so))` (JSPI) puis le `ModuleSpec` habituel ; hors contexte
  suspendable, `ImportError` qui dit d'importer depuis le script lancé par `qtpy6.web.lancer` ou un slot.
- `wasm/fumee.mjs` : importe les huit (par `runPythonAsync`, qui entre par `callPromising`), sqlite `:memory:`
  (créer, insérer, lire → 42), `QDomDocument`, `QTest.qWait(20)` mesuré par `QElapsedTimer`, `QHostAddress`,
  `QPrinterInfo.availablePrinterNames()`.
- `hebergement/telecharger.sh` : les jumeaux `.br`/`.gz` des `pyside_*.so` ; `qtpy6/web/versions.json` : archive
  `pyodide-pyside6-0.29.3.1` et son sha256 (`79c01295…fdc4b`) ; `wasm/README.md` ; `essais/spyder/preparer.py` : la
  doublure `PySide6.QtPrintSupport` retirée.

## Mesures (10/10/2026, lien avec `-Oz`, avant compression)

| Fichier | Octets |
|---|---|
| `pyside_agrege.so` (avant → après : +531 Ko d'exports forcés) | 25 228 382 → 25 759 804 |
| `pyside_QtSql.so` (avec sqlite) | 2 008 792 |
| `pyside_QtNetwork.so` | 927 244 |
| `pyside_QtPrintSupport.so` | 384 927 |
| `pyside_QtOpenGL.so` | 344 249 |
| `pyside_QtTest.so` | 276 019 |
| `pyside_QtXml.so` | 238 539 |
| `pyside_QtOpenGLWidgets.so` | 101 314 |
| `pyside_QtConcurrent.so` | 74 143 |
| zip (0.29.3.0 → 0.29.3.1) | 15 716 020 → 17 370 517 |

Vérification des symboles : zéro import non résolu sur les huit (`symboles.py --verifier`, phase `dynamique` code 0).
Test de fumée node (v26.8.2, JSPI) : `sqlite=42 dom=texte qWait=True hote=127.0.0.1 imprimantes=[] concurrent=6`,
« fumée : OK ». **Testé dans le bac à sable, sous node seulement** au moment où cette section est écrite ; la page
(sonde Firefox, jalon 6 sans doublure) est dans la section « État » plus bas.

## Choix, avec l'alternative écartée

- **Un `.so` par module plutôt qu'un agrégat plus gros** : la demande (« à la demande »). Coût accepté : l'agrégat
  grossit de 531 Ko (les exports forcés) même pour une page qui n'importe aucun des huit ; mesuré, pas optimisé.
- **Exports forcés (`--export=<sym>` par fichier de réponse) plutôt que `--export-all`** : `--export-all` exporte tout le
  défini de l'agrégat (des dizaines de milliers de symboles, non mesuré en taille car le premier essai a montré que
  la liste exacte suffisait). La liste vient des imports réels des huit, moins ce que le module principal fournit.
- **`metatypes_qtcore.cpp` lié dans chaque module plutôt que Qt recompilé en visibilité par défaut** : Qt et PySide
  sont compilés en `-fvisibility=hidden` (`FEATURE_reduce_exports`), et un objet caché référence les DONNÉES
  externes par une relocation directe (`R_WASM_MEMORY_ADDR_REL_SLEB`), que wasm-ld refuse vers un symbole non défini
  (« not supported against an undefined symbol ») ; les fonctions, elles, passent par des imports `env`, et les
  symboles Python (visibilité par défaut) par la GOT. Relevé complet avec `--error-limit=0` sur les huit modules :
  exactement 8 symboles, les `QMetaTypeInterfaceWrapper<T>::metaType` de bool, int, long long, QByteArray, QString,
  QStringList, QRegularExpression, QSize (extern template instanciés dans QtCore). Ce sont des constantes avec un
  `typeId` fixé : une copie par module est sans effet (QMetaType compare par id). Recompiler Qt (des heures) pour huit
  constantes a été écarté ; un module futur qui en manque une le dira au lien, et la liste s'allonge.
- **La bibliothèque JavaScript lue dans `pyodide.asm.js`** : la première vérification rendait 100 `gl*` « introuvables »
  alors que la page les a — `pyodide.asm.wasm` n'importe que ce que SON code appelle, mais MAIN_MODULE=1 inclut la
  bibliothèque entière (`INCLUDE_FULL_LIBRARY`), et c'est dans `wasmImports={…}` du `.js` qu'elle se lit.
- **Le chargement dans le finder, par `run_sync`, plutôt qu'un préchargement par l'application** : la règle
  « une application ne sait pas où elle tourne » (`CLAUDE.md`) ; l'import PySide de QtOpenGL par QtOpenGLWidgets
  (`Shiboken::Module::import` dans `PyInit`) passe par le même finder, la pile C est suspendue par JSPI comme pour
  `stockage.monter`. Un chargement synchrone est interdit par Chrome au-delà de 4 Ko de wasm. Coût : un import depuis
  un contexte non suspendable (le haut d'un module importé par `runPython` synchrone) échoue avec un `ImportError`
  explicite ; le script de `lancer` et les slots sont suspendables.
- **`QThreadPool` absent de QtCore** (Qt sans fils) : `QtConcurrent` ne lie que `QFuture`/`QFutureWatcher`, le test de
  fumée ne compte que ses noms publics.

## Limites (documentées dans `wasm/README.md`)

`QNetworkAccessManager` passe par `fetch` : même origine ou CORS, pas de sockets ; pas de TLS natif (`certonly`) ;
QtConcurrent sans fils ; `QPrinterInfo` ne voit aucune imprimante, `QPrinter` écrit un PDF dans le système de
fichiers de la page.

## État et points ouverts

- Les étapes `pyside`, `pyodide`, `dynamique`, `paquet`, le test de fumée : faites et vérifiées (ci-dessus).
- La release GitHub `pyodide-pyside6-0.29.3.1` (zip à téléverser) et le push : à l'utilisateur.
- Jalon 6 rejoué sous Firefox 155 (sonde, `essais/spyder/sonde_jalon6.log`, 11 h 21) sans la doublure QtPrintSupport :
  `import mainwindow` et les 33 plugins passent, le même et seul échec qu'avant (`pylint`, métadonnées absentes), 0,8 s,
  60 Mio. Les quatre plugins qui tombaient sans la doublure (`editor`, `ipythonconsole`, `debugger`, `profiler`) passent :
  c'est la preuve que `pyside_QtPrintSupport.so` a été chargé par le finder depuis l'import d'un plugin. Pas de relevé des
  requêtes (la sonde ne les journalise pas) : « aucun `.so` téléchargé avant le premier import » est vérifié par lecture
  de `pyodide-qt.mjs` seulement. `QOpenGLWidget` affiché et GET `QNetworkAccessManager` dans une page : NON testés.
- Chrome (postes du lycée) : non testé ; le relais Chromium de l'utilisateur reste à faire si une page l'exige.
- `hebergement/telecharger.sh` lancé depuis le bac à sable (sans réseau) : le zip dépaqueté dans `exemple/pyodide-qt`,
  la roue sqlite3 recopiée depuis `SmartTeacher/QCM/web/pyqt6/pyodide-qt` (même empreinte) et les jumeaux br/gz produits à
  la main (les cinq dernières lignes du script) : le dossier est complet, 42 fichiers.
