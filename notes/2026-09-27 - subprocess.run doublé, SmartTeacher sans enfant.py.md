# `subprocess.run` doublé, et SmartTeacher sans `enfant.py` (27/09/2026)

Suite de « qtpy6.web, fusion et trous comblés » (même jour, commit 98269d4). Même but : dire ce qui a été fait, POURQUOI,
ce qui a été écarté, et le niveau de preuve. La doc de référence reste `web.md`.

## 1. Les demandes

La demande, mot pour mot : *« commence par documenter tout ce que tu as fait dans /DATA/Python/qtpy6/notes/, ajoute des
instruction dans CLAUDE.md général à mon profil, pour systematiquement commenter ce qui a été fait et les choix que tu
as fait argumenté. puis commite qtpy6 et enfin aborde les 3 points. »* La note de l'étape précédente est « qtpy6.web,
fusion et trous comblés » (commit 98269d4). La règle est dans `Commun/config_files/Claude/CLAUDE.md` de SmartOS, révision 170,
avec comme déclencheur la demande d'autorisation de commiter. Les trois points :

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

## 5 bis. Les questions posées en chemin, et leurs réponses

- *« tout ce qui est spécifique au web ne se charge que si sur le web ? »* Oui, mesuré sur le bureau par `sys.modules`
  après le démarrage du lecteur : sont chargés seulement `qtpy6.web` (pour `navigateur()` et `application()`), `tactile`
  et `dispositions` (`Rangee` sert aussi en natif). Ne sont PAS chargés : `travailleur`, `sous_processus`, `bloquant`,
  `fils`, `stockage`, ni `js`, `pyodide` ou `sqlite3`. Les modules Qt de qtpy6 n'importent les doublures que sous
  `sys.platform == 'emscripten'`. Non fait : sortir `tactile` et `dispositions` de `qtpy6.web`. Ils servent aussi en natif,
  mais ce déplacement ne coûtait que des imports à renommer et n'a pas été demandé.
- *« le tactil n'est pas intégré dans Qt ? »* En partie. Qt fournit les `QTouchEvent`, la conversion d'un toucher en
  clic, et `QScroller` (défilement au doigt, jamais activé d'office : `tactile.defiler_au_doigt` le branche). Les styles
  de Qt Widgets n'ont en revanche aucun mode « doigt » : aucun ne grossit les boutons, les cases ou l'ascenseur. C'est ce
  que fait `tactile.activer`, par une feuille de style ajoutée à celle de l'application.
- *« ça garderait le meme rendu ? c'est un bonne idée ? »* puis *« le lecteur natif va tourner sur des pc tactiles »*.
  Sur un PC sans écran tactile, le rendu est identique (capture hors écran). Sur un PC tactile, il change (cibles de 44 px),
  et c'est voulu. D'où la détection native (§5).

## Le commit de SmartTeacher (révision 134) : les modifications d'une autre session laissées de côté

`QCM/README.md` et `QCM/modele.py` contenaient aussi le travail en cours d'une autre session (la classe `Paresse` et son
import de `QCoreApplication`, liés à `sonde_fluidite.py` ; deux passages du README). Seuls mes passages ont été commités :
version d'origine plus mon patch, commit, puis remise du fichier complet. Vérifié ensuite par `hg diff` : il ne reste
modifié que le travail de l'autre session. Écarté : `hg commit -i` avec les réponses envoyées d'avance, car avec dix
passages par fichier un décalage d'une seule réponse aurait commité le travail de l'autre session.

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

## 7. Les trois points laissés au relecteur, vérifiés ensuite (même jour)

Demande de l'utilisateur : « il reste des choses à faire ? », puis « oui » pour que je mène seul les trois vérifications.
Mesures dans Firefox (sonde, lecteur `essais_types`, un scénario jetable non versionné).

- **`timeout` de `sous_processus.run`** : `TimeoutExpired` levée à 4,2 s pour `timeout=4` ; la sortie écrite avant le
  `kill()` est rendue, qu'elle ait été vidée ou non (`'vidé\nnon vidé\n'`) ; une boucle infinie est arrêtée à 4,0 s avec
  sa sortie (`'go\n'`). Après une fin normale, le `QTimer` du délai ne lève rien. Rien à changer.
- **`_zipper`** : le dossier du script, dans le lecteur, est `/lecteur` (12,7 Mo : polices 7,6 Mo, pygments 4,5 Mo), zippé en
  0,05 s à chaque lancement ; `cwd` (`/home/pyodide`) et `/tmp` sont petits. Lancement complet d'un script de trois lignes :
  1,41 et 1,48 s depuis un petit dossier, 1,51 et 1,59 s depuis `/lecteur` — le zip coûte donc environ 0,1 s. Laissé tel
  quel : filtrer les dossiers copiés ajouterait une règle (quoi exclure ?) pour un gain invisible. Le cas d'un `cwd` énorme
  reste possible pour une autre application ; il n'existe pas dans SmartTeacher.
- **Double soumission : vrai défaut, corrigé dans SmartTeacher** (`modele.py`, `Code.soumettre`). Griser la question
  n'empêchait pas un second appel par programme : « Corriger mes réponses » (`noyau.soumettre_tout`) appelle `soumettre()`
  sur chaque question non fermée, y compris celle dont la vérification est en cours. Mesure : deux `soumettre()`
  d'affilée lançaient **2 workers**, et le second verdict fermait la question (seconde chance perdue). Correctif : un
  drapeau `en_correction`, posé avant le `QTimer.singleShot` et levé dans le verdict ; un appel pendant la correction
  ne fait rien. Même mesure après : **1 worker**, verdict unique, question fermée une fois. `tests_modele.py` vert.
  Écarté : se fier à `isEnabled()` — `setEnabled(False)` d'un parent grisé rend le même `False`, et le drapeau dit ce qu'il
  veut dire.
