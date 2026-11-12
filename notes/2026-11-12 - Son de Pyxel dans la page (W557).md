# Son de Pyxel dans la page (W557, 12/11/2026) — BLOQUÉ

Demande (brief W557, item 9 du TODO Portage) : « un `AudioContext` minimal doublé dans le Worker, dont le
`ScriptProcessorNode` est pompé depuis `memoire_partagee.reconcilier()` […] ; échantillons poussés dans un anneau
`SharedArrayBuffer` […], joués dans la page par un AudioWorklet. Vérification : la page compte les échantillons non nuls
reçus. »

## Commité (consigne du Superviseur, 12/11 18:00) : son_web.py INERTE

Le commit contient `son_web.py`, les seuls crochets du moteur de `memoire_partagee.py`, l'instrumentation de
`spe_monkey.py`, cette note et l'item 9.
- **Retiré** : la création de l'anneau dans `installer()`, qui faisait échouer 4 tests de test_web chez W547. Il
  faudra l'ajouter au branchement, dans un `try`.
  - Le relecteur l'a signalé : sans garde, une exception de `preparer_page()` casserait l'import de QtCore.
  - Un Worker déjà né ne recevrait pas l'anneau.
- **Débranché** : la ligne `son_web.doubler()` de `pyxel_web.py`. Sinon tout noyau qui joue un son meurt.
- **Non commité** : la ligne `"son_web.py"` de `travailleur.py`, mêlée aux modifications en cours de W548
  (`finished(code, statut)`). À ajouter au branchement.
- **Tests** : test_web, test_doublures et test_noyau_web, sur HEAD plus mes deux fichiers seuls (copie hors du dépôt
  partagé), donnent les mêmes 16 échecs que HEAD nu. Ce sont des tests de navigateur, non lancés dans le bac.

## FAIT (le noyau meurt dès qu'un jeu joue un son)

- `qtpy6/web/son_web.py` (neuf) :
  - **Worker** : `AudioContext` doublé (`createScriptProcessor`, `createBuffer`, `resume`, `close`), installé par
    `son_web.doubler()` depuis `pyxel_web.init_web`.
  - **Pompe** : crochet du moteur de `memoire_partagee`, appelé par la minuterie de 4 ms et par `reconcilier()`. Elle
    appelle `onaudioprocess` jusqu'à dépasser le temps écoulé plus une cible : 50 ms, 2 blocs, ou 1,5 × l'écart entre
    deux pompes.
  - **Anneau** : en-tête Int32 de 64 octets (ECR, LEC, DEMANDE, ETAT, NON_NULS, LUES, VIDES, PERDUES, SAUTS, POMPES…),
    puis 16384 trames stéréo Float32 entrelacées.
  - **Page** : un AudioWorklet « qtpy6-son » chargé depuis une URL blob. Il rééchantillonne linéairement si le
    contexte n'est pas à 48 kHz, et saute en avant si le retard dépasse 2 × la cible. L'audio est repris au premier
    geste (keydown, pointerdown).
- `memoire_partagee.py` :
  - Crochets du moteur (`ajouter_crochet`).
  - `installer()` crée l'anneau dans la page, sans AudioContext : condition 2 du Superviseur. L'anneau est envoyé à
    chaque Worker comme un segment.
  - `import js` est gardé : hors navigateur, pas d'anneau. Sans cette garde, deux tests de test_noyau_web étaient
    rouges (relevé de W548).
- `pyxel_web.py` : `son_web.doubler()`. `travailleur.py` : `son_web.py` ajouté au tuple (l. 50, autorisé).
- `essais/spyder/spe_monkey.py` (instrumentation) : `&son=1` lance un son en boucle en headless, avec les paramètres
  `&pompe=0` (témoin), `&profil=1` (compteur d'entrées Python pendant la pompe) et GC coupé. La page relève
  l'anneau chaque seconde.

## VÉRIFIÉ (mesuré, sonde Firefox headless, site privé `qtpy6_essais/w557/site`, logs `sonN.*`)

| essai | pompe | résultat |
|---|---|---|
| son7, son15, son19 | coupée après init (témoin) | noyau vivant ; sommeil 8,4-9,1 s ; 0 entrée Python ; segment `qtpy6_son` présent dans le Worker (son19 : `(2, True)`) |
| son8, son18 | minuterie + reconcilier | Worker : `RuntimeError: index out of bounds` (son18 : GC coupé, même plantage) |
| son16 | reconcilier seul, GC actif | `index out of bounds` |
| son20 | reconcilier seul, GC coupé | Worker figé : aucune trace en 300 s, aucune erreur |

Sous Node, la logique de la pompe a été vérifiée avec un faux `onaudioprocess` : 7 pompes, ECR 14336, CIBLE 7524,
DEMANDE 1. Dans la page, POMPES est resté à 0 dans tous les essais : le premier appel du vrai mixeur ne rend jamais.

**Compteurs demandés (perdues, non nuls, latence) : non mesurés.** Aucun échantillon n'a atteint la page.
**Condition 1 (aucune entrée Python pendant la pompe) : 0 mesuré, mais seulement pompe coupée.** Non prouvé.

## POURQUOI ça bloque (supposé, non prouvé)

Le mixeur de SDL, appelé par `dynCall` hors de son propre flux, plante :
- **Depuis la minuterie**, c'est la signature de l'item 1 bis (pile C d'une tâche JSPI suspendue écrasée), selon le
  Superviseur. `Module.enterTask()` avant l'appel n'y change rien.
- **Depuis `reconcilier()`**, imbriqué dans Python lui-même, le Worker se fige sans trace. Les traces de console d'un
  Worker qui ne rend plus la main sont perdues.

Alternative écartée : ne pomper que depuis la minuterie de SDL elle-même (son `silenceTimer`). Elle suppose un
contexte « suspended », et SDL ne remplit alors rien.

## Suite proposée

1. Faire produire les échantillons au mixeur de Pyxel côté Python, sans passer par SDL :
   - `pyxel` expose-t-il un rendu PCM, comme `pyxel.save` d'un son ? Le pousser dans l'anneau depuis `reconcilier`.
   - Sinon, attendre le patch Pyodide / JSPI (item 1 bis).
2. La machine chargée (charge 26-44) a rendu des essais instables : le délai de la sonde est passé à 450 s.
