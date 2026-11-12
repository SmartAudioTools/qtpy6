# Alert de l'iframe et environnement de l'exécution (W560, 12/11/2026)

## Demande

Brief W560 : item 2 ter (« rediriger `alert` et `console.error|warn` de l'iframe vers ces méthodes, avec le comportement
Qt par défaut (QMessageBox pour alert) quand elles ne sont pas surchargées ») et item 18 (« Exécuter » de Spyder « tourne
dans le vide en cherchant les variables d'environnement », professeur, 15:05). Ajout du Superviseur (15:2x) :
`ProcessusWeb.finished` en `(int, ExitStatus)` — NON fait (fermeture de Claude Dock demandée à 15:28).

## FAIT — item 2 ter (non commité)

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

## Item 18 — diagnostic mesuré, non corrigé

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

## VÉRIFIÉ

- Mesuré : les deux tests échouent sans le correctif (2 failed) et passent avec (5 passed, `tests/test_doublures.py`).
- Mesuré : le script `_RELAIS` exécuté sous node (frameElement et console simulés) rend alert, alert vide, warn à trois
  arguments, error et l'exception non rattrapée avec ligne et fichier.
- Non mesuré dans la page : alert du tuteur (le chemin `_ensure_web` n'est pas atteint par la sonde, W558).
- Règle : greffon non modifié.
