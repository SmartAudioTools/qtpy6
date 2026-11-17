# KeyError qtconsole `_handle_execute_reply`, cause (W585, 17/11/2026)

## Demandes
- Professeur, 17/11 17:20 (AskUserQuestion du Superviseur) : « Oui, diagnostic 2 pts » pour l'item 23 du TODO Portage.
- Professeur, 02:46 : « avancer sur le portage de SmartPythonEditor sur le web, en essayant de ne toucher qu'à qtpy6 ».
- Brief W585 : reproduction hors écran, cause prouvée par une sonde dans le vrai contexte, pas de correctif sans preuve
  ni sans accord du Superviseur ; dire si l'erreur dépend de l'`execute()` lancé par `QTimer` dans l'essai.

## Reproduction
Site privé `qtpy6_essais/equipe/w585/site` = copie de `w583/site_ecran` (site des élèves du 17/11 16:30 + page d'écran),
`construire.py` y ajoute `sonde_w585.py` (instrumentation) et `spe_w585.py` (= `spe_ecran.py` de W583, sonde posée au
début de `suite(main)`, `qt=0` dans l'URL supprime l'`execute()` du `QTimer` de 5 s). Une passe : `w585/passe.sh
<étiquette> qt=1|qt=0 <délai>` (sonde Firefox headless, jeu Pyxel avorté sans WebGL après le triangle : sans effet ici,
l'erreur vient avant). Journaux `w585/p_<étiquette>.console.log`.

Huit passes headless (17/11 17:30-17:47) : avec l'`execute()` du `QTimer` (`qt=1`), KeyError 1 fois sur 5 (a1 ;
a2-a5 non) ; sans (`qt=0`), 0 sur 3. Le critère du brief (« plus d'une fois sur cinq ») n'est PAS atteint : l'erreur est
une course (ci-dessous), reproduite une fois ici et une fois chez le professeur (W583, 17:05-17:18, même `…_42_4`).

## FAIT : la cause (mesuré)
Journal de la passe a1 (lignes 152-159 de `p_a1.console.log`), un seul relais connecté sur `message_received` du canal
shell (`connexions=1`) :
1. `ER> n=2` : la réponse de `…_42_4` (l'`execute()` du `QTimer`, seule exécution « user » en attente, `info=oui`) entre
   dans `_handle_execute_reply`, dict `_request_info['execute']` @c4e7c50.
2. `FL>` : le handler appelle `kernel_client.iopub_channel.flush()` (`frontend_widget.py:467`). Dans jupyter_client,
   `flush` poste `_flush` sur l'ioloop et attend `Future.result(timeout)` ; la doublure de qtpy6
   (`threading_web.doubler_futures` → `fils._attendre`) SUSPEND la pile par pas de 10 ms (JSPI) jusqu'au rappel.
3. Pendant cette suspension, la page continue : le canal shell livre la réponse `kernel_info_reply` →
   `JupyterWidget._handle_kernel_info_reply` (`_starting` vrai) → `FrontendWidget._started_channels` →
   `reset(clear=True)` (pile complète dans `p_a2.console.log`, ligne `W585 RESET`) ; `_executing` vrai, donc
   `self._request_info['execute'] = {}` : un NOUVEAU dict (@d584250).
4. `FL<` : la pile reprend, `executed.emit(msg)`, puis `self._request_info['execute'].pop(msg_id)` sur le nouveau dict →
   `KeyError '…_42_4'` (`ER! n=2 … dict@d584250`).

En natif, rien de tel n'arrive : `flush()` bloque le fil de l'interface sans traiter d'événement ; les messages du canal
shell, émis depuis le fil de l'ioloop, arrivent en connexion différée et ne passent qu'au retour du handler (lu dans les
sources : `jupyter_client/threaded.py:170-213`, `qtconsole/client.py:38-46`). Deux handlers du même widget ne
s'entrelacent jamais.

## Les hypothèses du brief
- « Une même réponse traitée deux fois » : ÉCARTÉE (mesuré). Une seule connexion de `_dispatch` au canal shell
  (`connexions=1`, `KC connexions shell=1`) ; chaque `msg_id` n'entre qu'une fois dans le handler.
- « Réentrée pendant une suspension JSPI d'un slot d'`executed` » : ÉCARTÉE dans sa lettre, juste dans son principe. La
  suspension n'est pas dans un slot d'`executed` (la pile reprend avant `executed.emit`) mais dans `iopub_channel.flush()`,
  et ce qui entre pendant ce temps n'est pas la même réponse mais un AUTRE message (`kernel_info_reply`), dont le handler
  remplace le dict. Troisième hypothèse, retenue : entrelacement de deux handlers de messages du même widget pendant la
  suspension de `flush()`.

## Dépendance à l'`execute()` du `QTimer`
Oui, dans les deux cas observés (mesuré). `…_42_4` est l'`execute()` lancé à 5 s par `spe_ecran.py`, AVANT la fin du
démarrage du noyau ; il faut que sa réponse soit dans `flush()` quand arrive le `kernel_info_reply` du démarrage (a1) ;
dans a2-a5 elle arrive avant et le `reset` trouve `_executing` faux. Sans cet `execute()` (b1-b3), aucune exécution
« user » n'est en attente au `reset` du démarrage : 0 KeyError. Un élève lance son code au triangle, bien après le
démarrage : ce chemin précis ne le touche pas. Le MÉCANISME, lui, reste ouvert en usage élève : tout message du canal
shell dont le handler touche l'état du widget peut entrer pendant la suspension de `flush()` d'une réponse d'exécution
(redémarrage du noyau pendant un `%runfile`, par exemple) — non observé dans ces passes (supposé).

## Correctif proposé (non codé : accord du Superviseur demandé)
Doublure dans qtpy6 (jamais une branche dans qtconsole ni Spyder, règle CLAUDE.md) : `ThreadedZMQSocketChannel.flush`
de jupyter_client, dans la page, appelle `self._flush()` sur place au lieu de poster sur l'ioloop et d'attendre un
`Future` : la page EST le fil de l'ioloop, il n'y a rien à attendre, et sans suspension aucun autre handler ne peut
s'intercaler — la sémantique native. Posée à l'import de `jupyter_client.threaded` par un chercheur de `sys.meta_path`,
comme `pyxel_web._Chercheur` (existant ; à factoriser plutôt que dupliquer). Coût estimé : ≈ 25 lignes + un test dans
`tests/test_web.py` (handler qui appelle flush, un second message posté : il ne doit passer qu'après) ; ≈ 1 point.
Alternative écartée : sérialiser dans `bloquant._relayer` les slots d'un receveur dont un slot est suspendu (proche du
natif pour TOUT receveur, mais interblocage dès qu'un slot attend un signal livré à ce même receveur — `attendre_signal`,
dialogues — et touche chaque slot de chaque application).

## Niveau de preuve
- Séquence get → suspension dans flush → reset → pop sur un autre dict : MESURÉ (sonde dans la vraie page, a1).
- Appelant du reset (`_handle_kernel_info_reply` → `_started_channels`) : MESURÉ (pile, a2).
- Absence en natif : LU dans les sources (jupyter_client, qtconsole), non rejoué en natif.

## Ce qui reste
- Accord du Superviseur sur la doublure ci-dessus, puis code, test rouge/vert, relecteur, commit.
- Après la doublure : rejouer `w585/passe.sh` (qt=1, cinq passes) et vérifier `FL>` sans `RESET` intercalé, 0 KeyError.
- Item 23 non fini (diagnostic seulement).
