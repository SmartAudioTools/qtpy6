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
  de `pyodide-qt.mjs` seulement — relevé ensuite par l'essai ci-dessous.
- **Essai dans une page, `essais/modules_demande/page.py`** (demande de l'utilisateur, 11 h 33 : « teste QOpenGLWidget et
  le GET réseau dans une page ») ; état « essai_fini » (pas « fini », que le gabarit pose lui-même dès que le script est
  lancé, avant tout rendu) ; mesuré sous Firefox 155 par la sonde, journal `sonde_gl.log` (git-ignoré) :
  - **GET `QNetworkAccessManager` : OK.** La page elle-même, HTTP 200, 2 175 octets, `NoError`, 0,07 s dans le bac à
    sable (2,0 s hors bac, où la machine servait aussi WebGL). `import QtNetwork, QtOpenGLWidgets` : 0,04 s, et
    `performance.getEntriesByType("resource")` montre `pyside_QtNetwork.so.br` et `pyside_QtOpenGLWidgets.so.br` chargés
    à ce moment-là, pas au démarrage : c'est le relevé des requêtes qui manquait au jalon 6.
  - **`QOpenGLWidget` : le module se charge et le widget s'exécute, mais ne s'affiche pas — et ce n'est pas réparable
    ici.** Hors bac à sable (la sonde lancée par l'utilisateur depuis son compte, seul endroit avec WebGL : le Firefox
    headless du bac n'ouvre aucun contexte WebGL, même sur un canvas nu, `/dev/dri` absent, préférences de rendu logiciel
    sans effet), le contexte est créé (OpenGL ES 3.0 via WebGL 2, `isValid()` vrai) et `paintGL` est appelé, mais chaque
    image donne « QRhiGles2: Context is lost » puis « QOpenGLWidget: Failed to create wrapper texture », `initializeGL`
    est rappelé 14 fois, et au bout de 0,6 s le wasm plante (« index out of bounds » dans Qt, page noire). Cause, lue dans
    `qwasmopenglcontext.cpp` : `makeCurrent` refuse toute surface autre que la première (`m_contextOwningSurface !=
    surface → false`), or le RHI de Qt rend son contexte courant sur une `QOffscreenSurface` de repli pour créer ses
    textures. C'est documenté par Qt (doc.qt.io/qt-6/wasm.html, lu le 10/10/2026) : « OpenGL context sharing is not
    supported. QOpenGLWidget and other classes which uses context sharing internally are not supported. » Le module
    `QtOpenGLWidgets` n'apporte donc rien d'utilisable dans une page ; il reste dans le paquet (101 Kio, chargé seulement
    si on l'importe) pour qu'un code de bureau qui l'importe sans l'afficher ne tombe pas sur un `ImportError`.
  - Trouvé en passant : la liaison WASM de `QtGui.QOpenGLFunctions` n'a **aucune méthode `gl*`** (`AttributeError:
    'QOpenGLFunctions' object has no attribute 'glClearColor'`), le bureau en a des dizaines. Shiboken les a écartées à
    la génération (ES 2 : des inlines dans l'en-tête Qt ?). Non creusé, sans objet tant que le widget est inutilisable ;
    l'essai peint par `QPainter`, qui marche des deux côtés.
  - Outil laissé dans le dossier : `sonde_console.py`, la sonde de qtpy6 plus la console du navigateur recopiée dans le
    journal (`console.warn`/`error`, erreurs JS, rejets). Sans elle, les qWarning de Qt-WASM (« WebGL context creation
    failed », « Context is lost ») sont invisibles : ils vont à `console.warn`, pas à stderr. **Idée, pas codée** : en
    faire une option `--console` de `qtpy6.web.sonde`.
- Chrome (postes du lycée) : non testé ; le relais Chromium de l'utilisateur reste à faire si une page l'exige.
- `hebergement/telecharger.sh` lancé depuis le bac à sable (sans réseau) : le zip dépaqueté dans `exemple/pyodide-qt`,
  la roue sqlite3 recopiée depuis `SmartTeacher/QCM/web/pyqt6/pyodide-qt` (même empreinte) et les jumeaux br/gz produits à
  la main (les cinq dernières lignes du script) : le dossier est complet, 42 fichiers.

## Suite (12 h 45 → 14 h) : Qt Quick, Multimedia et Charts, les sept derniers modules

### La demande, citée

« je te donne une ralonge de 5 points, pour finir les autres modules Qt comme Quick, Multimedia, Charts, et la doublure
QPdfView, mais essais d'economier en déléguant beaucoup plus ! » (12 h 45). La doublure `QPdfView` existe déjà
(`qtpy6/web/pdf.py`, `js/pdf_vue.js`, pdf.js vendu, servie par `qtpy6.QtPdf` et `QtPdfWidgets`) : rien à refaire, dit à
l'utilisateur. Délégation : la construction entière (recette, patch, liens, fumée) par un sous-agent, l'essai dans une
page par un second ; la session a relu le diff, les tailles et les journaux, et écrit cette note.

### Ce qui a été livré

- `wasm/telecharger_sources.sh` : qtshadertools, qtdeclarative, qtmultimedia, qtcharts en plus (archives récupérées par
  l'utilisateur, `journaux/telecharger.log`) ; `wasm/versions.txt` régénéré.
- `wasm/construire.sh` : `qt_hote <module> <témoin>` (qtshadertools pour `qsb`, qtdeclarative pour `qmltyperegistrar`,
  `qmlcachegen`… : la compilation croisée de Qt Quick les cherche par `-qt-host-path`) ; `qt_wasm <module> <lib>` pour
  qtsvg, qtshadertools, qtdeclarative, qtmultimedia, qtcharts, qui applique `wasm/patches/<module>-*.patch` ; `MODULES`
  à 20 liaisons, `MODULES_DEMANDE` à 15 ; archive `pyside6qml` (libpyside6qml, que QtQml lie) ; phase `dynamique`
  réécrite (ci-dessous) ; zip `pyodide-pyside6-0.29.3.2`.
- `wasm/patches/qtmultimedia-sans-fils.patch` : qtmultimedia refuse de se configurer sans la fonctionnalité `thread`
  (son `CMakeLists`) ; le portail est levé pour Emscripten seulement, et `qsamplecache_p.cpp` ne tire QNetwork que si
  `QT_CONFIG(network)`. Le greffon `wasm` de Qt Multimedia (balises `<audio>`/`<video>`, Web Audio) n'a pas de fil.
- `wasm/metatypes_qtcore.cpp` : ~35 instanciations `QMetaTypeInterfaceWrapper<T>` de plus (Qml, Quick, Multimedia,
  Charts), contre des relocations `R_WASM_MEMORY_ADDR_REL_SLEB` non résolues au lien.
- `wasm/symboles.py` : sous-commande `croises` (ce qu'un module fournisseur doit exporter aux modules chargés après lui) ;
  `manquants` ne retire plus ce que les modules exportent (Qml importe `QAbstractItemModel::hasChildren`, que Quick
  exporte aussi, mais Quick se charge APRÈS Qml : seul l'agrégat peut le servir).
- `wasm/pyodide-qt.mjs` : table `DEPENDANCES` (Qml ← Network, Quick ← Qml, QuickWidgets et QuickControls2 ← Quick,
  Multimedia ← Network, MultimediaWidgets ← Multimedia, Charts ← OpenGLWidgets) ; `charge()` charge les dépendances
  une à une avant le module (le wasm résout ses imports au chargement, pas à l'appel).
- `wasm/patches/pyodide-pyside6.patch` : `-lopenal` dans `MAIN_MODULE_LDFLAGS` (bibliothèque JS d'Emscripten, que le
  greffon multimedia importe ; `pyodide.asm.wasm` inchangé, md5 identique à la release, seul `pyodide.asm.js` grossit).
- `wasm/fumee.mjs` : QJSEngine (`6 * 7`), QQmlComponent qui instancie un `QtObject`, QAudioFormat, QMediaFormat,
  QLineSeries ; `globalThis.window = globalThis` (le répartiteur d'événements de Qt, une fois un QQmlEngine en poste,
  programme ses réveils par `window.setTimeout`, que Node n'a pas).
- `wasm/README.md`, `qtpy6/web/versions.json` (release `0.29.3.2`, sha256
  `c415eb71d1a11f0afb3bd52296ff24f840184a84316dceae2b3870c478fa9ad2`), `essais/modules_qt_suite/page.py` (l'essai page).

### Les choix, avec l'alternative écartée

- **Une bibliothèque Qt partagée par plusieurs modules vit dans UN module « fournisseur », lié en archive entière, et
  l'exporte** (Network dans QtNetwork, Qml/QmlMeta/QmlModels dans QtQml, Quick/QuickLayouts/QuickTemplates2 dans
  QtQuick, Multimedia dans QtMultimedia, OpenGLWidgets dans QtOpenGLWidgets). Écarté : la copie de la bibliothèque dans
  chaque module qui la lie (l'état statique de Qt dupliqué : deux registres de métatypes, deux moteurs QML). Mécanisme :
  `deja.txt` liste les archives et objets déjà pris (amorcé par l'agrégat, complété module après module dans l'ordre de
  chargement) ; `--whole-archive` pour les fournisseurs (Quick importe des membres de Qml que rien dans Qml ne
  référence : un lien partiel les aurait laissés dehors, vu au premier essai) ; second lien des fournisseurs en
  `--export-all` dans `tout/`, `symboles.py croises` en déduit la liste `--export=` du lien définitif. Coût accepté :
  les modules qtbase qui portent une bibliothèque grossissent (Network 927 → 968 Kio, OpenGLWidgets 101 → 158 Kio,
  Sql 2 009 → 2 064 Kio, PrintSupport 385 → 442 Kio).
- **L'agrégat est lié en DERNIER**, après le lien définitif des fournisseurs : le second lien d'un fournisseur importe
  cinq symboles de plus que le premier (`QImage::fill(QColor)`, `QAbstractItemModel::hasChildren`, `sibling`,
  `QPersistentModelIndex::flags`, `QMetaObject::Connection::operator=`), et `symboles.py verifier` échouait tant que
  l'agrégat se liait avant. Écarté : lier deux fois l'agrégat (plus long, même résultat).
- **Greffons QML statiques repris des `.prl`** : les objets `qrc_*.cpp.o` et `*_init.cpp.o` (`Q_IMPORT_QML_PLUGIN`) que
  les `.prl` de Qt nomment sont liés explicitement, par `prl_objets` et `qml_greffon` ; sans eux `import QtQuick` échoue
  à l'exécution (« module not installed »). Écarté : `qmlimportscanner` à la construction (il faudrait les `.qml` de
  l'application, inconnus ici) ; tout greffon QML existant (Controls : seuls les styles Basic et Fusion sont pris, les
  autres pèsent et demandent des ressources natives). Point ouvert : un style Controls non embarqué tombe sur Basic.
- **qtmultimedia patché plutôt qu'écarté** : le greffon `wasm` de Qt ne crée aucun fil, le portail `thread` du
  `CMakeLists` est une précaution générale. Écarté : construire Qt-WASM avec les fils (`-pthread`, SharedArrayBuffer,
  COOP/COEP sur GitHub Pages impossible). Niveau de preuve : construit, fumée Node (QAudioFormat, QMediaFormat) ; la
  lecture audio/vidéo réelle est l'objet de l'essai page ci-dessous.
- **Charts dépend d'OpenGLWidgets au chargement** (il lie la bibliothèque, pour `QAbstractSeries::useOpenGL`) alors que
  `QOpenGLWidget` ne marche pas dans une page (section précédente) : le rendu de `QChartView` est raster par défaut, le
  module OpenGLWidgets est juste chargé (158 Kio). Écarté : reconstruire qtcharts sans OpenGL (`-no-feature-opengl`
  est global à Qt, pas à qtcharts).

### Mesures (10/10/2026, `-Oz`, octets ; `.so` / `.br`)

Qml 4 930 997 / 1 029 596 ; Quick 6 348 938 / 1 549 903 ; QuickWidgets 211 560 / 48 938 ; QuickControls2 719 705 /
150 510 ; Multimedia 1 236 582 / 350 115 ; MultimediaWidgets 171 693 / 36 277 ; Charts 1 620 618 / 338 770. Agrégat
26 071 820 (avant : 25 759 804, +1,2 %) / 6 226 997 : le démarrage d'une page n'a pas bougé. Zip 22 385 362 octets (reconstruit après le correctif Quick ci-dessous).
Durées : `qthote` + `qt` 871 s ; `pyside` + `pyodide` < 10 min ; `dynamique` 100 à 150 s. Journaux : `qt-suite.log`,
`pyside-suite-1.log`, `dyn-suite3.log`, `fumee.log` dans `$RACINE/journaux/`.

### Niveau de preuve

- `symboles.py verifier` vert sur les quinze modules et `node wasm/fumee.mjs` vert (QJSEngine 42, QtObject instancié par
  le moteur QML, formats audio/média, série de points) : testé, journaux ci-dessus.
- Relu par la session : le diff entier (construire.sh, symboles.py, metatypes, pyodide-qt.mjs, patches, fumée, README),
  les tailles avant/après, le md5 de `pyodide.asm.wasm`.
- Non relu : le contenu du zip (liste fixe de `phase_paquet`, les quinze `.so` compris par construction).
- Navigateur réel : essai page ci-dessous.

### Essai page (Firefox 155 headless du bac à sable, `essais/modules_qt_suite/page.py`, 14 h)

La page importe QtCharts, QtMultimedia puis QtQuick/QtQuickWidgets depuis le script lancé par `lancer`, un contrôle
par module, et pose `essai_fini` ; la sonde (`essais/modules_demande/sonde_console.py`, console navigateur au journal)
lit les verdicts. Journal `essais/modules_qt_suite/sonde.log`, capture `capture.png` (relue : la courbe Charts).
- **Charts : OK**. `QChartView` peint (grab 978×748, 23 couleurs, 21 points), 0,9 s après l'import.
- **Multimedia : OK** pour ce qu'une page sans geste peut vérifier : `QMediaPlayer` + `QAudioOutput` créés, sortie
  « WebAssembly audio playback device », état `Stopped` ; le son lui-même n'est PAS vérifié (`NotAllowedError` : le
  navigateur refuse `play()` sans geste de l'utilisateur, c'est la règle de tous les navigateurs, pas un défaut).
- **Quick : import et exécution OK après correctif, rendu non vérifiable ici.** Premier essai : `import PySide6.QtQuick`
  fatal, `SuspendError: No matching WebAssembly.promising`. Cause, lue dans `pyodide.asm.js` : avec `global: false`, les
  exports d'un module latéral vont dans la portée locale, et le proxy `env` d'un module chargé ensuite ne résout
  DIRECTEMENT que `wasmImports` ; tout autre symbole reçoit un **stub JavaScript** (`stubs[prop] = (...args) =>
  resolveSymbol(prop)(...args)`), résolu au premier appel. Or l'init C de QtQuick appelle `Shiboken::Module::import("PySide6.QtOpenGL")`,
  module pas encore chargé (DEPENDANCES disait `Quick: ["Qml"]`) : le finder lance `run_sync(charge(...))`, et JSPI
  refuse de suspendre à travers une trame JS (le stub) sur la pile. Deux correctifs, les deux gardés :
  `Quick: ["Qml", "OpenGL"]` (relevé des `Module::import` de chaque `Qt*_module_wrapper.cpp` généré : Quick importe
  Core Network Gui OpenGL Qml), et `global: true` dans `charger` : les exports rejoignent `wasmImports`
  (`mergeLibSymbols`, premier défini gagne, ce qui est l'ordre de `resolveSymbol` de toute façon), un module chargé
  ensuite résout AU CHARGEMENT, sans stub. Sans `global: true`, tout `run_sync` (QFileDialog web, `monter`) appelé
  depuis un slot que déclenche un signal émis par un module latéral aurait le même défaut, latent. Vérifié : fumée Node
  verte avec `global: true` ; dans la page, QtQuick et QtQuickWidgets s'importent (0,14 s), `QQuickWidget` passe à `Ready`
  sans erreur QML. Le rendu, lui, échoue faute de WebGL dans ce Firefox (« WebGL context creation failed », « QQuickWidget:
  Failed to get a QRhi ») ; forcer le WebGL logiciel par préférences (`webgl.force-enabled`, `gfx.webrender.software`,
  `LIBGL_ALWAYS_SOFTWARE=1`) ne change rien, essai fait. Ce verdict-là est venu du navigateur hors bac à sable (points ouverts).
- Le zip `0.29.3.2` a été reconstruit après le correctif (il embarque `pyodide.mjs`) ; sha256 reporté dans
  `versions.json` et ci-dessus.

Passe de simplification avant commit (sous-agent Sonnet, relu) : enlevés `plus=()` (variable morte de la phase dynamique) et
le diagnostic `?import_tot` de page.py (plus de scénario) ; `MODULES` dérivé de `MODULES_DEMANDE` (une liste au lieu de
deux) ; commentaires « huit modules » mis à quinze (construire.sh, metatypes, README) ; dépendances du README renvoyées à
`DEPENDANCES`. Gardé contre son avis : `Quick: ["Qml", "OpenGL"]`, OpenGL n'étant pas un fournisseur de symboles mais la
liaison que l'init de QtQuick importe (c'est le défaut corrigé). Restent trois listes à tenir ensemble : `MODULES_DEMANDE`,
`DEMANDE` du .mjs, les imports de `fumee.mjs` ; le .mjs ne peut pas lire le .sh, non traité.

### Points ouverts (à regarder en premier)

- Rendu de Qt Quick : **vérifié** à 14 h 51, même sonde lancée par l'utilisateur hors bac à sable (Firefox 155 avec WebGL) :
  `VERDICT quick : OK QQuickWidget statut=Ready, framebuffer 978x170, 6612 points rouges, 4,03 s depuis l'import` ;
  capture `capture_hors_bac.png` relue (rectangle rouge « Qt Quick QML » sous la courbe Charts). Journal `sonde_hors_bac.log`.
  Commit `321f079`, release `pyodide-pyside6-0.29.3.2` publiée, push fait (`5e1b254..321f079`).
- Les jumeaux `.br` des sept nouveaux `.so` : **testés** à 14 h 55 (demande de l'utilisateur : « teste les .br des nouveaux
  modules dans la page »). `site/pyodide-qt-br/` = liens vers `dist/` + `brotli -q 11` des sept (mêmes tailles que ci-dessus),
  `site/pyodide-qt` pointé dessus, même sonde (`sonde_br.log`). La ligne des ressources ne montre que `pyside_QtCharts.so.br`,
  `pyside_QtMultimedia.so.br`, `pyside_QtQml.so.br`, `pyside_QtQuick.so.br`, `pyside_QtQuickWidgets.so.br` : décompressés par
  `DecompressionStream("brotli")`, chargés, sans repli sur le `.so` (les modules de qtbase, sans `.br` dans ce dossier,
  montrent le repli `.br` puis `.so` : c'est le témoin que le repli ne se confond pas avec le succès). Verdicts inchangés
  (Charts OK, Multimedia OK, Quick Ready sans rendu : Firefox du bac, pas de WebGL).
- `exemple/pyodide-qt` passé en 0.29.3.2 à 15 h 10 (« ok continues avec brotli ») : `hebergement/telecharger.sh pyside6
  <zip local>` jusqu'au curl de la roue sqlite3 (le bac à sable n'a pas le réseau, `Proxy CONNECT aborted` même en déclarant
  l'hôte), puis roue recopiée depuis `SmartTeacher/QCM/web/pyqt6/pyodide-qt` (sha256 de versions.json vérifié) et les cinq
  dernières lignes du script à la main : 63 fichiers, 18 `.br` (15,8 Mo), 18 `.gz`, les quinze `pyside_Qt*.so`. Le dossier
  est git-ignoré : rien à commiter, c'est ce que `deployer.sh`/l'action Pages publieront.
- Brotli plutôt que zstd (question de l'utilisateur, 15 h) : la décompression se fait dans la page par `DecompressionStream`,
  qui ne connaît que gzip, deflate et brotli (Firefox 155 ; pas Chromium 153). Zstd exigerait un décodeur WebAssembly
  embarqué dans la page, du code et du démarrage en plus pour un gain marginal face à `brotli -q 11`. Écarté sans mesure,
  par l'API ; l'utilisateur a tranché pour brotli.
- Style des Controls (`QQuickStyle`) : rien de réglé, le style Basic est celui que les greffons statiques apportent.
- `pyodide-qt.mjs` : l'`ImportError` « introuvable » d'un module absent de `DEMANDE` reste bruyante (pile JS entière).
- `sonde_console.py` n'affiche pas `x.message` d'une exception JS (une copie de travail l'ajoutait) : à intégrer.
- Une vérification que `DEPENDANCES` couvre les `Module::import` des wrappers Shiboken (sous-commande de `symboles.py`)
  aurait trouvé le défaut Quick à la construction : non écrite, c'est une fonction non demandée, notée ici.

## Suite (15 h 20 →) : WebSockets, Quick3D, Graphs et les greffons d'images, les quatre derniers modules de Qt-WASM

### La demande, citée

« tout ce qui peu être compilé de qt a été compilé en WASM ? » (15 h 15) — réponse : non, manquaient WebSockets, Graphs,
Quick3D, ImageFormats et Qt5Compat parmi les modules que Qt déclare pris en charge en WebAssembly ; WebEngine, Pdf, DBus,
Positioning… n'existent pas sur cette plateforme. Puis : « compile aussi WebSockets, Graphs, Quick3D et ImageFormats »
(15 h 18). Qt5Compat, non demandé, n'est pas construit.

### Ce qui a été livré

- `wasm/telecharger_sources.sh` : les quatre archives `*-everywhere-src-6.10.2.tar.xz` de plus (md5 vérifiés par le
  `md5sums.txt` de Qt, déjà présent) ; `wasm/versions.txt` les inscrit. Téléchargement tapé par l'utilisateur (le bac à
  sable n'a pas le réseau), journal `wasm/telecharger_sources.log` (git-ignoré) lu à mon réveil : « == Terminé », 1,9 Go.
- `wasm/construire.sh` : `qt_hote qtquick3d bin/balsam` (les outils hôte Quick3D que la configuration croisée de qtquick3d
  et qtgraphs réclame par `-qt-host-path`, comme qsb et qmltyperegistrar) ; `qt_wasm` prend un témoin relatif à
  `$QTWASM` et non plus sous `lib/`, parce que qtimageformats n'installe que des greffons ; `phase_qt` += qtwebsockets,
  qtimageformats, qtquick3d, qtgraphs. `MODULES_DEMANDE` += WebSockets Quick3D Graphs GraphsWidgets (dix-neuf) ;
  `FOURNISSEURS` += Quick3D Graphs ; l'agrégat prend les greffons `libq{tga,wbmp,tiff,webp,icns}.a` ; cas Quick3D
  (Quick3D et Quick3DUtils entières, RuntimeRender, ShaderTools, glslang et SPIRV-Cross, greffon QML `qquick3dplugin`)
  et Graphs (Graphs entière, QuickShapes, greffon QML `graphsplugin`) ; WebSockets et GraphsWidgets par le cas général.
  Trois défauts trouvés par `symboles.py verifier` au premier passage (15 h 34), corrigés dans la recette :
    - WebSockets importe douze membres de `QHttpHeaderParser`, classe privée de QtNetwork dont l'objet
      (`qhttpheaderparser.cpp.o`) n'est référencé par rien dans Network : jamais tiré, donc jamais exporté. Variable `tire`
      du cas Network, `-Wl,--undefined=` sur son constructeur, qui force le membre (écarté : Network entière, 2 Mo de plus
      sur un module de 1 Mo ; extraire l'objet de l'archive dans WebSockets, une classe privée liée deux fois) ;
    - GraphsWidgets importe `QQuickWidget::setContent`, `setResizeMode` et `engine` : QuickWidgets n'était pas dans
      `FOURNISSEURS`, ses symboles Qt restaient hidden. Ajouté ;
    - Graphs, relié une seconde fois avec ses exports pour GraphsWidgets, importe alors `QQuickItemGrabResult::image`
      de Quick (un export tire son objet, qui importe à son tour), mais Quick avait déjà été relié sur les imports du
      premier lien. La passe croises → relien des fournisseurs est répétée (trois au plus, arrêt dès que croises ne rend
      plus rien) ; seuls les fournisseurs qui gagnent des exports sont reliés. Le même effet était déjà traité pour
      l'agrégat (lié en dernier), pas entre fournisseurs.
  Paquet `pyodide-pyside6-0.29.3.3.zip`.
- `wasm/qt_statique.cpp` : `Q_IMPORT_PLUGIN` des cinq greffons d'images (QTgaPlugin, QWbmpPlugin, QTiffPlugin,
  QWebpPlugin, QICNSPlugin). mng et jp2 demandent libmng et jasper, absents ; dds n'existe plus dans qtimageformats 6.10.
- `wasm/patches/pyodide-pyside6.patch` : `-lwebsocket.js` sur le lien du module principal (`llvm-nm` : libQt6WebSockets.a
  importe dix `emscripten_websocket_*`, qui ne viennent que de cette bibliothèque JavaScript d'Emscripten) ; même ligne
  ajoutée à la main au `Makefile.envs` déjà patché (le patch se reconnaît à son inverse), ancien `pyodide.asm.{js,wasm}` à
  la corbeille pour forcer le relien.
- `wasm/pyodide-qt.mjs` : `DEPENDANCES` += `WebSockets:[Network], Quick3D:[Quick], Graphs:[Quick3D],
  GraphsWidgets:[Graphs, QuickWidgets]` (les `load-typesystem` des quatre typesystems PySide6 et les `.prl`) ; `DEMANDE` += les quatre.
- `wasm/fumee.mjs` : import des quatre, un `QWebSocket` construit, `QImageReader.supportedImageFormats()` doit contenir
  tga, wbmp, tiff, webp, icns. `wasm/README.md` à jour (phases, 24 liaisons, greffons, 0.29.3.3).

### Les choix, avec l'alternative écartée

- Greffons d'images dans l'agrégat et non dans un module à la demande : `QImageReader` cherche ses greffons au premier
  usage dans QtGui, qui est dans l'agrégat ; un module « ImageFormats » séparé n'aurait pas d'import Python qui le
  déclenche (PySide6 n'a pas de liaison ImageFormats). Coût : la taille de l'agrégat au démarrage, à mesurer ci-dessous.
- libtiff et libwebp ne sont pas des bibliothèques `Bundled*` séparées : les `.prl` des greffons ne citent que Gui, Core
  et les bundled de qtbase ; elles sont compilées dans l'archive du greffon (vérifié par lecture des `.prl`).
- Quick3D entière seulement pour Quick3D et Quick3DUtils, pas RuntimeRender (3,5 Mo) ni glslang/SPIRV-Cross (9 Mo
  d'archives) : Graphs importe l'API publique de Quick3D ; si `symboles.py verifier` manque des membres de RuntimeRender,
  l'ajouter à `entier`. ShaderTools, glslang et SPIRV-Cross restent nécessaires : Quick3D compile ses shaders à l'exécution.
- Greffons QML de Quick3D : le seul `qquick3dplugin` (`import QtQuick3D`) ; Helpers, Effects, Particles3D, AssetUtils
  ne sont pas liés (non demandés, ~2 Mo d'archives). Les composants QML de Graphs importent QtQuick, QtQuick3D, Layouts
  et Window (tous présents) ; `QtQuick.Controls` n'apparaît que dans ses fichiers `designer/`, hors exécution.
- Le script de construction a été modifié PENDANT que `qthote qt` tournait (faute : règle « ne jamais éditer un script
  shell qui tourne ») : bash a relu le fichier décalé et s'est arrêté sur une « erreur de syntaxe ligne 355 » — APRÈS
  la fin de `phase_qt` (les quatre modules installés, SBOM de qtgraphs finalisé), au moment de reprendre la boucle des
  phases. Sans conséquence ici, vérifié par la présence des bibliothèques et des `.prl` ; les phases suivantes sont
  lancées sans retoucher le script.

### Mesures (10/10/2026, `-Oz`, octets ; `.so` / `.br`)

Quick3D 6 511 042 / 1 818 825 ; Graphs 2 446 365 / 572 182 ; GraphsWidgets 232 925 / 47 770 ; WebSockets 270 346 /
66 107. Reliés avec des exports de plus : Network 1 004 979 / 244 008, Quick 6 403 718 / 1 561 452 (était 6 348 938).
Agrégat 26 846 656 (avant : 26 071 820, +3 %, les cinq greffons d'images) / 6 418 766. Zip 25 913 614 octets, sha256
`34562ae3…7394` (`qtpy6/web/versions.json`). Seconde passe des exports croisés : seul `croises_Quick.rsp` non vide
(`QQuickItemGrabResult::image`), la troisième vide. Journaux : `pyside.log`, `pyodide.log`, `4modules-dyn2.out`,
`paquet.log` dans `$RACINE/journaux/`. `exemple/pyodide-qt` régénéré depuis le zip : 20 `.so`, 22 jumeaux `.br` et `.gz`,
roue sqlite3 vérifiée par sha256.

### Niveau de preuve

- `symboles.py verifier` vert sur les dix-neuf modules et `node wasm/fumee.mjs` vert (`ws=1024 q3d=True graphs=True
  gw=True images=True`) : testé. Ce que la fumée prouve : les quatre liaisons s'importent et se chargent dans l'ordre de
  `DEPENDANCES`, un `QWebSocket` se construit, `QImageReader` liste les cinq formats.
- NON testé : un rendu Quick3D ou Graphs (il faut un navigateur avec WebGL, hors bac à sable comme pour Quick) ; une
  connexion WebSocket réelle (le bac à sable n'a pas le réseau) ; la lecture effective d'une image webp ou tiff.
- Relu par la session : le diff entier des onze fichiers ; les tailles ; le journal de l'exemple.

### Points ouverts (à regarder en premier)

- Sonde page (Firefox) non faite pour ces quatre : à importer depuis un slot comme les sept précédents (essai
  `essais/modules_qt_suite/page.py`, à étendre), et le rendu 3D hors bac à sable.
- Quick3D : seuls `QtQuick3D` (qquick3dplugin) est lié ; `QtQuick3D.Helpers`, `.Effects`, `.Particles3D`, `.AssetUtils`
  manquent à un QML qui les importe (erreur de module QML à l'exécution, pas de lien).
- Greffons d'images : mng et jp2 absents (libmng, jasper non fournis par Qt).
- La boucle des exports croisés est plafonnée à trois passes sans échec explicite si la troisième en laisse : c'est
  `symboles.py verifier`, juste après, qui arrêterait la phase.

## Le son d'un .ogg dans le navigateur : greffon audio de QtMultimedia corrigé (0.29.3.4, 10/10/2026)

Demandes de l'utilisateur, à l'essai du son dans le lecteur SmartTeacher : « je n'entend aucun son et la touche reste
grisé une fois cliquée », puis, après une cale JavaScript (`905cc1f`) : « c'est qt qui est bugé ?? » et « peux tu plutot
reparer qt ? ».

**Cause (mesurée, sonde Firefox du scratchpad de la session SmartTeacher)** : `qwasmaudiooutput.cpp`, `setSource` d'un
fichier local, pose sur le `<source>` le type tiré du NOM du fichier par `QMimeDatabase` : `audio/vorbis` pour un `.ogg`
en wasm. Firefox et Chrome répondent `canPlayType("audio/vorbis") == ""` : le `<source>` est écarté, son `error` part
sur lui, et le greffon, qui n'écoute que l'`<audio>`, ne l'apprend jamais. Résultat : ni son, ni `errorOccurred`, ni
`EndOfMedia`. En natif, le backend FFmpeg ignore ce type, d'où le bon fonctionnement sur le bureau.

**Fait** : `wasm/patches/qtmultimedia-type-de-source.patch`, appliqué par `patcher qtmultimedia` comme
`qtmultimedia-sans-fils.patch` :
  - le type n'est posé que si `canPlayType` le connaît ; sinon le navigateur reconnaît le fichier par son contenu ;
  - l'`error` du `<source>` est relayé en `errorOccured(3 = NetworkNoSource)`, donc en `QMediaPlayer::ResourceError`,
    jusqu'au premier `loadeddata`. Le relais est débranché à `loadeddata` : un `play()` refusé par le navigateur
    (geste absent) remet l'élément à zéro et relance cette erreur sur une source pourtant lisible (mesuré : `rs=0 ns=3
    err=null` après « can play »). Un premier jet gardé par `readyState == 0` relayait ce cas à tort.

`qtpy6web.js` : la cale `types_media()` de `905cc1f` est RETIRÉE. Le correctif est maintenant dans Qt, et la cale ne
corrigeait que le type, pas le silence sur un fichier illisible.

Archive `pyodide-pyside6-0.29.3.4.zip`, 25 913 626 octets, sha256 `0d8f5a7a…1544` (`versions.json`). Seul
`pyside_QtMultimedia.so` change d'origine ; `construire.sh dynamique paquet` relie le reste à l'identique.

**Alternatives écartées** :
  - garder la cale JS : l'utilisateur a demandé « plutôt » Qt. La cale masquait le défaut pour une page qtpy6 seulement,
    et ne disait rien d'un fichier réellement illisible ;
  - corriger `QMimeDatabase` (audio/ogg pour .ogg) : touche toutes les applications et tous les types, alors que le
    défaut est de faire confiance à un type deviné ;
  - relayer en `ResourceError` seulement sous `readyState == 0` : faux positif mesuré (voir ci-dessus).

**Niveau de preuve** :
  - Testé dans le Firefox de la sonde, sans la cale JS :
    - `la_440.ogg` atteint « loaded data » et « can play » (avant le correctif : aucun des deux) ;
    - un faux `.ogg` (texte) rend `ResourceError "The browser cannot play this media"` (avant : rien, par lecture du
      code ; non rejoué sans le correctif) ;
    - un `play()` refusé ne produit plus d'erreur.
  - NON testé : le son entendu et la fin de lecture (`EndOfMedia`). Le Firefox du bac à sable n'a pas d'horloge audio :
    c'est l'essai de l'utilisateur dans son navigateur, après publication.
  - Chrome non essayé.
