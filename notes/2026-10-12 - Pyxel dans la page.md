# Pyxel dans SmartPythonEditor web (12/10/2026)

Demandes de l'utilisateur : « il manque les outils pour Pyxel » (11/10), puis « avance sur pyxel » (12/10, 05 h).
Contrainte permanente : le code de SmartPythonEditor et de ses greffons (`SmartPythonEditorPlugins/spyder_pyxel`) ne
change pas ; ce qui manque dans la page est une doublure qtpy6.

## Ce qui est établi

- **La roue.** PyPI ne publie que des roues natives de pyxel 2.9.9. La version web officielle (`pyxel.js`, servi par
  `cdn.jsdelivr.net/gh/kitao/pyxel/wasm/`) charge Pyodide 314.0.4 et la roue
  `pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl`, posée à côté de pyxel.js (relevé WebFetch, non téléchargée :
  le shell n'a pas le réseau). Pyodide 314.0.4 et 314.0.7 (celui de `qtpy6/web/versions.json`) ont la même ABI
  (`2026_0`, emscripten 5.0.3) : **la roue officielle convient au Pyodide ordinaire de qtpy6**, sans recompilation.
  Elle ne convient PAS à Pyodide-Qt (0.29.3, Python 3.13, `pyemscripten_2025_0`), sur lequel `spe.py` fait tourner le
  noyau de la console (`travailleur.configurer("./pyodide-qt/")`). Les roues pyxel wasm plus anciennes trouvées sur le
  disque (sites de collègues NSI) visent emscripten 3.1.x : inutilisables.
- **Le noyau de la console tourne sur le Pyodide ordinaire** (option A ci-dessous) : `essais/spyder/spe_pyxel.py` (spe.py
  avec `./pyodide/` au lieu de `./pyodide-qt/`, lien `site/pyodide` → `exemple/pyodide`, Python 3.14.2) ; sonde Firefox,
  `capture_pyxel.png` : bannière « Python 3.14.2 … IPython 9.15.0 », invite `In [1]:`, zéro Traceback dans
  `sonde_pyxel.log`. *Testé dans la page (sonde), console non exercée au-delà de l'invite.* La page, elle, reste sur
  Pyodide-Qt 3.13 : seul le Worker du noyau change, ce que `configurer` permet déjà.
- **Ce que fait le greffon** (lecture de `bridge/kernel.py`, `bridge/hooks.py`, `bridge/reader.py`,
  `spyder/bridge_manager.py`) : dans le noyau, un crochet d'import remplace `pyxel.init/run/flip/show/quit` ; `init`
  pose `SDL_VIDEODRIVER=offscreen` ; `run` devient une boucle Python `update/draw/flip` ; à chaque image, `publish` copie
  `pyxel.screen.data_ptr()` et la palette dans un `multiprocessing.shared_memory.SharedMemory` (seqlock) puis écrit un
  octet dans une FIFO ; le panneau lit la mémoire partagée, réveillé par un `QSocketNotifier` sur la FIFO, et renvoie
  clavier/souris par la même mémoire (`set_btn`, `set_mouse_pos`).

## Options

- **A, retenue pour la suite : noyau sur Pyodide 314** — mesurée ci-dessus, démarre. Reste à vérifier sous ce noyau :
  matplotlib, l'explorateur de variables, le débogueur (non mesurés).
- **B : recompiler pyxel pour Pyodide-Qt (2025_0)** — écartée pour l'instant : Rust sans cible
  `wasm32-unknown-emscripten`, ni maturin, ni emsdk 4.x pour cette ABI sur la machine ; coût d'une chaîne complète.
- **C : jeux dans un ProcessusWeb séparé** — écartée : perd l'intégration au noyau (variables, débogueur, F5) qui est
  la raison d'être du greffon.

## Doublures qtpy6 que l'option A demande (à écrire)

1. `multiprocessing.shared_memory.SharedMemory` entre la page et le Worker du noyau, sur un SharedArrayBuffer (la page
   est déjà isolée COOP/COEP pour le travailleur, `travailleur.py`).
2. La FIFO de notification (`os.mkfifo`/`os.open`/`os.write` côté noyau) et `QSocketNotifier` sur son descripteur côté
   page — ou un réveil équivalent porté par la même mémoire partagée.
3. SDL dans un Worker : `pyxel.init` avec `SDL_VIDEODRIVER=offscreen` — à mesurer dès que la roue est là (le port SDL
   d'emscripten n'a peut-être pas ce pilote, et un Worker n'a pas de canvas DOM).
4. `pyxel.flip()` dans le Worker : la version web de Pyxel cadence par la boucle du navigateur ; à mesurer.

## Mesures du point 3 (12/10/2026, 05 h 15 → 05 h 45, sonde Firefox du bac à sable)

Roue téléchargée par l'utilisateur dans `essais/spyder/roues/` (5 024 321 octets, non versionnée), servie par
`travailleur.configurer("./pyodide/", roues=[...])` ; `essais/spyder/spe_pyxel.py` exécute un jeu minimal dans la console.
Chaque ligne est un essai, dans l'ordre ; le mur suivant n'apparaît qu'une fois le précédent levé.

1. `import pyxel` : **OK** dans le Worker du noyau (Python 3.14.2).
2. `pyxel.init` depuis une cellule : `FileNotFoundError /tmp/ipykernel_42` — le code Rust fait un `chdir` dans le dossier
   du script appelant. Levé en écrivant `/home/pyodide/jeux/jeu.py` et en l'exécutant sous ce nom (ce que fait F5).
3. Avec `SDL_VIDEODRIVER=offscreen` (ce que pose le crochet `patched_init` du greffon) : panique Rust « Failed to
   initialize SDL2: offscreen not available » — **le port SDL2 d'emscripten n'a pas ce pilote**. Le greffon tel quel ne
   peut donc pas marcher dans la page : il faudra une doublure qui le neutralise, sans toucher au greffon (à décider).
4. Sans pilote imposé : SDL veut un canvas. `pyodide.canvas.setCanvas2D(OffscreenCanvas)` le donne, puis il manque, l'un
   après l'autre : `screen` (ReferenceError), `navigator.getGamepads` (« Gamepads not supported »), `window` AVANT le
   chargement de Pyodide (emscripten fige `specialHTMLTargets` à ce moment-là : « Could not set gamepad connect
   callback »), `canvas.style` (« Module.canvas.style is undefined »), `document` (ReferenceError). Tous posés par l'essai
   (objets factices dans le Worker ; `window = self` en tête de `travailleur.js` servi par un blob modifié).
5. **SDL s'initialise alors et crée sa fenêtre** ; le mur suivant est le contexte GL : « Could not create EGL context
   (EGL_BAD_MATCH) », parce que `getContext("webgl2")` et `"webgl"` rendent `null`. **Ce n'est pas le Worker : le Firefox
   headless du bac à sable n'a aucun WebGL, page comprise** (« AllowWebgl2:false restricts context creation on this
   system », déjà constaté dans `notes/2026-10-10 - Modules Qt à la demande.md`). La sonde `--chromium` (QtWebEngine) ne
   rend pas la console du Worker ; non poursuivi.

Également vu dans la console, non expliqué : plusieurs `SystemError: Cannot enter a promising task from inside another
running promising task` (Pyodide), avant et après la panique ; à regarder si elles survivent à un init réussi.

## Point ouvert immédiat

- La même sonde lancée par l'utilisateur hors bac à sable (seul endroit avec WebGL) : `essais/spyder/sonde_pyxel_hors.log`
  et `capture_pyxel_hors.console.log` diront si `init` puis `cls`/`flip` passent dans le Worker sur un OffscreenCanvas
  WebGL. *Non mesuré.*
- Si oui, la forme des doublures se précise : dans le Worker, l'OffscreenCanvas et les objets DOM factices (qtpy6, pas le
  greffon) ; le crochet `SDL_VIDEODRIVER=offscreen` du greffon à neutraliser ; puis les doublures 1 et 2 (mémoire partagée,
  FIFO) pour que le panneau Pyxel reçoive les images comme en natif.
