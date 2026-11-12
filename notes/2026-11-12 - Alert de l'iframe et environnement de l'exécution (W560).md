# Alert de l'iframe et environnement de l'exécution (W560, 12/11/2026)

## Demande

Brief W560 : item 2 ter (« rediriger `alert` et `console.error|warn` de l'iframe vers ces méthodes, avec le comportement
Qt par défaut (QMessageBox pour alert) quand elles ne sont pas surchargées ») et item 18 (« Exécuter » de Spyder « tourne
dans le vide en cherchant les variables d'environnement », professeur, 15:05). Ajout du Superviseur (15:2x) :
`ProcessusWeb.finished` en `(int, ExitStatus)` — fait à 17:39, après annulation de la fermeture (Superviseur, 17:36).

## FAIT — item 2 ter (commité 5207053)

- `qtpy6/web/moteur_web.py` : `_RELAIS`, un `<script>` posé par `_avec_relais` en tête de toute page de même origine
  (`_poser` : `setHtml` et fichier local), après `<head>`, sinon `<html>`, sinon le doctype (jamais avant : mode quirks).
  Il remplace `alert` et `console.log|info|debug|warn|error` de l'iframe et écoute `error` (exceptions non rattrapées,
  « Uncaught … », ligne et fichier) ; il appelle `frameElement.qtpy6_relais`, proxy de `QWebEnginePage._relais`, qui
  appelle `javaScriptAlert(origine, msg)` ou `javaScriptConsoleMessage(niveau, msg, ligne, source)`. `console.*` garde
  son effet dans la console du navigateur. Énumération `JavaScriptConsoleMessageLevel` (Info 0, Warning 1, Error 2).
- Défauts comme Qt : `javaScriptAlert` ouvre une QMessageBox (titre « Javascript Alert - <origine> ») par `open()`,
  `javaScriptConsoleMessage` ne fait rien. Aucune ligne dans le greffon.
- `tests/test_doublures.py` (section W560) : `test_moteur_web_relais_alert_console`, `test_moteur_web_alert_par_defaut`.

## POURQUOI

Script injecté dans le HTML plutôt que posé au `load` de l'iframe : `load` vient après les scripts et les images, or
`loading.html` de la console appelle `alert()` dans un `onerror` d'image, pendant le chargement. `open()` et non
`exec()` : le relais est appelé par le navigateur, entrée non suspendable où `exec()` ne bloque pas (`bloquant.py`).
Existant : aucun relais de console d'iframe dans `qtpy6/` (grep `frameElement`, `window.alert`). Alternative écartée :
intercepter dans le greffon (branche interdite par CLAUDE.md). Pas fait : `javaScriptConfirm`/`Prompt` (un retour
synchrone, impossible sans boîte bloquante) ; pages d'une autre origine (`load` http) : rien n'y est accessible.

## Item 18 — diagnostic mesuré (15:xx)

Essais (instrumentation) : `essais/spyder/env18.py` (l'appel seul) et `essais/spyder/env18_spe.py` (Spyder entier puis
`create_new_client()`, comme « Exécuter » sans console). Site `/DATA/Python/qtpy6_essais/w560/site`, journaux
`sonde_env18.log`, `sonde_env18_spe.log` du même dossier.
- `get_user_environment_variables()` aboutit en 2 s dans la page, son QtSlot est appelé ; mais il rend **0 variable**
  (`asyncio.create_subprocess_shell` échoue, exception avalée, `psutil…terminal()` = None) contre 30 en natif.
- La page « Récupération des variables d'environnement… » reste affichée PENDANT `get_cached_kernel` (23 s, lancement
  du noyau dans un Worker, appel synchrone dans `_connect_new_client_to_kernel`) ; puis `connect_kernel` passe à
  « Connexion au noyau… », qui reste au-delà de 35 s : **le noyau n'est jamais connecté**. Le message du professeur
  désigne donc l'attente du noyau, pas l'environnement.
- Reste : (a) doublure d'`asyncio.create_subprocess_shell` (ou rendre `os.environ`) dans `sous_processus.py`, pour que
  le noyau reçoive l'environnement ; (b) la connexion au noyau (zmq/Worker) après `connect_kernel`, à relever dans
  `sonde_env18_spe.log` côté Worker ; (c) `finished(int, ExitStatus)` (travailleur.py:232, kill → CrashExit).

## Item 18 — environnement : FAIT (17:40)

- `psutil_web.Process().terminal()` rend `TERMINAL_PAGE` (« /dev/pts/0 ») pour le processus courant, `None` pour un pid
  factice (noyau, pylsp). Spyder (`utils/environ.py:121`) prend alors la branche « lancé d'un terminal » et rend
  `dict(os.environ)`, comme sur le bureau lancé d'un terminal ; il ne lance plus le shell de connexion (`$SHELL -l -i`)
  qui n'existe pas dans la page. Mesuré dans Firefox : **18 variables** (0 avant).
- POURQUOI : la page n'a pas d'autre environnement que `os.environ` (pas de fichiers de démarrage de shell), c'est
  exactement le cas « hérité d'un terminal ». Alternative écartée : doubler `asyncio.create_subprocess_shell` pour
  exécuter un script shell (aucun shell à émuler, et le résultat serait `os.environ` de toute façon). Penchant du
  professeur (via le Superviseur) : reprendre `os.environ` — c'est ce que fait la doublure. Limite : sous Pyodide
  `os.getpid()` vaut 42 aussi dans un worker, qui se dit donc lui aussi relié au terminal (sans usage connu).
- Test : `tests/test_psutil_web.py::test_process_courant` (rouge : `TERMINAL_PAGE` absent, puis vert), et un pid
  factice rend `None`.

## Item 18 — erreur du noyau : FAIT (17:54)

- Une fois l'environnement rendu, la console passait à une page d'erreur : `show_kernel_error` avec
  « jupyter_client/localinterfaces.py:58: UserWarning: Unexpected error discovering local network interfaces ».
  Cause : `psutil_web.net_if_addrs()` rendait `{}`, `_populate_from_dict` lève `NoIPAddresses` (non rattrapée par le
  repli), l'avertissement part sur la sortie d'erreur du noyau, que Spyder (`client.py:513`, console encore cachée)
  affiche comme une erreur. Doublure : l'interface `lo` seule (AF_INET, 127.0.0.1, 255.0.0.0), comme une machine sans
  réseau. Alternative écartée : ajouter le message aux erreurs bénignes de Spyder (greffon, branche interdite).
- Test : `tests/test_psutil_web.py::test_machine` (rouge : `KeyError: 'lo'`, puis vert).
- **Mesuré dans Firefox** (`env18_spe.py`, comme « Exécuter » sans console) : environnement 18 variables, noyau
  `spyder_kernel_ready` vers 30 s, console visible, `print('W560', 6 * 7)` rend `W560 42` à l'invite `In [1]`.
  Avant : page d'attente au-delà de 60 s, puis page d'erreur.

## `ProcessusWeb.finished(int, ExitStatus)` : FAIT (17:39)

- `travailleur.py` : `finished = Signal(int, ExitStatus)` déclaré après l'énumération ; fin du programme →
  `NormalExit`, `kill` → `(0, CrashExit)`. `sous_processus.py` : `run` et `Popen._fini` acceptent le second argument.
  `tests/test_noyau_web.py` (attribué par le Superviseur) : les trois `emit` du faux processus passent à deux arguments.
- Test : `test_finished_code_et_exitstatus_comme_qprocess` (rouge : abandon de PyQt, slot à deux paramètres sur un
  signal à un ; vert ensuite). `test_noyau_web.py` + `test_psutil_web.py` : 48 passés ; 1 échec préexistant sans rapport
  (`test_import_ipykernel_kernelbase_avec_psutil_masque` : `ipykernel` absent de ce Python).

## VÉRIFIÉ

- Mesuré : les deux tests échouent sans le correctif (2 failed) et passent avec (5 passed, `tests/test_doublures.py`).
- Mesuré : le script `_RELAIS` exécuté sous node (frameElement et console simulés) rend alert, alert vide, warn à trois
  arguments, error et l'exception non rattrapée avec ligne et fichier.
- Non mesuré dans la page : alert du tuteur (le chemin `_ensure_web` n'est pas atteint par la sonde, W558).
- Règle : greffon non modifié.
- Item 18 et finished (18:00) : suite entière (Python SmartPython) 274 passés, 5 échecs dans `tests/test_web.py` ;
  trois (`persistant`, `police_fixe`, `coller_passe_par_qt`) échouent pareil sur une copie de HEAD sans mes changements
  (préexistants) ; `test_service_worker[firefox|chromium]` passe seul (2 passés, 97 s) : échec de charge (sondes Firefox
  lancées en même temps). Relecteur : rien.
