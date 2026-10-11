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
