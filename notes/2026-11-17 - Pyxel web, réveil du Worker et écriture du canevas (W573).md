# Pyxel web : réveil du Worker et écriture du canevas (W573, 17/11/2026)

Demandes du professeur (16-17/11/2026) : « les jeux Pyxel saccadent franchement dans SmartPythonEditor web, pas en
natif » ; 01:43 : « images jamais montrées 34 % → 15 % ; c'est encore énorme » ; 02:41 : « on ne peut pas améliorer
pyxel pour avoir une vraie synchronisation verticale avec le greffon et en standalone ? ». Suite de la note W572
(`2026-11-16 - Synchro verticale de Pyxel web, mesure et correction (W572).md`).

État de départ (écran réel du professeur, 17/11 02:40, `w572/ecran.console.log`) : jeu Monkey à **35 i/s au lieu de 60**
(`CADENCE noyau` : `ips` 34,8-36,3, `ms_image` 27,6-28,7), `ms_sommeil_demande` 13,5, `ms_sommeil_reel` 26 ;
histogramme : 0 balayage 18 %, 1 : 67 %, 2 : 14 %.

## Étape 1 — où passent les 13 ms « en trop » (mesuré hors écran, écrit avant le code)

Instrumentation ajoutée à `essais/spyder/spe_monkey.py` (`&cadence=1`) : chaque top de balayage (valeur du compteur
`BALAYAGES` après tous les rappels de l'image, instant de l'image), chaque réveil du Worker (balayage lu, instant
absolu, nombre de sommeils de l'attente), durée et fin de chaque écriture du canevas, coût de `_deliver` du pont et
du `paintEvent` de l'écran du greffon. Site privé `qtpy6_essais/equipe/w573/site` (copie de `w572/site`, construit
depuis HEAD ; fichiers remplacés par `w573/maj_zip.py`). Machine chargée : 40 à 55 pour 20 cœurs pendant toute la nuit.

Mesures 1 et 2 (code W572, `w573/mesure1.console.log`, `mesure2.console.log`) :

| | mesure 1 | mesure 2 |
|---|---|---|
| `requestAnimationFrame` de la page, méd / 90 % | 49,2 / 84,2 ms | 17,1 / 50,3 ms |
| noyau, i/s | 30-32 | 20-42 |
| balayages comptés entre deux réveils du Worker | 1 : 1 042, 2 : 7 | 1 : 1 581, 2 : 7 |
| un sommeil de 1 ms dure réellement (10/50/90 %) | 2,3 / 2,6 / 3,2 ms | 2,4 / 2,6 / 3,3 ms |
| sommeils par attente, méd | 9 | 8 |
| réveil du Worker − début de l'image du top, méd / 90 % | 7,6 / 29,7 ms | 4,9 / 18,6 ms |
| écriture du canevas, durée méd / 90 % / max | 0,8 / 2,5 / 11,5 ms | 0,7 / 1,1 / 7,4 ms |
| `_deliver` du pont / `paintEvent` de l'écran, part du fil principal | — | 2,1 % / 3,6 % |

**Conclusion, niveau mesuré hors écran — l'hypothèse du brief est réfutée.**
- Le Worker ne se réveille PAS en retard : il voit chaque top (1 balayage entre deux réveils dans 99,4 % des cas).
  `ms_sommeil_demande` compte 1 ms par tour de scrutation alors que chaque tour dure 2,6 ms (minuterie du Worker) :
  l'écart « demandé / réel » est un artefact de la sonde, pas un sommeil en trop.
- L'écriture du canevas coûte moins d'une milliseconde ; les 250 ms « après l'image » de l'écran réel sont des arrêts
  du fil principal (le max de « fin depuis le début de l'image » vaut aussi 9 s au chargement), pas le coût d'écriture.
  Le pont et la peinture du greffon prennent 6 % du fil. Rien à alléger de ce côté-là.
- La vraie cause du jeu à 35 i/s : W572 cale le noyau sur le **compteur** des rappels `requestAnimationFrame`, et la
  page en saute dès que son fil est chargé (écran réel : rAF médian 17 ms mais 90 % = 50 ms, soit ≈ 36 rappels servis
  sur 59 balayages). Le noyau tourne donc à la vitesse de la page, et le jeu (dont la logique avance d'un pas par
  image) passe au ralenti.

## Étape 2 — correction : le noyau calé sur la GRILLE des balayages, pas sur le compteur

**FAIT.**
- `memoire_partagee.py` : le segment `BALAYAGES` passe à 16 octets. Int32 [0] compteur (inchangé), [1] période en µs
  **estimée** (moyenne glissante de `d / round(d / p)` : un rappel sauté compte pour m périodes, la période reste celle
  de l'écran) ; Float64 à l'octet 8 : instant absolu (`timeOrigin + t`, s) du dernier balayage servi. `t` est l'instant
  du balayage même quand le rappel arrive en retard.
- `pyxel_web.attendre_balayages` : vise le balayage `dernier + rang × période` (grille de l'écran), `n = round(hz/fps)`
  balayages après le précédent ; un seul `time.sleep` jusqu'à lui (plus de scrutation à 1 ms, qui en coûtait 2,6) ;
  en retard de plus d'une demi-période, balayage suivant ; aucun balayage depuis 100 ms (onglet caché, fil figé) :
  repli immédiat au temps, sans l'attente de 0,1 s de W572. `flip_web` inchangé.
- `__init__.py` (diff proposé par W577, appliqué ici) : le filtre `PleinEcran`, posé sur toute l'application, passe sur
  la seule fenêtre principale une fois trouvée (un appel Python par événement Qt en moins, au démarrage — 40 463 appels,
  1,7 s profilées par W577 — comme pendant le jeu).
- `tests/test_vsync_web.py` : `PageChargee` (page qui saute jusqu'à 40 % des balayages) ; 600 images à 60 i/s doivent
  durer 598/60 s à 1 % près, chaque image sur un balayage. **Rouge sur HEAD** : 15,85 s au lieu de 9,97 (38 i/s, le
  ralenti de l'écran réel), et images à 1-2 ms de la grille ; vert après. Les deux tests « page muette » lisent
  désormais l'instant du dernier balayage.

**POURQUOI.** Le compteur dit combien de rappels la page a servis, pas combien de balayages l'écran a faits. L'instant
et la période du balayage gardent la phase de W572 (pas de dérive entre les deux horloges : chaque image est recalée
sur le dernier balayage) sans hériter des sauts de la page. Le greffon publie l'image AVANT `flip` (`hooks.patched_flip`) :
réveillé sur le balayage, le noyau la publie juste après lui, ce qui laisse au pont presque une période entière.

**Doublure.** Ni le jeu ni le greffon ne changent ; en natif, `pyxel.flip` reste celui de Pyxel. Aucune branche web.

**Alternatives écartées.**
- `Atomics.waitAsync` sur le compteur, ou un Worker-minuterie qui notifie : le réveil n'était pas en retard (étape 1) ;
  ils resteraient calés sur les rappels servis, donc sur les sauts de la page.
- `Atomics.wait` bloquant : écarté par W572 (bloque le moteur de mémoire du Worker, qui envoie l'image) ; un sommeil
  JSPI unique fait la même attente sans le bloquer.
- Alléger l'écriture du canevas : 0,7 ms médiane, rien à gagner (étape 1).
- Garder le cadencement au compteur (W572) : le jeu au ralenti dès que la page saute des balayages (35 i/s sur
  l'écran réel). Un jeu Pyxel avance d'un pas par image : le ralenti se voit plus qu'une image sautée.

**VÉRIFIÉ** (hors écran, Firefox de la sonde, machine à 24-55 pour 20 cœurs ; `w573/mesure*.console.log`, `p*_w573`) :

| | mesure 2 (W572) | mesure 4 (W573) | paire 1 (W573) |
|---|---|---|---|
| noyau, i/s | 20-42 | 60,0 | 60-62 |
| noyau, intervalle méd / 90 % | 23,9 / 52,9 ms | 16,6 / 17,4 ms | 16,6 / 17,7 ms |
| réveil − balayage visé, méd / 90 % | — | 1,6 / 1,8 ms | 1,8 / 2,4 ms |
| rAF de la page, méd / 90 % | 17,1 / 50,3 | 17,1 / 49,3 | 17,5 / 66,7 |
| images montrées / rappels de la page | 0,57 | 0,70 | 0,63 |
| histogramme 0 / 1 / 2 / 3+ | 379 / 1 003 / 244 / 35 | 1 129 / 1 621 / 146 / 5 | 1 536 / 1 229 / 154 / 10 |

- Cible du brief « sommeil réel − demandé < 2 ms » : remplacée par « réveil − balayage visé », 1,6 ms en médiane (la
  première n'avait pas de sens, étape 1).
- Cible « un seul pic » : **non atteinte hors écran**. Le pic de 2 balayages tombe de 15 % à 5 %, mais le noyau
  produit maintenant 60 images/s pour une page qui n'en sert que ≈ 40 (rAF 90 % = 49-67 ms sur la machine chargée) :
  les images sans balayage montent (39 % en mesure 4). Ce reste est le fil principal de la page, pas le noyau.
- `tests/test_vsync_web.py` 10/10 ; `tests/test_web.py` + vsync : 75 réussis, 0 échec (Python de SmartPython).
- Paires avec un site HEAD (`site_head`) : le pont n'y a reçu aucune image (bilan vide), non exploitable ; la
  comparaison se fait contre la mesure 2.

## Pour le professeur, sur le vrai écran

`/DATA/Python/qtpy6_essais/equipe/w573/ecran_professeur.sh` : même usage que celui de W572 (fenêtre visible, WebGL,
2 à 3 min, lignes `VSYNC` et `CADENCE noyau` dans `w573/ecran.console.log`). À regarder : `ips` ≈ 60 (contre 35), et
les lignes `requestAnimFrame` (combien de balayages la page sert vraiment) et `réveil Worker − balayage visé`. Le
mieux : machine peu chargée (le 17/11 à 02:40, la charge était de 40 à 55 pour 20 cœurs, ce qui fait à lui seul
sauter des balayages à la page).

## Reste, hors de ce brief

- Le fil principal de la page saute des balayages (rAF 90 % ≈ 50 ms) : le pont et la peinture du greffon n'en
  prennent que 6 % ; le reste (Qt-WASM, Spyder, Pyodide de la page) est à profiler, item séparé.
- « Jamais reçues » (226 à 1 328) : la minuterie du pont (4 ms nominal, médiane 8-11) lit après que l'image suivante a
  remplacé la précédente ; une file d'images ou une lecture au rAF demande de toucher `spyder_pyxel` (lecture seule ici).
- Défaut antérieur (W572), relevé par le relecteur : `n = round(hz / fps)` fait tourner le jeu trop vite quand le
  rapport n'est pas entier (60 i/s sur 75 Hz : 75 i/s ; sur 144 Hz : 72 i/s). Remède : avancer une heure idéale de
  1/fps et viser le premier balayage qui la suit (mélange de 1 et 2 balayages) ; à faire avec le test 144/30.
- Le fork de Pyxel (W574 : `pyxel.step()`, `pyxel.vsync()`) est l'autre piste pour le standalone.
