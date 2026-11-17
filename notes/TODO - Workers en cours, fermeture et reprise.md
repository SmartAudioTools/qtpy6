# TODO - Workers qtpy6 en cours : références pour fermer et relancer plus tard

Fichier commité dans le dépôt qtpy6 (`notes/`), déplacé depuis `qtpy6_essais/equipe/` le 13/11 à 00:55 ; les chemins `w<n>/…`, `briefs/…` et `tableau_de_bord.md` restent relatifs à `/DATA/Python/qtpy6_essais/equipe/`.

Écrit le 13/11/2026 à 00:25 par le Superviseur qtpy6 [015c36], à la demande du professeur (00:24 : « stocker les
références/chemins de tout le travail de tes workers en cours dans un TODO, pour qu'on puisse les fermer et les
relancer plus tard »). Dépôt : `/DATA/Python/qtpy6` (git, HEAD 48883d3 à 19:56, index PARTAGÉ entre workers).
Équipe : `/DATA/Python/qtpy6_essais/equipe/` (tableau `tableau_de_bord.md`, briefs `briefs/`, ETAT `w<n>/ETAT.md`).

## État commun au 13/11 00:25

- **Fermés le 13/11 à 00:29** (demande du professeur 00:28), tous les cinq, par `claude-dock.sh fermer`.
- **PAUSE CPU** depuis le 12/11 19:54 (demande du professeur : priorité à l'équipe SmartTeacher) : aucun worker ne lance
  test, sonde Firefox, Node ni construction tant que le Superviseur n'a pas envoyé « REPRISE » (signal attendu du
  Superviseur SmartTeacher). À la relance, le premier message de chaque worker doit DIRE si la pause est levée.
- **Travail NON commité dans la copie partagée** (`git status` à 00:24) : 7 fichiers modifiés, attribués ci-dessous. Chaque
  diff est sauvé dans `w<n>/en_cours_0024.diff` (`git apply` depuis `/DATA/Python/qtpy6` si la copie a bougé entre-temps).
  Non suivis : `essais/spyder/gc_jspi/` (W568), `essais/loupe/`, `essais/profil_rendu/` (propriétaire non établi).
- **Fermer** (sessions restaurées au redémarrage du Dock de 20:02 : le script `claude-fermer-worker.sh` attendrait
  « demarrage » jusqu'à 1 h) : `/home/claude/.claude/hooks/claude-dock.sh fermer <session_id>`.
- **Relancer** : `/home/claude/.claude/hooks/claude-dock.sh reprendre /DATA/Python/qtpy6 <session_id> "Worker <n> qtpy6"
  "<message>"`, message = « Relancé par le Superviseur qtpy6 [réf. du moment]. Relis ton ETAT et ton diff
  `w<n>/en_cours_0024.diff`, vérifie `git status` sur tes fichiers, puis reprends au point RESTE. PAUSE CPU : <levée / tient>. »
  Les briefs citent la référence du Superviseur [015c36] : la mettre à jour (`sed` sur `briefs/`) si le Dock a redémarré.

## W564 — item 11 (interruption par setInterruptBuffer) + waitForStarted (2 bis) + `_RESERVE` morte (+0,5 pt)

- session_id : `3ba6f19e-6b78-4b88-9532-73bcba163713` ; brief `briefs/Worker_564.md` ; ETAT `w564/ETAT.md` ; budget 2,5 pts.
- Fichiers à lui : `qtpy6/web/travailleur.py`, `qtpy6/web/js/travailleur.js`, `qtpy6/web/preambule.py`,
  `qtpy6/web/sous_processus.py`, `tests/test_noyau_web.py`. Note : pas encore écrite (`notes/2026-11-12 - … (W564).md`).
- Non commité (263 lignes, `w564/en_cours_0024.diff`) : waitForStarted codé (test rouge → vert), `_reserve_morte` +
  `test_reserve_morte_n_est_pas_consommee` écrits NON lancés, sonde `interruption_brut.py` prête non lancée, traces
  `W564DBG` dans `preambule.py` (2) et `interruption.py` (1) À RETIRER avant commit (celle de travailleur.py:325 cassait
  3 tests de test_noyau_web en natif, signalée 19:32). Dans `js/travailleur.js`, ses lignes cohabitent avec l'on_fatal
  commité par W568 (1f5d5cf) : rejouer le diff SUR 1f5d5cf.
- RESTE : lancer la sonde interruption (3 cas), rouge→vert de `_reserve_morte`, retirer W564DBG, suite test_noyau_web
  (40 avant), lignes TODO sous 11, 2 bis et 16, note, commit à chemins explicites, vu dans la page par le professeur.

## W565 — item 8 (Pyxel : clavier muet, cadre de focus, « rame »)

- session_id : `6a7bff6b-e2d7-4b32-a2e8-7fd884e8c96a` ; brief `briefs/Worker_565.md` ; ETAT `w565/ETAT.md` ; contexte 76 %.
- Fichiers : `qtpy6/web/pyxel_web.py`, `qtpy6/web/memoire_partagee.py`, `essais/…/spe_monkey.py`.
  Note : `notes/2026-11-12 - Clavier et focus de Pyxel dans la page (W565).md`. Commits : 596b13a (clavier), cb76385
  (instrumentation `&cadence=1`). Rien de non commité.
- 00:50 generator-7f : cadre commité dans spyder_pyxel ba22b71 (non poussé, trait bleu 2 px, 4 tests OK) ; reste à voir à l'œil dans Spyder relancé.
- RESTE (ETAT, « RESTE item 8 ») : (1) après REPRISE, le professeur lance cadence5 (sonde `--visible`,
  URL `&cadence=1&headless=0`, sortie `w565/cadence5.*`), lire « CADENCE noyau » ; (2) cadre de focus : révision chez le
  generator (double trait ou plus épais, 19:06), vérification du professeur ; (3) dire quels restes passent à un
  successeur. Peut être relancé OU remplacé par un worker neuf à partir de l'ETAT (contexte 76 %).

## W568 — item 1, signature console (%runfile → SystemError) ; on_fatal fait

- session_id : `1beb210e-645f-4d0c-afc8-1d308b9ce29c` ; brief `briefs/Worker_568.md` ; ETAT `w568/ETAT.md` ; budget 4 pts.
- Fichiers : `qtpy6/web/qtpy6web.js`, `qtpy6/web/threading_web.py`, `essais/spyder/gc_jspi/` (non suivi), `spe_rf.py`
  instrumenté (app.zip régénéré 19:43). Note : `notes/2026-11-12 - runfile et tache promising imbriquee (W568).md`.
  Commit : 1f5d5cf (on_fatal dans travailleur.js, test node `tests/test_travailleur_js.py`). `bloquant.py` : jamais touché.
- Diagnostic (lu dans les sources) : les 5 SystemError = Pyodide MORT dans le Worker (ast.parse du %runfile) = item 1 ;
  la parade GC et l'item 1 bis restent au plan de nuit (D2 = D, machine calme).
- RESTE : déploiement (reconstruction d'app.zip, lourd : après REPRISE), vu par le professeur (« noyau mort » au lieu des
  5 SystemError), réponse du professeur sur la cause du fatal, ligne TODO sous l'item 1, ETAT final, session_id.

## W569 — item 18, suite (bandeau « Récupération des variables d'environnement » tourne toujours)

- session_id : `67f01ba2-e77b-4d2e-a6cf-d8e6dd8c8f9a` ; brief `briefs/Worker_569.md` ; ETAT `w569/ETAT.md` ; budget 2 pts.
- Fichiers : `qtpy6/web/psutil_web.py`, `essais/spyder/env18_spe.py`. Note :
  `notes/2026-11-12 - Bandeau environnement, suite de l'item 18 (W569).md`.
- Non commité (44 lignes, `w569/en_cours_0024.diff`) : sonde instrumentée `env18_spe.py` (trace Popen, start_kernel).
- RESTE (ETAT « En cours ») : vérification demandée au professeur à 19:50, SUSPENDUE par la pause ; établir si le
  professeur voit la construction d'après a0cc393 ou une régression (commits a0cc393..HEAD sur qtpy6/web/) ; corriger
  dans psutil_web ou demander la ligne à W564 (sous_processus.py) ; ligne TODO sous 18 ; commit ; vu par le professeur.

## Fermés aujourd'hui (pour mémoire, pas à relancer)

W547, W557, W559 (983750ef), W560, W562, W563 (fb621fe7), W566 (c0b44394, 6 commits dont 48883d3), W567 (c16eeed0,
14b8987 f6e2b78 8f8415a, alias natif déployé dans le venv SmartPythonEditor ; installation durable = SmartOS).

## Non attribués, plan de nuit (machine calme, concertation SmartTeacher)

Item 1 bis (patch Pyodide/JSPI, `w545/ETAT.md`), reste de l'item 3 (3 SignalAliasMasked, générateur du fork), item 21
(import par l'alias 760 ms contre 165, banc `qtpy6_essais/w567/mesurer_demarrage.py` + cProfile ; contrainte du
professeur 19:42 : profilage de nuit seulement, CPU libre), item 22 (démarrage de spe.py 62,6 s, `w566/sonde_spe.log`),
item 7 (hébergement, professeur), item 17, Vitesse 3/4/6.

## État au 17/11/2026 17:55 (Superviseur qtpy6 [5fd449]) — nuit et journée du 17/11, tout en pause

Consigne du professeur, 17:36 et 17:51 : « consigne tout dans un ou plusieurs TODO pour pouvoir reprendre plus tard ».
Chronologie complète : `/DATA/Python/qtpy6_essais/equipe/tableau_de_bord.md` (une ligne par événement, 03:27 → 17:51) ;
briefs `qtpy6_essais/equipe/briefs/Worker_572.md` à `Worker_585.md` ; ETAT de chaque worker dans `qtpy6_essais/equipe/w5xx/`.
Commits qtpy6 de la période : 2319f2e (W572) → 2e60039 (W584) + W585 (85c223f et son commit final), aucun poussé.

### Fermés (pour mémoire, pas à relancer)
- W572 2319f2e, W573 0755f7e, W574 3b9ca08/8d340df, W575 5e71ddc/557c87b/7df5008, W576 e1f2e8e/392b3df, W577 4174b11,
  W578 5721323, W579 4d24a5e/735cd91, W580 c46d5ba, W581 4c2efef (item 21 clos), W583 d49df6e/461f852/bddb37f,
  W584 2e60039 (item 1 CLOS, 1 bis diagnostiqué), W582 (item 24, dans 2e60039), W585 (item 23, diagnostic seul).
- Hors qtpy6 : fork Pyxel `/DATA/Python/FORKS/pyxel` branche `qtpy6-vsync` (c398acf, 61c7cad : `pyxel.step`,
  `pyxel.vsync`), dépôt local SANS remote ; greffon natif spyder_pyxel 2601e46 (tube `<shm>.vsync.fifo`), non poussé.
- SmartTeacher W744 796dfde dans qtpy6 (pompe : 16 octets de pile C rendus par callPromising), à pousser avec le reste.

### Où en est chaque sujet
- **Saccades Pyxel web (demande 02:45)** : chaîne complète (grille des balayages W573, fork step/vsync W574, roue W575,
  jonction W580 : 60,0 i/s hors écran). Sur l'écran réel 19-30 % d'images perdues ou doublées : item **24** du TODO
  Portage (W582 : mesures, correctif B tube + QSocketNotifier NON retenu, diff `qtpy6_essais/equipe/w582/correctif_W582.diff`
  sha256 f6f83444…, avis du Superviseur : OffscreenCanvas transféré au Worker + rAF du Worker, sondage d'une heure avant
  toute doublure, repli file d'une image). Question du professeur 17:32 « l'approche la plus proche du hardware » :
  réponse à l'item 24, décision non prise. Reprise : machine calme (charge < 2), six passes alternées.
- **Portage SPE web (demande 02:46)** : item 1 CLOS (W584 : la parade `_doubler_gc` n'a jamais été appliquée, diff en
  note) ; item 1 bis : Pyodide 314.0.7 patché EN PLACE dans `exemple/pyodide` (W579 patch `wasm/patches/pyodide314-pystate-
  masquer-cadres.patch`, W583 ; original `qtpy6_essais/equipe/w583/pyodide_origine_20261117/`, sources
  `/DATA/Python/outils_wasm/pyodide314/pyodide`, produit `w579/dist/`) ; plantage de page après triangles = fermeture de
  Firefox (probable) ; amont déjà corrigé (pyodide PR #6466, issue #6464 close 12/11) : signalement 1 bis d. SANS OBJET,
  au plus demander le rétroportage 314.x. Item 19 : rien à faire (W566). Item 21 clos (4c2efef). Item 22 : mesuré sur
  écran 12,6 s (`w577/ecran_professeur.sh`, post_visible_setup 7,0 s, tas 535 Mio), non attribué. Item 23 : cause
  mesurée (W585), doublure `flush` synchrone proposée (≈ 1 pt), décision du professeur en attente. Item 7 : le site
  embarquait un journal de session (`construire_site.py` corrigé d49df6e, `tests/test_site_sans_session.py`).
- **Site des élèves** `essais/spyder/site/app.zip` : reconstruit depuis HEAD le 17/11 16:30 (W583), à reconstruire par
  `qtpy6_essais/equipe/w572/maj_zip.py` après tout commit, jamais depuis l'arbre de travail.

### À trancher par le professeur (rien ne bouge d'ici là)
1. Diffs NON commités d'autrui, toujours dans l'arbre (156 lignes, `git diff --stat`) : `essais/spyder/env18_spe.py`,
   `qtpy6/web/js/travailleur.js`, `qtpy6/web/preambule.py` (hunk W564DBG : casse le noyau IPython, le site se construit
   depuis HEAD pour l'éviter), `qtpy6/web/travailleur.py`, `tests/test_noyau_web.py` : commit ou corbeille.
2. Item 24 (vsync) : sondage OffscreenCanvas 1 h, ou file d'une image, ou rien.
3. Item 23 : doublure `flush` synchrone (W585, ≈ 1 pt) ou rien.
4. Publier le fork Pyxel (branche `qtpy6-vsync`, aucun remote) ou le garder local.
5. Erreur « pompe : A value of type undefined … was thrown as an error » vue à 15,6 s sur la page w577 (site d'AVANT
   796dfde) : à revoir sur un site d'après ; non reproduite depuis.
6. Pousser qtpy6 et spyder_pyxel (le professeur pousse ; commande dans le message du Superviseur).

### Faits d'environnement utiles à la reprise
Le shell du bac n'a AUCUN réseau (téléchargements par le professeur, `w579/telecharger_pyodide314.sh`) ; le Firefox du
bac n'a pas de WebGL (Pyxel non headless y meurt en `__stack_chk_fail` : ce n'était ni Pyodide ni la pompe) ; les
mesures d'écran ne valent rien sous charge (huit sessions SmartTeacher le 17/11 après-midi, charge 9-14) ;
`w573/ecran_professeur.sh` n'existe pas (les pages d'écran : w577, w578, w580, w582, w583).
