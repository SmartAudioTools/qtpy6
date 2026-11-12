# Pyxel, ressources et son (Worker 549, 12/11/2026)

Brief : items 8 puis 9 du TODO Portage. Ordre du professeur (12/11 14:04) : « mets des workers sur tous les items qui
peuvent être traités indépendamment ». Origine : TODO son, « Suite du 12/10, 19 h 45 » — `load("projet_monkey.pyxres")`
→ `Exception: Failed to open file 'projet_monkey.pyxres'` malgré l'injection du fichier dans le noyau.

## Item 8 : le `.pyxres` introuvable — FAIT

**Cause, mesurée.** `pyxel.init` (dans `pyxel_binding`, lu par `strings`) exécute
`os.chdir(os.path.dirname(inspect.stack()[1].filename) or ".")` : le dossier de l'APPELANT d'`init`, censé être le jeu,
d'où ses `load` relatifs. En web l'appelant est la doublure `init_web` de `qtpy6/web/pyxel_web.py` : le cwd part dans
`/home/pyodide/app/qtpy6/web`. Le crochet du greffon (`spyder_pyxel/bridge/hooks.py`, `_resolve`) ne rattrape le cas que
si le cwd AVANT `init` est le dossier du jeu ; sinon `Failed to open file`.
Les trois vérifications du TODO, dans l'ordre (sonde, site privé, `init(headless=True)` : le Firefox du bac n'a pas de
WebGL) : (1) fichier présent dans le FS du noyau — oui, 10 485 octets ; (2) cwd à `init` — `/home/pyodide/monkey` avant,
`/home/pyodide/app/qtpy6/web` après ; (3) `load` — passe si le cwd d'avant `init` est le dossier du jeu, échoue avec
EXACTEMENT le message du professeur s'il ne l'est pas (`repro_sans.console.log`).
Pourquoi le cwd n'était pas le dossier du jeu chez le professeur le 12/10 : SUPPOSÉ — un premier lancement (fichier
encore absent, l'injection partait trop tôt) a laissé le cwd dans `qtpy6/web`, que l'`exec` suivant (sans `--wdir`)
garde. Le correctif rend la question sans objet : le cwd ne dépend plus de l'état d'avant.

**Fait.** `pyxel_web._cwd_du_jeu()`, appelé par `init_web` après l'`init` d'origine : remonte au premier cadre hors des
enveloppes (`qtpy6.*`, `spyder_pyxel.*`) et fait le même `chdir` que Pyxel. Le jeu retrouve la sémantique du bureau sans
greffon (cwd = dossier du script qui appelle `init`).
**Alternative écartée** : chemin absolu ou `chdir` dans l'essai / dans le jeu — c'est une adaptation de l'application
(règle du `CLAUDE.md`) ; corriger `_resolve` du greffon — fork en lecture seule, et le défaut vient de la doublure.
Existant : `_resolve` du greffon (garde, complémentaire : il couvre le bureau, où c'est SON `patched_init` l'appelant).

**Vérifié (mesuré, sonde Firefox du bac, site privé `/DATA/Python/qtpy6_essais/w549/site`)** : même essai, cwd mis
à `/home/pyodide` avant le lancement : sans le correctif `Failed to open file 'projet_monkey.pyxres'` ; avec, cwd après
`init` = `/home/pyodide/monkey`, `load OK`. Essai : `spe_monkey.py?jeu=…&diag=1` (instrumentation : jeu réduit à
`init(headless=True)` → `load`), journaux `repro_sans` / `repro_avec` dans `/DATA/Python/qtpy6_essais/w549/`.
Reste : la preuve dans le Firefox du professeur (WebGL), jeu complet.

**Défaut trouvé en passant, NON corrigé** : un second `pyxel.init` dans le même noyau (relancer le jeu) est fatal —
`Aborted(Assertion failed: handback_tstate == NULL, at: src/core/stack_switching/pystate.c,222,restoreThreadState)`
(`diag2.console.log`). Probablement le `run` d'origine relancé sous JSPI par `flip_web` ; ajouté au TODO Portage.

Site d'essai : copie privée (consigne du Superviseur, 14:17 : `app.zip` partagé corrompu à 14:11) ; `maj_zip.py` y
remplace des fichiers sans reconstruire. Relevés faits moi-même (≈ 8 commandes) : chaque sonde dépendait de la précédente.
