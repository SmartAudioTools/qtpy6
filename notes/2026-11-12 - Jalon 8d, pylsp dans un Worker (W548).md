# Jalon 8d : pylsp dans un Worker (W548, 12/11/2026)

## Demande

Item 6 du TODO Portage. Plan zmq, « Compléments », décision de l'utilisateur : « je souhaite le couvrir ». Le client LSP
de Spyder (`plugins/completion/providers/languageserver/client.py`), sans modification, doit parler à pylsp dans un Web
Worker ; la complétion et le diagnostic doivent arriver dans la page. Brief : doublure `QSocketNotifier` sous
`qtpy6.QtCore`, transport dans `zmq_web`, essai `essais/spyder/jalon8d.py` identique au bureau et dans la page.

## Ce que le client fait (lu dans le fork)

`LSPClient.start` crée deux sockets zmq PAIR (`bind_to_random_port`), puis lance deux QProcess :
- pylsp `--tcp`, qui tourne sur `socketserver.ThreadingTCPServer.serve_forever` (selectors) ;
- la passerelle `transport/main.py`, qui ouvre un TCP vers pylsp, le lit par `pexpect.fdpexpect.fdspawn(socket)` et
  surveille son parent par psutil.

Le client lit ensuite le FD zmq par `QSocketNotifier(Read)`. Le web doit donc fournir, sans branche dans
l'application :
- TCP de boucle locale entre deux Workers ;
- select/selectors ;
- `QSocketNotifier` sur un FD zmq ;
- les fd de socket lisibles par `os` ;
- termios et fcntl pour importer pexpect ;
- un psutil cohérent : parent vivant, se terminer soi-même.

## FAIT

- **`qtpy6/web/socket_web.py`** (doublure sous les noms de la stdlib : `socket`, `select`, `selectors`,
  `socketserver._ServerSelector`). TCP AF_INET/INET6 SOCK_STREAM vers l'hôte local, active sous emscripten :
  - bind, listen, accept, connect, send, recv, makefile, shutdown, close, délais ;
  - `select` et `Selecteur` ;
  - `doubler_qsocketnotifier` ;
  - `doubler_terminal` : termios, fcntl et resource absents de Pyodide, un appel lève ENOTTY ;
  - `doubler_os` : `os.fstat`, `read`, `write`, `close` sur le fd d'une socket doublée, pour fdpexpect.
- **`qtpy6/web/zmq_web.py`** (ajouts seuls). Les ops `flux_connect`, `accepte`, `refus`, `octets`, `fin` portent les
  octets par le même registre de ports que zmq, relayés de Worker à Worker par la page. `oublier` ferme les flux et
  purge les `_distants` du Worker. Un bind zmq sur un port TCP en écoute rend EADDRINUSE.
- **`qtpy6/QtCore.py`** : `QSocketNotifier` pour le FD d'une socket zmq_web. `activated` est émis à l'arrivée d'un
  message et à `setEnabled(True)` si la socket est prête ; pour tout autre FD, c'est la vraie classe.
- **`qtpy6/web/psutil_web.py`** :
  - la page a le pid 1, toujours vivante et intuable ;
  - `ppid()` rend ce pid ;
  - `terminate()` ou `kill()` sur soi-même lève `SystemExit` (le gardien du parent de la passerelle).
- **`qtpy6/web/travailleur.py`** (ProcessusWeb) : `error()`, `exitCode()` et `processId()`, avec la sémantique de
  QProcess. `"socket_web.py"` est ajouté à `_FICHIERS_WORKER`.
- **`qtpy6/web/sous_processus.py`** et **`preambule.py`** : sous Python 3.14, `get_event_loop()` lève s'il n'y a pas
  de boucle. Une boucle neuve est alors posée (`boucle()` / `_boucle()`).
- **`essais/spyder/construire_site.py`** : pexpect, ptyprocess, importlib_metadata et zipp ajoutés à PAQUETS. W551 y
  avait mis pylsp en 150070b.
- **Cas limites relevés par le relecteur** :
  - un connect expiré est retiré ;
  - `_lisible` est faux en attente ;
  - fermer une écoute ferme les connexions qu'elle n'a pas acceptées ;
  - `_distants` est purgé ;
  - un double listen lève EADDRINUSE.
- Le premier lot (socket_web, zmq_web, travailleur, deux tests) est entré dans 93a38e9, sous le message de W549 : ce
  git commit sans chemins a pris l'index partagé. Le contenu est celui qui a été testé et relu.

## POURQUOI, et l'alternative écartée

pylsp est gardé en `--tcp`, le réglage par défaut de Spyder (`generate_python_config`). L'alternative `stdio=True` est
écartée : elle demande PopenSpawn de pexpect dans le Worker, un Worker imbriqué et un réglage différent sur le bureau.
Le TCP de boucle locale passe par le registre de ports de zmq_web plutôt que par un second registre : un port est un
port, zmq ou TCP, et le relais par la page existe déjà.

Existant repris :
- `zmq_web` : `_lies`, `_distants`, routage postMessage, `select` ;
- `socket_web` : son `port_libre` d'origine est gardé ;
- `threading_web.attendre` et `plus_tard`.

## VÉRIFIÉ

- **Bureau (offscreen), mesuré** : jalon8d donne 5/5 en 15,2 s. initialize prend 7,6 s ; le diagnostic tombe ligne 2 ;
  la complétion `os.pa` donne `path` en 5,8 s.
- **Firefox, mesuré** (sonde, site construit avec `--sortie` sous `qtpy6_essais/w548-site/`) : 5/5 en 26,6 s. Lancement 6,3 s, initialize 16,2 s, diagnostic 0,6 s, complétion
  `path` 8,6 s, arrêt 0,0 s ; tas de la page 42 → 119 Mio. Journal : `qtpy6_essais/w548-site/capture_8d.console.log`, à
  partir de la ligne 273. Avant `processId()`, 2/3 : initialize échouait à 191 s, sur l'AttributeError de
  `client.py:559`. Avant psutil, la passerelle mourait d'`AccessDenied`.
- **Défaut résiduel corrigé après la mesure** : le `finished` différé de `ProcessusWeb.kill()` partait vers un objet
  détruit (« Signal source has been deleted »). La correction donne `self` comme contexte du `singleShot`. Test
  `test_kill_puis_destruction_sans_finished_orphelin` : rouge, puis vert (natif). Non resondé dans Firefox.
- **Tests natifs, mesuré** : zmq_web, socket_web, qsocketnotifier_web, noyau_web et psutil donnent 110 passés et
  1 sauté. Chaque correctif a été vu rouge, puis vert. test_noyau_web donne 34/34 sous 3.14 et sous 3.13 ; avant le
  correctif, 5 rouges sous 3.14, avec « There is no current event loop ».
- **Gel de jalon7 signalé par W547** : ce n'était pas ma doublure, son essai tournait sur un build qui ne l'avait pas
  (lu dans l'archive). Rejoué sur le build neuf : closing en 0,4 s (mesuré par W547). Un risque reste, lu dans le code
  et non mesuré : un `accept` suspendu pour toujours garde `bloquant._suspendus >= 1`. Un slot QTimer ne peut alors plus
  suspendre (`bloquant.py:152`).
- **Règle du dépôt** : jalon8d.py ne touche au web que par son instrumentation (témoin d'état, tas, Pyodide-Qt du site
  pour les Workers). Le client LSP du fork est intact.
