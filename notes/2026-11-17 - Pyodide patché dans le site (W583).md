# Pyodide patché dans le site (W583, 17/11/2026)

## Demande

Le professeur, 17/11/2026 11:41 (question du Superviseur) : « Oui, dans le site maintenant » — remplacer le Pyodide 314.0.7
d'origine du site des élèves par le 314 patché de W579 (note `2026-11-17 - Patch pystate de Pyodide compilé et rejoué
(W579).md`), rejouer la suite et la sonde ; il vérifie ensuite sur son écran avec le triangle.
Puis, 12:00-12:01, sur le partage du dossier avec W582 : « et le prévenir que tu vas changer pyodide et que ça peut fausser
ces mesures », « sinon il faut lui demander d'arrêter, changer pyodide et lui demander de reprendre tous ces tests.
choisis la meilleure option ».

## Inventaire (avant tout geste, relevé `releve`)

| Dossier `pyodide/` | Cible réelle | Rôle | `pyodide.asm.wasm` sha256 |
|---|---|---|---|
| `qtpy6/exemple/pyodide/` | lui-même (ignoré par git, `.gitignore:8`) | **le Pyodide du Worker du noyau** de `essais/spyder/site` (lien `site/pyodide`) et de 16 sites d'essai de workers (w546, w549, w550, w557, w565, w572, w573 ×2, w575, w577 ×2, w578, w580 ×2, w582) | `cc36e3ca…` (origine) → `72077364…` (patché) |
| `qtpy6/site/pyodide/` | lui-même (ignoré, `site/`) | démo du 27/09 (lecteur QCM de qtpy6) : aucun fichier du site ne lit `./pyodide/` (grep : 0) | `cc36e3ca…`, **laissé d'origine** |
| `w579/dist/` | lui-même | produit patché (sans `-g`) | `72077364…` |
| `w579/dist_origine/`, `w579/dist_g2/` | eux-mêmes | témoin d'origine ; patché avec noms | `cc36e3ca…` ; `3df441f7…` |

- `construire_site.py` ne crée pas `pyodide/` (il ne lie que `pyodide-qt`) ; le lien `essais/spyder/site/pyodide` date
  du 12/10. Le site n'a donc pas à être reconstruit, et `construire_site.py` n'est pas modifié.
- Lecteur QCM de SmartTeacher : `QCM/web/pyqt6/index.html:66` prend Pyodide sur le CDN (`cdn.jsdelivr.net/pyodide/v314.0.7`)
  → non concerné ; pas de ligne au Superviseur SmartTeacher (contrainte conditionnelle du brief), pas de suite à rejouer.
- Compatibilité : même tag (`pyodide.mjs` « 314.0.7 » des deux côtés) ; `pyodide-lock.json` **identique octet à
  octet** (`cmp`), info `{abi 2026_0, wasm32, emscripten_5_0_3, python 3.14.2}`, 357 paquets ; `pyodide.mjs`
  (`6f1d60f7…`), `python_stdlib.zip` (`fa1957e5…`), `pyodide-lock.json` (`5dc2fc11…`) identiques. Seuls changent
  `pyodide.asm.wasm` et `pyodide.asm.mjs` (`f7cdc8ec…` → `0ae669a2…`).

## FAIT

1. Original sauvé (les 5 fichiers) : `/DATA/Python/qtpy6_essais/equipe/w583/pyodide_origine_20261117/`, sommes
   identiques à l'inventaire.
2. Premier essai de copie (11:59) refusé par le garde-fou automatique (dossier partagé) ; question au professeur, puis
   W582 (seul worker actif dont le site lit ce dossier) mis en pause : « en pause (aucune mesure en cours) ».
3. **12:02** : `cp w579/dist/pyodide.asm.{mjs,wasm} exemple/pyodide/` sur la cible réelle (vérifiée `readlink -f`,
   aucun lien traversé) ; sommes après copie = `w579/dist`. W582 prévenu (« en place 12:02 »), il refait ses mesures.

## POURQUOI

- Copier deux fichiers plutôt que les cinq : les trois autres sont identiques ; on ne change que ce que le patch change.
- Pause de W582 plutôt qu'attente de la fin de son item : une mesure sur l'ancien Pyodide serait périmée dès le
  changement (décision demandée par le professeur à 12:01, « choisis la meilleure option »).

## Alternative écartée

- Pointer `essais/spyder/site/pyodide` vers `w579/dist` (lien) : le site des élèves dépendrait d'un dossier d'équipe
  temporaire, et les 16 sites d'essai liés à `exemple/pyodide` resteraient sur l'ancien Pyodide (deux Pyodide en
  service, mesures non comparables).
- Patcher aussi `qtpy6/site/pyodide/` : rien ne le lit.

## Preuves

- Sommes après copie : `pyodide.asm.wasm` `72077364…`, `pyodide.asm.mjs` `0ae669a2…` (= `w579/dist`) ; les trois autres
  inchangés.
- `tests/test_web.py` entier (`testeur`) : **65 passés, 0 échec**, 104,6 s ; aucune ligne pyodide.asm, out of bounds,
  unreachable, fatal.
- Triangle sans affichage, site en place (`w583/tri.sh`, `spe_m4.py` de W579, jeu headless, `--delai 90`), 3 passes :
  | | noyau vivant (« JEU load OK », K4) | erreur du Worker | erreur côté page (pyodide-qt 0.29.3) |
  |---|---|---|---|
  | sans parade | 3/3 | 0 | 2/3 (promisingApply ; fatal shibokensupport `feature_import` à 91 s) |
  | avec parade (`_doubler_gc`) | 3/3 | 0 | 1/3 (NoGilError puis `index out of bounds`, `tourner` → callPromising) |
  Les erreurs de page sont hors du patch (Pyodide-PySide6 de la page, pas le 314 du Worker) : piste W553 de l'item 1 bis.
  Journaux `qtpy6_essais/equipe/w583/tri_{sans,avec}_{1,2,3}.*` ; premier lot raté (site incomplet) dans `rate_1215/`.
- Sonde `spe.py` au démarrage (sans affichage) : 6,5 s puis **7,1 s après reconstruction du zip**, tas 215 Mio, état
  ouvert, aucune erreur console nouvelle, aucune `AttributeError isDir`. W577 : 12,6 s / 535 Mio, mais sur l'écran réel
  (conditions différentes, non comparables). `w583/demarrage{,2}.*`.

## Site des élèves reconstruit depuis HEAD (16:30), fuite d'un journal de session

- Au premier passage du professeur (12:52), « 'NoneType' object has no attribute 'isDir' » au démarrage :
  `essais/spyder/site/app.zip` datait d'avant le correctif de W578 (5721323, `bloquant._mode`, 17/11 03:09). Reconstruit
  (Superviseur, 16:29) **depuis HEAD** par `git show` (`w583/zip_depuis_head.py`), jamais depuis l'arbre de travail
  (hunk W564DBG non commité de `preambule.py`) : 16 fichiers `qtpy6/` remis à HEAD, `.pyc` correspondants retirés ;
  sha256 `185c36ad…` → **`653033df…`** ; ancien zip : `w583/app_site_avant_20261117.zip`.
- **Fuite** : l'ancien zip contenait 14 chemins cachés, dont `qtpy6/.claude/conversations/26b90c3c….jsonl` (2 Mo, un
  journal de session) et `spyder_pyxel/.claude/…`, `spyder_pyxel/.mcp.json`. Cause : `qtpy6/web/assembler.py` copie le
  dossier entier de chaque paquet (`rglob`) sans exclure les fichiers cachés depuis sa création (9520399, 27/09) ; exclusion
  ajoutée par W577 (4174b11, 17/11 03:10) pour `paquets=` seulement ; `spyder_pyxel/` passe par `fichiers=`
  (`_greffons()` de `construire_site.py`), hors de ce filtre. **Le site n'est pas hébergé** (TODO item 7) : rien n'est
  sorti de la machine.
- Correctif : `construire_site.py`, `Zip.write` écarte tout nom dont une composante commence par « . » (`.claude/`,
  `.mcp.json`, `.git*`) ou finit par `.jsonl`. `__pycache__` n'est PAS exclu : les `.pyc` précompilés de l'assembleur y
  sont voulus (démarrage). Garde `tests/test_site_sans_session.py` : **rouge sur l'ancien zip, vert sur le nouveau** ;
  construction complète privée (`--sortie w583/site_verif`, depuis l'arbre de travail, jamais servie) : 0 chemin caché.
- `spe_m4.py` du site (12/10) périmé : AssertionError l. 13 (motif `travailleur.configurer` retiré de `spe.py`, déjà
  noté par W579, item 1). Page d'écran : `w583/spe_ecran.py` (spe_m4 de W579 sans le forçage `headless=True` qu'il
  ajoute pour le bac) dans une copie du zip (`w583/site_ecran`).

## VÉRIFIÉ

- Pyodide patché en place, suite web verte, triangle sans affichage 6/6 noyau vivant : **mesuré**.
- Écran du professeur (`w583/ecran_professeur.sh`) : passage de 12:52 sur l'ancienne page (jeu forcé headless,
  triangle automatique, « JEU load OK », pas de fatal), dossier `w583/ecran_1252/`. 16:35-17:05 : `--visible` oublié
  par moi dans la réécriture du script, Firefox sans affichage 30 min (`ecran_1635_invisible/`) : deux triangles
  automatiques, « JEU load OK » deux fois, noyau vivant ; fatal de la PAGE à 1800 s (`shibokensupport/feature.py:94`
  `feature_import`, à la fermeture par la sonde), même signature que `tri_sans_2`. **17:05-17:18, Firefox visible,
  écran du professeur** : triangle automatique → `%runfile` (In [1]), jeu Monkey affiché et animé dans le panneau Pyxel
  (capture `w583/ecran.png` à 17:18), aucune erreur Pyodide ni du Worker ni de la page dans la console (seulement le
  bruit de Firefox) ; « Failed to initialize a device » (son SDL) en console du noyau ; une boîte d'erreur de Spyder,
  `KeyError` dans `qtconsole _handle_execute_reply` (nouveau, TODO item 23). La console n'a qu'un `In [1]` : les clics
  suivants n'ont pas donné de second `%runfile` (le jeu tourne toujours, le noyau est occupé). **Noyau vivant pendant
  13 min de jeu, un seul triangle prouvé à l'écran** ; « plusieurs triangles » n'est prouvé que sans affichage (6/6).
