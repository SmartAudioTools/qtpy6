# Doublure `zmq` : plan (11/10/2026, jalon 8a atteint le soir même)

Demande de l'utilisateur : « je voulais le code source de SmartPythonEditor agnostique et permetre à qtpy6 de l'executer
aussi bien en natif que sur le web » ; puis « oui, passe sur Fable pour zmq ». Plan conçu par un agent Fable (lecture
seule, 58 relevés dans jupyter_client 8.9.1, ipykernel 6.31.0, qtconsole 5.7.2, spyder_kernels, Spyder). Niveau de
preuve : **lu dans les sources, rien mesuré**. Suite de `2026-10-09 - Portage de SmartPythonEditor…`, jalon 7.

## Recommandation

Le vrai noyau (`spyder_kernels.console`, ipykernel entier) dans un **Web Worker** derrière `ProcessusWeb`, lancé par une
doublure de **`subprocess.Popen`** ; côté page ET côté Worker, le **même module doublure `zmq`** (API pyzmq, transport
`postMessage` par numéro de port) ; en dessous, une doublure coopérative de **`threading.Thread`** (obligatoire : c'est
le point ouvert du jalon 7). jupyter_client, qtconsole, spyder_kernels, Spyder : zéro ligne touchée.

## Q1. Où tourne le noyau : Worker ; InProcessKernel écarté

- Spyder suppose un processus à tuer et relancer (`utils/manager.py:90-123`), un battement de cœur (`kernel_handler.py`
  `hb_channel`, `time_to_dead=25`), l'interruption par message comm sur control (`widgets/shell.py:557`), un noyau par
  console, stdout/stderr lus par deux `StdThread(QThread)` (`kernel_handler.py:92-117,323-333`).
- Worker : isolement (une boucle infinie ne gèle pas l'interface, jalon 3), `kill()` = `worker.terminate()`, relance =
  nouveau Worker (0,25-0,5 s à froid, 20 ms préchauffé). Coût : un second Pyodide (~100 Mio supposé) et les roues
  ipykernel/IPython/tornado/spyder_kernels/jupyter_client à charger dans le Worker.
- **Écarté, InProcessKernel** : pas d'isolement (boucle infinie = page morte), un seul noyau, `restart`/`kill` vides
  (`inprocess/manager.py:44-82`), et il ne passe pas par `SpyderKernelManager`/`QtKernelClient` : il faudrait substituer
  des classes de Spyder, contraire à la règle.
- **Interruption** : sans `SharedArrayBuffer` (`setInterruptBuffer`), le Worker occupé ne lit pas le message. Donc
  interrompre = tuer + relancer (perte de l'espace de noms), ce que Spyder sait faire quand le cœur s'arrête. Supposé,
  à vérifier au jalon 8b ; limite à documenter.

## Q2. Niveau : le module `zmq` (API pyzmq)

- **Écarté, plus haut** (doubler QtKernelClient/QtKernelManager) : pas des API natives, Spyder les sous-classe et les
  étend ; on perdrait restarter, heartbeat, comms. **Écartée, la console web maison** : perd l'explorateur de variables.
- Surface pyzmq exercée (relevé) : types REQ/DEALER/SUB/ROUTER/PUB/STREAM/PULL/PUSH ; `socket`, `linger`, `identity`,
  `connect`/`bind`, `bind_to_random_port`, `getsockopt(LAST_ENDPOINT)`, `setsockopt(SUBSCRIBE)`, `send_multipart`/
  `recv_multipart(NOBLOCK, copy=)`, `ZMQError(EAGAIN)`, `MessageTracker`, `Poller`, `poll`, `select`, `device(QUEUE)`,
  `ZMQStream(socket, ioloop).on_recv(cb, copy=False)`/`flush`/`close`, `zmq.Message` (`.bytes`, `.buffer`),
  `zmq.asyncio` (classes vides suffisent), `zmq.has`, `curve_keypair`, `zmq.error.ContextTerminated`,
  `zmq.utils.garbage.gc`. qtconsole et Spyder : aucun zmq direct.
- Conception : `bind` inscrit le port dans un registre de l'interpréteur ; `connect` livre localement si le port est lié
  ici (boucle locale de spyder_kernels, pipes IOPub), sinon par `postMessage` vers le Worker qui le détient. Files par
  socket ; `recv` bloquant et `poll` → `_attendre` (JSPI). `ZMQStream.on_recv` appelle le rappel via `_plus_tard`, sans
  `io_loop.add_handler` (WebLoop lève sur `add_reader`). Heartbeat : la page peut répondre elle-même tant que le Worker
  vit (fidèle : le vrai bat dans un fil séparé).

## Q3. Lancement : doublure `subprocess.Popen` → `ProcessusWeb`

- Chemin : `kernel_handler.py:413` → `manager.py` (`run_sync`) → `local_provisioner.py:249` → `launcher.py:158`
  `Popen(cmd, **kwargs)`. QProcess n'est pas sur ce chemin.
- `Popen` : pid factice, `stdout/stderr` dont `read1()` suspend jusqu'au prochain `readyRead…` et rend `b""` à `finished`,
  `poll/wait/returncode/send_signal/terminate/kill`. `ProcessusWeb` doit tolérer `-Xfrozen_modules=off`. Fichier de
  connexion : `JUPYTER_RUNTIME_DIR` = dossier temporaire de la page (déjà zippé vers le Worker) ; Popen lit ses 5 ports et
  les inscrit dans le registre. La doublure psutil de `essais/spyder/preparer.py` doit lever `NoSuchProcess`.
- Préambule du Worker (`js/travailleur.js`) : poser les doublures zmq et threading, et rester vivant tant que des
  sockets sont liés (`IOLoop.start()` est un no-op sur WebLoop).

## Q4. Les fils : `threading.Thread` coopératif, obligatoire

- Côté page, `run_sync` de jupyter_core part dans `_TaskRunner` → `threading.Thread` (la WebLoop tourne dès
  `__init__`) ; `IOLoopThread`, `HBChannel`, `Lock`. Côté Worker : `Heartbeat`, `IOPubThread`, `ControlThread`,
  `SpyderParentPoller`.
- `fils.doubler_threading()` : `start()` → `run()` à la tâche suivante, `join`/`Event.wait`/`Condition.wait` →
  `_attendre`. Un `run()` qui boucle sans attente gèle la page (`zmq.device` est traité par la doublure zmq ; le serveur
  d'instance unique reste hors champ, `--new-instance`).
- Incertain : second WebLoop par `asyncio.new_event_loop()`, `run_until_complete` non suspendant sans
  `enableRunUntilComplete`. À mesurer au 8b.

## Fichiers

À créer : `qtpy6/web/zmq_web.py` (module zmq complet + registre, posé par un finder quand pyzmq manque). À modifier :
`travailleur.py`, `js/travailleur.js`, `sous_processus.py`, `fils.py`, `__init__.py` (`application`) ; essais :
`essais/spyder/preparer.py` (retirer le faux zmq, corriger psutil), `essais/spyder/jalon8*.py`.

## Jalons (même script bureau/page, verdict imprimé, page sondée)

1. **8a, preuve de voie** : `SpyderKernelManager.start_kernel`, `client.execute("1+1")` → `execute_result` `'2'`,
   `kernel_info_reply`, un `stream` stdout ; temps au premier message, tas page et Worker ; `shutdown_kernel`.
2. **8b, ce que Spyder suppose** : heartbeat pendant `while True: pass`, interruption (tuer + relancer), `input()`,
   deux noyaux, `KernelComm.open_comm`.
3. **8c, la console** : la sonde tape `1+1`, `Out[1]: 2`, `a = 3` visible dans l'explorateur, redémarrage du noyau.

## Risques

Mémoire et chargement du Worker (IPython + ipykernel + tornado + spyder_kernels, psutil à doubler aussi) ; `copy=False`
(`Message.bytes`) ; `TTYOutStream` de spyder_kernels non lu ; WebLoop à deux instances ; interruption = redémarrage.

## Compléments du Superviseur (11/10/2026, 19 h 10), avant tout code

- **Un zmq direct dans Spyder** : `plugins/completion/providers/languageserver/client.py` (fournisseur LSP) crée un
  `zmq.Context`, des sockets `PAIR` (`bind_to_random_port`) et lit `zmq.FD` dans un `QSocketNotifier` (vérifié par
  lecture dans le fork, l. 25-235). À trancher avant le jalon 8a : soit le fournisseur LSP reste hors champ dans la page
  (le noter, et vérifier que le jalon 7 tourne sans lui), soit la doublure expose un FD factice et un notifieur.
- **Ordre** : le correctif de `fils.py` (`import js` inconditionnel, défaut de 1475f75) passe d'abord, dans un commit à
  part, puisque le plan touche `fils.py`. Ensuite, la première étape commitable est le jalon 8a seul (preuve de voie),
  pas les trois jalons d'un coup.
- La décision de lancer revient à l'utilisateur (quota semaine 65 % pour 42 % de semaine écoulée).
- **Tranché par l'utilisateur, 19 h 14** : « je souhaite le couvrir ». Le fournisseur LSP est donc dans le champ :
  `zmq.FD` factice et doublure de `QSocketNotifier` déclenchée à l'arrivée d'un message, serveur pylsp dans un Worker
  comme le noyau. Écarté : le désactiver dans la page (fonction perdue). Il vient après la console (jalon 8d, à définir).

## Jalon 8a, réalisation (11/10/2026, soir ; en cours)

Demandes : « oui, vas-y, essaye d'aller le plus loin possible, tu peux utilise jusque 80% » ; « essaye de déléguer au
maximum à des models moins gourmands en token » (pièces écrites par des sous-agents Sonnet sur brief, relues ici).

- **`qtpy6/web/zmq_web.py`** (+ `tests/test_zmq_web.py`, 31 verts, 1 sauté) : l'API pyzmq relevée, transport par messages
  `{"op": …}`. Défauts trouvés à la relecture et corrigés test d'abord (rouges vus) : `Poller` de `zmq.asyncio`,
  `Socket.underlying`/`shadow`, `_socket_class`, `zmq.log.handlers` (importé par ipykernel). Limite connue : un `shadow`
  d'une autre classe partage le `__dict__`, une attente asyncio sur l'ombre n'est pas réveillée (non exercé par
  ipykernel 6.31).
- **`qtpy6/web/threading_web.py`** : `threading` coopératif (Thread, Timer, verrous, Event, Condition, sémaphores,
  Barrier, local) sur deux crochets `attendre`/`plus_tard` ; `installer()` remplace les noms dans le vrai module.
- **`qtpy6/web/psutil_web.py`** (+ `tests/test_psutil_web.py`, 12 verts, rouges vus) : registre de pids vivants (le pid
  courant, ceux qu'un Popen doublé inscrit, `JPY_PARENT_PID`), car `SpyderParentPoller` arrête le noyau si
  `pid_exists(parent)` est faux. Surface tirée d'un relevé (ipykernel, spyder_kernels, jupyter_client, fork). Écartée :
  l'ancienne doublure de `essais/spyder/preparer.py` (`pid_exists` toujours faux : le noyau se serait arrêté seul).
- **Paquets du noyau** (relevé de `sys.modules` au démarrage de `spyder_kernels.console` sur le bureau) : manquaient au
  site `ipykernel`, `comm`, `cloudpickle`, `matplotlib_inline` ; pyzmq et psutil sont doublés ; debugpy, orjson,
  nest_asyncio optionnels (try/except), laissés dehors.
- **`essais/spyder/jalon8a.py`** : chemin de Spyder lui-même (`KernelHandler.new_from_spec(SpyderKernelSpec())`), puis le
  client bloquant du gestionnaire. **Bureau, mesuré : 6/6** — lancement 0,05 s, premier message 2 s après
  `start_channels`, `kernel_info_reply` ok, stream `'bonjour\n'`, `execute_result` `'2'`, arrêt code 0 en 0,4 s.
  Écarté : un `BlockingKernelClient` autonome sur le fichier de connexion — il juge la vie du noyau au battement de cœur,
  dont le premier relevé précède le premier battement (« Kernel died before replying », mesuré) ; celui du gestionnaire
  la juge sur `poll()`. `JUPYTER_RUNTIME_DIR` jetable, comme `SPYDER_CONFDIR`.
- `preparer.py` : fausses doublures zmq et psutil retirées (elles auraient masqué celles de qtpy6, posées plus tard).

## État au 11/10/2026, 21 h 50 (pause demandée par l'utilisateur, rien commité)

Trois défauts trouvés et corrigés ce soir, chacun avec un test vu rouge puis vert. Suite complète : 218 passent, 3 sont ignorés. Le test des octets a été ajouté après ce dernier passage complet, et n'a tourné que dans `test_zmq_web` (vert).
- **`ThreadPoolExecutor` absent de Pyodide** : `import IPython` échouait dans le Worker (`terminal/debugger.py`).
  - Le code de `fils.doubler_futures` est déplacé dans `threading_web.doubler_futures(attendre, plus_tard)`, en pur Python.
  - `fils` l'appelle avec ses propres crochets, et le Worker l'installe aussi, dans `preambule.installer`.
  - Test : `test_futures_sur_fils_cooperatifs`.
- **Gel de la page** : `wait_for_ready` tourne comme coroutine (`run_sync` de jupyter_core).
  - Son `poll` zmq ne pouvait pas suspendre, parce que `bloquant` refuse dès qu'une autre pile est suspendue. La boucle tournait donc à vide pendant DELAI secondes, et la page ne recevait plus rien du Worker.
  - Correctif : `bloquant._en_tache()`. Le pas d'une tâche asyncio est une entrée promettante, puisque Pyodide sort de la tâche suspendue et y rentre à la reprise (`stack_switching/pystate.c`).
  - Test : `test_tache_asyncio_peut_suspendre_pendant_une_autre_attente` (test_web).
- **`connect(b"tcp://…")`** (valeur de `getsockopt(LAST_ENDPOINT)`, utilisée par ipykernel dans `init_control`) : `_analyser` accepte maintenant les octets. Test : `test_adresses_en_octets`.

Où en est jalon8a, d'après les mesures dans Firefox :
- le noyau démarre et lie ses 6 ports ;
- il reçoit les `kernel_info_request` (une par seconde) et y répond par `kernel_info_reply` (journal `--debug`) ;
- mais `wait_for_ready` expire quand même.

Étape suivante : savoir si la réponse shell et le message iopub, qu'exige `wait_for_ready`, arrivent à la page. Une trace `recu op port pair` a été posée sur `zmq_web.recevoir` dans jalon8a.py mais n'a pas encore tourné. Suspect n° 1 : le PUB du Worker ne connaît pas les abonnements du SUB de la page.

Instrumentation PROVISOIRE dans `essais/spyder/jalon8a.py`, à retirer avant le commit :
- `DELAI = 25` (à remettre à 120) ;
- `--debug` sur argv ;
- traces des boucles, de `recevoir` et du registre zmq.

Sondes d'essai : `sonde_noyau.py` et `noyau_pas.py`.

## Jalon 8a atteint (11/10/2026, 22 h 10) : 6/6 dans Firefox

Reprise après la pause (« reprends »). Deux défauts de plus, chacun avec un test vu rouge puis vert ; suite complète : 221
passent, 3 ignorés. Instrumentation provisoire retirée de `jalon8a.py` (DELAI remis à 120), sonde rejouée sur le code propre.
- **Réponses du noyau livrées à la mauvaise socket** : `_connectees` était indexé par l'identité seule. Or jupyter_client donne
  la MÊME identité (la `bsession` de la session) aux sockets shell, stdin et control d'un client : la dernière connectée
  recevait tout, `get_msg` du shell restait vide. Trouvé par une trace sur `ZMQSocketChannel.get_msg` (identité toujours
  `Empty`) et une sur `poster` (réponses adressées à l'autre). Correctif : clé `(port, identité)`, et le port voyage dans
  `vers_pair`. Test : `test_meme_identite_sur_deux_ports_distants`. Alternative écartée : une identité propre à chaque socket
  côté page — elle change ce que voit le ROUTER du noyau (l'identité est l'adresse de retour du protocole Jupyter).
- **`RuntimeError: cannot join current thread`** dans `stop_channels` (`hb_channel.join`) : `threading_web._pile` gardait
  les fils suspendus, si bien que le script principal, repris pendant que le fil hb attendait, se croyait ce fil. Correctif :
  `_courant` (un seul fil courant), mis de côté dans `attendre` et rétabli à la reprise. Test :
  `test_fil_suspendu_n_est_plus_le_fil_courant`. C'est la règle de JSPI : une pile suspendue n'est plus la pile qui tourne.

Mesure (Firefox 155, sonde, `capture_jalon8a.console.log`) : lancement 0,47 s ; premier message 2,87 s après
`start_channels` ; `kernel_info_reply` ipython 3.13.2 ; `print` → stream stdout `'bonjour\n'` ; `1+1` → `execute_result`
`['2']` en 0,10 s ; arrêt en 0,14 s ; tas wasm de la page 60 → 158 Mio ; 6,3 s au total. Niveau de preuve : mesuré dans
Firefox seul ; Chrome non essayé (relais `sudo -u smartaudiotools` requis).

Points ouverts :
- **Arrêt en code -2, pas 0.** `_async_shutdown_kernel` de jupyter_client appelle TOUJOURS `interrupt_kernel` avant le
  `shutdown_request` (manager.py, « if self.has_kernel ») ; en `interrupt_mode` « signal », c'est un SIGINT, et
  `Popen.send_signal` de la doublure traite tout signal comme une mort du Worker. Un vrai ipykernel attrape SIGINT
  (KeyboardInterrupt) et sort ensuite en 0 sur le `shutdown_request`. Le livrer pour de bon demande un tampon
  d'interruption Pyodide (`setInterruptBuffer`, SharedArrayBuffer, donc isolation cross-origin) : c'est aussi ce qu'il
  faudra au bouton « Interrompre le noyau » de Spyder, à traiter avec lui, pas ici. L'arrêt fonctionne (0,14 s).
- `ProcessusWeb._erreur` → kill → `finished(0)` : un Worker en erreur rend 0 (vu en lecture, pas de cas réel).
- `_garde_vie` (preambule) ne garde qu'un futur si plusieurs `run_forever` s'imbriquent (vu en lecture, pas de cas réel).
- Sondes d'essai `sonde_noyau.py`, `noyau_pas.py`, `sonde_boucle.py` : non commitées (diagnostic ponctuel).

À regarder en premier par un relecteur : `zmq_web.recevoir`/`_attacher`/`_detacher` (la clé), `threading_web.attendre`.

## Jalon 8b en cours (11/10/2026, 23 h) : état à la mise en pause

- `essais/spyder/jalon8b.py` : 7/7 sur le bureau. Témoin « comm prêt » = `_comm_ready_received` (l'état SpyderKernelReady
  attend le kernel_info que demande la console, absente ici) ; appel distant = `get_syspath` (un `@comm_handler`, `get_cwd`
  n'en est pas un). Verdicts imprimés dès qu'ils sont posés (la page peut geler).
- Battement : `zmq_web` op `echo` — le Worker annonce son `device(QUEUE, s, s)`, la page répond à sa place tant qu'il vit ;
  `oublier(worker)` à sa mort (`travailleur._mourir`). Tests rouges puis verts (test_zmq_web, 38 passent). Pas encore
  mesuré dans la page.
- Page (Firefox, `diag8b.py`, sonde jetable non commitée) : l'appel distant BLOQUANT expire (le non bloquant n'a pas été
  relevé), et le noyau renvoie `_comm_ready` toutes les secondes : le Worker ne voit donc pas les messages comm du
  client, ou ne voit pas la réponse au `_comm_ready`. Piste suivante : tracer côté Worker les `comm_msg` reçus sur shell.
- Interruption : `interrupt_kernel` tue le Worker (pas de SharedArrayBuffer sans isolation cross-origin) : décision à
  l'utilisateur, ne rien coder. Dans jalon8b la page a gelé à cette étape (jusqu'au délai de 500 s) : à localiser.
- Rien de commité pour 8b.

## Jalon 8b atteint (12/10/2026, 0 h 15) : 7/7 dans Firefox, trois passes de suite

Demande citée : « passe au jalon 8b et à tous les suivant , tu peux monter à 80% ! », reprise sur « reprends ».
Trois défauts de doublure trouvés et corrigés dans qtpy6, aucun dans le code de Spyder ni des noyaux (règle : rien dans
le fork, ni dans jupyter_client, ipykernel, spyder_kernels).

1. **Les messages comm étaient tous perdus dans le Worker** (`zmq_web.ZMQStream._livrer`). La cause : Spyder envoie ses
   messages comm sur le canal **control**, et ipykernel y abonne une coroutine, `dispatch_control`. pyzmq planifie un
   rappel awaitable par `asyncio.ensure_future`, mais la doublure l'appelait sans plus, d'où « coroutine
   'Kernel.dispatch_control' was never awaited ». La doublure fait maintenant comme pyzmq. Les deux symptômes de la note
   précédente (l'appel bloquant qui expire, `_comm_ready` renvoyé chaque seconde) avaient cette seule cause.
   - Test `test_zmqstream_rappel_coroutine_planifie` : rouge avant la correction, vert après.
2. **L'interruption tuait le noyau.** Avec `pgid` à None (mesuré dans la page), jupyter_client appelle
   `Popen.send_signal(SIGINT)`, que la doublure traduisait en `kill` du Worker. Hypothèse écartée par la mesure :
   « `os.killpg` muet sous emscripten » ; ce chemin n'est jamais emprunté.
   - Désormais SIGKILL et SIGTERM terminent le Worker. Les autres signaux partent en `{signal: n}`
     (`ProcessusWeb.signaler`). Dans le Worker, le préambule double `time.sleep` : il suspend (JSPI) au lieu de bloquer,
     et livre au réveil les signaux reçus au gestionnaire Python. Celui de SIGINT, posé par ipykernel, lève
     `KeyboardInterrupt`.
   - Limite documentée (décision de l'utilisateur : ne pas coder l'isolation) : un calcul qui ne dort jamais n'est pas
     interruptible. Il faudrait un SharedArrayBuffer, donc une page COOP/COEP.
   - Effet de bord voulu : pendant un `time.sleep` du noyau, les messages de la page passent (zmq, battement).
   - Tests : `test_popen_sigint_signale_sans_tuer` et `test_preambule_sleep_livre_les_signaux`.
3. **Le redémarrage ne répondait plus** (« Kernel didn't respond in 120 seconds »). Le nouveau noyau relie les mêmes
   ports dans un nouveau Worker, mais les sockets du client restaient branchées sur l'ancien. libzmq se reconnecte seul,
   et `declarer_distant` fait de même : une socket connectée à un port relié ailleurs s'y rattache, avec un `connect`
   renvoyé au nouveau Worker, abonnements compris.
   - Test `test_port_relie_ailleurs_reconnecte`.

Les **gels aléatoires** de la page (boucle JS vivante, CPU nul, une tâche Python suspendue jamais réveillée) ne se sont
pas reproduits en trois passes après ces corrections. Lien de cause supposé, non démontré : ils survenaient tous après
l'interruption ou pendant un lancement, quand le client parlait à un Worker mort. À surveiller aux jalons 8c et 8d.

**Vérifié.** Bureau : 7/7. Firefox, par la sonde : 7/7 sur trois passes (58 s, 31 s, 31 s), interruption en 1,2 à 1,5 s,
redémarrage avec un pid différent. Suite qtpy6 : 226 passent, 3 ignorés, 1 échec, `test_service_worker[chromium]`. Il
échoue aussi lancé seul : le cache v=1 de `sw.js` survit sous Chromium. C'est un fichier que ce travail ne touche pas, et
le défaut reste ouvert hors de ce jalon. Chrome n'a pas été essayé pour 8b.

## Jalon 7 rejoué avec le noyau dans la page (12/10/2026, 0 h 15 → 1 h) : 33/0, plus de récursion

Après le jalon 8b, `jalon7.py` (la vraie MainWindow) a été relancé dans Firefox. La console IPython y démarre désormais
son noyau. Ce relancement a révélé quatre manques, tous corrigés dans qtpy6. Ni l'application ni le fork n'ont été
touchés (demande de l'utilisateur : « je voulais le code source de SmartPythonEditor agnostique »).

1. **Le client LSP de Spyder** lance son serveur par `QProcess`. Il lui manquait :
   - `processEnvironment`, `setStandardOutputFile`/`ErrorFile`, `errorOccurred`, `close` et `waitForFinished` sur
     `ProcessusWeb` ;
   - `set_hwm` sur le `Socket` zmq ;
   - `Popen[bytes]` (une annotation d'IPython).

   Le serveur pylsp ne tourne pas encore dans un Worker : c'est le jalon 8d. `waitForFinished` rend faux tout de suite
   tant qu'un Worker tourne, sans attendre. Écarté : une attente suspendue par JSPI, alors que le seul appelant mesuré
   (l'arrêt du client) appelle `close()` juste avant.
2. **La cascade de `RecursionError` de la page.** Sa racine était un alias snake_case de qtpy6 : `move_cursor`, posé
   sur `QPlainTextEdit`, masquait le `BaseEditMixin.move_cursor` de Spyder, parce que le mixin est placé après la base Qt
   dans la MRO. La boîte d'erreur de Spyder levait donc, et la console interne réécrivait l'erreur, qui relevait, sans
   fin.
   - Correctif : l'alias de méthode est un descripteur `_Alias` (`qtpy6/_binding.py`). Il cède la place à un nom défini
     par une classe Python de la MRO, puis à un `__getattr__` Python, et ne rend la méthode Qt qu'à défaut.
   - Le même correctif règle le `FrameWebView.set_font` délégué. Le contournement (b) de `jalon7.py` est donc retiré.
   - Écarté : garder un attribut simple. Il masque les deux cas, et aucune liste d'exceptions ne peut prévoir les
     mixins d'une application.
   - Un cache par classe ramène l'accès à 0,45 µs, contre 1,9 µs sans cache et 0,15 µs pour le nom camelCase (mesuré,
     `timeit`, bureau). Limite : un nom ajouté à une classe Python de base APRÈS le premier accès par une sous-classe
     n'est pas vu.
   - Défaut du premier jet, trouvé par `test_web` : une doublure (classe Python, `ProcessusWeb`) porte elle aussi des
     `_Alias`, et l'alias s'y trouvait lui-même, d'où une récursion. Les `_Alias` sont désormais sautés dans la
     recherche.
3. **« Signal source has been deleted »** dans `bloquant.tache`. `QThread.started` est émis à la tâche suivante. Spyder
   détruit le fil sur `finished`, et un fil rapide finit avant cette tâche. `started` n'est plus émis si le fil a été
   détruit (`fils.py`, `_demarre`). Test `test_fil_detruit_avant_started`, qui échoue sans le correctif (vérifié dans une
   copie à part).
4. **Essai `essais/spyder/erreur7.py`.** Il rejoue jalon7 avec un `1/0` dans un slot une seconde après l'affichage, et
   trace chaque appel de `ConsoleWidget.handle_exception`. Au bureau comme dans Firefox, `ZeroDivisionError` arrive à la
   console interne et y est « traitée sans exception ».

**Toujours ouvert.** Le renommage des trois slots homonymes d'un signal, dans le fork (commit 591fdf005 du 09/10), a été
perdu à la reconstruction du fork du 11/10 : le générateur ne le reprend pas. Le contournement (a) de `jalon7.py` reste
donc nécessaire. C'est à corriger dans le générateur, par l'utilisateur ou la session du fork, pas ici.

**Vérifié.**
- Bureau PySide6 : jalon7 et erreur7, 33 passe, 0 casse, MainWindow visible à 8 s, code 0.
- Firefox 155, par la sonde : jalon7, 33/0, MainWindow visible, fin propre ; erreur7, la `ZeroDivisionError` est traitée.
- Suite qtpy6 : 193 passent, 3 ignorés ; `test_qtpy6` 39/39 sous pyside6 et sous pyqt6.
- Pas essayé : Chrome.

## Jalon 8c, la console dans la page (12/10/2026, nuit) : une cause trouvée, un gel encore ouvert

Demande : « passe au jalon 8b et à tous les suivant , tu peux monter à 80% ! ». L'essai `essais/spyder/jalon8c.py`
prolonge jalon7 (crochet `SUITE` ajouté à `jalon7.py`) en cinq étapes : In [1], `1+1`, `a` dans l'explorateur, redémarrage,
`a` oublié. Bureau : 5/5.

**Corrigé : `QCoreApplication.postEvent` d'un événement de l'application.** Dans Firefox, le démarrage du noyau échouait
sur un `TimeoutError` de `threading_web.Future.result`. Cause : Spyder rappelle ses futures par
`DispatcherFuture.connect` → `postEvent(_QCallbackExecutor, _QCallbackEvent)` → `customEvent`, qui attend un `result()`.
Qt appelait ce `customEvent` hors entrée suspendable, où `attendre` ne peut que vérifier une fois. Doublure
(`bloquant.doubler_qtcore`) : un événement de type ≥ `User` est remis à une tâche suivante (`_plus_tard`) et livré par
Python, `event()` s'il est redéfini en Python, sinon `customEvent()` ; les événements de Qt gardent sa file.
- Écarté : livrer par `QCoreApplication.sendEvent` dans la tâche. Plus fidèle (filtres d'événements), mais la suspension
  traverserait les trames C++ de Qt ; non retenu sans mesure qui le justifie. Limite assumée : les filtres d'événements
  ne voient pas ces événements-là.
- Test `test_evenement_poste_est_un_slot` (une boîte modale ouverte dans un `customEvent`) : échoue sans la doublure,
  passe avec. Suite qtpy6 : 233 passent, 3 ignorés.

**Toujours ouvert : la page gèle une fois la console connectée** (Firefox, « Script terminated by timeout »). Bissection,
instrumentation provisoire retirée de l'essai depuis :
- Le gel survient APRÈS `_connect_new_client_to_kernel` (fini normalement), avec un seul noyau (`get_cached_kernel`
  forcé à `cache=False`) et sans la page de chargement HTML : ni le noyau de réserve ni le `QWebEngineView` n'en sont la
  cause.
- Un seul battement d'un `QTimer` de 100 ms passe ensuite ; la dernière tâche `_plus_tard` tracée (le throttler superqt)
  se termine normalement.
- Un filtre d'événements global a vu 349 événements, les derniers : `Paint` de l'éditeur, `LayoutRequest` de
  IPythonConsoleWidget, PlotsWidget et VariableExplorerWidget, puis `Paint` et `Expose` de la fenêtre principale — puis
  plus rien, et aucun `Paint` de `ShellWidget`/`ControlWidget` après leurs `UpdateLater`. Hypothèse : une boucle
  synchrone dans la mise en page ou le dessin de la console (qtconsole), ou un fil de tubes (StdThread) qui ne rend
  jamais la main. Non tranché.
- Inutilisables pour situer la boucle : `sys.setprofile`/`_setprofileallthreads` (aucun échantillon) et les piles wasm
  (`pyodide.asm.wasm` sans section `name`).
- Prochain essai : neutraliser StdThread, puis tracer les `paintEvent`/`resizeEvent` de `ControlWidget`.

### Suite de la bissection du gel 8c (12/10/2026, nuit, arrêtée à 80 % du quota)

Instrumentation provisoire dans `essais/spyder/gel8c.py` (commitée le 12/10 pour être rejouée) ; sondes dans le scratchpad de la session.

- **Écarté** (en plus de la liste ci-dessus, mesuré dans la page) : les suspensions JSPI de Qt (refus forcé : le gel
  reste), un déluge de microtâches (≤ 8 `tourner` consécutifs), stdin et les alertes, `Calque._synchroniser` (appels
  réguliers, jamais > 50 ms), `HBChannel` (gel identique avec `_async_run` neutralisé : sa reprise avant le gel n'était
  qu'une coïncidence), les pauses de fils qui ne suspendent pas (aucune « PAUSE courte » ; une seule attente,
  `Event.wait(25000)`, par le crochet de fils), une insertion de texte géante dans la console (AUCUNE insertion avant le gel).
- **Le résultat qui compte** : le gel est UNE macrotâche d'environ 10 s. Pendant ce temps, aucun événement Qt ne passe le
  filtre global de l'application, aucun Python instrumenté ne tourne, les `setInterval` JS sont affamés. Un
  échantillon antérieur montrait `prom=true gil=0` : la pompe promettante exécute du C++ sans Python. Dernière activité
  Python avant le gel, d'un run à l'autre : les `eventFilter` de `FigureViewer` (×3) puis `ThumbnailScrollBar` sur un
  `Resize` (plugin Plots), ou des tâches throttler/`show_time`.
- **Piles nommées** (variables d'un run à l'autre) : dessin des enfants de MainWindow (fillRect, bézier) ;
  `Shiboken::getConverter` (copie de map à la recherche paresseuse) ; QTimer → slot Python → `JsProxy` getattr ;
  `run_sync`. Chaîne de cadres réentrante dans plusieurs piles.
- **Hypothèse de tête** : une longue boucle C++ dans `processEvents` (pompe) qui ne livre aucun événement par `notify`,
  probablement mise en page/dessin après le redimensionnement des docks Plots/console.
- **Outils** : traces T/R/O/EV, PILESUSP, setters SUSP/REFUS, MICRO, crochets DIALOGUE/STDIN ; anneau JS
  (`globalThis.anneau`, 600 entrées, compteur `NOTER`) — mais le `dismiss` de l'alerte de script lent par Selenium
  RECHARGE la page : l'anneau lu après vient d'un run neuf, inutilisable ; `wasmnoms.py` (scratchpad) nomme les cadres
  wasm par l'export le plus proche, candidat à un outil qtpy6.
- **Limites** : `sys.monitoring`/`settrace` inutilisables ; la limite de 10 s de Firefox ne se lève ni par
  `dom.max_script_run_time` (0 ou 600), ni par `dom.ipc.reportProcessHangs`, ni par `set_script_timeout(600)`.
- **Pistes suivantes** : compter en JS les `LayoutRequest`/`updateGeometry` (côté wasm) ; bissecter en désactivant les
  plugins Plots puis Variable Explorer dans jalon8c ; comparer la même séquence sur le bureau.
- Rappel : le renommage des slots homonymes (fork, 591fdf005) est perdu depuis la reconstruction du 11/10 ;
  contournement d'essai dans `jalon7.py`, correction attendue du générateur du fork (session du fork ou utilisateur).

### Tâche courante laissée par une pile suspendue (12/10/2026, nuit) — corrigé dans `qtpy6/web/bloquant.py`

- **Défaut mesuré** : au lancement du noyau de Spyder, « Cannot enter into task … while another task … is being
  executed » ; la tâche du client Jupyter en mourait. Cause : une tâche dont la pile est suspendue par JSPI (`run_sync`,
  ou une boucle imbriquée de Qt, `qtSuspendJs` via `saveState`/`restoreState`) reste la tâche COURANTE pour asyncio ;
  ni Pyodide ni Qt n'en sortent. Les rappels lancés entre-temps la trouvaient courante.
- **Correctif** : `_hors_tache`, posé sur les deux entrées de la page (`Handle._run`, rappels de la WebLoop ; `tour`,
  la pompe Qt) : la tâche courante est mise de côté (`asyncio.tasks._swap_current_task`) le temps de l'entrée, puis
  remise. Écarté : sortir de la tâche dans `_pyodide_suspendre` seul — mesuré insuffisant, une autre voie de
  suspension (Qt) laissait la même tâche courante.
- **Vérifié** : sonde Firefox, plus aucune erreur « Cannot enter », tâche courante None à chaque rappel ;
  `tests/test_web.py` 56 passés (natif : n'exerce pas ce code Pyodide). Jalon 7 avec le correctif : atteint
  « fenêtre : MainWindow, visible » puis le gel de 10 s ; même jalon sur un site au `bloquant.py` d'avant
  (`essais/spyder/site_ref`) : gel AVANT « fenêtre » — le gel n'est donc pas causé par le correctif.
- **Pièges d'instrumentation** : sous JSPI, `f_trace` et `sys.monitoring.set_events` corrompent le tas (« Pyodide fatal
  error index out of bounds ») ; `sys.setprofile` ne voit rien ; un relevé de tous les widgets toutes les 20 ms
  (`post_visible_setup` instrumenté) suffit à figer la page. Les lignes de la console Firefox sont préfixées
  `console.log: "` : pas de `^` dans les motifs.
- **Ouvert** : le gel restant après le second démarrage du noyau (deux lancements : à comprendre), qui empêche encore
  « 8c passe : noyau prêt (In [1]) ».

## Le gel au démarrage : les widgets web de Spyder (12/10/2026, nuit)

Demande de l'utilisateur, 12/10 : « Je n'utilise pas le panneau Plot. Peux-tu pour l'instant réussir à faire tourner
SmartPython Editor ? Avec les panneaux que j'affiche moi par défaut et laisser les panneaux potentiellement
problématiques que je n'utilise pas pour un peu plus tard. »

- **Le second noyau n'est pas un défaut** : `CachedKernelMixin.get_cached_kernel` (fork, `widgets/mixins.py`) démarre
  un noyau de réserve pour la console suivante. Forcer `cache=False` (essai `panneaux.py`) n'en laisse qu'un, le gel reste.
- **Le gel n'est pas côté Worker ni zmq** : il persiste avec le Worker du noyau terminé (`ProcessusWeb.start` enveloppé).
  `show_kernel_error` n'est jamais appelée.
- **Cause : la page de chargement de la console** (`ClientWidget._create_loading_page`, `FrameWebView`, donc la doublure
  `QWebEngineView` de qtpy6). Avec l'option de Spyder `--no-web-widgets` (`main_widget.py` l.311 :
  `enable_infowidget = False`), jalon8c passe 5 sur 5 avec les panneaux de l'utilisateur (Plots, Help, OnlineHelp,
  History, Profiler, Pylint, Completions désactivés) : noyau prêt `In [1]` en 3,6 s, `1+1` → `Out[1]: 2`, `a` dans
  l'explorateur de variables, redémarrage en 3,8 s, `a` oubliée. Testé dans Firefox (sonde), essai
  `essais/spyder/panneaux.py`, variable `PANNEAUX_WEB=1` pour rétablir les widgets web.
- **Correctif propre, à décider** : soit rendre la doublure `QWebEngineView` assez légère pour une page de chargement,
  soit faire que qtpy6 annonce l'absence de WebEngine (le `WEBENGINE` de Spyder devient False, comme sur un bureau PyQt6
  sans PyQt6-WebEngine). En attendant, `--no-web-widgets` est un réglage de configuration, pas une branche dans le code.
- **Reste ouvert : la fermeture, non mesurée jusqu'au bout.** La sonde finit sur « état : fini » (posé par `rapport()`
  de jalon7.py AVANT `main.closing`), donc les cinq étapes et le rapport sont acquis. La ligne `fenêtre :` du rapport
  part sur `sys.__stdout__`, absent de la capture console : son absence ne prouve rien. Pendant la fermeture, à 14,32 s,
  le chien de garde de `panneaux.py` (appel Python de plus de 3 s sans que la page respire) imprime :
  `KernelHandler._thread_shutdown_kernel` (kernel_handler.py:602) dans une doublure de fil (`fils._executer`) →
  `jupyter_core.utils.run` → `threading_web` `Future.result` → `fils._attendre` → `_pause`. C'est vraisemblablement
  l'attente normale de `shutdown_kernel` (jupyter_client attend la mort du noyau, jusqu'à `shutdown_wait_time`), mais
  la sonde s'arrête à « fini » : ni la durée réelle, ni un éventuel blocage de `wait_all_shutdown_threads`
  (`thread.wait()` depuis la page) ne sont mesurés. Un `InvalidStateError` de superqt (`_throttler._set_future_result`,
  futur déjà résolu) apparaît à 14,07 s, juste avant : bénin a priori (défaut de superqt ou de la doublure de
  `concurrent.futures` qui résout deux fois ?), non examiné.

### Relevé des essais de la nuit du 12/10 (pour les rejouer et les revérifier)

Tous dans `essais/spyder/panneaux.py`, qui ajoute des blocs avant d'exécuter `jalon8c.py`. Lancement (site construit
par `construire_site.py`, Firefox par la sonde ; capture dans `capture_p.console.log`, verdicts dans `sonde_p.log`) :

    cd /DATA/Python/qtpy6/essais/spyder
    P=/DATA/Python/SmartPython/CachyOS/versions/SmartPython/bin/python
    $P -m qtpy6.web.sonde 'site/index.html?script=panneaux.py' capture_p.png --racine site --delai 800 > sonde_p.log 2>&1

Variables d'environnement lues par l'essai (dans la page elles valent leur défaut : la page ne lit pas l'env, on change
le défaut dans le fichier) :

| Variable | Défaut | Ce qu'elle bascule |
|---|---|---|
| `PANNEAUX_SANS` | plots help onlinehelp historylog profiler pylint completions | panneaux désactivés (`<section>/enable`) |
| `PANNEAUX_STD` | 0 | 1 : les `StdThread` (stdout/stderr du noyau) tournent |
| `PANNEAUX_SPIN` | 0 | 1 : le spinner à 3 ms d'`EmptyMessageWidget` tourne |
| `PANNEAUX_RAYON` | 0 | 1 : peinture arrondie d'`EmptyMessageWidget` gardée |
| `PANNEAUX_FILTRE` | 1 | zip du noyau allégé pour le Worker |
| `PANNEAUX_WEB` | 0 | 1 : widgets web de Spyder gardés (le gel revient) |

Chaque bloc « Bissection » du fichier, dans l'ordre, et ce qu'il a montré :

| Hypothèse testée | Moyen | Résultat |
|---|---|---|
| Lecture de fichier bloquante (lseek dans la pile) | `StdThread.run` neutralisé | gel inchangé |
| Spinner d'`EmptyMessageWidget` à 3 ms | spinner coupé | gel inchangé |
| Widget de taille démesurée | trace des `resize` | gel inchangé (*) |
| `processEvents` imbriqué sans fin | compteur de profondeur | gel inchangé (*) |
| Page qui ne respire plus | battement JS + chien de garde Python (pile après 3 s) | c'est lui qui a donné les piles |
| Attente qui revient tout de suite, en boucle | compteur sur les attentes | gel inchangé (*) |
| Lecture de stdin (window.prompt) | trace | gel inchangé (*) |
| Report qui se reporte sans fin | compteur | gel inchangé (*) |
| Peinture arrondie, widget qui peint sans fin (`H2`/`PAINT`) | traces de peinture | gel inchangé (*) |
| Dialogue modal JS (alert/confirm/prompt) | trace | gel inchangé (*) |
| Qui lance le second noyau (`KM`/`KH`) | piles de `_async_start_kernel`, `new_from_spec` | noyau de réserve de Spyder |
| Sans noyau de réserve | `get_cached_kernel(cache=False)` | un seul noyau, gel inchangé |
| Où dans la connexion (`KH3`/`KC`) | traces de `connect_std_pipes`, `connect_`, `start_channels` | toutes rendent la main |
| Quel appel du widget console ne rend pas la main (`W>`/`W<`) | traceur des méthodes de `ShellWidget` et `ClientWidget` | dernière entrée : page de chargement |
| Messages du Worker (`RM>`/`RM<`) | chronométrage de `ProcessusWeb._recevoir` | rapides, pas en cause |
| Ce que la console interne reçoit | capture d'`InternalShell.write` | seulement les traces de l'essai |
| Erreur de noyau affichée | `show_kernel_error` | jamais appelée |
| Le Worker est-il en cause | Worker terminé dès son lancement (bloc gardé, neutralisé par `pass`) | gel inchangé SANS Worker |
| Widgets web | `--no-web-widgets` ajouté aux options | **plus de gel, 5/5** |

(*) Le relevé détaillé de ces premiers essais est resté dans une partie de la conversation résumée depuis : seul
« le gel a persisté » est sûr. Les blocs sont dans le fichier, à rejouer pour le détail.

Niveau de preuve : chaque ligne est un passage Firefox 155 par la sonde, une passe chacune (pas de répétition) ; le
dernier essai (`--no-web-widgets`) une passe, verdict « fini ». Non essayé : Chrome ; le bureau avec
`--no-web-widgets` (sans objet, le bureau n'a pas de gel) ; quel appel PRÉCIS de la doublure `QWebEngineView` coûte
(chargement de la page HTML de Spyder, `setHtml`, polices, iframe ?) — c'est la première chose à mesurer pour choisir le
correctif propre.

Pistes pour un relecteur : (1) mesurer la doublure `QWebEngineView` seule avec la page de chargement de Spyder
(`spyder/plugins/ipythonconsole/widgets/client.py`, `_create_loading_page`) ; (2) décider entre doublure légère et
« pas de WebEngine » (Help et OnlineHelp en dépendent aussi) ; (3) mesurer la fermeture jusqu'au bout (attendre un
autre état que « fini », ou poser l'état après `closing`) ; (4) l'`InvalidStateError` de superqt.

## SmartPythonEditor pour les élèves : config de référence, plein page, print (12/10/2026, nuit)

Demandes : « un lien vers SmartPythonEditor pour les élèves » ; « tu peux me faire essayer sous chromium ? » ;
« l'editeur ne resemble pas du tout aux disposition de SmartPythonEditor, et un simple print("bonjour") dans le code
génère : » (TypeError dans `spyder_kernels` `path_is_library`) ; « il faut qu'il utilise tout la page du navigateur sans
cadre ni titre ni boutons de fenetre ».

FAIT :
- `essais/spyder/spe.py` (l'essai « tel qu'un élève l'ouvrirait », `index.html?script=spe.py`) : pose le `spyder.ini` et le
  `transient.ini` de référence du fork (`smartos-support/config-reference`, `__HOME__` substitué) et les réglages de
  `installation_SmartPythonEditor.sh` ; c'est de la CONFIGURATION, le code du fork n'est pas touché. `construire_site.py`
  embarque ces deux fichiers et les `METADATA` des distributions (sans eux, superqt rendait la version « unknown » et le
  contrôle de dépendances de Spyder levait `InvalidVersion`). `essai_chromium.sh` : serveur + Chromium en une commande
  courte (une longue ligne collée se coupait dans zsh).
- `qtpy6/web/preambule.py` `_completer_site` : sous emscripten CPython rend `None` pour `site.getuserbase()` ; le noyau
  (Worker, qui exécute ce préambule) en faisait un `in None` au premier `runfile`. Posé à `~/.local`, comme ailleurs.
- `qtpy6/web/messages.py` (branché dans `QtCore.py`) : filtre les deux avertissements de QCollator que Qt-WASM émet par
  construction (pas d'ICU, repli POSIX, déclenchés par QFileSystemModel) ; Spyder envoie tout message Qt non listé à
  son rapporteur d'erreurs, qui ouvrait une boîte. La doublure est posée aussi sur le module du binding, que `qtpy` lit
  directement.
- `qtpy6/web/__init__.py` `_plein_ecran` (dans `application()`, navigateur seulement) : un filtre d'événements remet en
  plein écran la première QMainWindow sans parent à chaque Show / WindowStateChange. `web.md` point 8 mis à jour.

POURQUOI CES CHOIX :
- Plein écran par filtre plutôt qu'en doublant `show`/`showMaximized`/`setWindowState`/`showNormal` : Spyder passe par
  les quatre selon sa configuration (layout/plugin.py, mainwindow.py), et `qtpy` lit les classes PySide6 directement,
  donc une doublure de méthode qtpy6 ne les verrait pas ; le filtre de l'application voit tout. La première QMainWindow
  seulement : les fenêtres de plugins détachées et les dialogues gardent leur cadre. Écarté : `show_full_screen()` dans
  l'application (règle de web.md jusque-là) — une branche propre au navigateur dans le code de l'application.
- Filtre de messages par texte EXACT : un avertissement Qt réel continue de remonter.
- Config de référence dans l'essai, pas dans qtpy6 : c'est ce que l'installation pose sur le bureau, propre à l'application.

VÉRIFIÉ : sonde Firefox 155, une passe : capture plein page sans titre, disposition SmartPythonEditor (Projets/Fichiers
à gauche, éditeur, variables et console à droite ; pas de barre de menus, voulu par le fork : Ctrl+M), pas de boîte
d'erreur. Chromium (l'utilisateur, 04:30) : `print("coucou")` exécuté, « coucou » dans la console. Non vérifié : plein
écran sous Chromium vu par l'utilisateur (il ne l'a pas signalé), mobile.

Points ouverts : la boîte des dépendances manquantes est coupée dans `spe.py` (contournement d'essai) ; le lien élèves
(hébergement) reste à faire ; avertissement « Duplicate name six…METADATA » à la construction (six listé deux fois).

### Barre d'outils : boutons manquants et groupe centré (12/10/2026, 04 h 30)

Demande : « la barre d'outils manque de certains bouton (profiling , stop, choix de l'interpreteur) et n'ont pas la meme
disposition ( plays, pose, stop, intrepreeteur etc doivent être au milieu) ».

FAIT (essai seulement, ni le fork ni les greffons touchés) :
  - `construire_site.py` embarque les greffons `spyder_stop_toolbar` et `spyder_interpreter_toolbar`
    (`/DATA/Python/FORKS/SmartPythonEditorPlugins`, sources et `egg-info` pour leurs points d'entrée) ; `spe.py` ne
    désactive plus le profileur.
  - Centrage : `_recenter` (mainmenu du fork) suppose la barre `window_controls_toolbar` du greffon
    spyder_window_controls tout à droite, dont la zone extensible prend la place restante. Sans elle, c'est la barre
    Interpréteur qui la prend (438 à 496 px relevés par le journal `smartos_rangee.jsonl` lu dans la page) : largeur de
    la zone de gauche calculée à 0, groupe collé aux boutons Fichiers. `spe.py` (SUITE) pose une barre vide de ce nom,
    avec sa seule zone extensible.

POURQUOI : embarquer spyder_window_controls donnait la zone, mais aussi les boutons Réduire/Agrandir/Fermer (refusés :
« sans cadre ni titre ni boutons de fenetre ») et ses appels kwriteconfig6 ; il n'a aucune option pour masquer ses
boutons. viztracer et line_profiler restent dehors (extensions C).

VÉRIFIÉ : sonde Firefox, `capture_spe.png` : Exécuter, Exécuter la cellule, Profiler, Stop, Interpréteur centrés.
POINTS OUVERTS : la liste de l'Interpréteur est vide dans la page ; un réglage propre (greffon window_controls qui
masque ses boutons en plein écran, ou `_recenter` qui n'en dépend plus) est une décision du fork, pas de l'essai.

### Interpréteur vide, contour de focus, Pyxel : diagnostics (12/10/2026, 04 h 50, quota à 83 %, rien de corrigé)

Demande : « le choix de l'interpreteur est vide . pourquoi ? les onglet ne prennent pas le contour bleu clair en haut et
sur les coté quand fenetre à le focus. il manque les outils pour Pyxel ».
  - Interpréteur : le combo lit `main_interpreter/custom_interpreters_list`, remplie à l'installation par
    `SmartOS/Commun/scripts/update_spyder_interpreters.py` (environnements pyenv). Dans la page elle est vide, et
    `sys.executable` vaut `/home/pyodide/this.program` (relevé par la sonde), `main_interpreter/executable` vaut `''`.
    Essai écarté puis annulé : y mettre `sys.executable` donne le libellé « Python home » (le combo prend le dossier deux
    crans au-dessus). À décider : un chemin d'apparence pyenv propre à la page (libellé « Python 3.13 »), mais c'est un
    faux chemin passé à MainInterpreter, à vérifier contre le lancement du noyau dans le Worker.
  - Contour bleu : d'après une recherche par sous-agent (lecture seulement), il n'est posé que par les greffons
    spyder_konsole et spyder_claude (`_appliquer_cadre` sur `QApplication.focusChanged`), pas par le fork. Le style
    statique de l'onglet actif (stylesheet.py 685-708) est gris. Aucun de ces greffons n'est dans le site. À confirmer
    sur le natif : quels onglets bleuissent réellement.
  - Pyxel : spyder_pyxel dépend de `pyxel>=2.9` (moteur Rust, extension native), absent de Pyodide-Qt ; non évalué.

### Plein écran du navigateur et Interpréteur rempli (12/10/2026, 05 h)

Demandes : « il est possible de rajouter un bouton pour passer le navigateur en plein ecran , ou que spyder prenne tout
la fenetre du navigaeur en cachant ses barres de titre, outils , adresse ? », puis « avance sur tout ce qu'il manque ! ».
FAIT :
  - `qtpy6/web/__init__.py`, `_plein_ecran` : doublure de `showFullScreen` / `showNormal` / `showMaximized` pour la
    fenêtre principale. Le premier demande en plus le plein écran du NAVIGATEUR (`requestFullscreen`), les deux autres
    le quittent et laissent la fenêtre à la taille de la page. C'est le chemin du F11 de Spyder (`toggle_fullscreen`),
    donc rien dans l'application. Le filtre de démarrage appelle l'original (pas de demande hors geste).
  - `spe.py` : le bouton Plein écran de Spyder (action `Fullscreen` du greffon Layout) posé dans la barre de droite, à
    la place des boutons de fenêtre ; la liste Interpréteur reçoit `/pyodide/3.13/bin/python` (étiquette « Python
    3.13 »), un fichier vide créé dans la mémoire de la page parce que MainInterpreter retire de la liste tout chemin
    qui n'est pas un fichier. `custom` reste faux : le noyau ne lit pas ce chemin.
ÉCARTÉ : le manifeste d'application (installation par l'élève, sans barres) : utile, mais demande une action de
l'élève ; à ajouter à l'hébergement. Pyxel : pas commencé (moteur natif, voir plus haut).
VÉRIFIÉ : sonde Firefox, capture : bouton à droite, « Python 3.13 » dans la liste, aucun Traceback. NON VÉRIFIÉ : le
passage réel en plein écran (une sonde sans tête n'a pas de geste utilisateur) — à essayer dans Chromium. Limite
connue : sortir par Échap laisse l'état « plein écran » de Spyder ; le F11 suivant ne fait alors que le remettre à
jour (un second F11 rentre à nouveau).
  - Suite (05 h) : « il faut utilise les deux meme icone que pour mes dock pour le plein ecran / reduction ». Spyder
    repose ses icônes qtawesome (`window_fullscreen` / `window_nofullscreen`) à chaque bascule
    (`_update_fullscreen_action`) ; `spe.py` remet après lui celles du bouton Agrandir des volets (`window_full_screen` /
    `window_collapse`). Vérifié : capture, icône de départ ; la bascule n'est pas vérifiable sans clic réel.

### Contour bleu de l'onglet du volet qui a le focus (12/10/2026, 05 h)

Demande : « les onglet ne prennent pas le contour bleu clair en haut et sur les coté quand fenetre à le focus ».
Cause : ce n'est pas un défaut de qtpy6. Le fork (`/DATA/Python/FORKS/SmartPythonEditor`, commit 686fd148a du 11/10 à
16 h 55) a été généré AVANT quatre correctifs de `SmartPythonEditor_generator` : 6791937 (onglets ouverts sur leur
volet), c2e516e (volet qui a le focus : onglet actif en bleu, éditeur, marges, console éclaircis), 264f60c (congé de
l'onglet actif) et 8367c00 (croix fines). L'environnement installé `SmartPythonEditor-6.1.5` les porte. L'écart a été
relevé par `diff -rq` : il touche six fichiers, tous génériques (aucun chemin de la machine).
Fait : `construire_site.py` prend ces six fichiers (`EN_RETARD`) dans l'installé. La première écriture d'un nom dans le
zip gagne (`NameToInfo`), ce qui donne zéro doublon (vérifié).
Écarté :
  - regénérer ou patcher le fork : interdit ici, c'est le travail de la session du fork ;
  - reproduire le suivi du focus dans `spe.py` : il aurait dupliqué `patch_spyder_focus_volet.py`, et l'éclaircissement
    de l'éditeur et de la console aurait manqué.
Vérifié : capture de la sonde Firefox. L'onglet `temp.py` a le contour bleu en haut et sur les côtés, l'éditeur est
éclairci et les croix sont fines ; 0 Traceback. Le changement de volet par un clic n'a pas été mesuré (sonde sans clic).
Point ouvert : `EN_RETARD` est à retirer une fois le fork regénéré.
