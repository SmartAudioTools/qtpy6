# Patch pystate de Pyodide compilé et rejoué (W579, 17/11/2026)

Item 1 bis c. du `TODO - Portage de SmartPythonEditor.md`. Suite de la note W576 (`2026-11-17 - Plantage JSPI et GC,
reproduction minimale et cause (W576).md`), qui a prouvé la cause et préparé le patch sans le compiler.

## Demandes

- Professeur, 12/11 13:58 : « et on ne peut pas réparer Pyodide / JSPI ? »
- Professeur, 17/11 02:46 : « lancer des worker pour avancer sur le portage de SmartPythonEditor sur le web, en
  essayant de ne toucher qu'à qtpy6 »
- Professeur, 17/11 03:27 : « non directement le C » (le correctif en C, pas son émulation JS).

## Quel Pyodide

Le Worker du noyau charge **Pyodide 314.0.7** (`API.version`, `site/pyodide/` et `exemple/pyodide/`), CPython 3.14.2,
emscripten 5.0.3, ABI 2026_0 — pas Pyodide-PySide6 0.29.3.7 (celui de la page, que le TODO c. nommait). C'est donc
314.0.7 qui est reconstruit ; Pyodide-PySide6 n'a pas besoin du patch tant que le noyau tourne dans le Worker 314.

## Recette

- Sources (réseau, lancé par le professeur) : `qtpy6_essais/equipe/w579/telecharger_pyodide314.sh` → arbre
  `/DATA/Python/outils_wasm/pyodide314/` (clone du tag 314.0.7 avec sous-modules, archives de `cpython/Makefile`,
  libffi et hiwire aux commits de `Makefile.envs`, `npm ci`).
- Construction hors réseau : `qtpy6_essais/equipe/w579/construire_pyodide314.sh` (cibles par défaut
  `dist/pyodide.asm.mjs`) : emsdk 5.0.3 copié de `FORKS/pyxel-wasm/emsdk` + `emsdk/patches` de Pyodide ; cales `wget`
  (lit `telechargements/`), `shasum`, `patch` (→ `git apply`, le bac refuse à `patch` de recopier le propriétaire) ;
  `CFLAGS` du profil (`-march=native`) retirés ; `_EMCC_CCACHE` conditionnel (pas de ccache) ; puis
  `wasm/patches/pyodide314-*.patch` appliqué une fois.
- Patch : `wasm/patches/pyodide314-pystate-masquer-cadres.patch` (`src/core/stack_switching/pystate.c`) :
  `captureThreadState` rend une structure `SuspendedTask {tstate, current_frame}` et met `current_frame` à NULL pendant
  la suspension ; `restoreThreadState` le remet et libère la structure. Le JS (`suspenders.c`) ne fait que stocker et
  rendre le pointeur : aucune autre modification.
- Durée : quatre essais (dossier de journal absent ; `patch` refusé par le bac ; `-march=native` ; `npm ci` relancé
  hors ligne par `make`, qui a vidé `node_modules`, d'où le second téléchargement). Compilation utile ≈ 3 min
  (CPython ≈ 3 min à l'essai 3, cœur 35 s à l'essai 4). Journaux : `qtpy6_essais/equipe/w579/journaux/`.
- Produit (non commité) : `outils_wasm/pyodide314/pyodide/dist/pyodide.asm.{mjs,wasm}` (wasm 9 610 036 o, sha256
  72077364…), recopié dans `qtpy6_essais/equipe/w579/dist/` (Pyodide 314.0.7 complet, asm remplacé) ; site privé
  `qtpy6_essais/equipe/w579/site/` (copie de `essais/spyder/site`, `pyodide` → `../dist`).

## a. gcnu.mjs sous Node — mesuré

Même script (`essais/spyder/gc_jspi/gcnu.mjs`), même Node 26.11.1, les quatre cas du bilan corrigé de W576, 3 fois
chacun (`w579/gcnu_rouge_vert.sh`, bilans `w579/gcnu/`) :

| Pyodide | entrelace 4×200 GC=1 | entrelace 4×200 incr | imbrique 8×200 GC=1 | entrelace 16×300 GC=1 |
|---|---|---|---|---|
| 314.0.7 patché (`w579/dist`) | 3/3 OK | 3/3 OK | 3/3 OK | 3/3 OK |
| 314.0.7 d'origine (`essais/spyder/site/pyodide`) | 3/3 plante | 2/3 plante | 3/3 plante | 3/3 plante |

Plantage : `RuntimeError: memory access out of bounds`. 12/12 vert contre 11/12 rouge : le test échoue sans le
correctif et passe avec. Niveau : mesuré, 24 exécutions.

## b. Triangle sans parade — VERT avec le jeu en headless

- `spe_m4.py` (W545) ne tourne plus depuis D4 (W559) : il remplaçait dans `spe.py` la ligne
  `travailleur.configurer("./pyodide-qt/")`, retirée depuis (assertion au démarrage, 5/5). Variante PRIVÉE
  (`w579/spe_m4_d4.py`) : `configurer("./pyodide/", roues de la page + pyxel)` posé avant l'exec final.
  `essais/spyder/spe_m4.py` n'est pas touché ; ligne ajoutée au TODO, item 1, « Essai ».
- Premières passes (jeu tel quel) : le Worker meurt dans les deux Pyodide, `unreachable executed` à 5614094 en patché.
  Relien -g2 (`PYODIDE_SYMBOLS=1`, `w579/dist_g2/`) + `w579/fonction_a.py` : 5614094 = `__stack_chk_fail`, appelé par
  `abort` ← `__abort_js` ← module annexe `pyxel_binding` (`wasm-function[361]`, pile capturée par `w579/pile_worker.py`
  dans `travailleur.js` privé), juste après `PyInit_pyxel_binding` et l'avertissement SDL sur le canevas.
- **Ce n'est ni Pyodide ni le GC** (mesuré) : même arrêt avec `gc.disable()` dans le noyau (2/2), avec la roue vsync
  de W575 (2/2), et HORS triangle : `spe_monkey.py&cadence=1&headless=0` → `Aborted()` ; `&headless=1`, même Pyodide
  patché → 128 lignes CADENCE, aucun arrêt. Le Firefox du bac n'a pas de WebGL : pyxel appelle `abort()` à l'`init`
  avec rendu. Fichier et ligne côté pyxel non nommés (son .so n'a pas de section `name`) ; inutile pour le portage :
  avec WebGL (Firefox de l'utilisateur), le jeu s'initialise.
- Triangle avec le jeu en `headless=True` (copie privée `w579/site_monkey/monkey/`, .pyxres relu par XHR si absent :
  le `%runfile` du triangle ne voyait que le .py), sondes `SITE=site_monkey w579/tri.sh` :

| Pyodide | passes | résultat |
|---|---|---|
| 314.0.7 patché (`w579/dist`) | 5 (`tri_hlr_1..3`, `tri_hlr2_1..2`) | 5/5 : `load OK`, jeu affiché, aucune erreur wasm |
| 314.0.7 d'origine (`w579/dist_origine`) | 4 (`tri_hlo_1..2`, `tri_hlo2_1..2`) | 3/4 : `index out of bounds` (2120315) avant le load |

- Niveau : mesuré, 9 passes ; la passe `tri_hlr_3` a été coupée par le délai du lot après `load OK` (journal de
  sonde tronqué, console complète jusque-là). Le patch C supprime le plantage du triangle ; témoin rouge 3/4.

## Incident : Pyodide partagé écrasé deux minutes

`cp -r` de `essais/spyder/site` avait recopié le lien `site/pyodide -> exemple/pyodide` (et `w579/dist` était un lien
vers le même dossier) : la copie de l'asm patché a écrasé `qtpy6/exemple/pyodide/pyodide.asm.{mjs,wasm}` de 08:01 à
08:03. Restauré depuis `qtpy6/site/pyodide/` (314.0.7 d'origine, vérifié octet à octet par le Superviseur). Un essai
du professeur sur `essais/spyder/site` a pu tourner sur le Pyodide patché dans cette fenêtre. Depuis : copies par
`cp -L`, jamais à travers un lien.

## Alternative écartée

Le même correctif en JS dans la construction du site (`fabriquer_pyodide_patche.py` de W576, réécriture de
`pyodide.asm.mjs` autour de `saveState`/`restoreState`) : pas de reconstruction, mais un correctif qui dépend de la
forme du JS généré, à refaire à chaque version, et qui ne se signale pas en amont tel quel. Le professeur a tranché
(17/11 03:27 : « non directement le C »).

## Signalement amont (texte prêt, NON envoyé)

Titre : *Incremental GC follows the frame chain of suspended JSPI tasks into reused C stack (3.14, stack switching)*

> With Pyodide 314.0.7 (CPython 3.14.2), when several promising tasks are suspended (`run_sync`) and the incremental
> GC runs (`gc.collect(1)`, or default thresholds), `mark_stacks` in `Python/gc.c` walks `current_frame` of every
> thread state in the interpreter, including those of suspended tasks. Their frame chain ends in the
> `_PyEntryFrame` that lives on the C stack of `_PyEval_EvalFrameDefault`; `StackState` lends that C stack region to
> other tasks while the task is suspended, so the GC reads overwritten memory: `RuntimeError: memory access out of
> bounds`. Minimal reproduction under Node (attached `gcnu.mjs`): 4 interleaved promising calls × 200 rounds with
> `gc.set_threshold(1,1,1)` crash 3/3. Fix (attached patch): `captureThreadState` stores `current_frame` aside and
> sets it to NULL during suspension, `restoreThreadState` puts it back; the frames' references are then counted as
> external, as in a young collection. With the patch, 12/12 runs pass; without, 11/12 crash.
