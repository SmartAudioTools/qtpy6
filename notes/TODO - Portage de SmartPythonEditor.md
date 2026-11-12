# TODO - Portage de SmartPythonEditor dans le navigateur

Demande de l'utilisateur (11/10/2026, faisabilité, section « Doublure QWebEngineView ») : « je t'ai dis que je voulais
le code source de SmartPythonEditor agnostique et permetre à qtpy6 de l'executer aussi bien en natif que sur le web ».
Sources : `notes/2026-10-09 - Portage de SmartPythonEditor dans le navigateur, faisabilité.md` (dite « faisabilité »),
`notes/2026-10-11 - Doublure zmq, plan.md` (« zmq »), `notes/2026-10-12 - Pyxel dans la page.md` (« Pyxel »),
`notes/TODO - Son de Pyxel dans la page.md` (« TODO son »), `notes/TODO - Modules PySide6 non compilés.md`.
Règle (`CLAUDE.md` de qtpy6) : même code natif et web ; toute différence est un MANQUE de qtpy6, comblé par une
doublure sous le nom de l'API Qt ou par un réglage donné une fois, jamais par une branche `if WEB` dans l'application.

Fork : `/DATA/Python/FORKS/SmartPythonEditor` (a8aa440d4 du 01/11/2026, « Spyder 6.1.5 + correctifs SmartOS + support
de distribution », lu par `git -c safe.directory='*' log -1` le 12/11/2026). Essais : `essais/spyder/`. Commande
d'essai commune (zmq, « Relevé des essais de la nuit du 12/10 ») :

    cd /DATA/Python/qtpy6/essais/spyder
    P=/DATA/Python/SmartPython/CachyOS/versions/SmartPython/bin/python
    $P -m qtpy6.web.sonde 'site/index.html?script=<essai>.py' capture_x.png --racine site --delai 800 > sonde_x.log 2>&1

## Fait et commité

Révisions relevées par `git log -- essais/spyder qtpy6/web notes` le 12/11/2026.

- Note de faisabilité et jalon 1, le `CodeEditor` de Spyder dans la page (2,7 s, 86 Mio) : ff78408 (09/10).
- Renommage des trois slots homonymes d'un signal dans le fork, `retirer_alias_signaux` retiré de l'essai : 9d22c29
  (09/10). PERDU depuis : voir « Reste à faire », item 3.
- Jalon 2, frappe, sélection, pliage, mémoire stable ; correctif `bloquant.py` (slot à QEvent sur place) : c0dbf47.
- Jalon 3, programme de l'élève dans un Worker, console `ShellBaseWidget` : dd8befd (09/10).
- Jalon 4, complétion jedi dans un Worker derrière `QProcess` : db10fe6 (10/10).
- Jalon 5, fichiers relus après rechargement (IDBFS) : 76f4be4 ; jalon 5 bis, dossier autorisé de Chrome : a381c71,
  f18848f (10/10).
- Doublure `application(persistant=chemin)` (`autoPersist` d'IDBFS) : 4027e8f (10/10).
- Jalon 6, import de `mainwindow` et des 33 plugins, 1 à 2 s, 31 Mio : 6db34de (10/10).
- Jalon 7, vraie MainWindow, énumérations de `QProcess` sur `ProcessusWeb`, `application()` sur une QApplication créée
  ailleurs : 3a6d921 (11/10). La faisabilité dit « FAIT (non commité) » : périmé, c'est commité.
- Doublure `QWebEngineView` (`calque.py`, `moteur_web.py`, `QtWebEngineWidgets.py`, `QtWebEngineCore.py`) : 71c0849
  (11/10). La faisabilité dit « non commité » : périmé aussi.
- Correctif `js` lu à l'appel de `os.cpu_count()` (`fils.py`) : 9d29f8f (11/10).
- Jalon 8a, noyau Spyder dans un Worker, doublures `zmq_web`, `threading_web`, `psutil_web`, `socket_web` : 7662a9b.
- Jalon 8b, comm Spyder, battement, interruption par signal livré au `sleep`, redémarrage, 7/7 Firefox : a4ee0c6.
- Jalon 7 rejoué avec noyau : alias `_Alias` qui cèdent la place à l'application, doublures du client LSP : adf75de.
- Jalon 8c : `postEvent` d'un événement ≥ `User` livré comme un slot : 80998c9 ; entrée de page sans tâche asyncio
  courante (`_hors_tache`) : 9604419 ; gel attribué aux widgets web, relevé des essais : b4e8e99, 23a3a59 (12/10).
- SmartPythonEditor plein page, `site.getuserbase()` du noyau, avertissements ICU filtrés : e33f436 ; barre d'outils :
  a98e1ab ; plein écran du navigateur et Interpréteur rempli : 08b3ed5, 148c50f ; contour bleu (`EN_RETARD`) : 099e2fc.
- Pyxel : doublure `pyxel_web` (init, flip, run) 9326528, 48e5a9b, 9d46cab ; page isolée COOP/COEP f02c16c ;
  `SharedMemory` cc53b4e ; images et clavier en direct, `os.mkfifo` → `OSError`, `reconcilier()` : 2aea235 (12/10).
- Essai `spe_monkey.py` (jeu d'élève) et diagnostics du triangle : f4b0553, 8c4a009, 9c56eb7, 8d9c3db, b032805 (12/10).
  Le patch GC est commité comme FICHIER (`notes/2026-10-12 - doublure gc (preambule, non appliquée).diff`, 8d9c3db),
  pas appliqué.

## Fait, non commité

`git status --short essais/spyder qtpy6 notes tests` (12/11/2026) ne montre rien d'autre que
`notes/TODO - Vitesse du rendu dans le navigateur.md`, étranger à ce portage. Tout le code du portage est commité.
Restent hors git, ignorés (`git check-ignore`), donc perdus si le dossier est nettoyé : `spe_m3.py`, `spe_m4.py`
(reproduction du plantage du triangle), `sonde_noyau.py`, `noyau_pas.py`, `sonde_boucle.py`, `diag8b.py`, le site
`essais/spyder/site/` (construit AVEC le patch GC, TODO son) et les roues de `essais/roues/`, `essais/spyder/roues/`.

## Reste à faire

Du plus bloquant au moins bloquant. « Niveau » : mesuré / lu dans les sources / supposé.

1. **Le triangle « Exécuter » (F5, `%runfile`) tue le noyau.** Obtenir un `%runfile` qui ne plante jamais.
   - Cause (TODO son, « Suite du 12/10, 18 h 45 ») : passes AUTOMATIQUES du GC de Python 3.14 + piles JSPI entrelacées
     dans le Worker (fils de `threading_web`). Correctif écrit, mesuré, mis de côté : `preambule._doubler_gc`.
   - Existant : `grep _doubler_gc qtpy6/` → rien ; le patch est `notes/2026-10-12 - doublure gc (preambule, non
     appliquée).diff` (`git apply`). `_ramasser` (`qtpy6/web/__init__.py:104`) fait déjà la même chose côté PAGE.
   - Fichiers : `qtpy6/web/preambule.py` (installé aussi dans le Worker de la console du lecteur QCM : c'est la raison
     du report). Application : aucun.
   - Essai : `sh essais/spyder/sonde_tri.sh` (Firefox visible avec WebGL, l'utilisateur clique le triangle) ;
     reproduction sans affichage : `spe_m4.py?…&bouton=1` (ignoré par git).
   - Niveau : mesuré (triangle passé par l'utilisateur le 12/10 à 19 h 45 avec le patch).
   - Décision à prendre (section « Décisions », D2 : options A, B, C). Puis l'item 1 bis.
   - **W545, 12/11 14:15 (note `2026-11-12 - Doublure GC du Worker (W545).md`)** : parade factorisée avec `_ramasser`
     (module commun `ramasse_miettes.py`), conservée dans le .diff ci-dessus (136 lignes), NON appliquée. Lecteur QCM :
     même sortie avec et sans (console, soumettre, fin_epreuve python_tp). **Triangle sans affichage : la parade ne
     suffit pas** — build A et archive du 12/10 18:45 meurent 3/3 (`unreachable executed` pyodide.asm.wasm:5614267) ;
     témoin sans parade : `index out of bounds` 2120315 ; témoin « GC coupé sans passe » : pas d'erreur mais le code K4
     n'a jamais tourné. Machine chargée (8 workers, Firefox concurrents, `site/app.zip` reconstruit par W553 au même
     moment) : **à rejouer machine calme**, `qtpy6_essais/equipe/w545/tri.sh <étiquette> [n]` après
     `variante_app.py A|sans|coupe` (écrit `essais/spyder/site/app.zip`, PARTAGÉ). Niveau « mesuré 12/10 » ci-dessus :
     à revoir, il ne reposait que sur le triangle visible de 19:45.
   - **Autre signature, W568 (professeur, 12/11 19:20, ×5, dans la fenêtre de W566)** : `%runfile` dans la console de la
     page rend `SystemError: Cannot enter a promising task from inside another running promising task`, pile
     `code_runner._exec_code:597` → webloop `run_handle`. **Diagnostic W568 (19:45)** : la trace est le vidage
     faulthandler d'un Pyodide MORT dans le Worker (pendant `ast.parse` du `%runfile`) ; la tâche morte n'est jamais
     sortie, `in_task` reste vrai, chaque `run_handle` suivant est refusé. Le noyau ne survit pas : c'est ce plantage-ci
     vu dans la console, cause du fatal inconnue (question posée au professeur : la ligne « The cause of the fatal
     error was » de F12). Manque de qtpy6 : `travailleur.js` sans `on_fatal` (W568, après accord de W564). Source du message (lu, Pyodide 314.0.7 du Worker, `site/pyodide/pyodide.asm.wasm`) : `enter_promising_task`
     (`src/core/stack_switching/pystate.c`), drapeau unique `in_task` ; `run_handle` de la WebLoop est
     `create_once_callable(…, _may_syncify=True)`, donc une entrée promettante. Fichiers : `qtpy6/web/js/qtpy6web.js`,
     `bloquant.py`, `threading_web.py` (et le `preambule.py` de W564 : `_attendre`, `_garde_vie`, `time.sleep`, tous en
     `run_sync`). Essai : `sh essais/spyder/sonde_tri.sh` (spe_m4/spe_monkey périmés : assert `configurer`) ;
     `essais/spyder/gc_jspi/spe_rf.py` n'envoie pas le `%runfile` (`sw.execute` d'un QTimer ne revient pas). Niveau :
     lu dans les sources, pas reproduit ; note `notes/2026-11-12 - runfile et tache promising imbriquee (W568).md`.
1 bis. **Reproduction minimale, puis patch de Pyodide / JSPI** (demande de l'utilisateur, 12/11 13:58-13:59 : « et on
   ne peut pas réparer Pyodide / JSPI ? », « ajoute la reproduction minimale et le patch Pyodide au TODO »). La parade
   de l'item 1 tient l'éditeur en vie ; la cause, elle, n'est que supposée (GC jeune parcourant les piles des
   `PyThreadState` périmés de la réserve de Pyodide) et doit être PROUVÉE avant tout patch.
   - a. Reproduction minimale : Pyodide nu sous Node, piles JSPI entrelacées (deux fils coopératifs qui s'attendent),
     `gc.set_threshold(1, 1, 1)` ; le 12/10 l'essai `$TMPDIR/gcnu.mjs` (perdu) ne plantait PAS encore. Ce que la
     mesure de l'option C (item 1) apprend sur la fenêtre critique (la bascule seule, ou toute suspension) guide
     l'écriture. Garder le script dans `essais/spyder/gc_jspi/` (pas `$TMPDIR`), avec la version de Pyodide, de Node
     et la trace du plantage.
   - b. Cause prouvée : localiser dans les sources de Pyodide / CPython (bascule JSPI, `pystate`, `_PyThreadState` de
     la réserve) ce que la passe jeune lit de faux ; le dire avec le fichier et la ligne, niveau « lu dans les sources
     + mesuré ».
   - c. Patch Pyodide dans la chaîne de construction existante (`wasm/patches/`, même voie que
     `qtbase-wasm-defilement.patch` ; Pyodide-PySide6 0.29.3.7, release GitHub), reconstruire, rejouer a. puis le
     triangle (`sonde_tri.sh`) SANS la parade de l'item 1 : c'est le test qui échoue sans le correctif.
   - d. Signalement amont (Pyodide, et CPython si b. l'y situe) avec a. et c. Puis retirer la parade de l'item 1 si le
     patch suffit, ou la garder en la documentant comme redondance volontaire.
   - Existant : rien dans `qtpy6/` ; `outils_wasm/pyside6/build/` et `wasm/patches/` pour la construction. Niveau :
     supposé.
   - Piste (W553, 12/11) : dans 9 captures du 12/10, « Cannot enter a promising task » toujours par `pomper`
     (qtpy6web.js) → callPromising, puis « NoGilError » puis « index out of bounds » (monkey, ref, tri2). Option C non
     mesurée : `_garde_vie.run_forever` reste dans `run_sync` toute la vie du noyau (« pendant une suspension » = toujours).
   - Coût : chaque essai de c. est une reconstruction de Pyodide-PySide6 (durée à relever à la première). Ne commence
     c. qu'avec b. prouvée.
   - **Erreur fatale à 333 s, sans Exécuter** (W558, 12/11, non attribué ; `sous_processus.py` est à W548) : essai
     `--visible` du professeur, page laissée ouverte : Firefox « Script terminated by timeout » puis « Pyodide has
     suffered a fatal error » ; pile : `kernel_handler.py:106 run` → `sous_processus.py:101 read1` → `fils._attendre`
     → `bloquant._suspendre` → `bloquant.py:446 un_coup_` (lecture bloquante du canal noyau).
     Journal : `/DATA/Python/qtpy6_essais/w558/capture_tuteur.console.log`. Niveau : mesuré une fois.
2. **[FAIT W546, 12/11] Les widgets web de Spyder gèlent la page au démarrage de la console.** Obtenir la console sans `--no-web-widgets`.
   - FAIT (note `2026-11-12 - Widgets web, gel au démarrage (W546).md`) : le gel était l'`alert()` de `loading.html`
     (image en `'file:///…'` dans un script, non servie) ; `_urls_script` dans `moteur_web.py` ; 8c 5/5 avec widgets
     web, Firefox, une passe. D3 sans objet. Reste : `spe.py` sans l'option (W555) ; doublure `javaScriptAlert`.
   - Cause (zmq, « Le gel au démarrage ») : la page de chargement (`ClientWidget._create_loading_page`, `FrameWebView`)
     sur la doublure `QWebEngineView`. Avec `--no-web-widgets` : 5/5 (In [1] en 3,6 s, `1+1`, variables, redémarrage).
   - Existant : `qtpy6/web/moteur_web.py:438` (`class QWebEngineView(Calque)`), `qtpy6/web/calque.py`.
   - Fichiers : `moteur_web.py`, `calque.py` ; application : `spyder/plugins/ipythonconsole/widgets/client.py` (lecture
     seule). L'essai le contourne par une option (`spe.py:61`, `panneaux.py:556`), réglage et non branche.
   - Première mesure à faire (zmq, « Pistes pour un relecteur » 1) : quel appel de la doublure coûte (`setHtml`,
     polices, iframe ?), avec `PANNEAUX_WEB=1` dans `panneaux.py`.
   - Niveau : mesuré (une passe Firefox par hypothèse). Décision D3.
2 bis. **La doublure `QWebEngineView`/`QWebEnginePage` n'a pas `renderProcessTerminated`** (relevé par W551, 12/11).
   - Appelant : greffon `spyder_python_tutor`, `main_widget.py:385` (`page.renderProcessTerminated.connect`) →
     AttributeError à la première trace, avant la vue web.
   - À faire : un `Signal` sans émission dans `qtpy6/web/moteur_web.py` (un navigateur ne perd pas un processus de rendu à
     part ; l'iframe meurt avec la page), sous le nom Qt, sans branche dans le greffon.
   - Essai : `site/index.html?script=greffons.py` (W551), action « Lancer » du tuteur.
   - Niveau : lu dans les sources, non mesuré (les actions des greffons ne s'impriment pas encore, item 14).
   **[FAIT, W558, 12/11]** signal et énumération `RenderProcessTerminationStatus` sur la page et la vue, jamais émis ;
   test rouge puis vert (`tests/test_doublures.py`). Relevé des autres attributs appelés : aucun autre manque (mainFrame
   en branche QtWebKit morte). Reste : la trace dans la page (sonde arrêtée après la liste des greffons, item 14).
   Essai du professeur (`--visible`, 15:05) : « Lancer » du tuteur non observé ; dialogue d'erreur au démarrage =
   ImportError `QNetworkInterface` de `spyder_collab/network.py:43` (connu, item 14) ; « Exécuter » de Spyder « tourne
   dans le vide en cherchant les variables d'environnement » (professeur, non attribué : à inscrire comme item).
   **Mesuré 15:25 (3e essai du professeur)** : « Lancer Python Tutor » passe `_ensure_web` (plus d'AttributeError) et
   lance la trace ; à la fin, `TypeError: TutorRunner._on_finished() missing 1 required positional argument: 'status'`
   (`bloquant.py:377`) : `ProcessusWeb.finished = Signal(int)` (`qtpy6/web/travailleur.py:232`), Qt émet
   `finished(int, QProcess.ExitStatus)` — doublure à compléter (Signal(int, ExitStatus), émis avec NormalExit/CrashExit),
   fichier d'un autre worker, non attribué. Appelant : `spyder_python_tutor/spyder/tracer.py:78, 97`.
   `notes/2026-11-12 - Signaux manquants de la doublure QWebEngine (W558).md`.
2 ter. **`javaScriptAlert` / `javaScriptConsoleMessage` surchargées mais jamais appelées par la doublure** (W558, 12/11).
   - Appelant : `_DebugPage` du tuteur (`main_widget.py:372-380`) : intercepte `alert()` de pytutor.js, « garde-fou
     essentiel » ; dans la page, `alert()` de l'iframe ouvrirait le dialogue du navigateur (gel vu par W546).
   - À faire : dans `moteur_web.py`, remplacer `alert`/`console.error|warn` de l'iframe par des appels aux méthodes de
     la page (surchargeables) ; défaut Qt : `javaScriptAlert` ouvre un QMessageBox. Niveau : lu, non mesuré.
   - **W560, 12/11 15:30 : FAIT, non commité** (relecteur à passer) : `_RELAIS` injecté en tête de la page de même
     origine (alert, console.*, erreurs non rattrapées) ; défaut `open()` d'une QMessageBox ; 2 tests rouge→vert, script
     éprouvé sous node. Non mesuré dans la page (tuteur non atteint par la sonde). Note `notes/2026-11-12 - Alert de l'iframe et environnement de l'exécution (W560).md`.
3. **Slots homonymes d'un signal : le fork plante sans contournement d'essai.**
   - État : le fork du 01/11 définit encore `cursor_position_changed` (`spyder/plugins/editor/widgets/base.py:430`),
     `cell_changed` (`spyder/widgets/arraybuilder.py:156`), `item_expanded`
     (`spyder/plugins/profiler/widgets/profiler_data_tree.py:868`) : grep du 12/11. Le renommage 9d22c29 / 591fdf005
     est perdu (le générateur ne le reprend pas, zmq « Toujours ouvert »).
   - Existant : `essais/spyder/jalon7.py:67-75` retire les trois alias à la main. Dans qtpy6, `_pyside6_class`
     (`qtpy6/_binding.py:131`) pose encore les alias de SIGNAUX en attribut simple (l. 154-155) ; seuls les alias de
     méthodes cèdent la place (`_Alias`, l. 100).
   - Deux voies, à trancher (D1) : corriger le générateur du fork (session du fork ou utilisateur) ; ou que qtpy6
     cesse d'aliasser les signaux. Niveau : mesuré (core dump sans le contournement, faisabilité « Points ouverts »).
   **[FAIT, W547, 12/11, 4ca1a7f]** D1 tranché par le professeur (17:20) : D. L'alias de signal est un descripteur
   (`_SignalAlias`) qui cède au nom Python de la MRO comme `_Alias` (cas mixin de W562 : `BaseEditMixin` après
   `QPlainTextEdit`), sinon rend le signal camelCase ; avertissement `SignalAliasMasked` à la définition d'une
   sous-classe qui masque un alias, PySide6 seul (sous PyQt6, lire les enveloppes sip en création plante, mesuré).
   `delattr` retiré de `jalon7.py`. Mesuré : témoin sans plantage, tests W547 et W562 verts. Niveau dans la page :
   jalon 5 rejoué par W562 (en attente). Note `2026-11-12 - Jalon 7 sans contournement (W547).md`.
   - **Reste, non attribué (mesuré, W567, démarrage natif avec l'alias qtpy)** : 3 `SignalAliasMasked`,
     `TextEditBaseWidget.cursor_position_changed` (`spyder/plugins/editor/widgets/base.py`), `ArrayTable.cell_changed`
     (`spyder/widgets/arraybuilder.py`), `ProfilerDataTree.item_expanded` (`profiler/widgets/profiler_data_tree.py`) :
     renommage perdu dans le générateur du fork ; D1 gardé (l'avertissement reste). Ouvert à part par le Superviseur.
4. **Ce que les essais font encore « propre au web » hors instrumentation** (règle du `CLAUDE.md`).
   - a. `PySide6.QtCore` complété par les classes de qtpy6 et `PySide6.QtWebEngine*` posés vers les doublures :
     `essais/spyder/preparer.py:69-86`, parce que le `qtpy` du fork lit PySide6 directement. Existant : rien dans
     `qtpy6/` (grep `PySide6.QtWebEngine` → 0). À faire dans qtpy6, comme pour les autres modules absents de WASM
     (faisabilité, « Doublure QWebEngineView », POINTS OUVERTS) ; à trancher avec la question du qtpy du fork (D5).
   - b. `travailleur.configurer("./pyodide-qt/")` sous `if sys.platform == "emscripten"` : `spe.py:71-73`. Existant :
     `qtpy6/web/travailleur.py:66` (`configurer`), `:77` (`prechauffer`). Où vit la liste des roues : D4.
     **FAIT (W559, 12/11, non commité à l'écriture)** : le Worker prend par défaut le Pyodide et les roues de la page
     (`qtpy6web.js` → `lancer()`), `spe.py` sans branche ; mesuré : jalon8c sans `configurer` 5/5 (Firefox).
   - c. **FAIT (W559, 12/11)** : `jalon4.py` appelle `waitForFinished(1000)` sans `if not WEB`. Non relancé dans la page.
   - d. Doublures de l'essai qui sont des manques de qtpy6 ou de l'archive : `pickleshare`, `three_merge`,
     `jellyfish`, `bcrypt`, `keyring`, `inflection`, métadonnées de `pylint` (`preparer.py:36-62`).
     FAIT (W559, 12/11) : jellyfish/bcrypt retirés (importés par aucun module) ; pickleshare, three_merge, inflection
     en vraies roues ; keyring = doublure qtpy6 en mémoire (`qtpy6/web/keyring_web.py`) ; pylint gardé (pas propre au web).
   - Niveau : lu dans les sources (12/11). Commande : `grep -nE "emscripten|qtpy6\.web|import js\b|pyodide"
     essais/spyder/spe.py essais/spyder/preparer.py` (9 lignes le 12/11 : 6 et 3).
5. **Serveur d'instance unique dans un `threading.Thread` : `--new-instance` reste dans l'essai.**
   - Existant : `threading_web.Thread` (`qtpy6/web/threading_web.py:132`) est posé dans la PAGE par
     `sous_processus.doubler_zmq()` (`QtCore.py:45`, `sous_processus.py:250`) depuis 7662a9b. Le « can't start new
     thread » du jalon 7 a donc peut-être disparu ; le risque nommé reste un `accept()` bloquant sur le fil unique.
   - Essai : retirer `--new-instance` de `essais/spyder/jalon7.py:79`, rejouer par la sonde. Même question pour le
     serveur pydoc d'OnlineHelp.
   - Niveau : supposé (lu, non remesuré). Note : `web.md` point 3 dit encore « `threading.Thread` … pas doublés ».
   **[FAIT, W547, 12/11]** `--new-instance` retiré de `jalon7.py` ; sonde sur un site reconstruit avec le
   `socket_web.py` de W548 : `post_visible_setup` passe, `closing` en 0,4 s, état « fini ». Mesuré. Serveur pydoc
   d'OnlineHelp non essayé. Note `2026-11-12 - Jalon 7 sans contournement (W547).md`.
6. **Jalon 8d : le serveur pylsp dans un Worker** (tranché par l'utilisateur, zmq « Compléments », 19 h 14 : « je
   souhaite le couvrir »).
   - Obtenir : client LSP de Spyder (`plugins/completion/providers/languageserver/client.py`, sockets `PAIR`,
     `zmq.FD` lu dans un `QSocketNotifier`) parlant à pylsp dans un Worker.
   - Existant : `FD = 14` (`qtpy6/web/zmq_web.py:114`) ; aucune doublure de `QSocketNotifier` (grep → 0).
   - Fichiers : `zmq_web.py`, une doublure `QSocketNotifier` à poser sous `qtpy6.QtCore`. Essai : `jalon8d.py` à écrire.
   - Niveau : lu dans les sources. Le jalon n'est pas défini plus loin dans la note.
   **[FAIT, W548, 12/11]** jalon8d : 5/5 dans Firefox en 26,6 s (sonde). Détail : initialize 16,2 s, diagnostic 0,6 s,
   complétion `path` 8,6 s, tas 42 → 119 Mio. Sur le bureau : 5/5 en 15,2 s. Doublures : TCP de boucle locale,
   select/selectors, termios/fcntl, `os` sur fd (`socket_web.py`), ops `flux_*` (`zmq_web.py`), `QSocketNotifier`
   (`QtCore.py`), parent vivant et fin de soi (`psutil_web.py`), `error`, `exitCode` et `processId` de ProcessusWeb.
   Premier lot dans 93a38e9 (sous le message de W549), le reste au commit W548 suivant. Dépendances levées : PAQUETS
   pylsp (W551, 150070b) et pexpect, ptyprocess, importlib_metadata, zipp (W548). `notes/2026-11-12 - Jalon 8d, pylsp
   dans un Worker (W548).md`. Reste : le risque, lu et non mesuré, d'un `accept` suspendu pour toujours, qui interdit
   à un slot de suspendre (`bloquant.py:152`).
7. **Hébergement : un lien pour les élèves.** spe.py tourne par la sonde et dans le Chromium de l'utilisateur ; le lien
   reste à faire (zmq, « config de référence », Points ouverts). Manifeste d'application écarté pour l'instant, « à
   ajouter à l'hébergement ». Niveau : mesuré (Firefox sonde, Chromium par l'utilisateur pour `print`).
8. **Pyxel, chargement des ressources** : `load("projet_monkey.pyxres")` → `Failed to open file` malgré l'injection
   (TODO son, « Suite du 12/10, 19 h 45 »). À vérifier : fichier dans le FS du noyau, cwd à `init`, `load` par chemin
   absolu. Essai : `spe_monkey.py?jeu=…`. Fichiers : `qtpy6/web/pyxel_web.py`. Niveau : mesuré (échec), cause supposée.
   **[W549, 12/11] FAIT** : `init` fait `chdir` vers le dossier de son appelant, la doublure `init_web` → cwd dans
   `qtpy6/web` ; `_cwd_du_jeu()` refait ce `chdir` vers le jeu. Mesuré par la sonde (headless) : échec reproduit sans,
   `load OK` avec (note `2026-11-12 - Pyxel, ressources et son (W549).md`). Reste : jeu complet dans le Firefox du
   professeur. **Défaut trouvé** : un second `pyxel.init` dans le même noyau est fatal (`handback_tstate == NULL`,
   `pystate.c:222`) — relancer un jeu tue le noyau ; non traité.
   **Vérifié par le professeur (14:33)** : images et sprites affichés. **Défauts neufs, non traités** : le jeu ne
   répond pas au clavier ; le panneau Pyxel n'a pas de cadre de focus (« je ne peux pas être certain qu'il a le focus »).
   **[W565, 12/11] Clavier FAIT** : un clic sur le canevas de Qt (écran déjà focus de Qt) donne le focus DOM au `body`,
   Qt ne le reprend qu'au changement de widget → 0 KeyPress. Doublure `_garder_le_focus()` (`qtpy6/web/__init__.py`,
   f75949b par W559). Mesuré (sonde, vrai clic + vraies frappes) : 0 KeyPress sans, 3/3 et le noyau voit Espace avec,
   site reconstruit sans injection (`clavier7`). **Cadre** : au ras de l'image, coins arrondis (décision du professeur
   18:50), confié au generator de SmartPythonEditor (greffon). Note `2026-11-12 - Clavier et focus de Pyxel dans la page
   (W565).md`. Reste : vérification par le professeur (clavier et cadre).
9. **Le son de Pyxel** : renvoi au TODO son, premier item. Existant : `memoire_partagee.reconcilier()`,
   `preambule._doubler_sleep` (`qtpy6/web/preambule.py:70`) ; aucun `AudioContext` dans `qtpy6/` (grep → 0).
   Niveau : supposé (piste, rien d'écrit).
   - **W557, 12/11 18:00 — BLOQUÉ** (note `2026-11-12 - Son de Pyxel dans la page (W557).md`, journaux
     `qtpy6_essais/w557/sonN.*`) : `qtpy6/web/son_web.py` commité INERTE (AudioContext doublé dans le Worker, anneau
     SAB, AudioWorklet dans la page) ; débranché de `pyxel_web`, absent du tuple de `travailleur.py`. Le Worker reçoit l'anneau (mesuré) ; c'est le premier appel du mixeur SDL (`onaudioprocess` → `dynCall`)
     hors du flux de SDL qui tue le noyau : depuis la minuterie, « index out of bounds » (même GC coupé) ; depuis
     `reconcilier()` (dans `time.sleep`), le Worker se fige sans trace. Aucun échantillon n'a atteint la page.
10. **Fenêtre d'erreur fugitive de l'explorateur** (`directoryLoaded` → `initStyleOption`, `index.model()` None) :
    TODO son, avant-dernier item. Doublure de `QFileSystemModel` à écrire côté qtpy6 (aucune dans `qtpy6/web/`).
    Niveau : lu dans la pile relevée, cause supposée.
    W550 (12/11) : NON reproduite en quatre essais (modèle seul, slot reporté ou non, Spyder entier, `spe_monkey` jeu
    lancé : il casse avant, item 1). Reste : reproduire jeu tournant (après item 1, ou Chrome), pile entière ; pas de
    doublure sans cause. Note `2026-11-12 - QFileSystemModel et dossier Chrome (W550).md`, essai `essais/fsmodel/`.
    - **REPRODUIT chez le professeur, 12/11 19:52** (relevé par W566), au simple démarrage de spe.py dans son Firefox
      (site du 19:03, sans jeu lancé). Pile entière : `qtpy6_essais/equipe/w566/trace_professeur_explorateur_1952.txt`.
      Elle passe par `bloquant.py:354 __call__` → `_relayer:368` → `executer:377`, puis par `explorer.py:1009`
      (lambda `resizeColumnToContents(0)`) → `initStyleOption:184/193` `model.isDir` sur un modèle None. Piste à établir :
      un relais de `bloquant` qui rejoue le lambda alors que le modèle n'est plus là. Non attribué.
11. **Interruption d'un calcul qui ne dort jamais.** Aujourd'hui : signal livré au prochain `time.sleep` (a4ee0c6).
    Pour un vrai arrêt : `setInterruptBuffer` sur SharedArrayBuffer (grep → 0). La page EST isolée depuis f02c16c
    (`sw.js`, `isoler`) : voir « Contradictions ». Niveau : lu.
12. **Fermeture de l'application non mesurée jusqu'au bout** et `InvalidStateError` de superqt
    (`_throttler._set_future_result`) : zmq, « Le gel au démarrage », pistes 3 et 4. Essai : poser l'état de la sonde
    après `main.closing` dans `jalon7.py`. Niveau : mesuré partiellement.
    **[FAIT, W547, 12/11]** `jalon7.py` pose « fermeture » puis « fini » après la sortie de `exec()` : fermeture
    mesurée jusqu'au bout. L'`InvalidStateError` n'est PAS de superqt : `jupyter_client/manager.py:111` via
    `restarter.py:144 poll` (redémarreur du noyau qui tire pendant l'arrêt). Cause des minuteries pompées par les
    attentes coopératives : supposée ; sans effet sur la fermeture ; absente du dernier essai. Correctif non posé.
13. **Le reste du port** (faisabilité, « Points ouverts » et jalons 3-5) :
    - console : `max_line_count` (300 lignes) à monter ; Worker de réserve et complétion factice pour cacher 1,4 s ;
    - REPL persistant et explorateur de variables hors noyau : sans objet si la console IPython (8c) est retenue ;
    - doublure `chardet.detect → utf-8` (63 Mio économisés) : D6 ; **FAIT (W559)** `qtpy6/web/chardet_web.py`, utf-8
      sinon vrai chardet, mesuré en natif seulement ;
    - dossier autorisé de Chrome comme troisième emplacement de `persistant`, bouton « Réautoriser » : codé (W556),
      `application(persistant=chemin, disque=True)`, opt-in (l'automatique sur tout Chrome, écarté, changerait toutes les
      applications) ; repli Firefox mesuré (sonde), boutons vus sous Blink ; mesuré dans le Chromium du professeur
      (choix, une recopie pour 101 écritures, Réautoriser après fermeture : 101 fichiers retrouvés). Fait.
      Note `2026-11-12 - Dossier Chrome comme emplacement persistant (W556).md` ;
    - couche Dropbox par élève : hors qtpy6 (SmartTeacher), raccordement professeur à décider ;
    - `EN_RETARD` : FAIT (W551, 12/11), retiré, les six fichiers du fork sont identiques à l'installé (`cmp`) ;
    - Interpréteur : chemin factice `/pyodide/3.13/bin/python` dans `spe.py` ; `custom` reste faux. FAIT (W559, 12/11) : `qtpy6.web._executable`
      donne à `sys.executable` un vrai fichier au chemin pyenv ; spe.py écrit `sys.executable`. Mesuré page.
    Niveau : mesuré pour les coûts, supposé pour les remèdes.
14. **Les treize greffons** (faisabilité, « Les treize greffons » ; W551, `notes/2026-11-12 - Greffons dans la page
    (W551).md`). Embarqués les sept portables (`construire_site.py`, essai `greffons.py`). Inscrits dans la page :
    stop, interpreter, pyxel, `spyder_code_analysis`, `spyder_python_tutor` (mesuré). Reste : `spyder_collab` casse à
    l'import (`QNetworkInterface` absent de QtNetwork wasm ; doublure QTcpServer/QTcpSocket sur relais WebSocket à
    écrire) ; `spyder_smartteacher` absent sans erreur (cause non mesurée ; le pont veut le dossier QCM : réglage) ;
    `renderProcessTerminated` manque à `moteur_web.py` pour le tuteur (lu, item 2 bis) ; actions (Docteur, Lancer) non mesurées :
    la page ne rend plus rien après la liste des greffons ; volet pylint à activer dans la configuration pour Docteur.
    Hors champ : claude, konsole, tortoisehg, window_controls, viztracer, line_profiler. Commit 150070b : archive du site
    saine (sources seules, écriture atomique, `--sortie`), pylsp de W548 compris.
    - **[FAIT, W563, 12/11]** doublure `qtpy6/QtNetwork.py` → `qtpy6/web/reseau_web.py` (QTcpServer, QTcpSocket,
      QNetworkInterface sur la boucle locale de `socket_web`) : collab INSCRIT, octet échangé et hello CollabPeer reçu
      dans la page (mesuré, `notes/2026-11-12 - QtNetwork dans la page, spyder_collab (W563).md`). Trouvé : le « plus
      rien » après la liste était `sys.stdout` pris par la console de Spyder (corrigé dans `greffons.py`) ; défaut
      suivant mesuré : `spyder_code_analysis` casse sur `ProcessusWeb.waitForStarted` absent (`sous_processus.py`, W548).
    - **`spyder_collab` ABSENT, dialogue d'erreur au démarrage** (W558, 12/11, fait par W563 ci-dessus) : `ImportError: cannot
      import name 'QNetworkInterface' from 'qtpy.QtNetwork'` (`spyder_collab/network.py:43`, avec QTcpServer,
      QTcpSocket) ; vu dans les deux essais `--visible` du professeur (`/DATA/Python/qtpy6_essais/w558/capture_main.console.log`).
15. **Chrome** : jalons 8a à 8c, Pyxel, `QWebEngineView` mesurés sous Firefox seul ; phase 2 du jalon 5 jamais lancée
    sous Blink (branches de la sonde écrites). Niveau : non mesuré.
    Chrome : W552 (12/11), Blink de QtWebEngine (Chrome 140, sonde --chromium, dans le bac) : 7, 8a, 8b, 8c,
    QWebEngineView (panneaux), Pyxel passent ; jalon 5 : rechargement et IDBFS passent, puis arrêt
    dans `CodeEditor.setPlainText` IDENTIQUE sous Firefox (régression commune depuis le 10/10, à reprendre au jalon 5) ;
    **fait, W562 (12/11)** : cause hors dépôt (fork reconstruit le 11/10 : `BaseEditMixin.cursor_position_changed`
    masqué par l'alias du signal, signal connecté à lui-même), corrigée dans qtpy6 par `_SignalAlias` (W547, 4ca1a7f) ;
    jalon 5 phase 2 jusqu'au bout (relu, ouvert, enregistré, téléchargé) sous Firefox 158 ET Blink (Chrome 140), mesuré.
    Note `2026-11-12 - Régression du jalon 5, setPlainText (W562).md` ;
    propre à Blink : `cannot join current thread` (`threading_web.py:174`) à la fermeture de jalon7. Reste : Chrome de
    bureau avec GPU. Note `2026-11-12 - Jalons sous Chrome (W552).md`.
16. **Outillage** : `_fait` de la sonde par compare-and-set (`qtpy6/web/sonde.py`, rencontré aux jalons 3 et 5) ; test
    unitaire de la règle « slot à QEvent sur place » de `bloquant.py` dans `tests/test_web.py` ; `SystemError: Cannot
    enter a promising task` résiduels (Pyxel, « Point ouvert immédiat »). Niveau : lu.
    **[FAIT, W553, 12/11, e40d9f5]** compare-and-set et test de bloquant (deux tests, échouent sans) ; SystemError :
    pile relevée (pompe `tourner` → `callPromising`), suite de la corruption GC (item 1, transmis à W545) ; reste : repro
    à relancer sur site stable. `notes/2026-11-12 - Outillage sonde et bloquant (W553).md`.
    **[FAIT, W568, 12/11] Pyodide mort dans un Worker** : `travailleur.js` pose `_api.on_fatal` (`garder`) : cause sur
    stderr puis `{fin: 1}` (mode lancer) ou `{erreur}` (mode appels), et ferme le Worker, au lieu d'un noyau muet suivi de
    SystemError en série. Test node `tests/test_travailleur_js.py` (échoue sans). Reste : vu par le professeur.
16 bis. **Trois tests de `tests/test_web.py` échouent depuis 82f2793** (boîte noire démarrée par `application()`),
    relevé par W553 le 12/11 : `test_application_persistant_dans_le_navigateur`, `test_police_fixe_dans_le_navigateur`,
    `test_coller_passe_par_qt`. Même message dans le sous-processus `en_navigateur` : `AttributeError:
    'types.SimpleNamespace' object has no attribute 'window'`, levé par `qtpy6/web/boite_noire.py:24` (`_boite` :
    `getattr(js.window, "qtpy6BoiteNoire", None)`), appelé par `demarrer()` (l. 31) depuis `application()`
    (`qtpy6/web/__init__.py:95`). Le faux `js` des tests n'a pas de `window`. Sans propriétaire au tableau de bord.
    Niveau : mesuré (pytest, 14:15).
    - **FAIT, W566, 12/11 19:25** : `_boite` lit `window` par `getattr` (faux `js` sans fenêtre) ; même cause en
      natif dans `_reglages_du_worker` (`import js`, f75949b : deux échecs de plus) rendue sans effet hors page. Les
      cinq rouges de `test_web.py` passent (mesuré). Note W566.
16 ter. **[FAIT, W548, 12/11]** `test_noyau_web.py` sous Python 3.14 : `RuntimeError: There is no current event loop`
    (`asyncio.get_event_loop()` sans boucle posée, `sous_processus.doubler_zmq:251`, `preambule.py:52,156`) : rouges
    `test_popen_doublee_dans_le_navigateur`, `test_preambule_crochets_attendre_plus_tard_poster`,
    `test_preambule_installe_zmq_et_threading_sans_qt`, `test_preambule_recevoir_page`, `test_preambule_sleep_livre_les_signaux`.
    Correctif : boucle courante, sinon boucle neuve posée. 34/34 sous 3.14 et 3.13. Le « No module named 'js' »
    (`memoire_partagee`) était corrigé par W557. Niveau : mesuré (pytest, 15:14).
17. **Modules PySide6 non compilés** : renvoi à `notes/TODO - Modules PySide6 non compilés.md`. Aucun n'est importé par
    SmartPythonEditor au 11/10 (cette note). `QtPrintSupport` est lié depuis le 10/10 (faisabilité, jalon 6).
18. **« Exécuter » de Spyder « tourne dans le vide en cherchant les variables d'environnement »** (professeur, 12/11 15:05,
    essai `--visible` consigné par W558 à l'item 2 bis). Hypothèse à vérifier : `spyder/utils/environ.py`
    (`get_user_environment_variables` lance un shell par sous-processus, lu avec délai) sous la doublure QProcess ;
    attendu : la même ligne des deux côtés, doublure qui rend `os.environ` sans sous-processus dans la page
    (règle CLAUDE.md). Distinct de l'item 1 (%runfile tue le noyau) : ici le noyau n'est pas atteint.
    - **W560, 12/11 15:30, mesuré (sonde, `essais/spyder/env18_spe.py`)** : l'environnement arrive en 2 s mais VIDE
      (0 variable, `asyncio.create_subprocess_shell` échoue) ; le message reste pendant `get_cached_kernel` (23 s,
      lancement du Worker), puis « Connexion au noyau… » sans fin : le noyau n'est JAMAIS connecté. Reste : doublure de
      `create_subprocess_shell`/environnement (`sous_processus.py`, à W560 depuis 536b1a4), connexion du noyau à relever,
      `ProcessusWeb.finished(int, ExitStatus)` (travailleur.py:232, demandé par le Superviseur). Note `notes/2026-11-12 - Alert de l'iframe et environnement de l'exécution (W560).md`.
    - **FAIT, W560, 12/11 17:54, mesuré dans Firefox** : `psutil_web` `Process().terminal()` non None (Spyder reprend
      `os.environ`, décision du professeur 17:41 : 18 variables) et `net_if_addrs()` = `lo` 127.0.0.1 (le vide faisait
      avertir jupyter_client sur la sortie d'erreur du noyau, affiché comme erreur du noyau). Noyau prêt vers 30 s,
      `print('W560', 6 * 7)` rend `W560 42`. Aussi : `ProcessusWeb.finished(int, ExitStatus)`.
19. **Rapporteur d'erreur de Spyder à l'ouverture de spe.py** (W559, 12/11 18:59, note « Essais sans branche web, suite
    (W559) ») : `mainwindow.py:1526 start_open_files_server` → `AttributeError: module 'socket' has no attribute
    'SO_REUSEADDR'`. Mesuré (W566, chaînes de `pyodide.asm.wasm`) : `SO_REUSEADDR` et `SO_REUSEPORT` absents du
    `_socket` de Pyodide, les autres options présentes. Existant : `socket_web.Socket` (bind/listen/accept sur la boucle
    locale, `setsockopt` tolérant pour `SO_LINGER`). Fichiers : `qtpy6/web/socket_web.py`, `tests/test_doublures.py`
    (section W566). Essai : `test_serveur_open_files_sans_so_reuseaddr`, puis sonde Firefox sur `spe.py` (pas de
    rapporteur), puis le professeur dans son Firefox.
    - **FAIT, W566, 12/11 19:10, mesuré (sonde Firefox)** : `installer()` pose les deux constantes, `setsockopt` tient
      les options de liaison pour sans objet ; plus de rapporteur à l'ouverture de spe.py. Reste : vu par le professeur.
      Note `notes/2026-11-12 - socket SO_REUSEADDR dans la page (W566).md`.
20. **qtpy6 comme `qtpy` dans SmartPythonEditor natif** (reste de W559). **FAIT, W567, 12/11** : `.pth` paresseux du
    venv (`python -m qtpy6._qtpy` → `qtpy6_qtpy.pth`, qtpy6 chargé au premier `import qtpy` seulement), aucune ligne
    dans Spyder ni le lanceur ; `_Alias` lu par la classe porte une signature (Spyder `completion/plugin.py:577`
    tombait sur `create_win_id`). Mesuré hors écran : 47 greffons, mêmes stderr hors 3 `SignalAliasMasked` (item 3).
    Reste : installation durable (`installation_SmartPythonEditor.sh`, SmartOS) ; vu par le professeur. Note
    `notes/2026-11-12 - qtpy6 comme qtpy dans SmartPythonEditor natif (W567).md`.
21. **Vitesse : coût d'import de qtpy6 en natif** (non attribué, mesuré W567, venv SmartPythonEditor, PySide6 6.11,
    médianes sur 10) : `import qtpy.QtCore, QtGui, QtWidgets, QtWebEngineWidgets` 760 ms par l'alias qtpy6 contre
    165 ms par le vrai qtpy ; ~0,5 s de création d'énumérations PySide6 (~700) déclenchée par `_binding._pyside6_class`
    qui parcourt les classes (cProfile). Coût de qtpy6 en général, pas de l'alias.
    **Contrainte de l'utilisateur (12/11/2026 19:42)** : « le profilage ne devra se faire que cette nuit à un moment
    où le CPU n'est pas utilisé et en concertation avec les autres sessions ». Session neuve ; banc
    `qtpy6_essais/w567/mesurer_demarrage.py` (option cProfile à ajouter).
22. **Vitesse : démarrage de spe.py dans la page** (non attribué, plan de nuit : même contrainte du 12/11 19:42 que
    l'item 21). Professeur, 12/11 19:49, dans son Firefox : « le demarage est horriblement long ». Mesuré une fois
    (W566, sonde Firefox, 12/11 19:03, machine chargée : 8 sessions et Firefox concurrents) : durée totale 62,6 s, dont
    `post_visible_setup` 48,7 s ; tas wasm 215 Mio. Log `qtpy6_essais/equipe/w566/sonde_spe.log`.

## Décisions à prendre par l'utilisateur

- **D1. Alias snake_case des signaux de qtpy6.** Options : (a) qtpy6 cesse d'aliasser les signaux (`_binding.py:154`) :
  « le plus propre », aucun code de SmartTeacher ni de qtpy6 n'appelle un alias de signal (grep des 237 noms, 09/10),
  mais touche qtpy6 en service ; (b) renommer les slots dans le fork, à refaire dans le générateur (trois méthodes,
  perdu une fois déjà) et à chaque greffon qui reprendrait l'habitude ; (c) garder le retrait d'alias dans l'essai :
  contraire à la règle. La note ne recommande pas, elle dit (a) « à décider à part ».
- **D2. Doublure du GC du Worker** (TODO son, ordre de jeudi, point 2) : (A) à tout Worker (mesurer la console de code
  QCM : `tests_modele.py` côté web, sonde du lecteur), (B) aux seuls Workers de noyau Jupyter, ou (C) GC incrémental
  gardé partout et mis en pause par `gc.disable()` autour de chaque bascule de pile JSPI seulement (demande de
  l'utilisateur, 12/11 13:56 : « garder l'incrémental pour éviter de longues pauses ») ; C si la mesure la tient.
  **Décidé par l'utilisateur, 12/11 14:01 : (D) « correction de Pyodide et JSPI », item 1 bis ; la parade de l'item 1
  n'est qu'un secours provisoire en attendant le patch, à retirer ensuite.**
- **D3. Widgets web** (zmq, « Correctif propre, à décider ») : doublure `QWebEngineView` assez légère pour la page de
  chargement, ou qtpy6 annonce l'absence de WebEngine (`WEBENGINE` de Spyder faux, Help et OnlineHelp en repli).
- **D4. Liste des roues du Worker** (faisabilité, jalon 4, « propre au web » 1) : réglage commun sur
  `qtpy6.QtCore.QProcess` sans effet en natif, ou posée par la page à la construction (`window.roues`).
  **Décidé par l'utilisateur, 12/11 18:01 : la page** (Pyodide et roues de la page par défaut) ; **D6 : utf-8 sinon
  chardet réel**. Nuance de règle du même jour dans `CLAUDE.md` (branche emscripten évitée, pas interdite). Note W559.
- **D5. Le qtpy du fork** : qtpy6 pose-t-il lui-même ses doublures sous les noms `PySide6.*` (item 4a) ?
- **D6. `chardet`** : doublure `utf-8` (63 Mio de moins, un fichier d'un autre encodage mal lu) ou chardet réel.
- **D7. Vrais threads** (pthreads) : essai de faisabilité en mode plan, ordre (a)/(b)/(c) du TODO son ; décidé « à
  partir de jeudi » (15/10), pas d'entrée depuis dans les notes.

## Contradictions entre sources

- Faisabilité, jalon 7 et `QWebEngineView` : « FAIT (non commité) » ; git : 3a6d921 et 71c0849.
- Pyxel, essai 26 : « Correctif (non commité) » (`os.mkfifo`) ; git : 2aea235.
- Faisabilité, « Points ouverts » : renommage des slots « Fait » ; zmq : perdu au 11/10 ; fork du 01/11 : perdu.
- zmq, 8b : isolation cross-origin « décision de l'utilisateur : ne pas coder » ; Pyxel, essai 24 : page isolée par le
  service worker (f02c16c). L'interruption réelle redevient possible, non rediscutée.
- `web.md` point 3 : « `threading.Thread` … pas doublés » ; code : `threading_web.installer` posé dans la page à
  l'import de `qtpy6.QtCore` (`QtCore.py:45`).
- TODO son : « ramasse-miettes HORS DE CAUSE » (17 h 20), corrigé par lui-même à 18 h 45 (c'est bien le GC).

## Vérification finale

Commande du `CLAUDE.md`, sur le code de l'application, doit rendre zéro ligne hors instrumentation :

    grep -rnIE "emscripten|qtpy6\.web|import js\b|pyodide" --exclude-dir=.git /DATA/Python/FORKS/SmartPythonEditor

Le 12/11/2026 (fork a8aa440d4) : **0 ligne, 0 fichier** (lecture vérifiée : 20 fichiers du même arbre contiennent
« PySide6 »). Le fork ne porte donc aucune branche web ; ce qui reste propre au web est dans les essais
(`essais/spyder/spe.py`, `preparer.py`, `jalon7.py` : item 4) et doit passer dans qtpy6 avant de dire le port agnostique.
Les greffons (`/DATA/Python/FORKS/SmartPythonEditorPlugins/`) ne sont pas couverts par ce compte.
