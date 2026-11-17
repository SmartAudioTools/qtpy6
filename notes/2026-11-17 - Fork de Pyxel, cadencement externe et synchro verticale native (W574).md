# Fork de Pyxel, cadencement externe et synchro verticale native (W574)

## Demande

Le professeur, 17/11/2026 à 02:41 : « on ne peut pas améliorer pyxel pour avoir une vraie
synchronisation verticale avec le greffon et en standalone ? ». À 02:45 : « lance des worker
pour avancer au maximum sur ce sujet cette nuit, tu peux forker et compiler pyxel. »

## Lecture de la source (Pyxel v2.9.9, commit 5d8e7b4)

- `run_frame_loop` et `step_frame` (`crates/pyxel-core/src/platform/sdl2/platform_sdl2.rs`)
  dorment par `SDL_Delay` jusqu'à une grille de 1000/fps ms, horloge `SDL_GetTicks`, puis
  appellent `SDL_GL_SwapWindow`.
- Aucun `SDL_GL_SetSwapInterval` : l'horloge du jeu n'a aucun lien avec l'écran. À 30 i/s
  sur 60 Hz, une image reste affichée 1, 2 ou 3 balayages.
- En web, `run` passe par rAF (`emscripten_set_main_loop_arg`, fps 0), et `flip` y fait panic.
- Le Pyxel installé dans SmartPython est en 2.9.8.

## FAIT

1. API ajoutée, la même en natif et en web, transmise à W573 et W575 :
   - `pyxel.step()` : `flip` sans le sommeil.
   - `pyxel.vsync(enabled=True) -> int` : vrai swap interval ; renvoie le nombre de balayages
     par image, ou 0 si la vsync est indisponible.
2. Patch Rust à ancres, `qtpy6_essais/equipe/w574/patch_pyxel/appliquer_patch.py` :
   8 modifications dans 4 fichiers. Si une ancre est absente ou ambiguë, rien n'est écrit.
   La vsync passe d'abord par un intervalle n ; à défaut, intervalle 1 avec n swaps.
   `run` et `flip` se bloquent sur le swap au lieu de dormir.
3. Greffon spyder_pyxel, commit 2601e46 :
   - le panneau envoie un octet par balayage dans un tube `<shm>.vsync.fifo`, et la fréquence
     de l'écran dans la shm (offset 1092, en mHz) ;
   - le noyau attend round(hz/fps) octets, puis appelle `pyxel.step()` ;
   - si le panneau est muet ou masqué, horloge à fps ;
   - sans `pyxel.step` (Pyxel d'origine), le comportement reste inchangé.

## POURQUOI

- Une fonction séparée plutôt qu'un paramètre `vsync=` dans `init` : la signature de
  pyxel::init et ses appelants ne changent pas.
- Côté panneau, `QWindow.requestUpdate` plutôt que `QOpenGLWidget.frameSwapped` : un seul
  QOpenGLWidget fait passer toute la fenêtre de Spyder en composition OpenGL, pour une image
  de 256×256.

## Alternative écartée

Laisser `pyxel.flip` dormir et resynchroniser côté panneau, en peignant la dernière image au
balayage. Le jeu garde alors sa propre horloge et les sauts d'images restent.

## VÉRIFIÉ, niveau de preuve

- Greffon : 7 tests (`tests/test_vsync_pacing.py`), rouges avant le code et verts après, avec
  un faux Pyxel et de vrais tubes. Couvert : cadence à 2 balayages, horloge à 30 i/s, panneau
  muet, arriéré purgé, repli sur flip.
- Suite du greffon : 8 étapes vertes. Les 9 autres sont hors d'atteinte dans ce Python
  (`qtawesome` et `spyder` absents, paquet `tests` masqué par site-packages), et l'étaient déjà
  avant.
- Patch Rust **compilé hors ligne** (chaîne de W575), fork `/DATA/Python/FORKS/pyxel`,
  branche `qtpy6-vsync`, c398acf + 61c7cad. Roue native construite.
- Sonde hors écran : step 0,01 ms sans vsync, flip 32,3 ms.
  Défaut trouvé : le swap offscreen ne bloque pas. Corrigé par une garde d'une demi-période :
  33 ms avec vsync.
- Greffon avec le VRAI Pyxel du fork et des balayages simulés à 60 Hz :
  33,6 ms par image, image publiée lue.
- **Non vérifié** : que les UpdateRequest suivent vraiment l'écran sous Wayland.
- **Non vérifié** : l'histogramme des balayages. Le script est prêt :
  `w574/mesure_balayages.py`.

État et commandes du matin : `qtpy6_essais/equipe/w574/ETAT.md`.
