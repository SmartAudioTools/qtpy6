# `subprocess.run` doublé, et SmartTeacher sans `enfant.py` (27/09/2026)

Suite de « qtpy6.web, fusion et trous comblés » (même jour, commit 98269d4). Même but : dire ce qui a été fait, POURQUOI,
ce qui a été écarté, et le niveau de preuve. La doc de référence reste `web.md`.

## 1. Les trois points demandés

1. `subprocess.run` dans le navigateur, comme `QProcess` l'était déjà.
2. Safari : qu'en est-il de JSPI, sur lequel tout `exec()` et toute attente reposent ?
3. En profiter pour simplifier SmartTeacher : plus de `web/enfant.py`, de `python.zip`, de `configurer(…, module=…)`
   ni de `processus_web.py`. Le lecteur lance ses vrais scripts (`console_enfant.py`, `verifier.py`) comme sur le bureau.

## 2. `subprocess.run` (`qtpy6/web/sous_processus.py`, branché par `QtCore.py`)

**Ce qui est fait.** `run()` lance le programme dans un `ProcessusWeb` (Web Worker, Pyodide ordinaire), écrit `input`,
ferme l'entrée, puis attend `finished` suspendu par JSPI (`bloquant._suspendre`), exactement comme `exec()`. Les
tampons sont lus APRÈS `finished` puis répartis selon `stdout`/`stderr` (`PIPE`, `DEVNULL`, `STDOUT`, fichier, hérité).
`subprocess.call` est doublé aussi (le code de retour de `run`) : dans la bibliothèque standard, `check_output`
passe par `run` mais `check_call` par `call`, donc par `Popen`. La première version ne doublait que `run` et sa
docstring affirmait le contraire ; vérifié en relisant `inspect.getsource`, le test couvre maintenant `check_call`
(il échoue sans le doublage de `call`).

**Les choix.**
- *Doubler `subprocess.run` plutôt que `Popen`* : `Popen` promet `poll()`, `communicate()` morceau par morceau, des
  descripteurs de fichier — une surface qu'un worker ne tient pas honnêtement. `run` est un appel qui attend une fin :
  c'est exactement ce que JSPI sait faire, et c'est ce qu'utilisent les scripts réels (dont `verifier.py`).
- *Seul Python se lance* ; tout autre programme lève `FileNotFoundError`, l'erreur qu'un script reçoit déjà sur un
  bureau où l'exécutable manque : le code appelant a déjà le bon `except`, pas d'erreur inventée.
- *`finished` branché par le `connect` de PyQt* (`bloquant._connect_qt`), pas par le relais qui reporte les slots d'un
  tour : le relais retarderait la reprise sans rien protéger ici.
- *Hors d'une entrée suspendable, `RuntimeError`* plutôt qu'un blocage : même règle que `exec()`, une méthode virtuelle
  appelée par Qt ne peut pas attendre, autant le dire tout de suite.
- *Canaux séparés* (`sortie_erreur` dans `travailleur.js`, `readAllStandardError`, `MergedChannels`) : sans eux,
  `capture_output` rendait stderr dans stdout, et un verdict de correction mélangé à la trace d'erreur de l'élève.

**Écarté.** Un `subprocess.run` exécuté dans le Pyodide de la page (exec du script en place) : pas d'isolation (l'élève
écrase les modules du lecteur, une boucle infinie gèle la page, pas de `timeout` possible). Le worker coûte ~1,4 s par
lancement, mesuré acceptable ci-dessous.

## 3. Safari et JSPI

Safari n'a JSPI qu'à partir de la **27** (bêta annoncée à la WWDC de juin 2026) : un iPad ou un iPhone en 26 ne lance
AUCUNE application qtpy6, puisque la page elle-même en a besoin (Pyodide-Qt ; mesuré sous Firefox en coupant
`javascript.options.wasm_js_promise_integration` : « WebAssembly stack switching not supported », rien ne démarre).
Non essayé sur un appareil Apple. Sources :
- https://webkit.org/blog/17967/news-from-wwdc26-webkit-in-safari-27-beta/
- https://webkit.org/blog/17848/release-notes-for-safari-technology-preview-238/
- https://caniuse.com/wasm-jspi
- https://github.com/WebKit/standards-positions/issues/422

Écrit dans `web.md` à deux endroits (« Le worker », limites) : c'est une contrainte de déploiement, pas un détail.

## 4. Deux défauts de qtpy6 trouvés en y passant SmartTeacher

Aucun test de qtpy6 ne les voyait : c'est le premier vrai script lancé tel quel qui les a montrés.

1. **`ValueError: I/O operation on closed file` dans la console Python.** `console_enfant.py` enveloppe
   `sys.stdin.buffer` puis remplace `sys.stdin`. Sur un bureau, `sys.__stdin__` garde l'ancien objet en vie ; dans le
   worker il n'y avait que `sys.stdin`, donc l'ancien enveloppeur était ramassé et FERMAIT le tampon partagé. Correctif :
   `sys.stdin = sys.__stdin__ = …` dans `travailleur.js` — reproduire le bureau plutôt que d'adapter le script.
2. **`FileNotFoundError: '/tmp/tmpXXXX'` au `chdir`.** Le parent crée un dossier vide (`tempfile.mkdtemp`) et y lance
   l'enfant ; `_zipper` n'écrivait que des fichiers, le dossier vide n'existait pas de l'autre côté. Correctif : une
   entrée par dossier. Contre-épreuve faite : la version sans correctif rend le zip SANS le dossier vide, le test
   `test_zipper_chemins_depuis_la_racine_sans_doublon` échoue alors.

**Et l'ancien contrat retiré.** `configurer(indexURL, archives, module, fonction, cwd)` faisait de `ProcessusWeb` une
façade sur un `Travailleur` (chaque ligne écrite passée à `module.fonction(ligne)`) : c'était le chemin de `enfant.py`.
SmartTeacher parti, `grep` ne lui trouve plus aucun appelant ; il est retiré (`configurer(indexURL)` seul, plus de
`_demarrer_module` ni de branches `self.travailleur` dans `write`/`kill`, paragraphe de `web.md` supprimé). `Travailleur`
lui-même reste : `exemple/compteur.py` et `web.md` (« Le mode module ») s'en servent. Garder deux contrats pour une même
classe, c'était doubler les chemins à tester pour un appelant qui n'existe plus.

## 5. SmartTeacher (hg)

- `processus_web.py` et `web/enfant.py` supprimés ; `python.zip` n'est plus construit ni déployé
  (`construire.py`, `deployer.sh`, READMEs, note de déploiement). `lecteur.zip` embarque `console_enfant.py`,
  `verifier.py`, `bac_a_sable.py`, `pyxel_factice.py` : le worker reçoit le dossier du script par `ProcessusWeb`.
- `pont.configurer(pyodide)` : plus que l'URL du Pyodide des workers.
- `verifier.py` : `sqlite3` importé au besoin. Le Pyodide-Qt de la page n'a pas `sqlite3`, et `modele` importe
  `verifier` ; le SQL, lui, s'exécute dans le worker qui l'a.
- `modele.Code.soumettre` : la correction appelle `noyau.Code._verifier` (donc `subprocess.run`) dans un
  `QTimer.singleShot(0, …)` — un slot, seule entrée où l'attente est permise — et la question reste grisée pendant ce
  temps. Écarté : corriger APRÈS la soumission côté pont (l'ancien `pont.epreuve_code`), qui faisait un second chemin
  de correction propre au navigateur.
- `noyau.Code.epreuve()` (un dict JSON pour l'ancien pont, devenu mort) remplacé par `testee()` : la seule question
  qu'on lui posait encore.
- **Le tactile en natif** (le lecteur tournera sur des PC tactiles) : `tactile.detecte()` ne regardait que le navigateur
  (`any-pointer: coarse`) ; en natif il interroge maintenant `QInputDevice.devices()` (un `TouchScreen` parmi eux), et
  `lecteur.py` active de lui-même les cibles au doigt (`--tactile` force toujours). Choix : même règle que le navigateur,
  un écran tactile présent compte même si l'élève se sert de la souris — le rendu d'un PC tactile change donc (cibles de
  44 px), accepté par l'utilisateur. Écarté : QScroller partout ou un style « doigt » de Qt, qui n'existe pas.

## 6. Niveau de preuve

- qtpy6 : `tests/test_web.py`, 21 réussis (dont `test_subprocess_run_doublé_dans_le_navigateur` et le zip).
- SmartTeacher : `tests_modele.py` vert ; sonde du lecteur dans Firefox (`qtpy6.web.sonde`), en local :
  - `essais_types` (SQL) : console libre en 1,5 s (2,0 s avant), `6*7` → 42 ; soumettre : grisée, puis 2/2 en 2,0 s ;
  - `exemple_tp` (Python) : console libre en 2,0 s, 42 ; soumettre : 3/3 en 1,5 s ;
  - `rendre` : copie enregistrée dans les deux cas.
  - rejoué après le retrait de l'ancien contrat : `essais_types` console 42, `exemple_tp` console 42 et soumettre 3/3 en 2,0 s.
- Tactile natif : `test_tactile_detecte_en_natif` (périphériques simulés, 22 réussis ; échoue si `detecte()` rend
  `False` en natif). Non essayé sur un vrai écran tactile : il n'y en a pas ici, et `offscreen` n'en recense aucun.
- Non essayé : en ligne (GitHub Pages + Dropbox) après ce changement, et tout appareil Apple.

## 7. À vérifier en priorité par un relecteur

- `sous_processus.run` et le `timeout` : `p.kill()` puis lecture des tampons — un worker tué rend-il ce qu'il avait écrit ?
- `_zipper` zippe les dossiers du script, du `cwd` et du tempdir : un `cwd` très gros (dossier personnel) serait copié entier.
- Le `QTimer.singleShot` de `soumettre` : deux clics rapides lancent-ils deux corrections ? (la question grisée devrait l'empêcher).
