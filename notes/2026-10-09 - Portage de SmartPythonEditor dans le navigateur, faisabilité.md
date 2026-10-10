# Porter SmartPythonEditor (Spyder 6.1.5) dans le navigateur par `qtpy6.web` : étude de faisabilité

Note du 09/10/2026. C'est une ÉTUDE : rien n'a été écrit, rien n'a été construit, rien n'a tourné dans un navigateur.
Tout vient de la lecture des deux dépôts ce jour-là (`/DATA/Python/FORKS/SmartPythonEditor`, fork de Spyder 6.1.5 ;
`/DATA/Python/qtpy6`, `web.md` et `wasm/`) ; le relevé chiffré sur Spyder a été fait par un sous-agent (grep), les
points qui tranchent ont été relus à la main. Le niveau de preuve est donné section par section.

## La demande, citée

« pourrais-tu evaluer la faisabilité de porter SmartPythonEditor sur qtpy6 avec le backend web ? »

## Décision de l'utilisateur (09/10/2026, 20 h 24)

« je veux un vrai éditeur dans le navigateur, pas juste étendre le lecteur de SmartTeacher » : la voie C est écartée
par l'utilisateur, la voie B (Spyder allégé, transport réécrit) est la cible. Premier jalon lancé le soir même : le
`CodeEditor` de Spyder (coloration, pliage, numéros, `lsp_mixin`) dans une page `qtpy6.web`, chargé et mesuré par la
sonde (`essais/spyder/`, hors dépôt tant que ce n'est pas concluant). Les dépendances pures manquantes de SmartPython
(qtawesome, qdarkstyle, qstylizer, qtconsole, superqt, pyuca, intervaltree, diff-match-patch, textdistance) sont
téléchargées par l'utilisateur dans `essais/roues/` : le venv Spyder 3.13.15 est illisible depuis le bac à sable.

### Résultat du jalon 1 (09/10/2026, 20 h 47) : le `CodeEditor` de Spyder tourne dans le navigateur

Mesuré avec `essais/spyder/` (`editeur.py` : le script, le même sur le bureau et dans la page ; `construire_site.py` : le
site), par la sonde de qtpy6 (Firefox 155 sans interface, page et Pyodide-Qt servis en local, donc **sans le coût du
réseau** : 25 Mo d'archive plus Pyodide-Qt à télécharger sur un vrai hébergement). Capture vérifiée (`capture_web.png`) :
thème sombre, numéros de ligne, coloration Python, ligne de marge, surlignage de la ligne courante — le même rendu que sur
le bureau (`capture_bureau.png`).

| Mesure | Navigateur | Bureau (SmartPython 3.13, offscreen) |
|---|---|---|
| Pyodide-Qt chargé | 0,55 s | — |
| archive dépaquetée, Python lancé | 1,78 s | — |
| `import CodeEditor` | 0,73 s | 0,54 s |
| `CodeEditor` créé, fenêtre montrée (depuis le début du script) | 0,84 s | 0,86 s |
| durée totale, de la page au premier rendu | **2,7 s** | 1,4 s avec la capture |
| tas WebAssembly après le rendu | **86 Mio** (104 à un essai précédent, même site) | — |
| archive `app.zip` | 25 Mo compressés, 70 Mo dépaquetés, 9 584 fichiers | — |

Ce que pèse l'archive : Spyder 14 Mo (sans `plugins/help/utils/js/`, MathJax, 28 Mo, ni `locale/`, 6 Mo, ni les
`tests/`), jedi 14,6 Mo, pygments 8 Mo, qtawesome 6 Mo (polices d'icônes), wcwidth 4 Mo, IPython 4 Mo, prompt_toolkit 3 Mo,
qtpy6 2,6 Mo, qdarkstyle 2,6 Mo, polices DejaVu 2 Mo. Les `.pyc` sont compilés à l'assemblage (Python 3.13 des deux côtés).

Ce qu'il a fallu pour y arriver, et qui mesure l'écart entre Spyder et le navigateur à ce stade :
  - **neuf doublures** de modules absents, toutes minimales (`editeur.py`) : psutil, pickleshare, three_merge, jellyfish,
    bcrypt, keyring et keyring.errors, inflection (celle-ci avec de vrais `underscore`/`camelize`, qstylizer s'en sert) ;
  - **les classes que Qt-WASM n'a pas, posées sur PySide6** : qtpy (celui de Spyder) lit `QThread`, `QMutex`… dans
    `PySide6.QtCore` ; qtpy6 les double, mais dans ses propres espaces de noms. Le script recopie sur chaque module PySide6
    les classes `Q…` de qtpy6 qui y manquent, avant d'importer qtpy (dans la page seulement) ;
  - `spyder/locale/` créé vide (Spyder ne fait que le lister) ; qstylizer en `--distribution` (il relit sa version par
    `importlib.metadata`) ; les `tests/` exclus de l'archive (un cas de test contient une `SyntaxError` voulue, qui
    fait échouer la compilation des `.pyc`) ;
  - **une incompatibilité réelle entre qtpy6 et Spyder, trouvée sur le bureau** : voir « Points ouverts ».

Ce que le jalon ne mesure pas : la frappe (aucune touche envoyée), la complétion et le LSP (`lsp_mixin` importé, jamais
connecté), le pliage sur un vrai fichier long, la mémoire après une heure d'édition, le chargement sur un réseau réel.

### Résultat du jalon 2 (09/10/2026, 22 h 50) : on édite pour de vrai dans la page, et la mémoire ne bouge pas

Demande de l'utilisateur (22 h 20) : « lance le jalon 2, en essayant d'économiser au maximum les tokens, pour ça délègue au
maximum à des modèles moins gourmands ». Mesuré avec `essais/spyder/jalon2.py` (le même script sur le bureau et dans la
page, lancé par `site/index.html?script=jalon2.py`), sur `editeur.py` recopié jusqu'à 2 000 lignes. Les gestes qui comptent
sont RÉELS : un clic de souris et 29 touches envoyés par le navigateur (sonde `--pilote`), pas des événements Qt
synthétiques — ce sont eux qui traversent Qt-WASM, le relais de `bloquant` et le `keyPressEvent` de Spyder. Le reste
(sélection par Maj+Bas, pliage, annulation) est fait par l'API de l'éditeur, identique des deux côtés.

| Mesure (deux lancements de la page, machine chargée) | Navigateur | Bureau (offscreen) |
|---|---|---|
| texte de 2 000 lignes posé (coloration, numéros) | 230–460 ms | 126 ms |
| clic réel dans l'éditeur, jusqu'au rendu (aller-retour sonde compris, ~0,5 s) | 0,9–1,0 s | — |
| frappe de 29 touches réelles, dont 3 Entrée avec indentation automatique | 1,2–1,4 s (trajet Selenium touche par touche compris) | 19 ms (QKeyEvent) |
| annulation des 6 pas, texte d'origine retrouvé | 36 ms | 6 ms |
| tout sélectionner, rendu | 7–22 ms | 6 ms |
| Maj+Bas × 50, rendu | 93–254 ms | 29 ms |
| 247 plis calculés (ast) et posés | 51–113 ms | 116 ms |
| classe de la ligne 95 repliée, rendu | 22–51 ms | 12 ms |
| tas WebAssembly, du premier rendu à la fin (après gc) | **103 Mio, stable** | — |
| script entier | 3,8–5,2 s | 1,4 s |

Tout passe (« frappe : ok », « annulation : ok », « pli : ok » dans `sonde_jalon2.log` et `jalon2_bureau.log` ; captures
`capture_jalon2_plie.png` / `_fin.png` dans la page, `capture_jalon2_bureau_plie.png` / `_fin.png` sur le bureau). Le tas
ne grossit pas d'un Mio entre le premier rendu et la fin : rien ne fuit sur ces gestes-là. Les durées de la page sont 2 à
8 fois celles du bureau sur ce qui rend (sélection, repli), mais toutes sous 100 ms hors frappe pilotée ; le ressenti
d'un vrai utilisateur reste à voir à la main (point ouvert).

Ce qu'il a fallu corriger, et qui n'était pas dans Spyder :
  - **un défaut de qtpy6 (`web/bloquant.py`), corrigé** : tout slot Python connecté à un signal est reporté dans une tâche
    (pour qu'un `exec()` puisse y suspendre). Spyder émet `sig_key_pressed.emit(event)` DANS `keyPressEvent` et lit
    `event.isAccepted()` juste après : reporté, le slot (`ScrollFlagArea.keyPressEvent`, closebrackets, snippets,
    codefolding) lisait un QKeyEvent déjà détruit par Qt (`RuntimeError … already deleted`, 116 fois pour 29 touches) et
    son `accept()` venait trop tard. Correctif, une condition : un slot dont un argument est un `QEvent` s'exécute sur
    place. Écartés : cloner l'événement avant le report (ne règle que la destruction, pas l'`accept()` tardif : un
    crochet inséré deux fois) ; ne pas reporter les seuls QKeyEvent (même piège pour les autres événements). Ce que ça
    coûte : un tel slot ne peut plus suspendre (un `exec()` y rend un abandon et avertit) — aucun cas connu ;
  - **un défaut de la sonde (`web/sonde.py`), corrigé** : `"\n"` envoyé tel quel au navigateur donne un KeyboardEvent de
    touche `"\n"`, que Qt-WASM rend en Key 0xa, pas `Key_Return` : Spyder n'y voyait pas une Entrée, et QPlainTextEdit
    n'insère pas un caractère non imprimable (3 touches perdues sur 29, trouvé par un filtre d'événements dans la page).
    `"\n"` est maintenant la touche Entrée (Firefox : `Keys.ENTER` ; Chromium : `key="Enter"`). Un vrai utilisateur
    n'était pas touché : son clavier envoie `"Enter"` ;
  - **le pliage sans LSP** : Spyder reçoit ses plis d'un serveur de langage ; ici ils sont calculés par `ast` (classes,
    fonctions, `if`/`for`/`with`… de plus d'une ligne) et posés par `_update_folding_info` + `_finish_update_folding`,
    ce qui exerce le même chemin que le LSP (`merge_folding`, qui a demandé `textdistance` dans l'archive). Piège trouvé
    sur le bureau : les clés de pli sont 1-based, `toggle_fold_trigger` veut le PREMIER bloc à cacher ;
  - `preparer.py` : le préambule commun des essais (doublures, chemins, `etape`), sorti de `editeur.py` plutôt que recopié ;
    `construire_site.py` : un seul site, `?script=` choisit l'essai (sinon deux archives de 25 Mo pour un script de 250
    lignes) ; chaque étape chaînée par QTimer est gardée : une exception pose `window.etat = "erreur"` au lieu de laisser
    la sonde attendre jusqu'au délai (premier lancement perdu à ça).

Ce que le jalon ne mesure pas : la mémoire après une heure (le gc est appelé une fois), le défilement à la molette, la
complétion, un rendu jugé à l'œil par l'utilisateur dans son navigateur.

### Résultat du jalon 3 (09/10/2026, 23 h 15) : le programme de l'élève tourne dans un Worker, la console de Spyder suit

Demande de l'utilisateur (22 h 54) : « lance le jalon 3 ». Mesuré avec `essais/spyder/jalon3.py` (bureau et page,
`site/index.html?script=jalon3.py`, sonde `--pilote`) : le `CodeEditor` de Spyder au-dessus, et en dessous le widget de
console de Spyder (`ShellBaseWidget`, celui de sa console interne) relié comme un terminal à un `qtpy6.QtCore.QProcess` —
dans la page, `ProcessusWeb` : le programme de l'élève est lancé par `start(sys.executable, ["-u", script])` dans un Web
Worker neuf, avec le Pyodide-Qt du site comme interpréteur (`travailleur.configurer("./pyodide-qt/", filtre=…)`, l'archive
envoyée au Worker réduite au dossier de l'élève). Trois programmes : (1) à froid, deux `input()` tapés dans la console par
de vrais clics et de vraies touches, 1 000 lignes, un calcul d'une seconde, une exception ; (2) un Worker préchauffé
(`prechauffer()`), boucle infinie, `kill()` après une seconde ; (3) le même programme (1) en `exec()` dans l'interpréteur
de la page, pour comparer. Un `QTimer` de 50 ms mesure le plus long silence de la page pendant que l'élève calcule.

| Mesure (deux lancements de la page qui passent, charge machine 8 ; bureau offscreen, même charge) | Navigateur (Firefox, Worker) | Bureau (QProcess) |
|---|---|---|
| console de Spyder créée, premier rendu | 17 ms, 9 ms | 9 ms, 7 ms |
| programme 1, Worker à froid : premier octet reçu (Pyodide démarré, archive dépliée, script lancé) | **249–531 ms** (4 lancements) | 37 ms |
| réponse à un `input()` revenue, depuis la demande du geste | 925–968 ms, dont **730–830 ms de clic Selenium** ; ~150–190 ms propres à la page (frappe, Entrée, stdin du Worker, retour) | 2 ms |
| programme 1 entier (1 000 lignes, 5 000 000 d'itérations, traceback), gestes compris | 3,6 s | 0,4 s |
| plus long silence de la page pendant le programme 1 | **63 ms** sur 71 tics (la page reste réactive) | 50 ms |
| programme 2, Worker préchauffé : premier octet | **23 ms** | 22 ms |
| `finished` après `kill()` | 2 ms | 1 ms |
| programme 3, `exec()` dans la page : durée | 802 ms, **page figée** (0 tic) | 307 ms, figé |
| tas WebAssembly de la page, du premier rendu à la fin | **103 Mio, stable** (le Worker a le sien, non mesuré) | — |
| script entier | 10,7 s | 3,3 s |

Tout passe : « sortie : ok », « traceback : ok » (ZeroDivisionError, bonne ligne), « saisies dans la console : ok »
(« Ton nom ? Alice », « Un entier ? 16 » lus dans le widget), 1 000 lignes « ligne » dans la console, « boucle : sortie
reçue : ok » ; captures `capture_jalon3_fin.png` (page) et `capture_jalon3_bureau_fin.png`, relues : identiques.

**Verdict sur ce que le jalon devait trancher (exigence du Superviseur, 23 h 10) : pour EXÉCUTER le fichier de l'élève avec
sa console (sortie, erreurs, `input()`, arrêt), `ShellBaseWidget` + `ProcessusWeb` suffisent, et qtconsole/jupyter_client
sur un Worker n'est pas nécessaire.** La mesure qui le dit : le Worker rend tout ce qu'un `QProcess` rend sur le bureau
(stdout, stderr, stdin bloquant, code de retour, kill en 2 ms), avec la page qui reste réactive (63 ms de silence au pire
pendant un calcul d'une seconde) là où l'exécution dans la page la fige 800 ms. Le surcoût est le démarrage à froid d'un
Worker (0,25–0,5 s, 19–23 ms préchauffé : un Worker de réserve suffit à le cacher à l'élève). Ce que ce verdict ne couvre pas,
et qui est le seul motif de qtconsole : un REPL interactif entre deux exécutions (variables conservées, `%magics`),
l'explorateur de variables, la complétion dans la console. Pour ces besoins-là la voie la moins chère n'est pas jupyter
mais ce que `console_enfant.py` du lecteur SmartTeacher fait déjà : un interpréteur persistant (`code.InteractiveConsole`
sur le stdin du Worker) dans le même `ProcessusWeb` — à mesurer seulement si l'utilisateur le demande.

**Ce que `ShellBaseWidget` tire de Spyder dans la page (le coût caché, exigence du Superviseur)** : 6 modules de plus
que le `CodeEditor` du jalon 1 (`spyder.plugins.console`, `.utils`, `.utils.ansihandler`, `.widgets`, `.widgets.console`,
`.widgets.shell`), aucun paquet tiers de plus (relevé par différence de `sys.modules` sur le bureau, même préambule) ;
`imports` passe de 0,48 s (jalon 2, bureau) à 0,77–2,1 s dans la page selon la charge. Le Worker, lui, n'importe RIEN de
Spyder : il ne reçoit que `eleve.py` et l'historique (filtre de `configurer`), c'est un Pyodide nu, et c'est ce qui fait
ses 23 ms préchauffé.

Ce qu'il a fallu corriger, et qui n'était pas dans Spyder (tout dans `jalon3.py`, aucun fichier de qtpy6 touché) :
  - **la console interne de Spyder ne garde que 300 lignes** (`ConsoleBaseWidget.__init__`, `setMaximumBlockCount(300)`,
    réglage `max_line_count`) : 290 lignes sur 1 000 au premier essai, « saisies : ÉCART ». Ce n'est pas un défaut mais un
    réglage, à monter dans le port (`setMaximumBlockCount(5000)` ici) ;
  - **`SaveHistoryMixin` exige `SEPARATOR`** (None dans `ShellBaseWidget`, `TypeError` au premier Entrée) : posé comme
    `PythonShellWidget` le fait ;
  - **un `readyRead` de plus que d'octets** : dans la page, deux écritures rapprochées du programme (« Bonjour ! » puis
    l'invite) arrivent en deux messages du Worker, donc deux `readyReadStandardOutput`, et le second ne lit plus rien
    (le premier a tout pris). Le script répondait deux fois à la même invite. QProcess peut faire de même sur le bureau :
    un morceau vide n'est jamais une invite, c'est au lecteur de l'ignorer (une ligne). Écarté : fusionner les messages
    dans `travailleur.py` (changerait le comportement de tout `ProcessusWeb` pour un cas que le bureau a aussi) ;
  - **le protocole de la sonde n'admet qu'un geste à la fois** : la page a demandé « cliquer » (seconde invite) pendant
    que la sonde finissait encore « taper » ; la sonde a ensuite posé `taper_fait` par-dessus, et chacun attendait
    l'autre (blocage, délai de 600 s). Corrigé côté page : un geste n'est demandé que lorsque l'état est revenu à
    « jalon3 », et une attente sur un geste dépassé s'abandonne. Écarté pour l'instant : un `_fait` posé par la sonde
    seulement si l'état est encore le sien (compare-and-set dans `sonde.py` : plus robuste, mais c'est un fichier du
    paquet, à proposer au Superviseur avec le hunk si un autre essai tombe dessus) ;
  - **un chien de garde** dans la page : 20 s sans événement → diagnostic dans le journal (état, programme, réponses
    restantes, fin de la sortie) et `etat = "erreur"`. Les deux blocages ci-dessus ont coûté un délai de 600 s chacun
    avant lui, et c'est lui qui a nommé le second en une ligne.

Ce que le jalon ne mesure pas : la mémoire du Worker (son tas est séparé de celui de la page) ; plusieurs exécutions à la
suite (un seul Worker préchauffé) ; un REPL persistant ; la frappe directe dans la console sans programme en cours ; le
ressenti à la main. Le démarrage à froid a été mesuré site déjà en cache du navigateur : au premier chargement il
comprend le téléchargement de Pyodide-Qt.

### Résultat du jalon 4 (10/10/2026, 07 h 55) : la complétion, jedi dans un Worker, sans serveur de langage

Demande de l'utilisateur (07 h 40) : « oui, lance le jalon 4 » (rallonge de 2,5 points de quota pour les jalons 4 et 5).
Mesuré avec `essais/spyder/jalon4.py` (bureau offscreen et page, `site/index.html?script=jalon4.py`, sonde `--pilote`) : le
`CodeEditor` de Spyder avec les 2 000 premières lignes de `codeeditor.py` du fork, `completions_available = True`, et son
signal `sig_perform_completion_request` branché, à la place du client LSP, sur deux moteurs : **A**, jedi importé dans
l'interpréteur de la page (`jalon4_jedi.completer`) ; **B**, le même `jalon4_jedi.py` lancé en serveur (une requête JSON
par ligne sur stdin, une réponse par ligne sur stdout) par `qtpy6.QtCore.QProcess` — un vrai processus SmartPython sur le
bureau, `ProcessusWeb` (Web Worker) dans la page, par `start(sys.executable, ["-u", serveur])`, strictement le même code
appelant. Les réponses reviennent par `handle_response(DOCUMENT_COMPLETION)`, le chemin normal de Spyder. Trois requêtes
sur chaque moteur, dans le même ordre (`os.pa` à froid puis à chaud, `CodeEditor.set`, `"".up`), B deux fois (Worker à
froid, puis Worker préchauffé par `prechauffer(["jedi", "parso"])`), puis le geste réel : un clic dans l'éditeur, la
frappe de `import os` et `os.pat` (le « . » déclenche la complétion automatique de Spyder), Entrée sur la liste.

| Mesure (page : Firefox, site en cache, charge machine ≈ 2,5, 4 lancements qui passent ; bureau offscreen, 5) | Navigateur, A (page) | Navigateur, B (Worker) | Bureau, A | Bureau, B (QProcess) |
|---|---|---|---|---|
| moteur prêt (B : Pyodide démarré + `import jedi`) | 0 ms (jedi déjà importé par Spyder) | **801–898 ms** à froid, dont 518–576 d'`import jedi` ; **307–358 ms** préchauffé | 0 ms | 63–75 ms |
| `os.pa` à froid, 1re complétion (jedi lit typeshed) | **1 586–1 741 ms** | **1 391–1 517 ms** (aller-retour +8 ms), préchauffé ou non | 1 117–1 246 ms | 370–434 ms |
| `os.pa` à chaud | 83–88 ms | 69–75 ms (aller-retour 79–84) | 89–102 ms | 79–87 ms |
| `CodeEditor.set` (une classe du fichier) | **0 item, erreur** (364 ms) | 25 items, 62–68 ms | 141 items, **5 285–5 589 ms** | 25 items, 29–34 ms |
| `"".up` | 254–289 ms | 226–247 ms | 52–62 ms | 50–59 ms |
| plus long silence de la page pendant la série | **1 678–1 765 ms (page figée)** | **54–60 ms** | 5 337–5 637 ms | 50–52 ms |
| tas WebAssembly de la page | 103 → 124 Mio | 124 Mio, stable (le Worker a le sien) | — | — |
| geste réel (B) : frappe → réponse du widget, puis liste affichée | — | 102–107 ms (jedi 94–99), liste 50–59 ms après | — | 88 ms, liste 398–418 ms après |
| script entier | 16,7–16,9 s | | 10,4–10,7 s | |

Tout passe : « insertion : ok » (« os.path » sur la ligne du curseur après Entrée), une seule requête par frappe, captures
`capture_jalon4_liste.png` / `_fin.png` (page) et `_bureau_liste.png` / `_bureau_fin.png`, relues : la liste de Spyder
(« path variable », « pathsep », « pathconf »…) s'affiche aux deux endroits.

**Verdict (exigence du Superviseur, 07 h 46) : B, jedi dans un Worker derrière `qtpy6.QtCore.QProcess`.** Ce qui le dit :
la page reste réactive (54–64 ms de silence au pire) là où A la fige 1,7 s au premier appel — et 5,5 s sur le bureau pour
une classe du fichier (le cas de la classe de 2 000 lignes, pas celui d'un élève, mais c'est l'éditeur qui gèle). Et le
coût caché de A, qu'aucune durée ne montre : jedi (`InterpreterEnvironment`) IMPORTE dans l'interpréteur de l'éditeur les
modules que le fichier nomme (1 module par première complétion, relevé par différence de `sys.modules`) ; sur le bureau,
`import PySide2` (cassé dans SmartPython, nommé par qtpy) a fait tomber l'éditeur (core dump, deux fois, jusqu'à bloquer
ces imports dans `jalon4_jedi.py`) ; dans la page, le PySide6 de Pyodide-Qt rend `AttributeError: 'CompiledValue' object
has no attribute 'py__path__'` (0 item, la ligne « erreur » du tableau). Un moteur dans l'éditeur tombe avec le fichier de
l'élève ; dans un Worker, c'est le Worker qui tombe, et l'éditeur en relance un. Ce que B coûte : le démarrage (0,8 s à
froid, 0,3 s préchauffé) et la première complétion (~1,4 s, préchauffé ou non : `prechauffer` installe les roues mais jedi
lit typeshed à la première requête). Un Worker de réserve lancé à l'ouverture de l'éditeur, qui reçoit une complétion
factice (`import os\nos.pa`), cacherait les deux à l'élève ; non mesuré. B ne voit que le dossier de l'élève (filtre de
`configurer`) : 25 items sur `CodeEditor.set` contre 141 pour A, parce que les imports de Spyder ne s'y résolvent pas ;
pour un fichier d'élève (`os`, `math`, `random`, `json` : stdlib, typeshed) c'est sans effet.

**Les stubs tiers (exigence du Superviseur)** : retirer `jedi/third_party/typeshed/stubs/` (12 Mio : requests, six…) ne
change AUCUNE des 8 listes comparées (`os.pa`, `CodeEditor.set`, `"".up`, `os.pat`, `json.du`, `random.ra`,
`from math import s`, `l.ap` ; bureau, sous-processus, même `sys.path`, jedi complet contre la roue sans stubs) ; la
stdlib de typeshed reste. `essais/spyder/roues_jedi.py` reconstruit les deux roues (`jedi-0.20.0+sansstubs`, 1 262 Kio,
et `parso-0.8.7`) dans `essais/roues/`, non versionné (`.gitignore`) : `$P essais/spyder/roues_jedi.py`.
`essais/spyder/construire_site.py` les copie dans le site (`roues=` de `construire`) et les nomme dans `window.roues`
pour le Worker ; `app.zip` : 24 144 Kio (site reconstruit après la correction du chemin des roues, `ICI.parent / "roues"` : les deux roues trouvées).

**Même code natif et web (consigne de l'utilisateur, 07 h 55, transmise par le Superviseur : « j'aimerais avoir le même code
pour les versions natives et web de SmartPythonEditor. C'est à qtpy6 de rendre le code agnostique en créant des
doublures »)** — pour chaque mécanisme des jalons 3 et 4, ce qui est doublure qtpy6 et ce qui resterait propre au web :
  - **exécution du fichier (jalon 3)** : `ShellBaseWidget` + `qtpy6.QtCore.QProcess` ; natif, un vrai `QProcess` Python ;
    web, `ProcessusWeb`. Doublure déjà en service, aucune branche dans le code appelant.
  - **complétion (jalon 4)** : `jalon4_jedi.py` en serveur sous le même `QProcess` : `jalon4.py` le lance par la même ligne
    des deux côtés, et le protocole (JSON par ligne) ne sait pas où il tourne. Doublure déjà en service. Dans le port : un
    fournisseur de complétion de Spyder (à la place du client LSP) qui parle à ce serveur ; survol, signature, aller à la
    définition : les mêmes appels jedi, le même canal.
  - **explorateur de variables (question de l'utilisateur, 10/10 au matin, non tranchée)** : il faut un interpréteur qui
    survive à la fin du script ; même mécanisme, pas codé : le serveur du processus garde l'espace de noms du script une
    fois celui-ci fini (`exec` dans un `globals()` conservé, comme `console_enfant.py` du lecteur SmartTeacher le fait
    déjà) et répond à « donne tes variables » (nom, type, taille, repr : ce que `get_remote_data` de spyder_kernels rend)
    sur le même canal JSON, par la même API des deux côtés (`QProcess.write`). Coût estimé : quelques jours pour le
    protocole des variables ; brancher `NamespaceBrowser` de Spyder (qui attend un `shellwidget` jupyter) sur ce canal
    est la partie Spyder, hors qtpy6. Ce que ça exclut : un objet non sérialisable reste côté Worker (seul son repr
    passe), et l'édition en place d'une variable est une seconde commande.
  - **ce qui resterait propre au web, à soumettre à l'utilisateur** (c'est ce que `jalon4.py` fait aujourd'hui sous
    `if WEB`, l'instrumentation de l'essai mise à part : état de la page pour la sonde, tas, captures, plein écran) :
    1. `travailleur.configurer(indexURL, roues, filtre)` : quel Pyodide le Worker charge, quelles roues il installe (jedi,
       parso), quels fichiers il reçoit. Le natif n'a pas d'équivalent (le processus voit le disque et `site-packages`).
       Pour effacer la branche : une API commune sur `qtpy6.QtCore.QProcess` (un réglage « roues / dossier de travail »
       sans effet en natif), ou la page qui les pose elle-même à la construction (ce que `window.roues` fait déjà). À
       décider : où vit la liste des roues ;
    2. `travailleur.prechauffer(modules)`, le Worker de réserve : une doublure qui ne fait rien en natif (un processus
       démarre en 63 ms) suffit, mais c'est un appel qui n'existe que pour le web ;
    3. `waitForFinished` : absent de `ProcessusWeb` (une page n'attend pas), nécessaire en natif pour ne pas détruire un
       `QProcess` en cours. Soit `ProcessusWeb` l'offre (retour immédiat), soit le code appelant se fie à `finished` ;
    4. le dossier de l'élève existe des deux côtés, mais dans la page il est dans le système de fichiers virtuel, effacé
       au rechargement : c'est le jalon 5.

Ce qu'il a fallu corriger (tout dans `jalon4.py` et `jalon4_jedi.py`, aucun fichier de `qtpy6/` touché) :
  - **jedi importe les modules compilés qu'il rencontre** : `sys.modules[m] = None` pour PySide2, shiboken2, PyQt5, PyQt6
    avant `import jedi` (ImportError propre au lieu du core dump) ; dans la page, `try/except` autour de `complete`,
    l'erreur va sur stderr et la liste est vide (le tableau le montre, ce n'est pas masqué) ;
  - **le moteur A appelait `pret()` dans son constructeur**, avant d'être posé comme moteur courant : `QTimer.singleShot(0)` ;
  - **une réponse du serveur arrive en plusieurs morceaux** (`readyReadStandardOutput`, page comme bureau) : tampon
    découpé sur `\n`, la dernière ligne incomplète attend la suite ;
  - **un `QProcess` tué puis détruit** fait râler Qt à la sortie sur le bureau : `waitForFinished(1000)` après `kill`
    (branche native, voir le point 3 ci-dessus) ;
  - **l'insertion se vérifie sur la ligne du curseur**, pas sur la dernière ligne du fichier : le vrai clic de la sonde
    pose le curseur au milieu du fichier (ligne 1 978), là où « os.path » est inséré ;
  - **les roues ne sont pas dans `app.zip`** mais à côté de la page : `construire_site.py` les nomme dans `window.roues`,
    que `jalon4.py` relit pour `configurer`.

Ce que le jalon ne mesure pas : le ressenti à la main ; plusieurs complétions enchaînées (un seul geste réel) ; le tas du
Worker ; le premier chargement sans cache (les roues jedi et parso s'ajoutent à Pyodide-Qt, 1,3 Mio) ; le survol, la
signature et l'aller-à-la-définition (mêmes appels jedi, non lancés) ; un Worker de réserve qui aurait déjà fait une
première complétion.

## Conclusion en cinq lignes

| | Verdict |
|---|---|
| Spyder entier dans le navigateur | **pas tel quel, mais rien n'y est indispensable** (objection de l'utilisateur, voir « Ce qui est indispensable » ci-dessous) : ZMQ, les processus, les fils réels, psutil, git, conda sont des MÉCANISMES, chacun remplaçable ou désactivable ; ce qui est indispensable, c'est un noyau qui exécute et le protocole Jupyter que parlent les widgets de console, et ces deux-là passent dans un Worker (précédent JupyterLite). Le vrai inconnu est la mémoire et le chargement de ~220 000 lignes |
| Un « Spyder allégé » : Spyder avec ses plugins poste désactivés, une console sur Web Worker | **possible mais lourd**, et c'est la voie réelle : plusieurs semaines, qui réécrivent la couche transport (noyau et LSP) sans toucher au protocole, et qui doivent d'abord prouver que la mémoire tient |
| Ce que vise sans doute la demande, un éditeur Python exécutable dans le navigateur pour les élèves | **déjà là** : `editeur_code.py` + `console_code.py` + `console_enfant.py` du lecteur SmartTeacher (1 770 lignes) tournent dans le navigateur depuis septembre ; les étendre coûte des jours, pas des semaines |
| Ce qu'un essai devrait mesurer en premier, si la voie « Spyder allégé » est retenue | la mémoire et le temps de chargement d'un `import spyder` nu sous Pyodide-Qt, avant d'écrire une ligne |
| La question « sur qtpy6 » | n'est pas l'obstacle : Spyder accepte déjà PySide6 et c'est l'API que qtpy6 expose ; une ligne d'alias (`qtpy.QtCore` → `qtpy6.QtCore`) suffirait sur le papier pour que Spyder reçoive les doublures du navigateur |

## Ce qui a été relevé

### Ce que le navigateur offre (qtpy6, `web.md`, vérifié par lecture)

- Pyodide-Qt lie **QtCore, QtGui, QtWidgets, QtSvg, QtSvgWidgets** et rien d'autre (`wasm/construire.sh`, l. 172 et
  207) : ni QtNetwork, ni QtPrintSupport, ni QtWebEngine, ni QtTest, ni QtQuick. PySide6 6.10.2, Python 3.13, un seul
  fil, pas de `SharedArrayBuffer`.
- qtpy6 double, dans le navigateur seulement : `QProcess` (un Web Worker Pyodide, Python seulement), `subprocess.run`,
  les `exec()` bloquants (dans un slot, jamais dans une méthode virtuelle), `QThread`/verrous/`time.sleep` en fils
  coopératifs, `QFileDialog` par le navigateur, le stockage (localStorage, IndexedDB). **Pas doublés** :
  `threading.Thread`, `multiprocessing`, les sockets, tout exécutable qui n'est pas un script Python.
- Les roues se chargent par URL seulement (lock vide : ni `loadPackage`, ni micropip) ; une extension C doit exister pour
  l'ABI `cp313-pyemscripten_2025_0_wasm32`.
- Coût mesuré sur une application de 2 000 lignes : +360 Mio de mémoire, 32 Mio de wasm à télécharger (9,9 en gzip).

### Ce que Spyder est (relevé du 09/10/2026, sous-agent, chiffres exacts)

- 814 fichiers `.py`, ~222 000 lignes sous `spyder/` (plugins 159 000, api 13 400, utils 13 400, widgets 17 700,
  app 12 200), 35 plugins.
- Liaisons acceptées (`spyder/requirements.py`) : PyQt5, PySide2, PyQt6 6.9+, **PySide6 6.8 à 6.9** ; le fork SmartOS
  ajoute `SPYDER_QT_SKIP_VERSION_CHECK=1` qui lève la plage, donc la 6.10.2 de Pyodide-Qt passe. Défaut du fork :
  `pyside6`.
- Modules Qt importés (occurrences) : QtCore 300, QtWidgets 262, QtGui 155, **QtWebEngineWidgets 11** (5 fichiers hors
  tests, tous derrière un drapeau `WEBENGINE` avec repli `QTextBrowser` : aide, aide en ligne, navigateur), **QtPrintSupport
  3** (`widgets/printer.py`, `editor/widgets/main_widget.py`, `ipythonconsole/widgets/main_widget.py` : imports nus, sans
  repli — à doubler par un module vide dans qtpy6 ou à patcher), QtSvg 2 (lié), QtTest 1, QtQuick 1 (non lié ; usage non
  vérifié).
- Fils : QThread dans 25 fichiers (doublé, coopératif : un `run()` qui ne cède jamais fige la page), `threading.Thread`
  dans 8 (non doublé : transport LSP, interpréteur de la console interne, `utils/programs.py`, pydoc), asyncio 14,
  `concurrent.futures` 3, multiprocessing 1.
- Sous-processus : Python (pylint, pylsp, transport LSP, cookiecutter, relance) — transposables sur le Worker ; **git,
  hg, xdg-open, conda, pixi** (`utils/vcs.py`, `explorer/widgets/utils.py`, `kernelspec.py`) — impossibles, à désactiver.
- Réseau : **pyzmq dans 8 fichiers, jupyter_client dans 7, tornado 3, websocket 4, requests 5**. Aucun QTcpSocket.
- Extensions C déclarées (versions figées du fork) : **pyzmq, psutil (9 fichiers, dont `app/utils.py` au démarrage),
  watchdog, rtree, jellyfish, bcrypt, aiohttp, yarl**. Transitives : tornado, ujson (python-lsp-jsonrpc). Aucune roue
  Pyodide n'a été cherchée pour elles ce jour (non vérifié) ; pyzmq et psutil n'ont par nature pas d'équivalent dans un
  navigateur.
- Autres entrées système : keyring (8 fichiers), presse-papiers (17), `QDesktopServices.openUrl` (4), watchdog
  (projets).

### Ce qui est indispensable, et ce qui ne l'est pas (objection de l'utilisateur, 09/10/2026)

« tout cela est indispensable à SmartPythonEditor ? » — non, et le premier jet de cette note le laissait croire en
listant des mécanismes comme s'ils étaient le besoin. Repris point par point, vérifié dans les sources du fork :

| Mécanisme cité | Indispensable ? | Ce qui l'est, et ce qui le remplace |
|---|---|---|
| ZMQ + processus noyau (`jupyter_client`, `SpyderKernelManager`) | non | un **noyau qui exécute** et le **protocole Jupyter** (messages `execute_request`, `comm_msg`… en dicts Python, `jupyter_client.session`, pur Python) sont indispensables : c'est ce que parlent `qtconsole` et `KernelComm`. Seuls les sockets ZMQ sont à remplacer par un pont vers `ProcessusWeb`. Précédent : JupyterLite ne fait pas tourner ipykernel, il en garde une maquette (« an ipykernel mock that provides utility classes (like Comms) ») et un petit noyau (`run`, `complete`, `inspect`, `is_complete`) dans le Worker, le protocole étant joué côté client |
| pylsp en TCP relayé par ZMQ (`transport/main.py`) | non | la complétion est indispensable, pas son transport : Spyder a un mode stdio (`advanced/stdio`), qui colle au stdin/stdout de `ProcessusWeb`, et un fournisseur de repli dans le processus (`completion/providers/fallback`) qui marche sans serveur |
| psutil | non | 3 usages : `cpu_percent` de la barre d'état, `pid_exists` au démarrage (`app/utils.py`), `virtual_memory` ; un module de doublure de dix lignes suffit |
| watchdog, keyring, pyzmq | non | watchdog : surveillance des projets, à désactiver ; keyring : jetons distants, à désactiver ; pyzmq : voir ligne 1 |
| `threading.Thread` (8 fichiers) | non | transport LSP (remplacé), interpréteur de la console interne (plugin désactivable), `utils/programs.py` (lancement de programmes externes, sans objet), pydoc (aide en ligne, désactivable) |
| git, hg, conda, pixi en sous-processus | non | `vcs`, `explorer`, `kernelspec` : optionnels, détectés à l'exécution ; chaque plugin a sa clé `enable` (`config/main.py`), et `--safe-mode` / `--no-web-widgets` existent (`app/cli_options.py`) |

Reste indispensable, donc : le noyau et le protocole Jupyter (dans le Worker), la complétion (stdio ou repli), et la
mémoire pour charger le tout. Le verdict « non » du premier jet est corrigé en « pas tel quel » dans la conclusion.

### Les trois chantiers qui ne sont pas Qt (vérifié par lecture des fichiers nommés)

1. **La console IPython.** `SpyderKernelManager(QtKernelManager)` lance un processus noyau (`spyder_kernels` sur
   `ipykernel`) et lui parle par sockets ZMQ via `jupyter_client` et un fichier de connexion ; `KernelHandler` tient
   des threads sur les pipes du noyau ; `KernelComm` double le canal Jupyter. Rien de cela n'existe dans un navigateur.
   Le modèle qui marche ailleurs est celui de JupyterLite : un noyau Pyodide dans un Web Worker, un `ipykernel` de
   substitution sans ZMQ, un client qui parle au Worker par messages. Pour Spyder il faudrait écrire un `KernelClient`
   et un `KernelManager` sur `ProcessusWeb`, et porter `spyder_kernels` sur ce substitut. C'est le gros du travail.
2. **Le serveur de langage.** `pylsp` est lancé en TCP (`--host --port --tcp`) et relié par un second processus
   (`transport/main.py`) qui relaie entre ZMQ PAIR et TCP. Un mode stdio existe (`advanced/stdio`, `pexpect`), qui
   collerait au stdin/stdout de `ProcessusWeb`, mais le relais ZMQ reste entre les deux : à réécrire. Bonne nouvelle :
   pylsp et ses extras sont du Python pur, hormis `ujson` (à vérifier sur Pyodide).
3. **Ce qui est fait pour un poste** : psutil au démarrage, keyring, watchdog, git/hg, conda, les mises à jour, les
   projets distants (`remoteclient`, asyncssh, aiohttp). À retirer ou à mettre derrière `qtpy6.web.navigateur()`.

### Les treize greffons de SmartPythonEditor (`/DATA/Python/FORKS/SmartPythonEditorPlugins/`, relevé du 09/10/2026)

Oubliés du premier jet (question de l'utilisateur : « et tous mes plugins ajoutés à Spyder pour faire SmartPythonEditor ? »).
Relevé par grep des imports et des lancements de processus, hors tests ; le rôle vient de la `description` de chaque
`pyproject.toml`. Lignes de code entre parenthèses.

| Greffon | Verdict navigateur | Pourquoi |
|---|---|---|
| spyder_claude (6 900) | sans objet | docks des instances Claude Code du poste (`claude-window.sh`, panneaux Konsole) |
| spyder_konsole (2 440) | impossible | QTermWidget, un terminal : pas de pty dans un navigateur |
| spyder_tortoisehg (126 000, TortoiseHg embarqué) | impossible | `mercurial` (extensions C), QtNetwork, `subprocess`, `threading`, `socket` |
| spyder_window_controls (1 700) | sans objet | boutons de la fenêtre sans barre de titre, `subprocess` |
| spyder_interpreter_toolbar (640) | sans objet | choix de l'interpréteur : il n'y en a qu'un, Pyodide |
| spyder_viztracer (2 500) | improbable | `viztracer` (extension C, pas de roue Pyodide connue), `socket`, QtWebEngine pour Perfetto |
| spyder_line_profiler (12 900) | lourd | `line_profiler` (Cython) à construire pour l'ABI wasm, 5 fichiers de sous-processus → Worker |
| spyder_python_tutor (6 400) | à réécrire | QtWebEngineWidgets/Core (non liés) : le tracé est Python, l'affichage devrait passer par un onglet du navigateur ou un widget Qt |
| spyder_collab (5 200) | transport à réécrire | CRDT pur Python a priori, mais `network.py` sur QtNetwork (non lié) : WebSocket/WebRTC par JS |
| spyder_code_analysis (910) | possible | pylint/astroid purs, lancés en sous-processus → `ProcessusWeb` |
| spyder_pyxel (7 300) | remplacé | `pyxel` natif (SDL) ; le lecteur SmartTeacher a déjà `pyxel_studio.py` dans le navigateur |
| spyder_smartteacher (840) | possible, et déjà fait ailleurs | sujet de TP, aide, indices, soumission, note : c'est ce que le lecteur SmartTeacher fait nativement ; 1 `subprocess` |
| spyder_stop_toolbar (550) | possible | un bouton, aucune dépendance |

Lecture : cinq greffons sur treize sont des greffons de POSTE (Claude, terminal, Mercurial, fenêtre, interpréteur) et
n'ont pas de sens dans un navigateur ; trois tiennent à une extension C ou à QtWebEngine (viztracer, line_profiler,
python_tutor) ; les cinq qui concernent l'élève (analyse, pyxel, smartteacher, stop, collab hors transport) sont
portables, et deux ont déjà leur équivalent dans le lecteur web. Un SmartPythonEditor dans le navigateur ne serait donc
pas SmartPythonEditor : ce serait Spyder allégé + ces cinq-là. Cela renforce la voie C (étendre le lecteur) pour
l'usage élève, et confine la voie B au cas où c'est l'éditeur de Spyder lui-même (coloration, complétion LSP,
explorateur de variables) qu'on veut dans la page.

### Le reste, sans doute surmontable mais à auditer

- `exec()` dans une méthode virtuelle (`contextMenuEvent` → `menu.exec()`) ne bloque pas dans le navigateur : Spyder en a
  beaucoup, chacun à passer en `popup` ou en `QTimer.singleShot(0, …)`. Non compté.
- Qt-WASM n'expose pas de lecteur d'écran, ni la sélection/recherche du navigateur dans la fenêtre Qt.
- Polices : Spyder embarque les siennes (qtawesome, fonts/), à déclarer à `application(polices=…)`.
- Les 89 fichiers `.py` modifiés par le fork (+5 268 / −275 : scénarios `--actions`, trace de démarrage, support de
  distribution) sont orthogonaux au portage ; ils ne l'aident ni ne le gênent.

## Les voies, et ce qu'elles coûtent (estimations, rien n'est mesuré)

**A. Spyder entier, tel quel.** Écartée comme TEL QUEL seulement (la couche transport doit être réécrite, voie B) ; ce qui reste contre elle est la taille
(222 000 lignes + IPython, jedi, parso, pygments, sphinx, pylint, nbconvert…) fait craindre bien plus que les 360 Mio
mesurés pour 2 000 lignes ; un poste d'élève ou une classe de 30 à froid n'y résistent probablement pas. Spyder lui-même
n'a pas de port WebAssembly : son « Try Spyder online » est un bureau distant (Binder, noVNC), pas une page.

**B. Un Spyder allégé — la voie réelle.** Garder `app`, `api`, `plugins/editor` (avec `lsp_mixin`), `outlineexplorer`, `plots`,
`variableexplorer`, désactiver par `enable` les plugins poste (vcs, explorer distant, mises à jour, remoteclient, console
interne), et réécrire : un client noyau sur `ProcessusWeb` + un `spyder_kernels` sans ZMQ (obstacle 1), le
transport LSP en stdio sans relais (obstacle 2), des doublures vides pour QtPrintSupport, keyring, psutil, watchdog
(obstacle 3), puis l'audit des `exec()` et des `threading.Thread`. Ordre de grandeur : plusieurs semaines, et le premier
jalon n'est pas une fenêtre, c'est la mesure d'un `import spyder.app.mainwindow` nu sous Pyodide-Qt (mémoire, durée) —
si elle dépasse ce qu'un poste d'élève tolère, le reste est sans objet. À lancer sur `exemple/` de qtpy6, avec les roues
pures de Spyder dans l'archive.

**C. Étendre l'éditeur du lecteur SmartTeacher.** `editeur_code.py` (QPlainTextEdit, indentation, couleurs
donné/élève, numéros de ligne), `console_code.py` et `console_enfant.py` (un interpréteur dans un `QProcess` → Web Worker,
variables conservées entre deux commandes, reprise d'état) tournent déjà dans le navigateur, et sont écrits en qtpy6. Ce
qui manque par rapport à un éditeur : plusieurs fichiers, coloration syntaxique complète (pygments est en Python pur),
complétion (jedi, pur, dans le Worker), un débogueur (pdb dans le Worker, par stdin). Chaque brique est un item de
quelques jours ; aucune ne dépend de ZMQ ni d'un processus.

**D. Hors qtpy6, pour mémoire.** JupyterLite (notebook Pyodide dans le navigateur, noyau en Worker) : c'est le
précédent dont la voie B copierait l'architecture noyau ; Binder : un vrai Spyder, mais sur un serveur distant.

## Niveau de preuve

- Modules liés dans Pyodide-Qt, doublures de qtpy6, coûts mesurés : lus dans `wasm/construire.sh` et `web.md`.
- Précédent JupyterLite : lu en ligne le 09/10/2026 (`pyodide-kernel`, README du paquet `ipykernel` maquette et `kernel.py` :
  `PyodideKernel` hérite de `LoggingConfigurable`, pas d'ipykernel ; aucun ZMQ, le transport est côté JS).
- Mode stdio du LSP, fournisseur de repli, usages de psutil, clés `enable`, `--safe-mode` : relus dans les sources du fork.
- Greffons : imports et sous-processus relevés par grep, rôles lus dans les `pyproject.toml` ; aucun n'a été lancé ni lu en
  entier (l'existence d'une roue Pyodide pour viztracer et line_profiler n'a pas été cherchée).
- Chiffres sur Spyder : grep d'un sous-agent, non recomptés sauf QtWebEngine (drapeau `WEBENGINE` et repli relus dans
  `widgets/browser.py`, `plugins/help/widgets.py`) et QtPrintSupport (les trois imports relus).
- Jalon 1 : **mesuré en direct** (sonde, journal `essais/spyder/sonde.log`, captures relues), deux fois sur le même site
  (86 et 104 Mio de tas : la mesure varie d'un lancement à l'autre, à ne pas lire au Mio près). Le bureau : mesuré en
  offscreen, capture relue. L'incompatibilité d'alias : bissection automatique des 98 alias de `QPlainTextEdit`, puis
  reproduction en dix lignes sans Spyder (plante avec `import qtpy6`, passe sans), puis l'essai complet qui passe une
  fois l'alias retiré.
- Jalon 2 : **mesuré en direct**, deux lancements de la page (Firefox, sonde pilotée) et un du bureau, journaux
  `essais/spyder/sonde_jalon2.log` et `jalon2_bureau.log`, captures comparées par un sous-agent (voir la section).
  Le correctif de `bloquant.py` : vérifié par les 116 erreurs qui disparaissent et par la suite de tests de qtpy6
  (`tests/`, lancée après le correctif) ; celui de la sonde : par les 3 Entrée retrouvées (Firefox ; la branche Chromium, `key="Enter"` par CDP, est
  écrite sans avoir été lancée, Chromium n'ouvrant pas dans le bac à sable). Aucun des deux n'a de test dédié.
- Jalon 3 : **mesuré en direct**, quatre lancements de la page (deux bloqués par les défauts corrigés, un en
  `NameError` d'instrumentation, un qui passe) et cinq du bureau, journaux `essais/spyder/sonde_jalon3.log` et
  `jalon3_bureau.log`, captures relues (page et bureau identiques). Les durées de la page viennent d'UN lancement qui
  passe, machine à charge 8 : ordres de grandeur. Les modules tirés par `ShellBaseWidget` : différence de `sys.modules`
  sur le bureau, non refaite dans la page.
- Jalon 4 : **mesuré en direct**, quatre lancements de la page qui passent (après trois arrêtés par les défauts corrigés)
  et cinq du bureau, journaux `essais/spyder/sonde_jalon4.log` et `jalon4_bureau.log`, captures relues (liste et
  insertion, page et bureau). Les fourchettes du tableau sont les extrêmes de ces lancements. L'effet des stubs tiers :
  8 listes comparées sur le bureau (script de session, non conservé ; `roues_jedi.py` reconstruit la roue comparée).
  Les modules importés par A : différence de `sys.modules` autour de chaque complétion, page et bureau.
- Disponibilité des roues Pyodide pour les extensions C : **non vérifiée** (aucune n'a été nécessaire au jalon 1).
- Les durées sont des ordres de grandeur, pas des estimations fondées sur une mesure.

## Points ouverts

- **Un défaut de qtpy6, pas une particularité de Spyder** (question de l'utilisateur, 21 h 16 : « pour un vrai programme en
  qtpy6 qui veut respecter PEP 8 on aurait des conflits de nom entre des signaux et des slots ? » — oui, reproduit :
  `essais/alias_signal_slot.py`, un QLineEdit ordinaire dont le slot s'appelle `text_changed`, plante avec `import qtpy6`,
  passe sans ; c'est le test qui échoue tant que qtpy6 n'est pas corrigé). Mesuré le même soir : aucun code de
  SmartTeacher ni de qtpy6 n'appelle un alias de signal, ni d'ailleurs un alias de méthode (grep des 237 noms posés) ;
  cesser d'aliasser les signaux ne casserait donc rien d'existant. Le mécanisme : qtpy6 pose sur chaque classe PySide6 un
  alias snake_case de chaque méthode et signal (`_binding._pyside6_class`), dont `cursor_position_changed` pour le signal
  `cursorPositionChanged` de `QPlainTextEdit`. Spyder (`plugins/editor/widgets/base.py`, l. 76 et 425) définit une
  MÉTHODE de ce nom et la connecte à ce signal : PySide6 plante alors au premier `setPlainText` (segfault, pas
  d'exception). **Retenu à 20 h (l'utilisateur, « le plus propre sans toucher à qtpy6 »), puis remplacé à 22 h par le renommage
  dans le fork (voir plus bas) : l'essai retirait, après les imports de Spyder et avant le premier widget, TOUS les alias
  de signaux** (`retirer_alias_signaux` dans `editeur.py` :
  même objet `Signal` sous deux noms dans `vars(cls)`, sur les classes que qtpy6 a préparées, `_binding._prepared`) —
  309 sur le bureau, 423 dans la page ; les alias de méthodes restent, une redéfinition les masque sans planter. Écartés :
  retirer le seul `cursor_position_changed` (premier jet : juste, mais à refaire à chaque greffon dont une méthode porte
  le nom d'un signal) ; renommer la méthode du fork (deux lignes, même défaut) ; que qtpy6 cesse d'aliasser les signaux
  (le plus propre, mais touche qtpy6 en service : à décider à part). **PySide6 a-t-il le même problème ? (question de
  l'utilisateur, 09/10/2026)** Le mécanisme, oui : `essais/alias_signal_pyside6.py`, PySide6 seul, un `Signal` sous un second
  nom de classe (`alias = changed`), masqué par une méthode `alias` du sous-type, connecté → core dump (mesuré). En
  pratique, non : son `from __feature__ import snake_case` renomme les méthodes à l'accès (`set_text` marche, `setText`
  disparaît) mais ne pose aucun nom pour les signaux (ils restent en camelCase : pas PEP 8 pour eux, mesuré) (`text_changed` n'existe ni sur la classe ni sur l'instance, `textChanged` reste) ;
  un slot `text_changed` connecté à `textChanged` passe (mesuré). Un slot nommé EXACTEMENT comme le signal plante aussi en 100 % camelCase (`def textChanged` dans un
  sous-type de QLineEdit, connecté : core dump, mesuré) — mais la collision saute alors aux yeux de l'auteur, et deux
  conventions distinctes (signaux camelCase, slots PEP 8) la rendent impossible. Le défaut est donc propre à qtpy6 :
  en posant un nom snake_case sur chaque signal, il réunit les deux espaces de noms, et un slot PEP 8 écrit sans
  jamais voir de signal de ce nom le masque à l'insu de l'auteur. Un programme écrit POUR qtpy6, 100 % snake_case,
  n'est pas plus exposé qu'en camelCase (l'utilisateur, 09/10/2026) : son auteur voit `cursor_position_changed` comme
  un signal et ne nomme pas son slot ainsi — à ceci près que ce nom n'est dans aucune doc Qt. Seul le code écrit pour
  Qt camelCase avec des slots PEP 8 (Spyder) tombe dedans. **Combien de méthodes de Spyder à renommer pour suivre la
  convention `on_…` / verbe (question de l'utilisateur, 09/10/2026) : trois**, relevé par AST sur tout le fork (hors
  tests) croisé avec les signaux de QtCore/QtGui/QtWidgets de PySide6, puis filtré à la main par héritage et connexion :
  `TextEditBaseWidget.cursor_position_changed` (base.py), `ArrayTable.cell_changed` (widgets/arraybuilder.py l. 143/156),
  `ProfilerDataTree.item_expanded` (plugins/profiler/widgets/profiler_data_tree.py l. 551/868) — chacune connectée au
  signal homonyme du widget dont elle hérite. 32 méthodes portent le nom snake_case d'un signal Qt, mais 29 sont dans des
  classes qui n'héritent pas de ce signal (sans effet). Et Spyder masque déjà un signal en camelCase pur :
  `DirView.clicked` (explorer.py l. 1062) redéfinit `QAbstractItemView.clicked` ; sans plantage, le signal n'y est jamais
  connecté par ce nom. Script : `$TMPDIR/conflits.py` de la session, non conservé (à refaire en une minute si besoin).
  **Fait (l'utilisateur, 21 h 51 : « renomme les trois méthodes dans le fork ») : les trois slots renommés `on_…` dans
  le fork** (six lignes, aucune autre occurrence dans le dépôt, tests compris), et `retirer_alias_signaux` est sorti de
  `editeur.py` (l'utilisateur, 22 h 16 : « il y aurait toujours besoin de --retirer-alias ? » — non : aucun scénario réel
  ne le déclenche plus, le relevé ci-dessus est exhaustif ; un greffon futur qui reprendrait l'habitude se corrige comme
  ici, le mécanisme reste décrit dans ce point et dans `essais/alias_signal_slot.py`). Vérifié : avant
  le renommage, l'essai avec alias conservés plante (core dump) ; après, il passe en natif (capture) et dans Firefox
  (site reconstruit, sonde : 2,9 s, tas 86 Mio, capture relue, la page est identique). Le contournement générique
  n'est donc plus en service. Pourquoi PySide6 plante au lieu de lever n'a pas été cherché.
- Jalons 1, 2, 3 et 4 atteints (le 3 : exécution dans un Worker par `ProcessusWeb`, pas dans le même interpréteur, qui fige
  la page ; le 4 : complétion jedi dans un Worker par le même `QProcess`, pas dans la page) : reste le jalon 5 de la voie
  B, les fichiers (lire, enregistrer, retrouver — stockage du navigateur ou téléchargement), un `essais/spyder/jalon5.py`
  mesuré par la sonde avant de toucher au fork. Dans le port lui-même : monter `max_line_count` de la console (300
  lignes), garder un Worker de réserve (`prechauffer()`) entre deux exécutions et lui faire faire une première complétion
  factice (jalon 4 : `prechauffer` installe les roues, mais la première requête jedi coûte encore 1,4 s), et décider si
  un REPL persistant est voulu (voir le verdict du jalon 3 et l'explorateur de variables au jalon 4).
- Les quatre points « propres au web » du jalon 4 (réglages du Worker, `prechauffer`, `waitForFinished`, dossier de
  l'élève) sont à trancher par l'utilisateur avant le port : ce sont les seules lignes qui, aujourd'hui, ne sont pas les
  mêmes sur le bureau et dans la page.
- `jalon2.py`, `jalon3.py` et `jalon4.py` recopient les mêmes outils (horloge de silence, gestes de la sonde, captures,
  chien de garde) : un `essais/spyder/commun.py` à faire au jalon 5, pas avant (les trois essais mesurés restent tels
  qu'ils ont été lancés).
- La sonde (`web/sonde.py`) ne protège pas contre un geste demandé pendant qu'elle finit le précédent (jalon 3) : un
  `_fait` posé par compare-and-set la rendrait sûre ; hunk à proposer au Superviseur si un autre essai y tombe.
- La règle « un slot qui reçoit un QEvent s'exécute sur place » (`bloquant.py`) n'a pas de test unitaire dans
  `tests/test_web.py` ; seul l'essai jalon 2 la prouve (réserve du Superviseur, 09/10/2026 : à écrire sur le modèle du
  test des DeferredDelete de 50a2747).
- Un essai À LA MAIN de `essais/spyder/site/index.html?script=jalon2.py` (et `jalon3.py`) dans le navigateur de
  l'utilisateur (servi par `http.server`) : le ressenti de la frappe et du défilement n'est pas dans les chiffres.
- Ce qu'un relecteur devrait regarder en premier : la condition ajoutée dans `qtpy6/web/bloquant.py` (`_relayer`,
  elle change le comportement de tout slot recevant un QEvent, pour toutes les applications), puis `essais/spyder/editeur.py` (les doublures et le bloc qui complète
  PySide6 — ce sont les deux listes qui diront ce que la voie B coûte vraiment), puis la capture web.
- Si c'est la voie C : lister ce que l'utilisateur attend d'un « éditeur » pour les élèves (fichiers multiples ?
  débogueur ? complétion ?) ; chaque brique est un item de TODO du lecteur web.
