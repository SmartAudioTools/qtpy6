# Pyxel web, step du fork dans la grille des balayages (W580)

## Demande

Le professeur, 17/11/2026 à 02:45, à la fenêtre du Superviseur : « lance des worker pour avancer au maximum sur ce
sujet cette nuit, tu peux forker et compiler pyxel. » Le sujet : les jeux Pyxel saccadent dans SmartPythonEditor web.
Les trois morceaux existaient : grille des balayages (W573, 0755f7e), API `pyxel.step`/`pyxel.vsync` du fork (W574,
8d340df), roue Pyodide du fork (W575, 7df5008). Il manquait leur jonction côté web.

## Ligne commune (règle CLAUDE.md : même code natif et web)

- Natif (spyder_pyxel 2601e46, `bridge/hooks.py`, `VsyncPacer`) : le `flip` du greffon attend round(hz/fps) octets du
  tube des balayages, puis appelle `pyxel.step()`. Sans `step` ou sans tube, il appelle `original_flip`.
- Web : le greffon n'a pas de tube, il appelle `original_flip`, qui EST `flip_web` (complété avant sa capture).
- **L'application écrit des deux côtés `pyxel.run(update, draw)` / `pyxel.flip()`, sans changement.** La différence
  reste dans la doublure : `flip_web` attend la grille puis appelle `pyxel.step()`, le même appel que le greffon natif
  après son attente.

## FAIT

- `qtpy6/web/pyxel_web.py` : `step = getattr(pyxel, "step", None)`. Avec `step`, `flip_web` ne pose plus la boucle
  d'emscripten (`run` à rappels vides, `MainLoop.pause`). À chaque pas de la grille, il appelle `step()`. Sans `step`
  (roue officielle de Pyxel), la voie W573 est inchangée : `MainLoop.func()`.
- Roue du fork copiée dans `essais/spyder/roues/qtpy6-vsync/pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl`
  (md5 231bff03…, celle de W575). Le dossier est ignoré par git ; un sous-dossier évite d'écraser la roue officielle,
  qui porte le même nom. `ROUE` de `spe_monkey.py` et de `spe_pyxel.py` pointe vers elle.
- `tests/test_vsync_web.py` : deux tests appellent le vrai `completer`/`flip_web` avec de faux `js`, `pyodide_js` et
  `pyodide.ffi`. Le test « fork » est rouge sur HEAD (`run`, `pause` et `MainLoop.func` au lieu de `grille`, `step`) et
  vert après. Le test « Pyxel d'origine » protège la voie W573, vert avant comme après.
- Outils `qtpy6_essais/equipe/w580/` :
  - `construire_sites.py` : `site_avant` et `site`, copiés de `w575/site`, avec la même roue du fork et tous les
    fichiers de qtpy6 de l'app.zip ramenés à HEAD. Seul le `pyxel_web.py` de `site` vient de la copie de travail.
  - `mesure.sh`, `campagne.sh` (avant/après alternés, deux passes chacun).
  - `diag_sommeil.py` : instrumentation privée, donne la pile de chaque `time.sleep`.
  - `ecran_professeur.sh` : écran réel ; argument `site_avant` pour comparer.

## Mesures (sonde hors écran, Firefox du bac, rendu headless, 59 Hz, `w580/{avant,apres}{1,2}.*`)

| passe | ips noyau | 0 balayage (non montrées / jamais reçues) | 1 | 2 | 3 | rAF 90 % |
|---|---|---|---|---|---|---|
| avant 1 | 60,1 / 60,0 | 913 (777 / 136) | 1883 | 117 | 4 | 33,3 ms |
| après 1 | 60,0 / 59,9 | 456 (390 / 66) | 2325 | 138 | 6 | 17,2 ms |
| avant 2 | 60,0 / 59,9 | 954 (808 / 146) | 1864 | 148 | 3 | 33,2 ms |
| après 2 | 60,1 / 59,9 | 840 (707 / 133) | 1927 | 156 | 5 | 33,2 ms |
| final (après + init de `t`) | 60,3 / 59,0 | 1326 (949 / 377) | 1428 | 142 | 13 | — |

- Cadence : 60 i/s dans toutes les passes. Le correctif ne la dégrade pas ; la grille W573 la tenait déjà.
- Histogramme : **pas de conclusion**. Images perdues : 913 et 954 avant ; 456, 840 et 1 326 après. La dispersion
  entre passes d'une même voie dépasse l'écart entre les voies. La page headless sert ≈ 40 rAF/s sur une machine
  chargée (limite déjà relevée par W573, d'autres workers tournent cette nuit), et c'est elle qui borne le pic à
  1 balayage hors écran. Seul l'écran réel tranchera (`ecran_professeur.sh`, comparer `site` et `site_avant`).
- `ms_sommeil_demande` passe de 15 à 30 ms par image alors que l'image dure toujours 16,7 ms. Cause mesurée
  (`diag2`) : un fil de la doublure `threading_web` (`run_handle:491`, sommeil de 1 000 ms par seconde) est
  désormais servi pendant le jeu, et le compteur de l'instrumentation additionne ses sommeils. Dans la voie
  `MainLoop.func`, ce fil n'apparaît pas dans les 30 sommeils relevés (`diag_avant`, tous dans `flip_web`). Le fil
  n'est pas identifié (supposé : une minuterie du noyau). La voie `step` laisse donc tourner les autres tâches du
  Worker entre deux images, ce que l'ancienne voie empêchait.
- Dans les deux voies, le noyau bascule par moments sur le repli au temps (`flip_web`, `time.sleep`) : la page
  headless se fige plus de 100 ms. Ce comportement de W573 est inchangé.

## POURQUOI

- `step` plutôt que `MainLoop.func` : c'est l'appel que le fork a créé pour un cadencement externe (W574), le même
  que le greffon natif. On n'a plus besoin de poser puis suspendre une boucle d'emscripten par un `run` à rappels
  vides, ni du trampoline, ni de `_skip_unwind_fatal_error`, ni de dépendre de `Module.MainLoop`.
- Détection par `getattr(pyxel, "step")`, sans réglage : la roue installée dit elle-même ce qu'elle sait faire.
  L'application et le greffon n'ont rien à configurer, conformément à CLAUDE.md.

## Alternative écartée

Appeler `pyxel.vsync(True)` dans le Worker et laisser Pyxel bloquer sur le swap. Dans un Worker avec OffscreenCanvas,
le swap ne bloque pas : W574 l'a mesuré en offscreen natif, 0,01 ms par flip, d'où sa garde d'une demi-période. Ce
serait revenir à une horloge propre à Pyxel, sans lien avec les balayages de la page. La grille W573 reste
l'horloge ; `step` ne fait que présenter l'image.

## VÉRIFIÉ, niveau de preuve

- **Mesuré** : `tests/test_vsync_web.py` 12/12, dont le nouveau test rouge sur HEAD. Suite
  `tests/test_web.py` + vsync : 77/77 (fiche testeur, Python de SmartPython).
- Relecteur (sonnet) : aucun défaut bloquant. Un défaut mineur corrigé : avec `step`, `etat["t"]` restait à 0,0, donc
  la première image du repli au temps partait sans attente. `init_web` l'initialise désormais. Le relecteur a aussi
  noté un décalage sans conséquence : les événements sont traités après le draw, comme dans `flip` natif.
- **Mesuré** : sonde hors écran, deux passes avant et trois après (table ci-dessus). Le jeu tourne avec la voie
  `step` : 2 940 images, aucun Traceback.
- **Lu dans les sources** : `step_screen` (fork, `system.rs`) ne dépend pas d'un état posé par `run` (draw_frame,
  frame_count, present, begin_update_frame).
- **Non vérifié** : l'écran réel (WebGL, vraie fréquence) : `w580/ecran_professeur.sh`, à lancer le matin.
- Règle CLAUDE.md : aucune ligne propre au web ajoutée dans le code d'application (`spe_*.py` : chemin de roue seul).
