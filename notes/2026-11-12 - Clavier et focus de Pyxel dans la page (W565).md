# Clavier et focus de Pyxel dans la page (Worker 565, 12/11/2026)

Brief : item 8 du TODO Portage, défauts relevés par le professeur le 12/11 à 14:33 (note W549) : « il n'a pas l'air de
répondre au clavier » ; « comme il n'y a pas de cadre autour du jeu Pyxel, je ne peux pas être certain qu'il a le focus ».

## Clavier muet — cause mesurée, doublure qtpy6

**Mesure** (sonde Firefox du bac, site privé `/DATA/Python/qtpy6_essais/w565/site`, essai
`spe_monkey.py?jeu=…&clavier=1` : jeu minimal `init(64, 48, headless=True)` qui trace quand il voit Espace ; la page fait
un VRAI clic au centre de l'écran du panneau Pyxel, puis trois vraies frappes d'Espace, et relève le focus DOM, le focus
Qt, les événements reçus par l'écran et les `sig_key` du greffon) — journaux `clavier3` (sans) et `clavier5` (avec) :
- avant le clic : focus DOM sur `qt-window-focus-helper` (dans l'ombre de `qt-shadow-container`), focus Qt sur
  `PyxelScreenWidget` (le panneau prend le focus à l'apparition du jeu) ;
- après le clic : focus DOM sur **BODY** ; les `keydown` partent au BODY ; l'écran ne reçoit que `MouseButtonPress`,
  **0 KeyPress**, le jeu ne voit rien ;
- témoin : un clic sur l'éditeur rend le focus DOM à `qt-window-input-element` (le widget focus de Qt CHANGE).

**Cause** : un clic sur le canevas de Qt n'a rien de focusable sous la souris ; l'action par défaut du navigateur donne
le focus au `body`. Qt-WASM ne redonne le focus à son élément qu'au CHANGEMENT de widget focus ; cliquer un widget qui a
déjà le focus de Qt (cas de l'écran Pyxel) le laisse sans clavier. Lu dans les mesures, non dans les sources de Qt
(absentes de la machine).

**Fait** : `_garder_le_focus()` dans `qtpy6/web/__init__.py` (fichier de W559, intégré par lui, appelé par
`application()` après `_coller()`) : un élément de Qt (`qt-window-*`) qui perd le focus vers RIEN pendant un appui de
pointeur le reprend aussitôt. Le code du jeu, du greffon et de SmartPythonEditor ne change pas.
**Vérifié (mesuré, sonde)** : injection de la même fonction par l'essai (`&refocus=1`) → 3 KeyPress sur 3, `sig_key`
(32, True/False), le noyau voit Espace (images 120 puis 117, `clavier4`, `clavier5`). Puis avec le code COMMITÉ
(f75949b) dans le zip, sans injection (`clavier7`) : focus DOM resté sur `qt-window-focus-helper` après le clic, 3/3
KeyPress, « espace vue » image 227 ; témoin éditeur inchangé.
**Alternatives écartées** : `preventDefault` sur `mousedown` (empêcherait aussi un focus voulu hors de Qt) ;
`setFocus` côté greffon (fork, et Qt a déjà le bon focus : le défaut est entre le navigateur et Qt, donc dans qtpy6).
Limite : au toucher, le navigateur déplace le focus au `click`, après `pointerup` : non couvert, non mesuré.

## Cadre de focus — décision du professeur, confiée au generator

Au bureau, le panneau « Pyxel » (jeu) n'a AUCUN cadre : retiré à la demande du professeur le 31/07
(`spyder_pyxel/spyder/widgets/panes.py`, `_apply_tabs_stylesheet`) ; Pyxel Studio en peint un, gris au repos, bleu au
focus, autour du panneau. Décision du professeur (12/11 18:47-18:50) : un cadre AU RAS DE L'IMAGE du jeu (« ce qui fait
bizarre c'est les bandes noires au-dessus et en dessous du jeu »), coins arrondis (« essaie avec l'arrondi »), quelques
pixels rognés aux coins acceptés. Écarté : remplir les bandes par étirement des bords (`edge_bleed`) — « dégueulasse ».
Le greffon ne se modifie que depuis la session du generator (CLAUDE.md satellite) : demande envoyée à
`smartpythoneditor-generator-7d` le 12/11 à 18:52, avec les lieux (`_chemin_du_cadre`, `PyxelGameWidget`).

## « Le jeu rame complètement » (professeur, 19:20) — mesuré sans rendu GL, cause non trouvée

Instrumentation `&cadence=1` de `spe_monkey.py` : le VRAI jeu, `init` forcé headless (`&headless=0` : vrai rendu) ;
noyau, toutes les 60 images : images/s et ms par image d'update, draw, sommeil demandé / réel ; page, toutes les 2 s :
images/s reçues par le panneau (`sig_frame`), pire retard d'une minuterie de 50 ms, durée d'une passe du moteur de
`memoire_partagee`.
**Mesuré** (`cadence2`, Firefox du bac, headless, machine chargée ≈ 25-33 de charge pour 20 cœurs) : noyau 59-60 images/s
(16,7 ms : update 0,3, draw 1,5-4, sommeil 11-14) ; page 27-39 images/s reçues ; une passe 1-2,7 ms sur les deux
segments (131 136 et 282 624 octets) ; retard de minuterie 50-280 ms. La chaîne noyau → mémoire partagée → panneau tient
donc ; la pompe par `reconcilier()` (dans `time.sleep`) suffit, la minuterie de 4 ms coûte 1-3 ms par passe.
**Non mesuré** : le vrai rendu (WebGL de l'`OffscreenCanvas` du Worker, `boucle.func()` de `flip_web`) — le Firefox du bac
n'a pas de WebGL ; `--chromium` : `ImportError QNetworkInterface` (zip privé antérieur à la doublure QtNetwork, non
poursuivi) ; sonde `--visible` lancée par le professeur : fenêtre fermée à 30 s, avant le jeu (`cadence4`). Suspect
principal : le rendu GL, puis la charge de la machine (relevée par le professeur). Commande prête (même URL,
`&headless=0`, `--visible`, `cadence5`), suspendue par la PAUSE CPU de 19:54.

## Reste

Mesure `&headless=0` (après la reprise) ; cadre par le generator (révision à venir) ; vérification par le professeur dans son Firefox (clavier ET cadre).
