# TODO : le son de Pyxel dans SmartPythonEditor web (jeudi 15/10/2026 au soir, après la remise à zéro du quota)

Demande de l'utilisateur, 12/10/2026 : « je veux l'intégration de pixels complètes dans l'éditeur », puis, le quota
à 90 % : « ajoute au TODO pour jeudi soir ». Les images et le clavier sont faits (essai 28, commit 2aea235) ; contexte,
essais et pièges : `notes/2026-10-12 - Pyxel dans la page.md`.

- [ ] **Le son** : le pilote audio emscripten de SDL2 teste `AudioContext`, absent d'un Worker. Piste : doublure
  qtpy6, un `AudioContext` minimal dans le Worker dont le `ScriptProcessorNode` est pompé depuis
  `memoire_partagee.reconcilier()` (le sleep bloquant, comme pour les images) ; échantillons poussés dans un anneau
  `SharedArrayBuffer`, joués dans la page par un AudioWorklet. Vérification : la page compte les échantillons non nuls
  reçus. Rien du greffon ni de l'éditeur ne change.
- [ ] **`SystemError: Cannot enter a promising task…`** : c'est `ast.parse` dans le noyau, appelé par `%runfile`
  (triangle « Exécuter », F5) — le noyau plante, un jeu d'élève ne se lance pas par le bouton. Isolé le 12/10
  (`notes/2026-10-12 - Pyxel dans la page.md`, essai `spe_monkey.py`). Le 12/10 à 17 h : c'est en fait le ramasse-miettes
  (fonction wasm 4219, voisine de `PyGC_Collect`) qui plante sur un objet corrompu ; trouver qui le crée (`gc.collect()`
  après chaque étape du noyau). Essai : `spe_monkey.py?…&bouton=1`.
  **Suite du 12/10, 17 h 20 (reproduit sans affichage : `essais/spyder/spe_m4.py`, non commité, `&bouton=1`)** :
  - ramasse-miettes HORS DE CAUSE : même plantage avec `gc.disable()` ;
  - `ast.parse` du fichier dans le noyau passe seul, et après un `time.sleep` ; il meurt (Worker muet, ni retour ni
    exception) après `frontend_call(blocking=True).get_file_code(...)`, l'attente de la réponse de l'éditeur que fait
    `%runfile` (`code_runner._get_file_code` → `wait_until` → `time.sleep(0.01)` en boucle). Pas toujours au premier
    appel : intermittent, donc une corruption qui dépend de l'entrelacement ;
  - pendant cette attente, le fil d'historique d'IPython (`HistorySavingThread`, émulé par `threading_web`) sonde en
    boucle par `run_sync` : deux piles suspendues s'entrelacent ; l'arrêter (`stop_now`) n'a pas suffi (il sonde encore) ;
  - écarté : traiter les messages de la page à la tâche asyncio suivante (`recevoir_page` → `call_soon`) au lieu de
    l'appel synchrone d'`onmessage` — même mort, correctif retiré ;
  - pistes : l'ordre de reprise non LIFO des piles JSPI (pile C ou `datastack` de l'état de fil partagé), ou le
    traitement de la réponse de comm lui-même ; tracer `zmq_web.recevoir` et la réponse `_handle_remote_call_reply`.
  **Suite du 12/10, 18 h 45 — cause et correctif (corrige le « hors de cause » ci-dessus)** :
  - c'est bien le GC, mais ses passes AUTOMATIQUES seulement (3.14, incrémental) : `gc.set_threshold(1, 1, 1)` dans le
    noyau meurt à la première passe ; `gc.collect()` complet avant/après chaque pas passe toujours. Le `gc.disable()`
    du premier essai était annulé par parso (`parso/cache.py` fait `gc.enable()` sans condition dans un `finally`) ;
  - correctif écrit, mesuré, puis MIS DE CÔTÉ : `preambule._doubler_gc` — GC automatique coupé, passe complète toutes
    les 2 s si plus de 20 000 objets nouveaux (27–34 ms pour 108 000 objets), `gc.enable/disable/isenabled` doublés.
    Patch : `notes/2026-10-12 - doublure gc (preambule, non appliquée).diff` (`git apply`). Retiré de la copie de travail
    le 12/10 à 19 h 15 : `preambule.installer` tourne aussi dans le Worker de la console de code du lecteur QCM
    (`travailleur.js` → `_executer`), et l'utilisateur ne veut rien risquer sur le lecteur QCM avant jeudi (« j'ai peur
    en attendant, si on touche à [Pyodide], de casser le lecteur de QCM dans le navigateur ») ;
  - écartés par mesure : seuil de trou d'`enterTask` de Pyodide (patché à l'infini dans une copie : même mort),
    `recevoir_page` → `call_soon` (idem), nombre de fils suspendus (le seuil bougeait avec la disposition mémoire) ;
    Pyodide nu sous Node avec piles entrelacées et seuil 1 passe : hypothèse non prouvée, le GC jeune parcourt les
    piles de `PyThreadState` périmés de la réserve de Pyodide ;
  - avec la doublure, le triangle passe `%runfile` et arrive à l'init SDL de Pyxel ; au-delà, le Firefox du bac à sable
    meurt toujours (`Aborted()`, pas de WebGL — vrai aussi du lancement automatique, sans la doublure) : **reste la
    vérification par l'utilisateur dans son Firefox**.
- [ ] **Jeudi : la suite du portage de SmartPythonEditor dans le navigateur, threads compris** (report décidé par
  l'utilisateur le 12/10 à 19 h 10, même raison : ne pas toucher au Pyodide du lecteur QCM d'ici là). Dans l'ordre :
  1. vérification du triangle par l'utilisateur avec le patch du GC appliqué (Firefox visible, WebGL) :
     `sh essais/spyder/sonde_tri.sh` (non commité, il cliquera lui-même le triangle) — le site d'essai `essais/spyder/site`
     est construit avec le patch ; le Firefox du bac à sable n'a pas de WebGL, Pyxel y meurt toujours (`Aborted()`) ;
  2. décider où vit la doublure du GC sans risque pour le lecteur QCM : l'appliquer à tout Worker (mesurer la console
     de code QCM : `tests_modele.py` côté web, sonde du lecteur), ou seulement aux Workers de noyau Jupyter ;
  3. signaler le défaut à Pyodide (passes automatiques du GC de 3.14 + piles JSPI entrelacées), reproduction minimale
     à écrire : Pyodide nu sous Node ne le reproduit pas encore (`$TMPDIR/gcnu.mjs`, perdu à la fermeture) ;
  4. essai de faisabilité de vrais threads (Pyodide compilé avec pthreads), en mode plan d'abord. Ce qu'on sait, sans
     l'avoir mesuré : Emscripten et Qt-WASM savent faire, la page est déjà isolée (COOP/COEP, f02c16c) ; Pyodide
     officiel ne le fait pas, tout est à recompiler (Python, Pyodide, Qt, PySide, roues dont Pyxel en Rust avec
     `build-std`/atomics), le chargement dynamique de modules avec pthreads est expérimental chez Emscripten, et la
     couche JS de Pyodide suppose un seul fil (un thread = un Worker qui ne voit pas les objets JS des autres).
     Explication donnée à l'utilisateur : la doublure `threading_web` simule les fils en suspendant des piles (JSPI de
     Pyodide) ; c'est cette simulation, pas la compilation, qui heurte le GC.
- [ ] La fenêtre d'erreur fugitive au lancement de `spe_monkey.py` (console interne, relevée par l'utilisateur) :
  `fsmodel.directoryLoaded` → `resizeColumnToContents(0)` (relayé par `bloquant.py`) → `initStyleOption` du délégué de
  l'explorateur reçoit un index sans modèle (`index.model()` vaut None → `'NoneType' object has no attribute 'isDir'`).
  Sans conséquence sur le jeu. Natif : jamais vu. Piste : `QFileSystemModel` sans fils en WASM émet `directoryLoaded`
  avant que ses lignes soient valides ; à corriger côté qtpy6 (doublure), pas dans Spyder.
- Les sondes se donnent en bloc NON vert à coller dans une Konsole tant que le relais `!` sudo est bloqué.
