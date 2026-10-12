# Pyxel dans SmartPythonEditor web (12/10/2026)

Demandes de l'utilisateur : « il manque les outils pour Pyxel » (11/10), puis « avance sur pyxel » (12/10, 05 h).
Contrainte permanente : le code de SmartPythonEditor et de ses greffons (`SmartPythonEditorPlugins/spyder_pyxel`) ne
change pas ; ce qui manque dans la page est une doublure qtpy6.

## Ce qui est établi

- **La roue.** PyPI ne publie que des roues natives de pyxel 2.9.9. La version web officielle (`pyxel.js`, servi par
  `cdn.jsdelivr.net/gh/kitao/pyxel/wasm/`) charge Pyodide 314.0.4 et la roue
  `pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl`, posée à côté de pyxel.js (relevé WebFetch, non téléchargée :
  le shell n'a pas le réseau). Pyodide 314.0.4 et 314.0.7 (celui de `qtpy6/web/versions.json`) ont la même ABI
  (`2026_0`, emscripten 5.0.3) : **la roue officielle convient au Pyodide ordinaire de qtpy6**, sans recompilation.
  Elle ne convient PAS à Pyodide-Qt (0.29.3, Python 3.13, `pyemscripten_2025_0`), sur lequel `spe.py` fait tourner le
  noyau de la console (`travailleur.configurer("./pyodide-qt/")`). Les roues pyxel wasm plus anciennes trouvées sur le
  disque (sites de collègues NSI) visent emscripten 3.1.x : inutilisables.
- **Le noyau de la console tourne sur le Pyodide ordinaire** (option A ci-dessous) : `essais/spyder/spe_pyxel.py` (spe.py
  avec `./pyodide/` au lieu de `./pyodide-qt/`, lien `site/pyodide` → `exemple/pyodide`, Python 3.14.2) ; sonde Firefox,
  `capture_pyxel.png` : bannière « Python 3.14.2 … IPython 9.15.0 », invite `In [1]:`, zéro Traceback dans
  `sonde_pyxel.log`. *Testé dans la page (sonde), console non exercée au-delà de l'invite.* La page, elle, reste sur
  Pyodide-Qt 3.13 : seul le Worker du noyau change, ce que `configurer` permet déjà.
- **Ce que fait le greffon** (lecture de `bridge/kernel.py`, `bridge/hooks.py`, `bridge/reader.py`,
  `spyder/bridge_manager.py`) : dans le noyau, un crochet d'import remplace `pyxel.init/run/flip/show/quit` ; `init`
  pose `SDL_VIDEODRIVER=offscreen` ; `run` devient une boucle Python `update/draw/flip` ; à chaque image, `publish` copie
  `pyxel.screen.data_ptr()` et la palette dans un `multiprocessing.shared_memory.SharedMemory` (seqlock) puis écrit un
  octet dans une FIFO ; le panneau lit la mémoire partagée, réveillé par un `QSocketNotifier` sur la FIFO, et renvoie
  clavier/souris par la même mémoire (`set_btn`, `set_mouse_pos`).

## Options

- **A, retenue pour la suite : noyau sur Pyodide 314** — mesurée ci-dessus, démarre. Reste à vérifier sous ce noyau :
  matplotlib, l'explorateur de variables, le débogueur (non mesurés).
- **B : recompiler pyxel pour Pyodide-Qt (2025_0)** — écartée pour l'instant : Rust sans cible
  `wasm32-unknown-emscripten`, ni maturin, ni emsdk 4.x pour cette ABI sur la machine ; coût d'une chaîne complète.
- **C : jeux dans un ProcessusWeb séparé** — écartée : perd l'intégration au noyau (variables, débogueur, F5) qui est
  la raison d'être du greffon.

## Doublures qtpy6 que l'option A demande (à écrire)

1. `multiprocessing.shared_memory.SharedMemory` entre la page et le Worker du noyau. ⚠ Corrigé à 11 h 40 : la page
   n'est PAS isolée COOP/COEP (web.md, « Les fils sont coopératifs » ; `travailleur.signaler` le dit aussi), donc pas de
   SharedArrayBuffer. Deux voies : un miroir par messages (le segment du noyau envoyé à la page à chaque notification de
   la FIFO, les événements de la page renvoyés au noyau) ; ou isoler la page (service worker qui pose COOP/COEP, ce qui
   apporterait aussi l'interruption du noyau, au prix des ressources tierces refusées sans CORP). Choix de l'utilisateur.
   **Choix de l'utilisateur (11 h 40, « oui on essaye ») : isoler la page** — fait et mesuré, essai 24 ; doublure
   `SharedMemory` écrite, essai 25.
2. La FIFO de notification (`os.mkfifo`/`os.open`/`os.write` côté noyau) et `QSocketNotifier` sur son descripteur côté
   page — ou un réveil équivalent porté par la même mémoire partagée.
3. SDL dans un Worker : `pyxel.init` avec `SDL_VIDEODRIVER=offscreen` — à mesurer dès que la roue est là (le port SDL
   d'emscripten n'a peut-être pas ce pilote, et un Worker n'a pas de canvas DOM).
4. `pyxel.flip()` dans le Worker : la version web de Pyxel cadence par la boucle du navigateur ; à mesurer.

## Mesures du point 3 (12/10/2026, 05 h 15 → 05 h 45, sonde Firefox du bac à sable)

Roue téléchargée par l'utilisateur dans `essais/spyder/roues/` (5 024 321 octets, non versionnée), servie par
`travailleur.configurer("./pyodide/", roues=[...])` ; `essais/spyder/spe_pyxel.py` exécute un jeu minimal dans la console.
Chaque ligne est un essai, dans l'ordre ; le mur suivant n'apparaît qu'une fois le précédent levé.

1. `import pyxel` : **OK** dans le Worker du noyau (Python 3.14.2).
2. `pyxel.init` depuis une cellule : `FileNotFoundError /tmp/ipykernel_42` — le code Rust fait un `chdir` dans le dossier
   du script appelant. Levé en écrivant `/home/pyodide/jeux/jeu.py` et en l'exécutant sous ce nom (ce que fait F5).
3. Avec `SDL_VIDEODRIVER=offscreen` (ce que pose le crochet `patched_init` du greffon) : panique Rust « Failed to
   initialize SDL2: offscreen not available » — **le port SDL2 d'emscripten n'a pas ce pilote**. Le greffon tel quel ne
   peut donc pas marcher dans la page : il faudra une doublure qui le neutralise, sans toucher au greffon (à décider).
4. Sans pilote imposé : SDL veut un canvas. `pyodide.canvas.setCanvas2D(OffscreenCanvas)` le donne, puis il manque, l'un
   après l'autre : `screen` (ReferenceError), `navigator.getGamepads` (« Gamepads not supported »), `window` AVANT le
   chargement de Pyodide (emscripten fige `specialHTMLTargets` à ce moment-là : « Could not set gamepad connect
   callback »), `canvas.style` (« Module.canvas.style is undefined »), `document` (ReferenceError). Tous posés par l'essai
   (objets factices dans le Worker ; `window = self` en tête de `travailleur.js` servi par un blob modifié).
5. **SDL s'initialise alors et crée sa fenêtre** ; le mur suivant est le contexte GL : « Could not create EGL context
   (EGL_BAD_MATCH) », parce que `getContext("webgl2")` et `"webgl"` rendent `null`. **Ce n'est pas le Worker : le Firefox
   headless du bac à sable n'a aucun WebGL, page comprise** (« AllowWebgl2:false restricts context creation on this
   system », déjà constaté dans `notes/2026-10-10 - Modules Qt à la demande.md`). La sonde `--chromium` (QtWebEngine) ne
   rend pas la console du Worker ; non poursuivi.

Également vu dans la console, non expliqué : plusieurs `SystemError: Cannot enter a promising task from inside another
running promising task` (Pyodide), avant et après la panique ; à regarder si elles survivent à un init réussi.

6. **Hors bac à sable (sonde lancée par l'utilisateur, Firefox 155 avec WebGL, 12/10/2026)** : `getContext("webgl2")`
   rend un contexte dans le Worker, et **`pyxel.init(64, 48)` réussit** (« RESULTAT init OK 64 48 /home/pyodide/jeux »).
   « Failed to initialize audio device » est écrit mais n'arrête rien : un Worker n'a pas d'AudioContext, le son est à
   traiter à part. `pyxel.flip()` panique ensuite : « **pyxel.flip is not supported on Pyxel Web** »
   (`platform_sdl2.rs:544`). C'est un refus délibéré de Pyxel, pas un manque de doublure. Relevés :
   `essais/spyder/sonde_pyxel_hors.log`, `capture_pyxel_hors.console.log`.

7. **Sans `flip`, le dessin marche et `time.sleep` cadence** (même relais, 12/10/2026 07 h 30) : dix images `cls(i)` +
   `rect(…, 15 - i)` sans aucun `flip` ; `pyxel.screen.data_ptr()` relu à chaque image donne exactement les valeurs
   dessinées (`(15, 0), (14, 1) … (6, 9)`), et dix `time.sleep(1/30)` durent 0,339 s pour 0,333 attendues. Le tampon
   d'écran est donc à jour dès le dessin, sans passer par le rendu GL. (Premier essai : `memoryview` au format `<B` ne
   s'indexe pas sous Pyodide, `NotImplementedError` ; lu par `bytes(...)`.)
8. **Mais sans `flip`, `frame_count` n'avance pas, et le `pyxel.run` d'origine tue Pyodide** (même relais, 07 h 35) :
   après les dix images, `pyxel.frame_count` vaut 0 ; `set_btn(KEY_SPACE, True)` puis `btn`/`btnp` rendent True/True (sur
   l'image 0 seulement : `btnp` et toute animation qui lit `frame_count` seraient faux tant que le compteur reste figé).
   `pyxel.run(update, draw)` appelle `emscripten_set_main_loop`, qui lève « unwind » pour quitter la pile C : dans le
   noyau, c'est une **erreur fatale de Pyodide** (« Pyodide has suffered a fatal error … unwind »), le Worker meurt.
   L'option « laisser tourner `pyxel.run` » est donc écartée telle quelle, et la doublure de `flip` devra faire avancer
   `frame_count`, ce que l'API Python publique ne permet pas (rien dans `__init__.pyi`). Source Rust non consultable
   d'ici : WebFetch rend 404 sur github.com et raw.githubusercontent.com (12/10, 07 h 35), et aucune copie sur le disque.
9. **Le `flip` d'origine ne se rattrape pas** (même relais, 07 h 45) : appelé sous `try/except BaseException`, sa panique
   Rust (`platform_sdl2.rs:544`) n'arrive jamais en Python : « Aborted(Assertion failed: handback_tstate == NULL …
   restoreThreadState) », « Pyodide has suffered a fatal error », « RuntimeError: unreachable executed ». Le Worker
   meurt. `flip` est donc inutilisable sous toute forme en web ; `frame_count` ne peut avancer que par la boucle de Pyxel.
   Piste suivante, celle de Pyxel Studio (`pyxel.js`, lu par WebFetch sur cdn.jsdelivr.net) : il pose
   `pyodide._api._skip_unwind_fatal_error = true` (« Keep Pyodide from treating Emscripten's main-loop unwind as a fatal
   error ») et laisse `pyxel.run` tourner dans la boucle principale d'emscripten. Essai 10 : même drapeau, `pyxel.run`
   lancé depuis une pile JS neuve (`setTimeout`), la cellule dormant à côté.
10. **Échec** (07 h 44) : en 1,5 s, `frame_count` reste à 0 et `update` n'est jamais appelé. Quatre `SystemError: Cannot
    enter a promising task from inside another running promising task` : les rappels de `requestAnimationFrame` tentent
    d'entrer dans Python pendant que la cellule est suspendue par JSPI dans `time.sleep`. Le `set_btn` suivant panique
    (« RefCell already borrowed », `pyxel-core/src/pyxel.rs:47`) : le `run` interrompu par l'unwind garde l'instance
    Pyxel empruntée. Puis abandon fatal. Conclusion : la boucle de Pyxel ne peut pas tourner À CÔTÉ d'une cellule
    suspendue, et seuls `update`/`draw` peuvent toucher Pyxel une fois `run` lancé. Essai 11 : `pyxel.run` appelé dans la
    cellule elle-même, exactement comme pyxel.js, entrées posées depuis `update`.
11. **Encore fatal** (10 h 31) : « Pyodide has suffered a fatal error … Error: unwind », bien que le drapeau soit posé.
    Lecture de `pyodide.asm.mjs` (314.0.7) : seul l'appel SYNCHRONE d'un PyProxy (`__pyproxy_apply`, chemin de
    `runPython`, celui de pyxel.js) passe l'exception par `API.maybe_fatal_error`, qui épargne « unwind » sous le drapeau.
    L'appel PROMETTEUR (`promisingApply`, JSPI, celui du noyau qui exécute la cellule) appelle `API.fatal_error` sans
    condition. Le drapeau de Pyxel Studio ne vaut donc que hors JSPI. Essai 12 : faire appeler `pyxel.run` par un
    trampoline JS synchrone (une fonction JS qui appelle un PyProxy), pour que l'unwind s'arrête dans
    `maybe_fatal_error`, puis laisser la cellule finir et les images arriver par `requestAnimationFrame`.
12. **Plus d'erreur fatale** (10 h 34) : `pyxel.run` lancé par le trampoline rend la main (« RESULTAT run rendu »), la
    cellule se termine et le noyau reste vivant (invite `In [2]:`). En revanche, aucune trace de `update` (journal
    `js.console.log` dans la console du Worker) : soit la boucle ne tourne pas, soit ses traces n'ont pas été capturées.
    Essai 12 bis : une seconde cellule, 3 s plus tard, relève `frame_count`.
    **Résultat : `frame_count` vaut toujours 0 après 3 s** ; la boucle ne bat pas, ou n'entre pas dans Python. Essai 12
    ter : relever `Module.MainLoop` (exporté par emscripten : `running`, `func`, `timingMode`, `currentFrameNumber`) et
    deux compteurs en JS pur (`requestAnimationFrame` et `setTimeout` de 16 ms), 2 s d'écart.
    **Résultat de 12 ter : aucune mesure, la PAGE est morte pendant la cellule 1** (identique à celle de 12 bis, qui
    passait) : erreur fatale Pyodide côté page (`pyodide-qt/pyodide.asm.js`, « A value of type undefined … was thrown as
    an error »), pile Python `jupyter_client/channels.py:145 _async_run` → `threading_web.py:129 wait` →
    `fils.py:32 _attendre` → `bloquant.py:45 _pyodide_suspendre` (suspension JSPI dans un `run_handle` de la webloop),
    suivie de deux « uncaught exception: undefined ». Hypothèse non vérifiée : un `throw undefined` venu du Worker (fin
    de l'unwind du trampoline ?) ou une course dans l'attente du canal ; à départager en relançant la même sonde
    (intermittent ou non).
    **Cause trouvée à la relance (même chute) : un faux arrêt de l'essai.** L'écho de la cellule dans la console contient
    `"ULTAT run fin"`, qui satisfait la condition d'arrêt ` fin` du relevé : la sonde se ferme aussitôt l'écho affiché,
    et la page, coupée en pleine attente JSPI, meurt (« Script terminated by timeout », `throw undefined`). Ce n'est pas un
    défaut de qtpy6. Corrigé (`"run f" "in"`), site reconstruit, 12 ter relancé.
    **Résultat de 12 ter (11 h 00)** : `MainLoop.running` vrai, `func` posée, mode 1 (requestAnimationFrame), mais
    `currentFrameNumber` reste à 1 pendant que, dans le même Worker, un `requestAnimationFrame` JS pur bat 180 fois en 2 s
    (et un `setTimeout` de 16 ms 183 fois). `frame_count` reste à 0. La boucle s'arrête donc à la première image : le
    `runner` d'emscripten n'appelle `scheduler()` qu'après un `runIter` qui rend normalement, et `callUserCallback` avale
    l'exception. Essai 13 : remplacer `MainLoop.runIter` par une version qui capture l'exception, puis `MainLoop.resume()`.
13. **L'exception est une panique Rust de l'essai lui-même** (11 h 03) : « RefCell already mutably borrowed »
    (`pyxel-core/src/platform/facade.rs:24`), rendue en « RuntimeError: unreachable executed ». C'est le `pyxel.set_btn`
    que l'`update` de l'essai appelait : en web, `update`/`draw` tournent DANS la boucle de Pyxel, qui tient déjà
    l'emprunt de la plateforme. La boucle elle-même n'y est pour rien. (Le source Rust de 2.9.9 reste illisible d'ici :
    jsDelivr liste `crates/pyxel-core/src/platform/facade.rs` mais rend 404 sur le fichier ; diagnostic par la chaîne
    du message, présente dans le `.so` de la roue.) Conséquence pour le pont : les entrées (`set_btn`,
    `set_mouse_pos`) doivent être posées ENTRE deux images, jamais depuis `update`/`draw`. Essai 14 : `update` sans
    `set_btn` (relève `frame_count`, `btn`, `btnp` dans un journal JS), `set_btn` posé depuis la cellule 2.
14. **Correction du 13 : la vraie première erreur est JS** (11 h 06). Même panique d'emprunt, mais `runIter` capture
    d'abord « ReferenceError: _readVirtualGamepadBitmask is not defined » : à chaque image, le Rust évalue
    `_readVirtualGamepadBitmask();` (`emscripten_run_script_int`). C'est la manette virtuelle tactile de `pyxel.js`, une
    fonction globale de sa page. L'exception JS traverse le Rust sans libérer l'emprunt, d'où la panique à l'image
    suivante. Le 13 accusait donc à tort le `set_btn` de l'essai (hypothèse retirée ; qu'un `set_btn` depuis `update`
    soit sûr reste à mesurer). Les noms JS que la roue évalue (`strings` du `.so`) : `_readVirtualGamepadBitmask()`,
    `resetPyxel()`, `_savePyxelFile(…)`. Essai 15 : `self._readVirtualGamepadBitmask = () => 0` dans le Worker.
15. **Plus d'erreur, mais plus rien après la cellule 1** (11 h 10) : « run rendu », invite `In [2]:`, puis la cellule 2
    n'apparaît jamais et le relevé finit sans elle. Soit la boucle tourne et le noyau ne traite plus ses messages, soit
    autre chose ; les `console.log` du Worker ne sont pas capturés par la sonde. Essai 16 : `update` arrête la boucle à
    l'image 60 par `_emscripten_cancel_main_loop()` (l'arrêt de `pyxel.js`) ; si le noyau reprend, la cellule 3 rend le
    journal des images.
16. **La boucle tourne, et le noyau reprend à son arrêt** (11 h 13) : la cellule 2 s'exécute après l'arrêt, avec
    `frame_count 61`, `MainLoop` à l'image 115 (rAF à 60 Hz, Pyxel à 30 images/s). Pendant la boucle, la cellule 2
    n'est pas traitée (essai 15). Le `resume()` de la cellule 2, reste de l'essai 13, lève `MainLoop.scheduler is not a
    function` (planificateur effacé par l'arrêt), et la mise en forme de cette exception finit en erreur fatale : défaut
    de l'essai, pas de Pyxel. Essai 17 : touche posée depuis un `setTimeout` JS à 1 s (relâchée à 1,5 s), compteur
    `setTimeout` pour savoir si les tâches JS passent pendant la boucle, cellule 2 en simple lecture.
17. **Avec la touche posée à 1 s, la boucle ne s'arrête plus à l'image 60** (11 h 17) : « run rendu », puis plus rien
    pendant 90 s (plafond du relevé), avec la même `uncaught exception: Object { message }`. Le noyau restant bloqué,
    le journal est illisible. Essai 18 : la touche est posée dans un `try` JS qui écrit l'erreur au journal, et un
    `setTimeout` JS pur arrête la boucle à 3 s, sans passer par Python, pour que la cellule 2 puisse lire le journal.
18. **Même blocage malgré l'arrêt JS à 3 s** (11 h 20) : l'arrêt ne s'est pas produit. Hypothèse : pendant la boucle de
    Pyxel, les `setTimeout` du Worker ne passent plus (ce qui expliquerait aussi le noyau sourd de l'essai 15), et la
    touche posée à 1 s n'y est pour rien. Essai 19 : l'arrêt revient dans `update` (image 90, le moyen qui a marché à
    l'essai 16), et chaque ligne du journal porte le compteur `setTimeout`.
19. **Tout marche, l'hypothèse de l'essai 18 est fausse** (11 h 22) : pendant la boucle, les `setTimeout` du Worker
    passent (88 en 1,5 s), la touche posée depuis JS entre deux images est vue (`btn=True btnp=True` à l'image 27, puis
    `btnp=False` à l'image 30, relâchée ensuite), et **le noyau exécute la cellule 2 pendant que la boucle tourne**
    (`running True`, `frame_count 43`). Le jeu et la console coexistent donc. Les essais 15, 17 et 18, bloqués,
    portaient chacun une `uncaught exception: Object { message }` dans le journal du navigateur, absente ici : le
    blocage est réel mais intermittent ou dû à une autre différence non identifiée (point ouvert, à reproduire en
    relançant l'essai 19 tel quel).
    Reprise à 11 h 23, à l'identique : même résultat (touche vue images 28 à 30, cellule exécutée à l'image 51,
    aucune `uncaught exception`). Les blocages des essais 15, 17 et 18 restent inexpliqués : le module qtpy6 devra
    capturer et journaliser toute exception levée dans une image plutôt que de la laisser filer.
20. **Doublure de `flip` seule** (11 h 26) : la boucle du greffon (`patched_run`) ne peut pas tourner à côté de
    la boucle emscripten (essai 10 : une cellule suspendue interdit aux images d'entrer dans Python). Idée : lancer une
    fois le `pyxel.run` d'origine par le trampoline avec des rappels vides, mettre aussitôt sa boucle en pause
    (`MainLoop.pause()`), et faire de `flip` « cadence par `sleep`, puis UNE image » : appel synchrone de
    `MainLoop.func`, la fonction d'itération posée par emscripten. La boucle reste celle de l'appelant, donc le greffon
    tourne tel quel, et `frame_count`/`btnp`/rendu avancent par Pyxel lui-même. Essai : 60 tours `cls` + `flip_web`,
    touche posée par `setTimeout` JS à 1 s (le `sleep` JSPI laisse passer les tâches JS).
    **Résultat : la doublure fonctionne.** `fc` 0 → 1 → 3 (un saut au démarrage), puis +1 par `flip` (k=50 → 51), 61
    images en 2,0 s pour 2,0 attendues, `MainLoop.running` reste vrai (la pause n'efface que le planificateur). La touche du
    `setTimeout` n'est PAS vue (btn False à 1,0–1,67 s), avec « uncaught exception: undefined » : le rappel JS entre dans
    Python pendant que la cellule est suspendue dans le `sleep` (même cause que l'essai 10). Chemin sans objet pour le
    greffon, qui pose ses entrées depuis Python (`InputConsumer.pump`) : essai 21.
21. **Entrées posées dans la boucle** (11 h 28) : `set_btn(KEY_SPACE, True)` à k=30, `False` à k=45, avant `flip_web`,
    comme `pump` du greffon. **Résultat conforme** : k=30 btn True btnp True ; k=31 à 44 btn True btnp False ; k=45 et
    au-delà btn False. Cadence et `frame_count` identiques à l'essai 20. Niveau de preuve : sonde Firefox lancée par
    l'utilisateur (WebGL), une exécution.

22. **La doublure dans qtpy6** (11 h 33) : `qtpy6/web/pyxel_web.py`, installé par `preambule.installer`, et
    `window ??= globalThis` posé en tête de `js/travailleur.js` (avant `loadPyodide`). L'essai ne porte plus aucune
    instrumentation : `SDL_VIDEODRIVER=offscreen` posé comme le greffon, `pyxel.init`, puis 60 tours `set_btn`/`cls`/
    `pyxel.flip`. **Résultat identique à l'essai 21** : `pyxel.flip.__module__` = `qtpy6.web.pyxel_web`, 61 images en
    2,0 s, btn/btnp conformes, dernier pixel 11 (le `cls(11)` de la dernière image). Le reste de la console (zmq,
    affichage) n'est pas gêné par `window` dans le Worker. Niveau de preuve : sonde Firefox, une exécution ; `run` doublé
    et réinitialisation (`init` appelé deux fois) non testés.

23. **Ordre du greffon** (11 h 35) : défaut trouvé à la lecture de `bridge/kernel.py` : le greffon pose ses crochets
    depuis un `__import__` enveloppé, dès que `pyxel` ENCORE PARTIELLEMENT initialisé a `init`/`run`/`flip`, donc juste
    après `from .pyxel_binding import *` et avant la fin de `pyxel/__init__.py`. La version de l'essai 22 complétait
    `pyxel` après son exécution : le greffon aurait capturé le `flip` d'origine. Correctif : le chercheur complète
    l'extension `pyxel.pyxel_binding` dès son exécution, avant la recopie de ses noms. Essai : un `__import__` enveloppé
    comme celui du greffon capture `pyxel.flip` au premier instant possible → `qtpy6.web.pyxel_web` ; essai 22 rejoué à
    l'identique. Niveau de preuve : sonde Firefox, une exécution.

24. **Page isolée par le service worker** (11 h 45). Demande : « on aura besoin de ressources d'autres domaines ? » puis
    « oui on essaye ». Seul domaine tiers chargé par la page : cdn.jsdelivr.net (Pyodide des Workers, roue sqlite3).
    Fait : `qtpy6/web/js/sw.js`, paramètre `isoler` : COOP `same-origin` et COEP `credentialless` ajoutés à toute
    réponse de la même origine (type `basic`, ou `default` pour un jumeau rangé décompressé), servie du cache comme du
    réseau ; `qtpy6web.js`, `service_worker(…, { isoler: true })` : rechargement UNE fois à la première visite (une page
    chargée ne change pas d'en-têtes), garde sessionStorage contre la boucle, pas de rechargement sans stockage.
    Branché dans la page d'essai par `essais/spyder/construire_site.py`. Choix : `credentialless` plutôt que
    `require-corp`, qui exigerait un en-tête CORP de jsdelivr (non vérifié) ; coût accepté : un rechargement à la première
    visite, et Safari, qui n'a pas `credentialless` (non mesuré). Écarté : le miroir par messages (copie de chaque image
    vers la page, plus lent, et pas d'interruption du noyau). Résultat : page `crossOriginIsolated` True,
    `SharedArrayBuffer` présent ; Worker du noyau (True, True) ; jsdelivr toujours chargé (console et Pyxel intacts,
    61 images en 2,0 s, pixel 11). Bizarrerie non expliquée : un `print` en toute première ligne de la cellule n'est pas
    apparu dans la console (déplacé après `import pyxel`, il sort). Niveau de preuve : sonde Firefox, deux exécutions ;
    Chrome non mesuré.

25. **Doublure `SharedMemory`** (11 h 55). Fait : `qtpy6/web/memoire_partagee.py` (`SharedMemory(name, create, size)`,
    `buf`, `name`, `size`, `close`, `unlink`), posée dans `multiprocessing.shared_memory` côté page (`QtCore.py`) et côté
    Worker (`preambule.installer`, fichier ajouté à `_FICHIERS_WORKER`). Le segment est un `SharedArrayBuffer` créé par
    la page ; `travailleur._nouveau_worker` inscrit chaque Worker, qui reçoit les segments existants puis chaque nouveau
    (`{memoire: {nom, sab}}`, rangé par `travailleur.js` dans `self.qtpy6_memoires`) ; l'attache par nom attend 2 s le
    message dans un Worker, puis `FileNotFoundError` comme en natif. `buf` est un `bytearray` local (Pyodide ne voit que
    sa mémoire wasm), réconcilié en JavaScript toutes les 4 ms contre l'image du dernier passage : mots changés ici
    poussés (de la fin vers le début), puis mots changés ailleurs tirés (du début vers la fin), la queue non alignée par
    octet ; cet ordre sert le verrou de séquence du greffon (en-tête avant les données). Écartés : `buf` posé directement
    sur le SharedArrayBuffer (impossible : un memoryview Python ne pointe que dans la mémoire wasm de son Pyodide) ;
    une copie entière à chaque passe (écraserait les écritures de l'autre côté). Limites : un segment créé dans un Worker
    reste dans ce Worker ; un même mot écrit des deux côtés entre deux passes : le dernier passage gagne. Essai
    (`spe_pyxel.py`) : la page crée 4 099 octets, écrit `0xCAFE` et `page` en queue ; le noyau s'attache par nom, lit
    `('0xcafe', b'page', 4099)`, écrit `noya` et `0xBEEF` ; la page relit `(b'noya', '0xbeef')`. Premier passage : taille
    4 100 au lieu de 4 099 (tampon arrondi au mot), corrigé (taille exacte, queue par octet ; réconciliation vérifiée
    aussi sous node). Pyxel intact (61 images, 2,0 s, pixel 11). Niveau de preuve : sonde Firefox, deux exécutions.

## Ce que cela change pour le pont

**Forme retenue (essais 20 et 21) : la boucle du greffon tourne telle quelle, qtpy6 ne double que `pyxel.flip` et
`pyxel.init`**, posés dans le Worker AVANT le crochet du greffon (qui capture `original_flip` et `original_init` à
`install()`). `flip` web : au premier appel, `pyxel.run` d'origine lancé par le trampoline avec des rappels vides puis
`MainLoop.pause()` ; ensuite cadence à `fps` par `time.sleep` (JSPI) et `MainLoop.func()` synchrone, qui déroule une
image (rendu, `frame_count`, `btnp`). `init` web : sans `SDL_VIDEODRIVER=offscreen`, avec les objets factices du DOM et
le stub `_readVirtualGamepadBitmask`. Une doublure de `run` (boucle Python update/draw/flip) sert le code hors greffon.
Écartée : laisser tourner la boucle emscripten de `pyxel.run`, qui demandait de contourner `patched_run` (code du
greffon) et interdit à la cellule d'être suspendue pendant les images (essai 10).

## Essais 26 et 27 : le greffon embarqué (12/10/2026, 12:00 → 12:27)

Demande de l'utilisateur (12:01, dictée) : « tu ne vas pas attaquer les notifications, je veux l'intégration de pixels
complètes dans l'éditeur. Donc tu vas jusqu'au bout, quitte à monter jusqu'à 93% ». Donc pas de FIFO : le pont du
greffon sonde son segment (minuterie à 4 ms).

- **Essai 26** (`spyder_pyxel` ajouté à `GREFFONS` de `essais/spyder/construire_site.py`) : `PONT page canaux []`.
  Cause, trouvée sous node : **`os.mkfifo` n'existe pas dans Pyodide** → `AttributeError` dans `PyxelChannel.create()`,
  qui ne rattrape que `OSError`, et `attach_console` l'avale sans rien dire. Puis plantage `drop_gil: GIL is not locked`
  pendant la suspension du fil de jupyter_client.
- **Correctif (non commité)** : `qtpy6/web/memoire_partagee.py`, `installer()` pose `os.mkfifo` = `_mkfifo`, qui lève
  `OSError(ENOSYS)` (ce que rend une plateforme sans FIFO) ; le greffon retombe sur son sondage. Écarté : une vraie
  FIFO (refusé par l'utilisateur), modifier le greffon (interdit).
- **Essai 27b/c** : canal créé (`('spyder_pyxel_42_…', None)`), **plus de plantage du GIL** (sans doute dû à l'échec
  précédent, non démontré), le jeu tourne 150 images, le greffon est accroché (`patched: True` après le jeu). Mais
  le panneau reçoit 0 image : l'en-tête vu par la page a MAGIC et le pid (écrits par le constructeur du publieur),
  `seq` = 0 → `publish()` sort avant le verrou de séquence : soit la largeur, soit `pyxel.screen.data_ptr()` (ctypes
  sur une adresse wasm ?) lève, et c'est avalé.
- **Essai 27d** : `data_ptr()` marche (`c_ubyte_Array_3072`), taille 64×48 ; le segment vu par la page a `seq` = 300
  et la bonne image, mais seulement **en fin de cellule**, et le jeu est lent (150 images en ~18 s).
- **Essai 27e** (mesure dans `update`, image 10) : **`can_run_sync()` est faux dans le noyau IPython** ; le `time.sleep`
  doublé retombe sur le sleep bloquant (50 ms tenues, jeu à 30 i/s : 150 images en 4,98 s), mais un Worker bloqué ne
  passe jamais la minuterie JS de `memoire_partagee` : la page ne voit rien (segment à zéro). Cause pas cherchée plus
  loin (pourquoi le contexte d'exécution du noyau n'est pas JSPI) : le correctif ne l'exige pas.
- **Correctif (qtpy6)** : `memoire_partagee.reconcilier()` (le moteur JS gagne `passer()`, une passe immédiate sur
  tous les segments) ; `preambule._doubler_sleep`, dans sa branche bloquante, l'appelle avant et après l'attente : avant
  pousse l'image que le jeu vient d'écrire, après tire les touches écrites par la page pendant l'attente (l'anneau
  d'entrée du greffon est dans le même segment). Écartés : rendre le noyau JSPI (cause non localisée, et touche à
  l'exécution de toutes les cellules) ; réconcilier depuis le greffon ou `pyxel_web` (le premier est interdit, le
  second ne couvrirait pas un autre utilisateur de `SharedMemory` qui attend par `time.sleep`).
- **Essai 28 — VÉRIFIÉ** (sonde Firefox, 12:43) : le panneau reçoit **148 images sur 150, en direct** (17,18 s → 22,11 s,
  soit 30 i/s) ; Espace, envoyée par la page en `QKeyEvent` réel à l'écran du panneau vers l'image 40, est **vue par le
  jeu à l'image 42**, et l'effet (carré qui change de couleur, pixel 8 → 7) revient au panneau aux images 43-82.

## Point ouvert immédiat

- Images et clavier : faits (essai 28). Reste **le son** (pas d'AudioContext dans un Worker) et les
  `SystemError: Cannot enter a promising task…` à examiner.
- **Piste pour le son (relevée à 12:44, rien d'écrit)** : la console de l'essai 28 ne montre aucune erreur audio. Le
  pilote audio emscripten de SDL2 teste `AudioContext`, qui n'existe pas dans un Worker. Piste : une doublure qtpy6, un
  `AudioContext` minimal dans le Worker dont le `ScriptProcessorNode` est pompé depuis `memoire_partagee.reconcilier()`
  (le sleep bloquant, comme pour les images), avec des échantillons poussés dans un anneau `SharedArrayBuffer` et joués
  dans la page par un AudioWorklet. Vérification : la page compte les échantillons non nuls reçus.
