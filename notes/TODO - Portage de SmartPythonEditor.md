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
2. **[EN COURS W546, 12/11 14:10] Les widgets web de Spyder gèlent la page au démarrage de la console.** Obtenir la console sans `--no-web-widgets`.
   - Cause (zmq, « Le gel au démarrage ») : la page de chargement (`ClientWidget._create_loading_page`, `FrameWebView`)
     sur la doublure `QWebEngineView`. Avec `--no-web-widgets` : 5/5 (In [1] en 3,6 s, `1+1`, variables, redémarrage).
   - Existant : `qtpy6/web/moteur_web.py:438` (`class QWebEngineView(Calque)`), `qtpy6/web/calque.py`.
   - Fichiers : `moteur_web.py`, `calque.py` ; application : `spyder/plugins/ipythonconsole/widgets/client.py` (lecture
     seule). L'essai le contourne par une option (`spe.py:61`, `panneaux.py:556`), réglage et non branche.
   - Première mesure à faire (zmq, « Pistes pour un relecteur » 1) : quel appel de la doublure coûte (`setHtml`,
     polices, iframe ?), avec `PANNEAUX_WEB=1` dans `panneaux.py`.
   - Niveau : mesuré (une passe Firefox par hypothèse). Décision D3.
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
4. **Ce que les essais font encore « propre au web » hors instrumentation** (règle du `CLAUDE.md`).
   - a. `PySide6.QtCore` complété par les classes de qtpy6 et `PySide6.QtWebEngine*` posés vers les doublures :
     `essais/spyder/preparer.py:69-86`, parce que le `qtpy` du fork lit PySide6 directement. Existant : rien dans
     `qtpy6/` (grep `PySide6.QtWebEngine` → 0). À faire dans qtpy6, comme pour les autres modules absents de WASM
     (faisabilité, « Doublure QWebEngineView », POINTS OUVERTS) ; à trancher avec la question du qtpy du fork (D5).
   - b. `travailleur.configurer("./pyodide-qt/")` sous `if sys.platform == "emscripten"` : `spe.py:71-73`. Existant :
     `qtpy6/web/travailleur.py:66` (`configurer`), `:77` (`prechauffer`). Où vit la liste des roues : D4.
   - c. `waitForFinished` : existe sur `ProcessusWeb` (`travailleur.py:344`, rend faux tout de suite, adf75de) ; le
     point 3 du jalon 4 est donc réglé, à vérifier dans `jalon4.py` (la branche native y est-elle encore ?).
   - d. Doublures de l'essai qui sont des manques de qtpy6 ou de l'archive : `pickleshare`, `three_merge`,
     `jellyfish`, `bcrypt`, `keyring`, `inflection`, métadonnées de `pylint` (`preparer.py:36-62`).
   - Niveau : lu dans les sources (12/11). Commande : `grep -nE "emscripten|qtpy6\.web|import js\b|pyodide"
     essais/spyder/spe.py essais/spyder/preparer.py` (9 lignes le 12/11 : 6 et 3).
5. **Serveur d'instance unique dans un `threading.Thread` : `--new-instance` reste dans l'essai.**
   - Existant : `threading_web.Thread` (`qtpy6/web/threading_web.py:132`) est posé dans la PAGE par
     `sous_processus.doubler_zmq()` (`QtCore.py:45`, `sous_processus.py:250`) depuis 7662a9b. Le « can't start new
     thread » du jalon 7 a donc peut-être disparu ; le risque nommé reste un `accept()` bloquant sur le fil unique.
   - Essai : retirer `--new-instance` de `essais/spyder/jalon7.py:79`, rejouer par la sonde. Même question pour le
     serveur pydoc d'OnlineHelp.
   - Niveau : supposé (lu, non remesuré). Note : `web.md` point 3 dit encore « `threading.Thread` … pas doublés ».
6. **Jalon 8d : le serveur pylsp dans un Worker** (tranché par l'utilisateur, zmq « Compléments », 19 h 14 : « je
   souhaite le couvrir »).
   - Obtenir : client LSP de Spyder (`plugins/completion/providers/languageserver/client.py`, sockets `PAIR`,
     `zmq.FD` lu dans un `QSocketNotifier`) parlant à pylsp dans un Worker.
   - Existant : `FD = 14` (`qtpy6/web/zmq_web.py:114`) ; aucune doublure de `QSocketNotifier` (grep → 0).
   - Fichiers : `zmq_web.py`, une doublure `QSocketNotifier` à poser sous `qtpy6.QtCore`. Essai : `jalon8d.py` à écrire.
   - Niveau : lu dans les sources. Le jalon n'est pas défini plus loin dans la note.
7. **Hébergement : un lien pour les élèves.** spe.py tourne par la sonde et dans le Chromium de l'utilisateur ; le lien
   reste à faire (zmq, « config de référence », Points ouverts). Manifeste d'application écarté pour l'instant, « à
   ajouter à l'hébergement ». Niveau : mesuré (Firefox sonde, Chromium par l'utilisateur pour `print`).
8. **Pyxel, chargement des ressources** : `load("projet_monkey.pyxres")` → `Failed to open file` malgré l'injection
   (TODO son, « Suite du 12/10, 19 h 45 »). À vérifier : fichier dans le FS du noyau, cwd à `init`, `load` par chemin
   absolu. Essai : `spe_monkey.py?jeu=…`. Fichiers : `qtpy6/web/pyxel_web.py`. Niveau : mesuré (échec), cause supposée.
9. **Le son de Pyxel** : renvoi au TODO son, premier item. Existant : `memoire_partagee.reconcilier()`,
   `preambule._doubler_sleep` (`qtpy6/web/preambule.py:70`) ; aucun `AudioContext` dans `qtpy6/` (grep → 0).
   Niveau : supposé (piste, rien d'écrit).
10. **Fenêtre d'erreur fugitive de l'explorateur** [EN COURS W550] (`directoryLoaded` → `initStyleOption`, `index.model()` None) :
    TODO son, avant-dernier item. Doublure de `QFileSystemModel` à écrire côté qtpy6 (aucune dans `qtpy6/web/`).
    Niveau : lu dans la pile relevée, cause supposée.
11. **Interruption d'un calcul qui ne dort jamais.** Aujourd'hui : signal livré au prochain `time.sleep` (a4ee0c6).
    Pour un vrai arrêt : `setInterruptBuffer` sur SharedArrayBuffer (grep → 0). La page EST isolée depuis f02c16c
    (`sw.js`, `isoler`) : voir « Contradictions ». Niveau : lu.
12. **Fermeture de l'application non mesurée jusqu'au bout** et `InvalidStateError` de superqt
    (`_throttler._set_future_result`) : zmq, « Le gel au démarrage », pistes 3 et 4. Essai : poser l'état de la sonde
    après `main.closing` dans `jalon7.py`. Niveau : mesuré partiellement.
13. **Le reste du port** (faisabilité, « Points ouverts » et jalons 3-5) :
    - console : `max_line_count` (300 lignes) à monter ; Worker de réserve et complétion factice pour cacher 1,4 s ;
    - REPL persistant et explorateur de variables hors noyau : sans objet si la console IPython (8c) est retenue ;
    - doublure `chardet.detect → utf-8` (63 Mio économisés) : D6 ;
    - [EN COURS W550] dossier autorisé de Chrome comme troisième emplacement de `persistant`, bouton « Réautoriser » : non codé
      (existant : `stockage.monter`, `qtpy6/web/stockage.py:59`) ;
    - couche Dropbox par élève : hors qtpy6 (SmartTeacher), raccordement professeur à décider ;
    - `EN_RETARD` de `construire_site.py:45` : à retirer « une fois le fork regénéré » ; il l'a été le 01/11, non
      vérifié s'il porte les six fichiers ;
    - Interpréteur : chemin factice `/pyodide/3.13/bin/python` dans `spe.py` ; `custom` reste faux.
    Niveau : mesuré pour les coûts, supposé pour les remèdes.
14. **Les treize greffons** (faisabilité, « Les treize greffons »). Embarqués : `spyder_stop_toolbar`,
    `spyder_interpreter_toolbar`, `spyder_pyxel`. Portables, non embarqués : `spyder_code_analysis` (pylint en
    `ProcessusWeb`), `spyder_smartteacher`, `spyder_collab` (transport QtNetwork à réécrire). À réécrire :
    `spyder_python_tutor` (QtWebEngine : la doublure `moteur_web.py` peut suffire, non mesuré). Hors champ : claude,
    konsole, tortoisehg, window_controls (remplacé par la barre vide de `spe.py`), viztracer, line_profiler.
    Niveau : grep des imports, aucun greffon lancé hors des trois embarqués.
15. **Chrome** : jalons 8a à 8c, Pyxel, `QWebEngineView` mesurés sous Firefox seul ; phase 2 du jalon 5 jamais lancée
    sous Blink (branches de la sonde écrites). Niveau : non mesuré.
16. **Outillage** : `_fait` de la sonde par compare-and-set (`qtpy6/web/sonde.py`, rencontré aux jalons 3 et 5) ; test
    unitaire de la règle « slot à QEvent sur place » de `bloquant.py` dans `tests/test_web.py` ; `SystemError: Cannot
    enter a promising task` résiduels (Pyxel, « Point ouvert immédiat »). Niveau : lu.
    **[FAIT, W553, 12/11, e40d9f5]** compare-and-set et test de bloquant (deux tests, échouent sans) ; SystemError :
    pile relevée (pompe `tourner` → `callPromising`), suite de la corruption GC (item 1, transmis à W545) ; reste : repro
    à relancer sur site stable. `notes/2026-11-12 - Outillage sonde et bloquant (W553).md`.
16 bis. **Trois tests de `tests/test_web.py` échouent depuis 82f2793** (boîte noire démarrée par `application()`),
    relevé par W553 le 12/11 : `test_application_persistant_dans_le_navigateur`, `test_police_fixe_dans_le_navigateur`,
    `test_coller_passe_par_qt`. Même message dans le sous-processus `en_navigateur` : `AttributeError:
    'types.SimpleNamespace' object has no attribute 'window'`, levé par `qtpy6/web/boite_noire.py:24` (`_boite` :
    `getattr(js.window, "qtpy6BoiteNoire", None)`), appelé par `demarrer()` (l. 31) depuis `application()`
    (`qtpy6/web/__init__.py:95`). Le faux `js` des tests n'a pas de `window`. Sans propriétaire au tableau de bord.
    Niveau : mesuré (pytest, 14:15).
17. **Modules PySide6 non compilés** : renvoi à `notes/TODO - Modules PySide6 non compilés.md`. Aucun n'est importé par
    SmartPythonEditor au 11/10 (cette note). `QtPrintSupport` est lié depuis le 10/10 (faisabilité, jalon 6).

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
