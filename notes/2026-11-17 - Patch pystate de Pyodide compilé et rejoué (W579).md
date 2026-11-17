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

## b. Triangle sans parade — ROUGE : le patch ne suffit pas

- `spe_m4.py` (W545) ne tourne plus depuis D4 (W559) : il remplaçait dans `spe.py` la ligne
  `travailleur.configurer("./pyodide-qt/")`, retirée depuis (assertion au démarrage, 5/5). Variante PRIVÉE, dans
  `w579/site/app.zip` seulement (`w579/spe_m4_d4.py`, original gardé en `w579/app.zip.origine`) : `configurer("./pyodide/",
  roues de la page + pyxel)` posé avant l'exec final. `essais/spyder/spe_m4.py` n'est pas touché ; **le triangle de
  `sonde_tri.sh` est cassé pour tous depuis D4** (à réparer par qui possède l'essai).
- Pyodide patché, 3 passes (`tri_patche_1`, `tri_g2b_1..2`) : le noyau démarre (`K4`), « M4 triangle », puis le Worker
  meurt : `RuntimeError: unreachable executed`, offset 5614094, les 3 fois.
- Pyodide d'origine, même site privé, 2 passes (`tri_origine_1..2`) : meurt aussi (`index out of bounds` puis
  `unreachable executed`).
- Fonction nommée : relien du cœur avec `PYODIDE_SYMBOLS=1` (-g2, mêmes objets, 20 s, `w579/dist_g2/`) ; même offset de
  plantage que le binaire -g0 (le code ne change pas, la section `name` s'ajoute à la fin). `w579/fonction_a.py` :
  **5614094 = `__stack_chk_fail`** — le canari de protection de pile d'une fonction C a été écrasé. Les offsets du
  Pyodide d'origine (binaire de la release, autre disposition) ne se nomment pas avec cette carte.
- Lecture (supposé, non prouvé) : une seconde corruption de la pile C sous JSPI, hors GC — une fonction suspendue dont
  la zone de pile C est prêtée à une autre tâche par `StackState` et rendue abîmée, ou réécrite pendant la suspension.
  Le patch pystate retire la lecture du GC (prouvé par a.) mais pas celle-ci. Firefox ne journalise pas la pile du
  Worker : prochaine étape, appelant de `__stack_chk_fail` (`-sSTACK_OVERFLOW_CHECK=2` ou pile capturée dans
  `travailleur.js` via `onerror` du Worker, ou reproduction sous Node avec run_sync imbriqués + lecture pyxel).
- Niveau : mesuré, 5 passes ; cause de ce second plantage non établie.

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
