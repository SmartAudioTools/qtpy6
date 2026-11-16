# Synchro verticale de Pyxel web, mesure et correction (W572, 16/11/2026)

Demande du professeur (16/11/2026 21:18, dictée) : en natif, quels widgets ont la synchro verticale ; pour un jeu ou un
lecteur vidéo sans saccade, quelle approche qtpy6 ; le canevas HTML reste-t-il le bon support. Constat : « les jeux
Pyxel saccadent franchement dans SmartPythonEditor web, pas en natif ». Partie théorique :
`notes/2026-11-16 - Synchronisation verticale, natif et navigateur.md`. Ici : la mesure, puis la correction.

## Étape 1 — mesure (écrite avant tout code de correction)

Instrumentation : `&cadence=1` de `essais/spyder/spe_monkey.py` (W565) étendue, pas de seconde sonde. Fonction
`horloges()` : noyau (fin de chaque `draw`, horodatage absolu envoyé par `BroadcastChannel`), moteur de mémoire
partagée (`memoire_partagee.ajouter_crochet`), minuterie du pont du greffon, images reçues (`sig_frame`), chaque
`requestAnimationFrame` de la page, et l'image d'écran où chaque numéro Pyxel arrive au canevas (écritures
`putImageData`/`drawImage` enveloppées, datées par `document.timeline.currentTime`). Bilan affiché DANS la page (cadre
en haut à droite) et dans la console (`VSYNC …`), toutes les 2 s, 25 relevés à partir de la première image.
`spe_monkey.py` réparé au passage : son `assert` sur `travailleur.configurer` (retiré de `spe.py` par W559, D4) cassait
l'essai ; le `configurer("./pyodide/", roues=[pyxel])` est maintenant ajouté au lieu d'être substitué.

Conditions : site privé `qtpy6_essais/equipe/w572/site` (`construire_site.py --sortie`), jeu
`projet_monkey_correction_exercice_33_tilemaps_images.py` (60 i/s), headless (`init` forcé, bac sans WebGL), Firefox
hors écran de la sonde, charge machine ≈ 13 pour 20 cœurs. ⚠ La copie de travail porte des diffs non commités de
W564 (`preambule.py` : trace `W564DBG` qui fait échouer le démarrage du noyau, « Une erreur est survenue lors du
démarrage du noyau », mesure2) : les quatre fichiers `bloquant.py`, `preambule.py`, `travailleur.py`,
`js/travailleur.js` ont été remis à leur version HEAD DANS le zip du site privé seulement.

**Mesuré** (`w572/mesure3.console.log`, 2 891 images Pyxel) :

| balayages par image Pyxel | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| images | 974 (789 reçues jamais montrées, 185 jamais reçues) | 1 658 | 253 | 6 |

Attendu à 60 i/s sur 59-60 Hz : 1 partout. Horloges (médiane, 10 %, 90 %, max) :
- noyau (`flip_web`, `time.sleep`) : 16,7 ; 16,2 ; 17,1 ; 39,4 ms — régulier, à SA cadence ;
- moteur mémoire : 6,4 ; 4,2 ; 13,8 ; 60,9 ms — minuterie de 4 ms qui glisse ;
- minuterie du pont (4 ms) : 5,5 ; 1,7 ; 11,9 ; 68,2 ms ;
- reçues (`sig_frame`) : 17,1 ; 11,0 ; 24,4 ; 564 ms — la gigue de deux minuteries s'ajoute ;
- `requestAnimationFrame` : 17,1 ; 16,1 ; 33,2 ; 4 883 ms — la page manque elle-même des images (fil chargé).

**Conclusion, niveau mesuré (hors écran)** : l'hypothèse des horloges non accordées est confirmée, et plus forte
qu'attendue : à fps = Hz, ce n'est pas « 1, 2 ou 3 au lieu de 2 » mais une image sur trois jamais montrée (deux
images arrivent dans le même intervalle de balayage, la première est écrasée) et une sur dix montrée deux fois. Hors
écran, Firefox cadence seul (`sonde.py`) : la vraie fréquence de l'écran reste à mesurer `--visible` (page prête,
ci-dessous).

Mesure 4 (même code, `.pyc` du zip qui masquait le correctif : voir plus bas) : 894 images à 0 balayage (671 + 223),
1 772 à 1, 251 à 2, 1 à 3 — deuxième relevé de l'état d'avant, concordant (31 % contre 34 %).

## Étape 2 — correction : le noyau cadencé par les balayages de la page

**FAIT.**
- `memoire_partagee.py` : au premier Worker enregistré, la page crée le segment `BALAYAGES` (`qtpy6-balayages`,
  `Int32Array` [compteur, période en µs]), incrémenté à chaque `requestAnimationFrame` et envoyé aux Workers comme
  tout segment. Sans effet sur une page non isolée (pas de `SharedArrayBuffer`).
- `pyxel_web.py` : `flip_web` attend `attendre_balayages` — l'image part quand le compteur a avancé de
  `round(hz / fps)` balayages (sommeils de 1 ms par le `time.sleep` du préambule, qui laisse tourner le moteur de
  mémoire) ; en retard, on repart du balayage courant ; si la page ne compte plus (onglet caché, 100 ms sans
  balayage) ou n'a pas de segment, repli sur l'ancien cadencement au temps.
- `tests/test_vsync_web.py` (7 cas, hors navigateur) : horloge fictive, page à 60 / 59,95 / 120 / 144 Hz, jeu à 30 et
  60 i/s, `draw` de durée aléatoire : chaque image dure exactement `round(hz/fps)` balayages ; retard ; page muette.
  Rouge sur HEAD (fonction absente), vert après.

**POURQUOI.** Deux horloges indépendantes (le `time.sleep` du noyau, le `requestAnimationFrame` de la page) dérivent
l'une contre l'autre : deux images tombent dans le même balayage, la première est écrasée. Cadencer le producteur sur
l'horloge du consommateur supprime la dérive à la source, sans toucher au greffon ni au jeu.

**Doublure, côté natif.** Le code de l'application (le jeu, le greffon `spyder_pyxel`) ne change pas : la synchro est
dans la doublure `pyxel.flip` de `pyxel_web` (web seulement) ; en natif, `pyxel.flip` reste celui de Pyxel, déjà
calé par SDL sur l'écran. Aucune branche `emscripten` ajoutée (grep sur l'écran du greffon : 0 ligne).

**Alternatives écartées.**
- File d'images côté page, une par `requestAnimationFrame` (présentation à pas fixe dans l'écran du greffon) : demande
  de modifier `spyder_pyxel` (hors des fichiers du brief) et ajoute une image de latence ; reste la suite naturelle si
  la mesure sur écran réel montre des doublons dus au pont (minuterie de 4 ms, 90 % à 13 ms).
- `Atomics.wait` sur le compteur dans le Worker : bloque la boucle d'événements du Worker, donc le moteur de mémoire
  qui envoie justement l'image ; les sommeils de 1 ms (JSPI) la laissent tourner.

**VÉRIFIÉ.**
- Mesure 7 (hors écran, mêmes conditions que 3 et 4, `w572/mesure7.console.log`, 2 228 images) :

  | balayages par image | 0 | 1 | 2 | 3 |
  |---|---|---|---|---|
  | avant (mesure 3) | 974 (34 %) | 1 658 (57 %) | 253 | 6 |
  | après (mesure 7) | 332 (15 %) — 219 non montrées, 113 jamais reçues | 1 586 (71 %) | 294 | 16 |

  Le noyau suit les balayages (médiane 17,9 ms contre 17,1 pour `requestAnimationFrame` ; plus de sommeil à l'heure).
  Le reste vient de la page elle-même : `requestAnimationFrame` à 90 % = 33,8 ms (Firefox hors écran, machine chargée
  à 13 pour 20 cœurs, qui saute des balayages) et de la gigue du pont (4 ms nominal, 90 % = 13 ms). Niveau : mesuré
  hors écran ; le vrai écran (WebGL, fréquence réelle) reste à mesurer.
- `tests/test_vsync_web.py` : 7/7. `tests/test_web.py` : un premier passage a révélé un défaut (le segment levait
  `OSError` sur une page non isolée : 7 échecs), corrigé ; après relecture, `tests/test_web.py` + `tests/test_vsync_web.py` : 73 réussis, 0 échec.
- Piège rencontré pour le site privé : `construire_site.py` met dans `app.zip` des `.pyc` à empreinte non vérifiée ;
  remplacer un `.py` dans le zip sans retirer son `.pyc` ne change rien (mesures 4 et 5). `w572/maj_zip.py` les retire.

## Pour le professeur, sur le vrai écran

`/DATA/Python/qtpy6_essais/equipe/w572/ecran_professeur.sh` : fenêtre Firefox visible, rendu WebGL réel
(`&headless=0`), histogramme en haut à droite de la page et dans `w572/ecran.console.log` (lignes `VSYNC`), 2 à 3 min (la sonde s'arrête à l'état « fini »).

**Relecture (relecteur), deux défauts corrigés avant commit.** Onglet caché : chaque image réattendait 0,1 s le
compteur figé (≈ 8 i/s au lieu de `fps`) — l'état `fige` retient la valeur figée, le repli au temps est immédiat
tant qu'elle ne bouge pas (test `test_page_muette_ne_fait_attendre_qu_une_fois`). Retour d'onglet : la première
période écrite valait la durée de l'absence — ignorée au-delà de 100 ms. Débordement de l'`Int32` du compteur :
après ≈ 1,1 an à 60 Hz, et rattrapé par le repli : laissé.
