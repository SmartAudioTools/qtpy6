# QtNetwork dans la page : QTcpServer, QTcpSocket, QNetworkInterface (greffon spyder_collab) — W563, 12/11/2026

## Demande

Brief W563 (TODO Portage, item 14, sous-point W558 « spyder_collab ABSENT, dialogue d'erreur au démarrage ») : « Doublure
qtpy6 sous le nom Qt (`qtpy6/QtNetwork.py` […] natif = vraie classe, web = doublure dans `qtpy6/web/reseau_web.py`), sur
le relais que `socket_web.py` / `zmq_web.py` emploient déjà […]. Mesure : la page démarre sans dialogue, `spyder_collab`
inscrit dans la liste des greffons, une connexion QTcpSocket → QTcpServer dans la page échangeant un octet ; test rouge
avant. Le code de spyder_collab ne se modifie pas. »

## État de départ (mesuré, W558)

`ImportError: cannot import name 'QNetworkInterface' from 'qtpy.QtNetwork'` (`spyder_collab/network.py:43`), dialogue
d'erreur au démarrage, greffon ABSENT (`/DATA/Python/qtpy6_essais/w558/capture_main.console.log`). Cause, lue dans les
sources : `wasm/patches/pyside-qtnetwork-features-absentes.patch` retire `qnetworkinterface_wrapper.cpp` et
`qnetworkaddressentry_wrapper.cpp` ; `QTcpServer`/`QTcpSocket`/`QHostAddress`/`QAbstractSocket` sont compilés
(`strings pyside_QtNetwork.so`), mais une page n'écoute pas.

## FAIT

- `qtpy6/QtNetwork.py` (neuf, modèle `QtPdf.py`) : QtNetwork de la liaison ; sous emscripten, `QTcpServer`, `QTcpSocket`,
  `QNetworkInterface`, `QNetworkAddressEntry` de `qtpy6/web/reseau_web.py`. `qtpy.QtNetwork` le sert par `_qtpy.py`
  (sans changement : `importlib.import_module('qtpy6.QtNetwork')`).
- `qtpy6/web/reseau_web.py` (neuf) : signaux et méthodes Qt (`connected`, `disconnected`, `readyRead`, `errorOccurred`,
  `stateChanged`, `bytesWritten`, `newConnection` ; `listen`, `connectToHost`, `write`, `read`, `readAll`,
  `bytesAvailable`, `state`, `error`, `errorString`, `peerAddress`, `nextPendingConnection`…) sur `socket_web.Socket` en
  non bloquant, réveillés par `socket_web._veiller`. Comme Qt, rien n'est émis pendant l'appel. Un hôte autre que la
  boucle locale : `NetworkError`. `QNetworkInterface` : la seule boucle locale (le collab affiche « aucune adresse IPv4
  detectee », ce qui est vrai d'une page).
- `QAbstractSocket` et `QHostAddress` restent ceux de la liaison (présents dans Qt-WASM) : `_enum` de network.py trouve
  `QHostAddress.Any`, `QAbstractSocket.ConnectedState`, `ConnectionRefusedError` sur les vraies énumérations.
- `socket_web.py` non modifié : rien n'y manquait.
- Relecture (relecteur) : quatre écarts à Qt corrigés et testés (second `listen` refusé ; `close` du serveur ferme les
  connexions jamais reprises ; « localhost » → 127.0.0.1 pour `peerAddress` ; un rappel programmé avant `abort` ou un
  nouveau `connectToHost` n'émet plus rien, `_tentative`).
- `essais/spyder/greffons.py` : `_collab` (instrumentation) échange un octet QTcpSocket → QTcpServer et lance le transport
  du greffon (CollabPeer hôte + invité sur 127.0.0.1) ; lancé avant `editor.load`, différé de 3 s (la page ne rend plus
  rien après ce chargement, défaut connu de l'item 14, non traité ici).

## POURQUOI

Existant : `socket_web.Socket` (boucle locale TCP, registre de ports et routage page ↔ Worker de `zmq_web`, ce que
pylsp `--tcp` emploie) ; la doublure Qt s'y pose au lieu d'un second transport. Alternative écartée : un relais
WebSocket vers un serveur hors navigateur (piste de W551) — il faudrait un service à côté du site statique, pour un
greffon dont l'usage entre deux postes ne se fait de toute façon pas depuis une page ; et la doublure par la boucle
locale suffit à ce que le greffon s'importe et fonctionne dans la page (hôte et invité de la même page ou de ses
Workers). Alternative écartée aussi : sous-classer le `QTcpSocket` de la liaison — son moteur wasm ne s'écoute pas et
`QAbstractSocket` n'expose pas de crochet Python pour un autre transport.

## VÉRIFIÉ

- Test rouge avant le code : section W563 de `tests/test_doublures.py`, 3 échecs `ModuleNotFoundError` (mesuré), puis
  verts ; `test_doublures.py` 12 passés sous PySide6, 5 tests W563 sous PyQt6 (mesuré).
- Suite entière (PySide6, SmartPython) : 280 passés, 5 échecs dans `tests/test_web.py` (`ModuleNotFoundError: js`,
  `SimpleNamespace … 'window'` dans `_reglages_du_worker` de `qtpy6/web/__init__.py`, modifié et non commité par un autre
  worker) ; sans lien avec QtNetwork (mesuré : traces lues).
- Page (sonde Firefox, `site/index.html?script=greffons.py`, site `/DATA/Python/qtpy6_essais/w563/site`, journal
  `capture_greffons4.console.log`, mesuré) : aucun `ImportError`, aucun dialogue ; « greffon spyder_collab : INSCRIT »
  (18,96 s) ; « écoute=True, hôte=True, adresses=[] » ; « octet reçu b'x' » (19,85 s) ; « demande de Eleve (invite,
  127.0.0.1) » : la trame hello de l'invité CollabPeer décodée par l'hôte, par le code du greffon inchangé.
- Règle du dépôt : `spyder_collab` non modifié ; aucune branche web hors instrumentation (lu).

## Trouvé en chemin (item 14, hors de cet item)

- « La page ne rend plus rien après la liste des greffons » (W551, W558) : ce n'était pas un blocage. Après
  `post_visible_setup`, la console interne de Spyder a pris `sys.stdout` (`jalon7.py`, `rapport` le rend à
  `sys.__stdout__`) : les relevés partaient dans la console de Spyder. `greffons.py` imprime désormais sur
  `sys.__stdout__` (`_dire`). Mesuré : les actions tournent ensuite.
- Défaut suivant, mesuré (25,49 s) : `spyder_code_analysis : action CASSE AttributeError: 'ProcessusWeb' object has no
  attribute 'waitForStarted'` — doublure `QProcess` de `qtpy6/web/sous_processus.py` (W548), à doubler (méthode Qt).
- Règle du dépôt : `spyder_collab` non modifié ; aucune branche web hors instrumentation (lu).
