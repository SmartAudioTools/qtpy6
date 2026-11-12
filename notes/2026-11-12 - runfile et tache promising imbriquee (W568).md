# %runfile → « Cannot enter a promising task from inside another running promising task » (W568, 12/11/2026)

## Demande
Brief W568 : signature du professeur (12/11 19:20, ×5, fenêtre de W566) : dans la console de la page, `%runfile` rend
`SystemError: Cannot enter a promising task from inside another running promising task`, pile `code_runner._exec_code:597`
→ webloop `run_handle`. Établir QUI est la tâche promettante externe et QUI tente d'en entrer une seconde, puis corriger
dans qtpy6.

## Diagnostic (en cours)
- **Source du message** (lu dans les sources) : Pyodide 314.0.7 du Worker (`site/pyodide/pyodide.asm.wasm`, absent de
  Pyodide-Qt 0.29.3 de la page), `enter_promising_task` de `src/core/stack_switching/pystate.c` : drapeau unique statique
  `in_task`, mis à vrai à l'entrée d'une tâche promettante (`_pyproxy_apply_promising`, `run_main_promising`), remis à
  faux à sa sortie ou quand elle se suspend (`captureTaskState`, appelé par `saveState` de `suspenders.c`).
  `run_handle` de la WebLoop est un `create_once_callable(…, _may_syncify=True)` : chaque rappel de la boucle est une
  entrée promettante.
- **La trace du professeur** (`qtpy6_essais/equipe/w566/trace_professeur_runfile_1915.txt`) n'est PAS une pile
  d'exception : « Stack (most recent call first): » est le vidage `faulthandler` que Pyodide écrit quand il meurt
  (« Pyodide has suffered a fatal error », même format mesuré dans la page aux essais rf_1 à rf_3 ci-dessous). La pile
  s'arrête dans `ast.parse` ← `code_runner._exec_code:597` ← … ← `kernelbase.dispatch_queue` ← `webloop.run_handle` :
  le Pyodide du Worker (noyau) est mort pendant l'analyse du fichier. Les 5 SystemError viennent APRÈS : la tâche
  morte n'est jamais sortie, `in_task` est resté vrai, et chaque rappel suivant de la WebLoop (minuteries de ipykernel)
  est refusé à l'entrée.
- **Réponse à la question du brief** : la tâche « externe » est le `run_handle` de l'`execute_request` du `%runfile`,
  mort dans `ast.parse` ; la « seconde » est n'importe quel `run_handle` suivant. Ni `pomper` (qtpy6web.js : page, autre
  Pyodide), ni `_garde_vie`, ni `bloquant._suspendre` ne sont en cause. Le noyau ne « survit » pas : son Pyodide est
  mort, seules les minuteries JS tournent encore. Niveau : lu dans les sources + format mesuré dans la page ; la cause
  du fatal dans le Worker n'est PAS connue (candidats : le plantage de l'item 1, `index out of bounds` /
  `unreachable executed` ; un « Script terminated by timeout » de Firefox).
- **Défaut de qtpy6 relevé** (lu) : `qtpy6/web/js/travailleur.js` (fichier de W564) n'a aucun `on_fatal` : un Pyodide
  mort dans le Worker n'est ni signalé à la page ni arrêté. La page (qtpy6web.js, `mourir`) le fait pour son propre Pyodide.

## Essais (sonde, sans affichage)
- `spe_m4.py` et `spe_monkey.py` sont périmés (assert sur `travailleur.configurer`, retiré de spe.py).
- Essai neuf `essais/spyder/gc_jspi/spe_rf.py` (`index.html?script=spe_rf.py&n=5`, ajouté à `site/app.zip`) :
  rf_1 (120 s), rf_2 (300 s), rf_3 (200 s) : la console est prête vers 115 s, une première cellule passe dans le noyau,
  mais `sw.execute("%runfile …")` appelé depuis un `QTimer.singleShot` ne revient jamais (ni « RF envoye 1 », ni
  « RF debut 1 » côté noyau) : le `%runfile` n'est jamais parti, la signature n'est pas reproduite par cette voie.
  Les « fatal » de la page à la fin de chaque essai suivent l'arrêt de Marionette (fermeture de la sonde) : artefacts.
  Journaux : `qtpy6_essais/equipe/w568/rf_*.log`, `rf_*.console.log`.

## Correctif (W568, zone loadPyodide accordée par W564)
- **FAIT** : `qtpy6/web/js/travailleur.js`, fonction `garder(p, signaler)` posant `p._api.on_fatal` sur tout Pyodide du
  Worker : mode `lancer` (via `charger`, préchauffage compris) → `{sortie_erreur: "Pyodide mort (erreur fatale) dans le
  Worker : <cause>"}` puis `{fin: 1}` ; mode `demarrer` (appels) → `{id: courant, erreur}` ; puis `close()`.
- **POURQUOI** : la page le fait déjà pour son propre Pyodide (`qtpy6web.js`, `mourir`) ; sans lui, un noyau mort reste
  muet et la WebLoop enchaîne les SystemError. Objectif mesurable (Superviseur) : le professeur voit « noyau mort » et
  la cause au lieu des 5 SystemError.
- **Alternative écartée** : remettre `in_task` à faux (rattraper l'erreur dans la WebLoop) : le Pyodide est mort, son
  état C n'est plus fiable ; le relancer serait mentir.
- **Ne corrige pas** la cause du fatal (inconnue, question posée au professeur ; item 1 / parade GC dans le plan de nuit).
- **VÉRIFIÉ** : `tests/test_travailleur_js.py` (node, faux Pyodide) rouge avant (« on_fatal n'est pas posé »), vert après.
  Pas encore vu par le professeur.
- **Relecture** (relecteur) : crochet vérifié dans `site/pyodide/pyodide.asm.mjs` (`API.fatal_error` → `API.on_fatal(t)`
  puis `throw t`, `_api` épargné). Corrigé sur ses remarques : en mode appels hors appel (`courant` 0), `{erreur}` SANS id
  (sinon `_clore(0)` l'ignore, la page ne sait pas le worker tombé) — second cas du test, rouge sans ; après le signal,
  `postMessage` neutralisé (le `throw t` aurait ajouté un `{erreur}` après `{fin}`, donc un second `finished`). Reste,
  hors de mes fichiers : `travailleur.py` ne vide pas `_RESERVE` quand la réserve meurt (un seul `start` raté, faible).
