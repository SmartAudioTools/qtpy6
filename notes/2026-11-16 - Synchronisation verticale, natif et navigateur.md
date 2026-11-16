# Synchronisation verticale, natif et navigateur (16/11/2026, réflexion, rien de mesuré)

Demande de l'utilisateur (21:18, dictée) : en natif, la synchro verticale existe-t-elle dans qtpy6, pour quels
widgets ; pour un jeu ou un lecteur vidéo sans saccade, quelle approche ; la retrouve-t-on sur le web ; le canevas
HTML reste-t-il la bonne solution, ou faut-il parler au GPU (OpenGL, Vulkan, DirectX) ? Constat : Pyxel porté dans
SmartPythonEditor web saccade franchement.

## Natif

- `QWidget` ordinaire (raster) : pas de cadence de présentation. Le backing store est envoyé quand Qt le décide ;
  sous Wayland le compositeur évite le déchirement, mais une animation menée par `QTimer` tombe à des instants sans
  rapport avec le balayage → saccades (ex. 30 i/s sur 60 Hz : 1 ou 3 images d'écran au lieu de 2).
- `QOpenGLWidget` / `QOpenGLWindow` : `QSurfaceFormat.setSwapInterval(1)` (défaut) → `swapBuffers` bloque sur le
  balayage ; enchaîner `update()` dans `paintGL`/`frameSwapped` donne une cadence calée. C'est ce que l'utilisateur
  employait.
- `QWindow.requestUpdate()` : sur Wayland (frame callbacks) et macOS (CVDisplayLink), réveil calé sur l'écran.
- `QQuickWindow` (QML, render loop « threaded ») et `QRhiWidget` (Qt ≥ 6.7, Vulkan/Metal/D3D11-12/OpenGL selon l'OS
  par QRhi) : cadence vsync native, et c'est l'abstraction GPU de Qt — inutile d'écrire du DirectX ou du Vulkan à
  la main, QRhi choisit.
- Vidéo : `QVideoWidget` / `QGraphicsVideoItem` / `VideoOutput` QML (QtMultimedia passe par QRhi) présentent au
  balayage.

## Navigateur

- Tout ce qui est dessiné (canvas 2D, WebGL, WebGPU) est présenté par le compositeur du navigateur au rythme de
  l'écran ; seul `requestAnimationFrame` donne le top d'image. WebGL ou WebGPU ne donnent PAS une meilleure synchro
  que le canvas 2D : ils ne changent que le coût du dessin. Vulkan/DirectX n'existent pas dans une page.
- Qt-WASM présente déjà au `requestAnimationFrame` (`_dessiner_aussitot`, qtpy6/web/__init__.py). Le canevas reste
  donc le bon support ; ce n'est pas lui qui saccade.

## Hypothèse sur Pyxel web (à mesurer)

`qtpy6/web/pyxel_web.py`, `flip_web` : cadence à `fps` par `time.sleep` dans le Worker, sans lien avec l'écran ;
l'image passe ensuite par le pont du greffon, sondé par une minuterie de 4 ms, puis par l'`UpdateRequest` de Qt et le
`requestAnimationFrame` suivant. Trois horloges non accordées → durée d'affichage par image irrégulière (à 30 i/s
sur 60 Hz : 1, 2 ou 3 balayages). Piste : présenter au `requestAnimationFrame` avec un pas fixe (chaque image Pyxel
montrée exactement `hz / fps` balayages), le Worker cadencé par un top envoyé depuis le `requestAnimationFrame` de la
page plutôt que par `time.sleep`. Côté natif, même principe : une doublure de présentation calée sur
`frameSwapped`/`requestUpdate`, sous le même nom des deux côtés (règle du CLAUDE.md du dépôt).

Mesure à faire avant toute correction : horodater dans la page chaque `requestAnimationFrame` et le numéro d'image
Pyxel présenté ; histogramme du nombre de balayages par image Pyxel. Niveau de preuve de cette note : lecture du
code et connaissance des API, aucune mesure.

Avis du Superviseur SmartTeacher (21:19) : sujet qtpy6/SmartPythonEditor, hors de son périmètre. Mesurer d'abord dans
le vrai contexte (sonde horodatée côté Worker, côté pont, côté rAF, sur le cas qui saccade : un chiffre par horloge),
ensuite seulement la piste du pas calé sur rAF. Si la correction change l'API de qtpy6 employée par le lecteur web de
SmartTeacher (QCM/web), le prévenir avant de pousser : un de ses workers touche ce code.
