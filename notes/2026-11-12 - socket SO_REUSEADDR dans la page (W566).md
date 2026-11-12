# socket SO_REUSEADDR dans la page (W566) — TODO Portage, item 19

## Demande

Brief W566 (Superviseur, 12/11) : « à l'ouverture de spe.py dans la page, le rapporteur d'erreur de Spyder s'ouvre sur
`mainwindow.py:1526 start_open_files_server` : le `socket` de Pyodide n'a pas `SO_REUSEADDR` (ou `setsockopt` le
refuse). Manque de qtpy6 : la doublure `socket_web.py` doit accepter ce que le natif accepte […]. Spyder ne se modifie
pas. » Fait trouvé par W559 (note « Essais sans branche web, suite (W559) », 18:59).

## État de départ (vraie condition d'usage)

Sonde Firefox sur `spe.py`, `--etat ouvert` : rapporteur d'erreur ouvert sur la fenêtre (`qtpy6_essais/w559/
capture_spe_c.png`), `AttributeError: module 'socket' has no attribute 'SO_REUSEADDR'`.

## Diagnostic (mesuré)

Chaînes de `essais/spyder/site/pyodide/pyodide.asm.wasm` : `SO_REUSEADDR` et `SO_REUSEPORT` absents ; `SOL_SOCKET`,
`SO_LINGER`, `SO_KEEPALIVE`, `SO_SNDBUF`, `SO_RCVBUF`, `SO_ERROR`, `SO_BROADCAST`, `TCP_NODELAY` présents. Le
`setsockopt` d'Emscripten refuse les options qu'il ne connaît pas (« Protocol not available » déjà mesuré sur
`SO_LINGER` au jalon 8a). Le reste du chemin de Spyder (`bind(('127.0.0.1', port))`, `listen(20)`, `accept()` dans un
`threading.Thread`) passe déjà par la boucle locale de `socket_web` (W548/W563).

## FAIT

`qtpy6/web/socket_web.py` :
- `installer()` pose `socket.SO_REUSEADDR = 2` et `socket.SO_REUSEPORT = 15` (valeurs de Linux) s'ils manquent ; en
  natif ils existent, rien ne change ;
- `Socket.setsockopt` tient pour sans objet l'échec d'une option de liaison au niveau `SOL_SOCKET` (`SO_LINGER`,
  `SO_REUSEADDR`, `SO_REUSEPORT`), même avant le `bind` ; toute autre option refusée sur une socket non doublée lève
  comme avant.

Existant : la tolérance de `SO_LINGER` (jupyter_client, jalon 8a), étendue ; aucune fonction neuve.

## POURQUOI, alternative écartée

- Écartée : une socket « open files » sans effet dans la page (serveur nul). La boucle locale sait déjà lier, écouter et
  accepter : le serveur de Spyder y tourne tel quel, et un client de la page qui lui envoie un nom de fichier serait
  servi comme sur le bureau. Rien à coder de plus.
- Écartée : modifier Spyder (`setsockopt` sous `try`) — règle du dépôt, le fork ne se modifie pas.
- Valeurs de Linux plutôt qu'un entier libre : Emscripten imite l'ABI Linux (musl) ; c'est le nombre qu'un code lirait
  sur le bureau.

## VÉRIFIÉ

- Test `tests/test_doublures.py::test_serveur_open_files_sans_so_reuseaddr` (section W566) : rouge avant le code
  (`AttributeError` sur `socket.SO_REUSEADDR`, comme dans la page), vert après. Il simule le `setsockopt`
  d'Emscripten (ENOPROTOOPT) et rejoue la séquence de Spyder ; il vérifie aussi qu'une autre option refusée lève.
- Page (mesuré, sonde Firefox, site reconstruit 19:03, même commande que W559) : plus de rapporteur d'erreur
  (`qtpy6_essais/equipe/w566/capture_spe.png`), aucune trace `SO_REUSE`/`open_files` dans la console.
- Suite entière (SmartPython, 19:05) : 283 passés, 3 sautés, 5 échecs, tous dans `tests/test_web.py`, dus à
  `import js` en natif dans `qtpy6/web/__init__.py:319` (`_reglages_du_worker`, commit W559 f75949b) : sans rapport
  avec ce diff, signalé au Superviseur. `test_doublures.py` + `test_socket_web.py` : 28 passés.
- Relecteur : rien de réel ; un cas de réserve (valeurs 2/15 figées, sous macOS 2 = SO_ACCEPTCONN) corrigé : l'ensemble
  toléré prend la valeur réelle du système quand elle existe.
- Règle du dépôt : aucune ligne ajoutée hors de `qtpy6/web/`.

## RESTE

- Vérification par le professeur dans son Firefox.
