# Plantage JSPI + GC : reproduction minimale et cause (W576, 17/11/2026)

Item **1 bis, a. et b.** du TODO Portage (pas c. : aucune reconstruction de Pyodide cette nuit).

## Demandes citées
- Le professeur, 12/11/2026 13:58-13:59 : « et on ne peut pas réparer Pyodide / JSPI ? », « ajoute la reproduction
  minimale et le patch Pyodide au TODO ».
- Le professeur, 17/11/2026 02:46 (fenêtre du Superviseur) : « il faudrait aussi lancer des worker pour avancer sur le
  portage de SmartPythonEditor sur le web, en essayant de ne toucher qu'à qtpy6 ».

## FAIT
1. **a. Reproduction minimale, sous Node** : `essais/spyder/gc_jspi/gcnu.mjs` (Pyodide 314.0.7 du site, CPython 3.14.2,
   Node v26.11.1). Quatre entrées promettantes (`callPromising`) allouent des cycles et se suspendent par `run_sync`
   (une promesse `setTimeout`), entrelacées comme les fils de `threading_web` qui s'attendent. Plantage en moins d'une
   seconde : « Pyodide has suffered a fatal error … RuntimeError: memory access out of bounds » (V8 ; c'est le
   « index out of bounds » de Firefox), parfois un blocage (timeout). Trace : `gc_jspi/traces/trace_plantage.txt`.
2. **b. Cause localisée et prouvée** (lecture des sources + trois mesures, ci-dessous).
3. Émulation du correctif, sans reconstruire : `gc_jspi/fabriquer_pyodide_patche.py` modifie une COPIE de
   `pyodide.asm.mjs` (`pyodide_patche/`, non suivie) ; test rouge sans, vert avec.

## Variantes et témoins (3 essais par cas, `traces/bilan*.txt`)
| Cas | Résultat |
|---|---|
| `seul` : 4 entrées l'une après l'autre, GC seuil (1,1,1) | 3/3 OK |
| `entrelace` 1 entrée | 3/3 OK |
| `entrelace` 4, sans suspension (`SUSP=0`) | 3/3 OK |
| `entrelace` 4, GC coupé (`gc.disable()`) | 3/3 OK |
| `entrelace` 4, seuils PAR DÉFAUT (`GC=0`) | **3/3 plantage** |
| `entrelace` 4, seuil (1,1,1) | **3/3 plantage** |
| `imbrique` 8 (une entrée en lance une autre pendant sa vie, comme `pomper`) | **3/3 plantage** |
| GC auto coupé + `gc.collect(0)` (jeune) à chaque tour | 3/3 OK |
| GC auto coupé + `gc.collect(1)` (incrément) à chaque tour | **2 plantages + 1 blocage** |
| GC auto coupé + `gc.collect(2)` (pleine) à chaque tour | 3/3 OK |
| Copie corrigée (`CORRIGE=1`) : entrelace 4 seuil 1, incr, imbrique 8, entrelace 16×300 | **12/12 OK** |
| Même copie sans `CORRIGE` (témoin de la copie) | 1 plantage + 1 blocage /2 |

Il faut donc : au moins deux piles suspendues en même temps, ET la passe **incrémentale** (génération 1, celle de
toute collecte automatique en 3.14). Les seuils par défaut suffisent : le plantage n'est pas un artefact du seuil 1.

## Lecture des sources — ce que la passe lit de faux
Sources : `pyodide/pyodide` au tag 314.0.7 et `python/cpython` au tag v3.14.2, lues par web-fetch (le bac à sable n'a
pas accès à GitHub par git ni curl : `/DATA/Python/FORKS/pyodide-src` n'a donc PAS été cloné). URLs ouvertes :
`https://raw.githubusercontent.com/pyodide/pyodide/314.0.7/src/core/stack_switching/pystate.c`, `…/pystate_pycore.c`,
`https://raw.githubusercontent.com/python/cpython/v3.14.2/Python/gc.c`, `…/Python/ceval.c`,
`…/Include/internal/pycore_interpframe_structs.h`. Côté JS, `site/pyodide/pyodide.asm.mjs` (local).

1. **Une tâche = un PyThreadState neuf, laissé dans la liste de l'interpréteur pendant sa suspension.**
   `pystate.c` (314.0.7) : `enter_promising_task` (l. 87) crée le tstate par `pystate_threadstate_new` →
   `PyThreadState_New(interp)` (`pystate_pycore.c`) ; `captureThreadState` (l. 204) ne fait que
   `PyThreadState_Swap(handback_tstate)` et rend le tstate de la tâche au JS (`saveState`) ; `restoreThreadState`
   (l. 220, `assert(handback_tstate == NULL)` l. 222) le réinstalle. Le tstate suspendu garde son `current_frame`.
   (Il n'y a plus de « réserve » : `delete_tstate`, l. 64, « We used to keep a freelist of thread states but … ».)
   Numéros comptés à la main sur le texte brut (224 lignes, total vérifié avec GitHub).
2. **Le cadre d'entrée de chaque tâche vit sur la pile C (mémoire linéaire).** `ceval.c` (v3.14.2),
   `_PyEval_EvalFrameDefault` : `_PyEntryFrame entry;` (variable locale dont l'adresse est prise → pile C de
   l'emscripten), `entry.frame.owner = FRAME_OWNED_BY_INTERPRETER;`, puis `entry.frame.previous =
   tstate->current_frame; frame->previous = &entry.frame;`. La chaîne `current_frame → … → previous` de toute tâche
   passe donc par une adresse de la pile C.
3. **Pendant la suspension, cette zone de pile C est rendue aux autres tâches.** `pyodide.asm.mjs`, classe
   `StackState` / `evictStackUpTo` / `enterTask` : la pile d'une tâche suspendue n'est recopiée qu'au moment où une
   autre tâche a besoin de la même zone (`_save_up_to`), puis la zone est réécrite par la tâche qui tourne ; la recopie
   inverse n'a lieu qu'à `restore()`. Entre-temps, la mémoire à l'adresse du cadre d'entrée appartient à une autre
   tâche.
4. **La passe incrémentale parcourt les cadres de TOUS les tstates.** `gc.c` (v3.14.2), `mark_stacks` : boucle
   `PyInterpreterState_ThreadHead` / `PyThreadState_Next`, pour chacun `frame = ts->current_frame`, lit
   `frame->owner`, `frame->previous`, `localsplus` … `stackpointer`, et ÉCRIT `frame->visited = 1`. Appelée seulement
   par `mark_at_start` et `gc_collect_increment` (génération 1, `_Py_RunGC` → `_PyGC_Collect(tstate, 1, …)`) ;
   `gc_collect_young` et `gc_collect_full` ne parcourent aucune pile. Numéros de ligne de gc.c/ceval.c non obtenus
   (web-fetch rend le texte sans numéros, la vue GitHub s'arrête à 1 000 lignes) : citer par nom de fonction.

**Cause** : `mark_stacks` suit la chaîne de cadres d'une tâche suspendue, arrive sur son cadre d'entrée dans une zone
de pile C réécrite par une autre tâche, lit un `owner`/`previous` faux et déréférence un pointeur sauvage (« out of
bounds », `unreachable`, ou boucle = blocage). Ce n'est pas la « réserve de PyThreadState périmés » supposée le 12/10.

## Mesures qui le prouvent (`SONDE=1`, offsets relevés : `PyThreadState.current_frame` = +52, confirmé par
`/usr/include/python3.14/cpython/pystate.h:132` juste après `what_event` ; `_PyInterpreterFrame.previous` +4, `owner` +38)
- À chaque suspension, la chaîne de la tâche contient **exactement un cadre dans sa propre zone de pile C**
  (800/800 suspensions) : le cadre d'entrée.
- À la reprise, avant la recopie, l'en-tête de ce cadre **a changé dans 471 reprises sur 800** (GC coupé, sans
  plantage : personne ne le lit) ; 52/101 avec GC, plantage à la 104e suspension.
- Masquer la chaîne pendant la suspension (`current_frame = NULL` à `saveState`, rétabli à `restoreState`) : 12/12 OK
  dans les cas qui plantaient tous.

## VÉRIFIÉ, niveau de preuve
- Cause : **lu dans les sources + mesuré** (discrimination par passe, sonde d'écrasement, correctif émulé rouge/vert),
  sous Node. Pas encore rejoué dans Firefox ni sur le triangle (`sonde_tri.sh`) : c'est c.
- Machine chargée pendant les mesures (six workers de nuit) : sans effet sur des résultats binaires répétés 3 fois.
- **Non couvert** : `handback_tstate == NULL` (pystate.c:222, second `pyxel.init`) n'a pas été reproduit ; c'est un
  `assert` de `restoreThreadState`, autre chemin (reprise alors qu'une tâche tourne), à traiter à part. « Cannot enter
  a promising task » en est une CONSÉQUENCE : le fatal tue la tâche sans `exit_promising_task`, `handback_tstate` reste
  non NULL et toute entrée suivante est refusée (`enter_promising_task`, l. 90-94) — cohérent avec W568.
- Même défaut probable pour tout lecteur des cadres des autres tstates : `faulthandler` (vidage de tous les fils — la
  trace de W568 en est un), `sys._current_frames()`. Lu, non mesuré.

## Ce que c. devra patcher, et son coût
- **Correctif** (Pyodide, `src/core/stack_switching/pystate.c` + `pystate_pycore.c`, accès à `current_frame` par
  l'en-tête interne) : dans `captureThreadState`, mettre de côté `mine->current_frame` et le mettre à NULL ; dans
  `restoreThreadState`, le rétablir avant le swap. Environ 15 lignes C. Sûr : `mark_stacks` n'est qu'une optimisation
  (marquer vivant tôt) ; les références fortes des cadres suspendus restent comptées comme externes par
  `gc_collect_region`, exactement comme lors d'une passe jeune, qui ne parcourt jamais les piles. Les cadres de la
  tâche ne sont plus visibles de `faulthandler`/`sys._current_frames()` pendant la suspension (mieux que des déchets).
- **Alternative écartée** : retirer le tstate de la liste de l'interpréteur pendant la suspension (touche le verrou
  `HEAD_LOCK` et la finalisation : plus intrusif pour le même effet) ; recopier la pile C d'avance (ne change rien :
  la zone est réutilisée quand même) ; couper le GC dans le Worker (parade de l'item 1 : perd les cycles, et ne
  suffisait pas au triangle d'après W545).
- **Coût** : voie C = une reconstruction de Pyodide-PySide6 (durée à relever). **Voie sans reconstruction** : la même
  correction en JS dans `pyodide.asm.mjs` (ce que fait `fabriquer_pyodide_patche.py`, ≈ 6 lignes utiles,
  offset +52 propre à 314.0.7 / CPython 3.14.2, à garder par une assertion de version), appliquée par la
  construction du site. Décision à prendre (voir ETAT W576) ; puis rejouer `sonde_tri.sh` SANS la parade de l'item 1.
- **Décidé par le professeur, 17/11 03:27 : « non directement le C »** (voie JS écartée, même comme étape de test).
  Patch préparé, non compilé : `qtpy6_essais/equipe/w576/pystate_masquer_cadres.diff` (`captureThreadState` rend une
  petite structure {tstate, current_frame} et met `current_frame` à NULL ; `restoreThreadState` le rétablit ; aucun
  changement du JS). Reconstruction à attribuer par le Superviseur (hors brief W576).
- d. Signalement amont : Pyodide (le défaut est dans l'interaction de leur bascule avec `mark_stacks`), avec
  `gcnu.mjs` comme reproduction ; CPython n'est pas en faute.

## Délégation
Lectures des sources par deux `web-fetch` (pas de réseau depuis Bash) ; campagnes par `campagne.sh` (zéro jeton).
