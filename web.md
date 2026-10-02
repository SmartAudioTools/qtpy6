# qtpy6 dans le navigateur (`qtpy6.web`)

*Run a qtpy6 application in the browser, unchanged, on a Pyodide where Qt 6 and PySide6 are linked to WebAssembly
(built by the `wasm/` recipe of this repository, LGPL v3) — documentation in French below.*

Une application écrite avec **qtpy6** tourne **telle quelle dans le navigateur** : Qt 6 et PySide6 compilés en WebAssembly
dessinent la fenêtre dans un élément de la page, le code Python de l'application n'est pas modifié.

**Ce que Qt-WASM n'a pas et qui a un nom Qt, qtpy6 le double lui-même**, sous ce nom, dans le navigateur seulement
(`sys.platform == "emscripten"`) ; en natif, rien ne change :

| Nom Qt | Dans le navigateur |
|---|---|
| `QtCore.QProcess` | `ProcessusWeb` : la surface de `QProcess` sur un Web Worker Pyodide (section « Le worker ») |
| `QtGui.QFontDatabase.systemFont(FixedFont)` | la première police à chasse fixe que l'application a chargée (`addApplicationFont`), à la taille de celle de l'interface |
| `exec()` de `QApplication`, `QDialog`, `QMenu`, `QEventLoop` ; `QMessageBox.question`, `QInputDialog.getText`, `QFileDialog.getOpenFileName`… | suspendus par JSPI jusqu'à leur fin, puis rendent leur valeur comme en natif (`qtpy6.web.bloquant`) ; les sélecteurs de fichiers passent par ceux du navigateur (téléverser, télécharger) |
| `QThread`, `QThreadPool`, `QRunnable`, `QMutex`, `QWaitCondition`, `QSemaphore`, `time.sleep` | des fils coopératifs sur le fil unique de la page : un `sleep`, un `wait()`, un verrou pris cèdent la main (`qtpy6.web.fils`) |
| `QtPdf.QPdfDocument`, `QtPdfWidgets.QPdfView` | le PDF dessiné par pdf.js (vendu, `js/pdfjs/`) dans un `<div>` de la page calé sur le widget, texte sélectionnable et copiable (`qtpy6.web.pdf`) ; Qt-WASM n'a pas QtPdf |

Le reste n'a pas d'équivalent Qt et vit dans le sous-paquet **`qtpy6.web`** : le chargeur de la page, la `QApplication`
et ses polices, les cibles au doigt, le stockage du navigateur, l'assemblage de l'archive et une sonde Firefox sans
interface pour vérifier le tout sans écran ni clic.

```python
# mon_application.py : une application de bureau ordinaire, rien n'y parle du navigateur
import sys
from qtpy6.QtWidgets import QApplication, QMessageBox, QPushButton

app = QApplication(sys.argv)
bouton = QPushButton("Bonjour")
bouton.clicked.connect(lambda: print(QMessageBox.question(bouton, "Question", "Continuer ?")))
bouton.show()
sys.exit(app.exec())
```

```bash
python -m qtpy6.web.construire mon_application.py site/    # site/index.html, qtpy6web.js, app.zip
python -m qtpy6.web.sonde --racine site site/index.html capture.png   # ou n'importe quel serveur statique
```

`construire` prend le dossier du script entier (sauf fichiers cachés et `__pycache__`), qtpy6, et ce qu'on ajoute
(`--paquet`, `--distribution`, `--police`, et `--roue` pour une extension compilée pour Pyodide-Qt, copiée à côté de la page sous son nom) ; la page (`js/gabarit.html`) lance le script comme `python mon_application.py`
(`qtpy6.web.lancer` : `__main__`, `sys.argv`, dossier courant, `sys.exit` rattrapé) et le montre quand il entre dans
`app.exec()`. Pyodide-Qt (voir Installation) vient par défaut de l'hébergement de qtpy6 (`--pyodide ./pyodide-qt/` pour un dossier local).

Une page à soi qui embarque l'application dans un élément garde la main sur le chargement :

```html
<div id="qt" style="position:fixed; inset:0"></div>
<script type="module">
  import { preparer, lancer } from "./qtpy6web.js";   // qtpy6/web/js/, copié à côté de la page
  const py = await preparer(document.getElementById("qt"), {
    indexURL: "./pyodide-qt/",                                        // Pyodide avec Qt et PySide6
    archives: [{ url: "./app.zip", dossier: "/home/pyodide/app" }],  // le code, qtpy6, les polices
  });
  lancer(py, "/home/pyodide/app/mon_application.py");  // ou py.pyimport(...) d'une fonction qui ne fait pas exec()
</script>
```

Extrait du lecteur d'épreuves de SmartTeacher (septembre 2026), où
un lecteur Qt de 2 000 lignes (tableaux, éditeur de code avec exécution, graphes à tracer, SVG) s'est mis à tourner dans
le navigateur sans qu'une ligne de son interface change.

## Installation

```bash
pip install qtpy6               # qtpy6.web en fait partie ; PyQt6 n'est PAS nécessaire en natif si PySide6 est là
pip install qtpy6[sonde]        # + selenium, pour la sonde (Firefox et geckodriver viennent du système)
```

Python ≥ 3.10. Le paquet n'embarque **pas** le Pyodide où Qt est lié — appelé **Pyodide-Qt** dans la suite, quelle
que soit la liaison : la page le charge depuis l'URL `indexURL` (à côté d'elle, ou sur un hôte qui autorise CORS). Deux
builds, épinglés dans `qtpy6/web/versions.json`, tous deux Pyodide 0.29.3, Qt 6.10.2, Python 3.13 (le Pyodide ordinaire
du worker : 314.0.7, Python 3.14) ; `preparer` compare la version chargée à celle du fichier et écrit une ligne
d'avertissement au journal si elles diffèrent :
- **`pyodide_pyside6`, le défaut** : PySide6 6.10.2, construit par la recette `wasm/` de ce dépôt (Qt et PySide6 liés
  statiquement), **LGPL v3** : une application commerciale peut le servir sans publier son propre code, chargé à part
  dans `app.zip` ; la notice `pyodide-qt/LICENSE.txt` (`hebergement/LICENSE-Pyodide-PySide6.txt`) donne les textes et
  le moyen de re-lier exigés par la LGPL.
- **`pyodide_qt`, le repli** : [Pyodide-Qt](https://github.com/JarrettSJohnson/pyodide-with-pyqt6) de JarrettSJohnson,
  PyQt6 6.10.2, **GPL v3** : toute page qui le sert distribue PyQt6, et le code de l'application servi avec doit en
  tenir compte.
qtpy6 est MIT et ne contient aucun binaire.

**Installation éditable (développement)** : si le dépôt est rangé sous un dossier déjà présent sur `sys.path` (un `.pth`
qui met `~/Python` ou `/DATA/Python` sur le chemin), le dossier du dépôt lui-même devient un paquet-espace de noms
`qtpy6` que Python trouve avant le finder éditable de setuptools : `import qtpy6` réussit et le paquet est vide
(`__file__ is None`). Installer alors en mode compat, qui écrit un `.pth` classique :

```bash
pip install -e . --no-deps --no-build-isolation --config-settings editable_mode=compat
```

## Ce que fait `qtpy6.web`

| Où | Quoi |
|---|---|
| `qtpy6.web.navigateur()` | `True` sous Pyodide (`sys.platform == "emscripten"`) : l'interrupteur de tout le reste. Une fonction, pas une constante, pour rester forçable par un test. |
| `qtpy6.web.application(polices=None, defaut=None)` | La `QApplication`, créée au besoin et rendue (idempotente). Sans session graphique (ni `DISPLAY` ni `WAYLAND_DISPLAY`) elle passe en `offscreen` : tests et exports tournent sans écran. Dans le navigateur, où Qt n'a **aucune** police système, les `.ttf`/`.otf` du dossier `polices` sont chargés (la première à chasse fixe devient `systemFont(FixedFont)`) et `defaut` (`QFont` ou `("Noto Sans", 10)`) devient la police de l'interface. Elle garde une référence à l'application : sous PyQt6, une `QApplication` dont la dernière référence Python disparaît est détruite, et toutes ses fenêtres avec. Partout, natif compris, elle ne laisse plus passer le ramasse-miettes de Python qu'entre deux événements : livré à lui-même, il libère un cycle au hasard d'une allocation, parfois au milieu d'un appel de Qt, et un widget sans parent pris dans ce cycle est alors détruit sous les pieds de Qt (segmentation fault). `gc.disable()`, puis une minuterie de 500 ms qui ramasse la génération que le ramasse-miettes aurait ramassée lui-même (`_ramasser`). Dans le navigateur enfin, ce qui change à l'écran part au canevas dans l'image même (`_dessiner_aussitot`) : Qt poste un `UpdateRequest` au widget, et Qt-WASM n'envoyait son dessin qu'au `requestAnimationFrame` que ce dessin demande, l'image suivante ; une image sur deux restait vide pendant un défilement (56 envois pour 110 roulements, 86 à 89 pour 110 pas d'une minuterie). Les `UpdateRequest` en attente sont traités au début de chaque image, les images qu'ils demandent servies dans celle-ci (animations, minuteries, défilement au doigt), et aussi sitôt une entrée traitée par Qt (molette, souris, clavier, en bouillonnement sur `window`). Résultat : 110 envois sur 110 roulements, 103 à 104 pour la minuterie (Firefox, 01/10/2026 ; chacun des deux moments mesuré nécessaire en retirant l'autre). |
| `qtpy6.web.tactile` | `detecte()` : un doigt parmi les pointeurs du navigateur (`any-pointer: coarse`, ou `navigator.maxTouchPoints` > 0), ou en natif parmi les périphériques de Qt (`QInputDevice`, écran tactile). `activer(app, cible=44)` : boutons, listes, champs, cases montent à la taille d'une cible au doigt par une feuille de style **ajoutée** à celle de l'application, à appeler avant de construire les widgets. `activer_au_doigt(app)` : `activer` si `detecte()`, sinon au premier doigt posé sur la page (`pointerdown` tactile ; Firefox sous Linux ne dit rien de l'écran). `marge()` : l'espace à mettre autour d'un widget d'une ligne pour en faire une cible. `defiler_au_doigt(zone)` : une `QScrollArea` que le doigt fait défiler (`QScroller` ; sans lui, un glisser fait 0 px). |
| `qtpy6.web.dispositions` | `Disposition`, `Rangee` : des dispositions qui se **replient** quand la place manque. `QHBoxLayout` impose la somme de ses colonnes comme largeur minimale (mesuré : une barre de boutons à 574 px, une fenêtre à 451 px au minimum) ; `Rangee` passe à la ligne comme du texte. |
| `qtpy6.web.travailleur` | Un Web Worker Pyodide piloté depuis l'application (`Travailleur`), et `ProcessusWeb`, le `QProcess` du navigateur (section suivante). |
| `qtpy6.web.stockage` | `lire(cle)`, `ecrire(cle, texte)`, `effacer(cle)` sur `localStorage` (du texte, quelques Mio, qui survit au rechargement) ; `monter(dossier)` range un dossier dans IndexedDB (des fichiers ordinaires, binaires compris, jusqu'au quota de l'origine) et y remet ceux de la visite précédente, `synchroniser(attendre=False)` l'y recopie après une écriture ; `telecharger(nom, contenu, mime, lien=None)`, le seul chemin vers le disque de l'utilisateur (tout de suite, ou par un `<a>` de la page qu'il clique). |
| `qtpy6.web.assembler` | `assembler(archive, fichiers, paquets, distributions, polices)` écrit le zip que la page dépaquette : des fichiers, des paquets purs Python pris là où ils sont installés (`qtpy6`, `qtpy6.web` compris, et ceux de l'application), des distributions avec leurs métadonnées, des polices. `polices(*motifs)` : des globs, erreur si aucun fichier. |
| `qtpy6.web.sonde` | `python -m qtpy6.web.sonde page.html capture.png [--racine DIR] [--delai 120] [--etat fini] [--taille 1000x900] [--zoom 2] [--tactile]` : sert `--racine` en local, ouvre la page dans Firefox sans interface, attend `window.etat`, imprime `window.journal`, capture l'écran et écrit chaque image de `window.captures` (`{suffixe: png en base64}`) en `capture_<suffixe>.png`. Code de retour 0 si l'état attendu est atteint. |
| `qtpy6.web.lancer(script, args=(), pret=None, module=None)` | Exécute un script écrit pour le bureau comme `python script args…` (avec `module`, `script` est son `__main__.py` et c'est `python -m module` qui est imité : imports relatifs compris) ; `app.exec()` y suspend jusqu'à `quit()`, `sys.exit` est rattrapé et donne le code de retour ; `pret()` quand l'application entre dans `exec()`. À appeler d'une entrée suspendable : `lancer` de `qtpy6web.js`. |
| `qtpy6.web.lanceur` | `executer(chemin, args, pret)` : un `.py`, ou un `.zip` dont `point_d_entree` trouve le script — `__main__.py` à la racine, `paquet/__main__.py` (par `-m`), `paquet/paquet.py` ou `nom_du_zip.py`, le seul `.py` ; un zip dont la racine n'est qu'un dossier (le « Download ZIP » de GitHub) est lu depuis ce dossier. Ce que fait tourner la page de lancement (section « Hébergement »). |
| `qtpy6.web.construire` | `python -m qtpy6.web.construire app.py [site] [--pyodide URL] [--paquet p]… [--distribution d]… [--police f]… [--roue f.whl]… [--titre t]` : le site complet d'une application de bureau (page, chargeur, archive). |
| `qtpy6.web.pdf` | Les doublures de `QPdfDocument` (`load` d'un chemin ou d'un `QIODevice`, `status`, `pageCount`, `close`, leurs signaux) et `QPdfView` (`setDocument`, `setDocumentMargins`, `setPageSpacing`, modes gardés sans effet : toujours ajusté à la largeur, pages les unes sous les autres ; liens internes suivis au clic ; `setPageLimit`). Posé par `qtpy6.QtPdf` et `qtpy6.QtPdfWidgets`. En natif, ces deux modules sont les vrais, et `QPdfView` y gagne la sélection à la souris et Ctrl+C, le suivi des liens internes (le `QPdfView` de Qt n'a ni l'un ni l'autre) et `setPageLimit(n)`, ajout de qtpy6 : les `n` premières pages seules (ascenseur borné, la suite masquée). |
| `qtpy6.web.bloquant` | Les `exec()` et boîtes statiques suspendus (première ligne du tableau d'en tête), le report des slots venus de Qt vers une entrée suspendable, et la pompe de la boucle d'événements (section « Pièges »). Posé par `QtCore`/`QtWidgets` de qtpy6 : rien à importer. |
| `qtpy6.web.fils` | `QThread` (`run()` redéfini, ou un travailleur `moveToThread`), `QThreadPool`, verrous et `time.sleep` coopératifs ; un interblocage lève `RuntimeError` au lieu de figer la page. Posé par `QtCore` de qtpy6. |
| `js/qtpy6web.js` | `preparer(conteneur, {indexURL, archives, roues, env, sur_ligne, progres, tailles, brotli})` : charge Pyodide-Qt et les archives en parallèle, dépaquette, charge les roues WebAssembly par URL (`roues`, pour une extension compilée : le lock de Pyodide-Qt est vide, ni `loadPackage("nom")` ni micropip ; une adresse qui finit par `.whl`, sans requête `?v=` : Pyodide y lit le nom du paquet), pose `env` (`QT_API=pyqt6` par défaut) et met chaque dossier d'archive dans `sys.path` ; rend l'objet Pyodide. `progres(fraction)` reçoit l'avancement, de 0 à 1 sans jamais reculer : les octets reçus par `fetch` pendant le chargement, comptés sur un `clone()` de la réponse (l'original reste intact, Chrome garde son cache de wasm compilé) ; `tailles` (`{nom: octets}`) donne la taille DÉCOMPRESSÉE des gros fichiers, celle qu'on compte, quand `Content-Length` ne donne que la compressée (gzip de GitHub Pages). `pyodide.asm.wasm`, `python_stdlib.zip` et les noms de `brotli` (une archive écrite en `ZIP_STORED` par `assembler(compression=…)`) sont demandés d'abord en `NOM.br` et décompressés dans la page (`DecompressionStream("brotli")`, Firefox 155), le fichier lui-même en repli (navigateur sans Brotli, ou pas de jumeau) : GitHub Pages ne sert qu'en gzip, et `hebergement/telecharger.sh` publie les jumeaux de Pyodide-Qt (premier chargement 4,7 → 3,7 s à 50 Mbit/s, mesuré le 02/10/2026). Une réponse marquée de l'en-tête `DECOMPRESSE` (exporté) est prise telle quelle : c'est celle d'un service worker qui range le jumeau déjà décompressé. La molette est remise à la mesure du bureau (`molette`) : Qt-WASM faisait d'un pixel du navigateur un demi-pixel défilé, et d'un cran de Firefox (3 lignes) 18 px au lieu de 60 ; chaque roulement sur le conteneur est rejoué en pixels doublés (une ligne = 20 px). `lancer(py, script, args)` : `qtpy6.web.lancer` dans une entrée suspendable, rend `{pret, fin}` (deux promesses : l'application est dans `exec()`, le script est fini avec son code). `print` et `journal` : le journal horodaté (console, `window.journal`, `sur_ligne`) que lit la sonde. `rendu()` : attend quelques images pour qu'une capture voie la fenêtre. |
| `js/pdf_vue.js`, `js/pdfjs/` | La vue PDF de la page (rendu paresseux, couche de texte de pdf.js) et pdf.js 6.2.108 (`versions.json`, licence Apache 2 en tête des fichiers), chargés par URL `blob:` au premier `QPdfView`. |
| `js/travailleur.js` | Le Worker (lu par `importlib.resources`, lancé depuis une URL `blob:`). |
| `js/gabarit.html` | La page minimale, que `construire` remplit (sinon à copier) : conteneur `position: fixed; inset: 0` qui **a sa taille dès le chargement** (Qt la prend au démarrage ; `display: none` donne une fenêtre de 0 px, cacher par `visibility`), message d'attente, `window.etat`. |

### Le worker : un sous-processus sans processus

Le navigateur n'a pas de `QProcess`, et Qt-WASM tourne dans le fil de la page : un calcul long, le programme d'un
utilisateur, une boucle infinie y gèleraient l'écran. `Travailleur` lance un **Web Worker** avec un Pyodide ordinaire
(pas Pyodide-Qt), y dépaquette des archives, y importe un module, et appelle ses fonctions :

```python
from qtpy6.web.travailleur import Travailleur

w = Travailleur("pyodide/", [("app.zip", "/home/pyodide/app")], "echo", parent=fenetre)
w.sortie.connect(lambda numero, texte: ...)    # ce que la fonction imprime, au fil de l'eau (même sans "\n")
w.termine.connect(lambda numero, retour: ...)  # le retour (dict, list, str, nombres, None convertis)
w.erreur.connect(lambda numero, texte: ...)    # la trace
w.expire.connect(lambda numero: ...)           # rien au bout de `delai`
numero = w.appeler("echo", "bonjour", delai=60)
w.tuer()                                       # le seul « Arrêter » qu'un navigateur connaisse ; le prochain appel relance
```

Dans le navigateur, `qtpy6.QtCore.QProcess` EST `ProcessusWeb` (alias snake_case compris) : le code écrit pour le
bureau, `QProcess(self).start(sys.executable, ["-u", "enfant.py", …])`, tourne sans une ligne changée. Le script (ou
`-m module`) est lancé en `__main__` dans un Web Worker neuf, avec un Pyodide ordinaire : son dossier, le dossier de
travail et le dossier temporaire (`tempfile.gettempdir()`, où un parent dépose souvent ce qu'il passe à l'enfant) y sont
recopiés au même chemin (zip, sans `__pycache__`) ; `sys.argv` et le dossier de travail sont ceux du bureau. Ce que
l'enfant écrit sur disque ne revient pas au parent. Ce que `write` envoie
est son stdin, qu'il lit comme sur le bureau (`input()`, `sys.stdin.readline()`, `for ligne in sys.stdin` attendent la
prochaine écriture), `closeWriteChannel` lui donne la fin de fichier ; stdout arrive par `readyReadStandardOutput`, stderr par
`readyReadStandardError` (les deux par le premier avec `setProcessChannelMode(MergedChannels)`), et `finished(code)`
porte le code de `sys.exit`. Les options d'une lettre (`-u`, `-B`) sont
sans objet ; `-c`, `-X`, `-W` lèvent `ValueError`.

L'attente sur stdin tient à **JSPI** (`pyodide.ffi.run_sync`, le code tournant sous `runPythonAsync`), sans
`SharedArrayBuffer` : elle marche donc dans le cadre isolé du site, sans COOP/COEP (Firefox 155, mesuré le 27/09/2026 :
l'essai ci-dessous rend dans le cadre exactement ce qu'il rend sur le bureau). JSPI n'ajoute aucune exigence : la
page elle-même en a besoin (Pyodide-Qt, mesuré Firefox avec `javascript.options.wasm_js_promise_integration` à faux :
« WebAssembly stack switching not supported », rien ne démarre). Safari ne l'a qu'à partir de la 27 (bêta à la WWDC
de juin 2026, non essayé ici) : un iPad en 26 ne lance aucune application qtpy6. Chaque `start` coûte un Pyodide (~1,4 s) :
c'est un processus, pas un fil. Le Pyodide du worker vient de `versions.json` (jsdelivr), ou de
`travailleur.configurer(indexURL)`. Les URL passées au worker sont relatives à la **page** (le worker naît d'un `blob:`
et n'a pas d'adresse propre : elles sont rendues absolues côté Python) ; un `import()` de `pyodide.mjs` depuis un autre
hôte exige CORS.

```python
p = QProcess()                                   # le même code sur le bureau et dans le navigateur
p.readyReadStandardOutput.connect(lambda: print(bytes(p.readAllStandardOutput()).decode(), end=""))
p.finished.connect(lambda code, *_: app.quit())  # enfant.py : input(), puis sum(int(l) for l in sys.stdin), sys.exit(3)
p.start(sys.executable, ["-u", "enfant.py", "arg1"])
p.write(b"Alice\n2\n3\n"); p.closeWriteChannel()
```

`subprocess.run` et `subprocess.call` (donc `check_output`, `check_call`) sont doublés de même (`sous_processus`) : le programme tourne dans
un `ProcessusWeb`, et l'appel attend sa fin suspendu par JSPI, la page continuant pendant ce temps. `input`,
`capture_output`, `stdout`/`stderr` (`PIPE`, `DEVNULL`, `STDOUT`, fichier), `text`, `timeout`, `check`, `cwd` sont
tenus. Comme un `exec()`, il n'attend que dans une entrée suspendable (script principal, slot) : ailleurs,
`RuntimeError`. Un autre programme que Python lève `FileNotFoundError`, comme un exécutable absent du bureau.

## Rendre une application qtpy6 compatible

Le plus souvent rien : `construire` et le script tel quel. Ce qui reste différent du bureau, mesuré :

1. **Un `exec()` bloque dans un slot, pas dans une méthode virtuelle.** Dans un slot (un `clicked`, un `triggered`, la
   fonction d'un `QTimer.singleShot`, le script principal), `QDialog.exec()`, `QMessageBox.question()`, `menu.exec()`, `QFileDialog.getOpenFileName()` attendent
   et rendent leur valeur comme en natif. Dans une méthode que Qt appelle lui-même (`contextMenuEvent`,
   `mousePressEvent`, `closeEvent`…), rien ne peut suspendre : `exec()` y ouvre sans bloquer et rend la valeur d'un
   abandon (`Rejected`, `None`), avec un avertissement une fois. Y préférer `menu.popup(pos)` et les signaux, ou
   en sortir par `QTimer.singleShot(0, …)`.
2. **Un `exec()` que Qt lance en C++ ne bloque pas** : le menu d'un `QPushButton`/`QToolButton` (`setMenu`, `showMenu()`)
   s'ouvre et `showMenu()` revient aussitôt ; le choix arrive par `triggered`, comme il se doit.
3. **Les fils sont coopératifs** (Pyodide-Qt est mono-fil : ni `SharedArrayBuffer`, ni en-têtes COOP/COEP, un serveur
   statique nu suffit). Un `run()` qui calcule sans jamais appeler `time.sleep`, `msleep`, un verrou ou `wait()` garde la
   main jusqu'au bout et fige l'écran pendant ce temps ; `threading.Thread` et `multiprocessing` ne sont pas doublés. Un
   vrai calcul long va dans un `Travailleur`.
4. **`QProcess` lance un script Python, pas un exécutable quelconque** : `sys.executable` et un `.py` (ou `-m`) de
   l'application, dans un worker (section « Le worker ») ; `subprocess.run` aussi, dans une entrée suspendable. Tout
   autre programme lève `FileNotFoundError`.
5. **Les fichiers** vivent dans le système de fichiers de Pyodide (en mémoire, perdu au rechargement) : ce qui doit
   survivre passe par `stockage.ecrire` (du texte), ou par un dossier que `stockage.monter` range dans IndexedDB au
   démarrage — vide au montage, qui cache son contenu : les fichiers livrés avec l'application se recopient dedans au
   premier lancement — et que `stockage.synchroniser()` recopie après chaque écriture (une copie à la fois, une écriture
   venue pendant la copie en relance une à sa fin). Éprouvé dans Firefox le 01/10/2026 : écriture, copie, démontage,
   remontage, octets relus identiques ; sans `synchroniser`, le fichier est perdu. `monter` demande aussi
   `navigator.storage.persist()`, sans quoi le navigateur peut effacer l'origine quand le disque se remplit. `QFileDialog.getOpenFileName` ouvre le sélecteur du navigateur et y dépose le
   fichier choisi ; `getSaveFileName` demande un nom, et le fichier est téléchargé dès que l'application l'a écrit
   (`stockage.telecharger` pour le faire soi-même).
6. **Les polices** : livrer celles de l'interface et la fixe dans l'archive (`assembler(..., polices=...)`), les déclarer
   à `application(polices=..., defaut=...)`, `QFontDatabase.systemFont(FixedFont)` pour les éditeurs, comme en natif. Sans cela Qt-WASM dessine avec sa police
   de secours, différente du natif ; et un symbole qu'aucune police livrée n'a (⭘, ◉…) sort en carré vide, là où le natif
   le prend dans une police système : livrer un sous-ensemble (`fontTools.subset`, les blocs U+2190-U+2BFF de Noto Sans
   Symbols 2 font 134 Kio).
7. **Le doigt** : `tactile.activer_au_doigt()` avant les widgets (`activer()` si `detecte()`, sinon au premier doigt), `defiler_au_doigt` sur les zones défilantes, `Rangee` là où
   une barre de boutons imposerait sa largeur à la fenêtre.
8. **La fenêtre principale en `show_full_screen()`** dans le navigateur : tout le conteneur, sans barre de titre (une
   fenêtre Qt-WASM ordinaire a une barre de titre dessinée par Qt, que l'utilisateur peut déplacer et fermer).
9. **PyQt6 sous le capot** : qtpy6 traduit l'API, mais pas ce que PyQt6 ne fait pas. Pas d'arguments nommés de propriétés
   dans les constructeurs (`QPlainTextEdit(read_only=True)` échoue : setters), et une méthode redéfinie en Python se
   teste en camelCase (`heightForWidth`) — l'appel snake_case tombe sur la méthode de base C++.
10. **Une méthode, pas une lambda, branchée sur un signal** (vaut aussi en natif). Le binding ne tient une méthode liée
   que faiblement, mais garde en vie tout ce qu'une lambda ou une fonction locale capture : un widget qui capture son
   parent le tient alors en vie, et quand Qt détruit ce widget, la lambda libérée emporte la dernière référence au
   parent, détruit au milieu de la destruction de son enfant (segmentation fault, mesuré sous PySide6 le 01/10/2026).
   Un argument du signal à jeter : une méthode sans ce paramètre (le binding n'en passe pas plus que la méthode n'en
   prend) ; une valeur à fixer : un attribut, ou `self.sender()` et sa `property()`. Seule exception, `destroyed` : son
   slot ne peut pas être une méthode de l'objet détruit (`pdf.py`).

Puis `construire` (ou, pour une page à soi, `assembler` l'archive et copier `js/gabarit.html`), et vérifier par la
sonde : `python -m qtpy6.web.sonde --racine site site/index.html capture.png`, en lisant la capture.

## L'exemple

`exemple/` est la preuve sans autre application : un compteur (`compteur.py`, un bouton, un affichage, une zone d'écho)
et un worker `echo.py` qui imprime une invite sans retour à la ligne, attend, répond et rend un dict.

```bash
# Pyodide-Qt dans exemple/pyodide-qt/ (hebergement/telecharger.sh, section Hébergement) et un Pyodide ordinaire dans
# exemple/pyodide/ (le tarball npm `pyodide` 314.0.7, ou son dossier full/ du CDN) : ni l'un ni l'autre ne sont versionnés
python exemple/construire.py                                     # exemple/app.zip (qtpy6 et deux polices)
python -m qtpy6.web.sonde --racine . "exemple/index.html?auto" capture.png
```

`?auto` clique le bouton depuis la page, attend l'écho, et pose `window.captures = {grab}` (le `grab()` de la fenêtre).
Mesuré le 26/09/2026 (Firefox sans interface, fichiers en local) : Pyodide-Qt chargé et archive dépaquetée en 1,2 s,
fenêtre montrée en 0,27 s de plus, worker prêt 1,2 s après son démarrage, écho revenu en 1,75 s (l'invite sans `\n` arrive
tout de suite, en message séparé), tas WebAssembly 35 Mio.

En natif : `python exemple/compteur.py` ouvre la même fenêtre (le worker ne s'y lance pas : `Travailleur` ne sert que
dans le navigateur).

## Tests

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_web.py tests/test_stockage.py -q
```

En natif, tout s'importe et est inerte ; les doublures sont vérifiées dans un sous-processus où `sys.platform` est forcé à
`emscripten` avant l'import de qtpy6 (`QProcess` est `ProcessusWeb`, la police fixe est celle qu'on a chargée). Les
`exec()` suspendus et les fils coopératifs y sont éprouvés sous PyQt6 avec `greenlet`, qui imite JSPI (des piles qui se
suspendent et reprennent dans n'importe quel ordre) et son mensonge de `can_run_sync()` ; sans PyQt6 ou greenlet, ces
tests sont sautés.

Ce que le navigateur fait vraiment se mesure avec la sonde sur `exemple/` (section précédente) : c'est le test
d'intégration, il demande Firefox, geckodriver et selenium.

## Servir la page par Google Apps Script, sans serveur à soi

Un tableur Google et son projet Apps Script suffisent comme serveur : `doGet` sert la page, et l'application appelle
des fonctions du script par `google.script.run` (lire un fichier du Drive, déposer un résultat, le reprendre depuis un
autre appareil), sous le compte de celui qui déploie (`executeAs: USER_DEPLOYING`, le script écrit dans SON Drive) et
sans compte pour les utilisateurs (`access: ANYONE_ANONYMOUS` ; le prix : qui connaît le nom d'un utilisateur peut
rouvrir ce qu'il a déposé). Google affiche un bandeau « Cette application a été créée par un utilisateur de Google Apps
Script » au-dessus de la page, qui ne s'enlève pas. *Mesuré en septembre 2026 avec une page Pyodide sans Qt (un lecteur
d'épreuves HTML) ; pour Qt-WASM, les inconnues sont à la fin de cette section.*

**Ce que Google impose, et la réponse.**
- **Une page d'un seul fichier `.html`** : ni CSS, ni JS, ni zip à côté, pas de chemins relatifs. Un script de
  construction fabrique le fichier servi à partir des sources (feuille de style et scripts en ligne, par des
  remplacements dont chacun est asserté unique) ; le dérivé n'est pas versionné, on n'édite que les sources.
- **Deux iframes sandbox** : `script.google.com/macros/s/<id>/exec` → iframe `*.googleusercontent.com` → iframe
  `userCodeAppPanel`, où tourne le code. `location.search` y est vide : `doGet` écrit `e.parameter` dans la page
  (`<script>window.PARAMETRES = <?!= parametres ?>;</script>`, avec `page.parametres = JSON.stringify(e.parameter)`),
  et `new URLSearchParams(window.PARAMETRES ?? location.search)` sert en local comme chez Google (`URLSearchParams`
  accepte un objet). Chromium y signale « An iframe which has both allow-scripts and allow-same-origin for its sandbox
  attribute can escape its sandboxing » : c'est Google, inoffensif.
- **`importScripts` est refusé** dans un Worker né de cette page ; **`import()` passe** (mesuré le 25/09/2026).
  `js/travailleur.js` est déjà ce qu'il faut : un module ES lancé depuis un `blob:`, qui charge Pyodide par `import()`.
- **`localStorage`** est celui de l'origine `googleusercontent`, pas de l'adresse `/exec` : `stockage` y marche (`lire` rend
  `None` pour une clé absente), la reprise au rechargement aussi.
- **Ni COOP ni COEP** : Google ne les pose pas, Pyodide-Qt n'en a pas besoin.
- **Les fichiers de l'application** : un petit fichier (une archive de quelques centaines de Kio, un document) se
  demande au script, qui rend le base64 d'un fichier du dossier Drive du tableur (filtrer le nom, `/^[^\/\\]+\.(zip|…)$/`,
  pour que rien d'autre ne sorte du Drive). Pyodide-Qt (36 Mo, dont `pyodide.asm.wasm` 32 Mio) et une archive de
  plusieurs Mo sont **hors de portée d'Apps Script** : un hôte statique avec CORS (GitHub Pages, un serveur à soi qui
  envoie `Access-Control-Allow-Origin`) est inévitable, et il doit compresser (section suivante). Dans la page servie
  par Google, `indexURL`, `archives`, `roues` et le `indexURL` du `Travailleur` sont des **URL absolues** de cet hôte :
  `preparer` et `Travailleur` les rendent absolues par rapport à `location.href`, qui est celui de l'iframe. Le Pyodide
  ordinaire du worker peut venir de jsdelivr (`https://cdn.jsdelivr.net/pyodide/v314.0.7/full/` : CORS, mesuré).

**Le script, en quatre fonctions** (`Code.gs`, lié au tableur : `SpreadsheetApp.getActive()` le désigne, et son dossier
Drive est `DriveApp.getFileById(SpreadsheetApp.getActive().getId()).getParents().next()`) :

```javascript
function doGet(e) {
  const page = HtmlService.createTemplateFromFile("page");      // page.html, le seul fichier
  page.parametres = JSON.stringify(e.parameter);
  return page.evaluate().setTitle("…").addMetaTag("viewport", "width=device-width, initial-scale=1");
}
function fichier(nom) {                                          // un fichier du dossier, en base64
  if (!/^[^\/\\]+\.(zip|dat)$/.test(nom)) throw new Error("nom refusé");
  const f = dossier_().getFilesByName(nom);
  if (!f.hasNext()) throw new Error(nom + " introuvable");
  return Utilities.base64Encode(f.next().getBlob().getBytes());
}
function deposer(r) {                                            // r : {utilisateur, contenu, …} ; ne rend rien
  const verrou = LockService.getScriptLock(); verrou.waitLock(30000);   // deux dépôts en même temps
  try { /* écrire ou remplacer <utilisateur>.dat dans un sous-dossier ; une ligne du tableur si l'on veut y lire l'état */ } finally { verrou.releaseLock(); }
}
function reprendre(utilisateur) {                                // {contenu, date: f.getLastUpdated().getTime()} ou null
}
```

Un modèle : les noms des champs et des arguments sont ceux de l'application, pas de Google.

Côté page, un appel est une promesse :
`new Promise((ok, echec) => google.script.run.withSuccessHandler(ok).withFailureHandler(echec)[fonction](...args))`.
`deposer` ne rend rien : le succès est l'absence d'échec. La date que rend `reprendre` arbitre entre la copie locale
(`stockage.ecrire`, avec une seconde clé `<cle>|date` posée à chaque écriture) et la distante : la plus récente gagne. Depuis Python, le même appel se fait par
`js.google.script.run…` avec des arguments convertis (`pyodide.ffi.to_js(d, dict_converter=js.Object.fromEntries)`) et
des gestionnaires gardés par `create_proxy` ; ou l'envoi reste en JavaScript et le pont Python n'expose que l'état à
déposer, ce qui est plus simple.

**L'outillage** : `clasp` (`npm install -g @google/clasp`, `clasp login`, l'API Apps Script activée sur
`script.google.com/home/usersettings`) et `rclone` (un remote `drive`, `scope drive`). *Une fois* : `clasp create --type
sheets --title <nom> --rootDir . --json` **dans un dossier temporaire** (le `Code.gs` vide du projet neuf n'écrase pas le
vôtre), n'en garder que `scriptId` dans `.clasp.json` ; `appsscript.json` avec sa section `webapp` (`executeAs`,
`access`) ; `clasp push -f` ; `clasp create-deployment -d "mise en place" --json` rend l'id du déploiement, l'URL est
`https://script.google.com/macros/s/<id>/exec`, à ouvrir une fois connecté au compte pour autoriser le script (Drive,
Sheets). Si cette page répond « Un problème est survenu », l'éditeur du projet (`script.google.com/d/<scriptId>/edit`,
Exécuter > une fonction) pose la même demande, et elle y aboutit (vu le 25/09/2026). *Chaque mise à jour* : construire
la page, `clasp push -f && clasp deploy -i <id du déploiement> -d "<libellé>"`, `rclone copy` des fichiers du Drive.
**Sans `-i`, `clasp deploy` crée un NOUVEAU déploiement, donc une nouvelle URL**, et le lien déjà distribué meurt (coûté
le 25/09/2026). `rclone` avertit que son client_id partagé pour Google Drive est retiré courant 2026 : répondre `y`
jusque-là, puis créer le sien dans la console Google Cloud.

**Vérifier en ligne** : Selenium + Chromium `--headless=new` (Firefox de la sonde en local, Chromium pour Google : il
faut le réseau, donc un poste qui l'a), descendre les deux iframes (`switch_to.frame` de la première iframe de chaque
niveau), attendre `window.etat`, lire `window.journal`. Le critère d'un dépôt réussi est un dépôt **postérieur** à
l'action testée (poser `window.envoi = {date}` à chaque dépôt et comparer à un `Date.now()` pris après l'action), pas « un
dépôt » : une page qui dépose dès l'ouverture (ce qu'elle a repris) validait une reprise vide (coûté le 25/09/2026). Puis
`localStorage.clear()`, rechargement : l'état doit revenir depuis le Drive.

**Inconnues pour Qt-WASM**, jamais mesurées au 26/09/2026, à lever dans l'ordre sur une page minimale (`exemple/`) avant
de brancher une application : (1) Qt-WASM dessine-t-il dans l'iframe sandbox de Google (canvas, `requestAnimationFrame`,
clavier) ; (2) `import()` cross-origin depuis cette iframe vers un hôte à soi (mesuré pour jsdelivr seulement) ;
(3) le quota `localStorage` de l'origine `googleusercontent` ; (4) la mémoire (+360 Mio sur un poste de bureau) sur les
postes visés ; (5) le temps de chargement à froid derrière le bandeau, avec la compression de l'hôte choisi.

## Pièges et mesures (Qt-WASM 6.10, Pyodide-Qt 0.29.3)

- **La boucle d'événements ne tourne pas seule** : compilé avec JSPI, Qt-WASM n'envoie ni minuteries ni événements
  postés de lui-même, il attend qu'on reprenne SA boucle `exec()` suspendue (`onTimer` : `if (useAsyncify()) return;`,
  `qeventdispatcher_wasm.cpp`) ; or cette boucle native, imbriquée, arrête tout (`Aborted()`). Mesuré : un `QTimer` ne
  part que tant que la page redessine, puis plus du tout, `exec()` ou pas. `bloquant` pose donc une pompe
  (`setInterval` de 10 ms qui appelle `processEvents()`), dès le chargement de `QtCore` ; avec elle, soixante
  tics de 100 ms sur six secondes.
- **`can_run_sync()` ment** pendant qu'une entrée est suspendue : un slot que Qt appelle alors y voit `True`, mais un
  `run_sync` n'y reprend jamais (ni retour ni erreur). `bloquant` tient donc son propre compte (`_actif`, `_suspendus`) :
  un slot venu de Qt n'est exécuté sur place que si aucune pile n'attend ; sinon il part à la tâche asyncio suivante.
- **Un `started` de `QThread` émis avant `exec()`** laissait le `quit()` d'un travailleur rapide le précéder (`wait()`
  rendait `False`) : il est émis à la tâche suivante, comme les slots d'un autre fil en Qt.

- **Téléchargement** : `pyodide.asm.wasm` fait 32 Mio, 9,9 en gzip, 8,6 en brotli ; l'hôte doit compresser (une classe
  de 30 postes à froid : 300 Mio si oui, 1,2 Gio sinon). Une archive d'application ne se compresse plus (zip).
- **Mémoire** : +360 Mio sur un Firefox de bureau pour une application de 2 000 lignes ; un téléphone d'entrée de gamme
  peut tuer l'onglet, d'où `stockage` pour reprendre au rechargement.
- **Listes déroulantes** : Qt-WASM 6.10 referme un `QComboBox` au relâchement qui suit l'appui d'ouverture (le
  relâchement tombe sur le cadre de la liste, personne ne le prend). Un filtre d'événements sur la liste, qui consomme ce
  relâchement, le corrige ; la sonde `--tactile` sert à le vérifier.
- **Clavier virtuel** : un clic dans un champ donne le focus à l'`<input>` caché de Qt (`inputmode=text`, le clavier d'un
  téléphone monte) ; une liste déroulante au `focus-helper` (`inputmode=none`).
- **Lecteur d'écran** : Qt-WASM n'expose que « boutons et cases à cocher » ; une vue complexe ne produit rien. Un usage
  accessible reste au DOM.
- **Ce que le navigateur ne fait plus** dans la fenêtre Qt : sélection et recherche dans le texte, traduction
  automatique, clic droit. Safari (iPad, iPhone) : pas avant la 27, la première à avoir JSPI (section « Le worker ») ; non essayé.
- **Deux Pyodide** : la page (Pyodide-Qt, roues par URL seulement, ABI `cp313-cp313-pyemscripten_2025_0_wasm32`) et le
  worker (Pyodide ordinaire, Python 3.14) ; les deux versions sont dans `versions.json`.
- **`import js`** n'existe que dans le navigateur : jamais au niveau d'un module qui doit s'importer en natif (un test le
  garantit ici) ; dans le worker, `js` existe mais ni `document` ni `localStorage`.
- **Un PDF par-dessus le canevas** : un `<div>` de la page, pas un `<iframe>` — cliquer dans un iframe fait perdre le
  focus à la page (`blur`), ce qu'une surveillance d'épreuve compte comme une sortie ; un `<div>` non. Le `<div>` est
  au-dessus de Qt : il n'est montré que si le widget est visible, **activé** (un rideau posé par `setEnabled(False)` le
  cache sans code dédié) et qu'aucun menu ni boîte modale d'une autre fenêtre n'est ouvert — Qt les dessinerait dessous.
  Sa place suit le widget à chaque événement de taille ou de visibilité, et toutes les 100 ms pour ce qu'aucun
  événement ne signale (un séparateur déplacé). Le chargement est asynchrone (`status() == Loading`, puis `Ready`).
  Ctrl+C et Ctrl+F sont ceux du navigateur tant que le `<div>` a le focus.
- **La sélection en natif** : `QPdfDocument.getSelection(page, a, b)` ne rend rien si un point tombe hors d'un
  caractère (une marge, un interligne) ; `QPdfView` accroche donc chaque point à la ligne de texte la plus proche, les
  lignes étant regroupées depuis `getAllText().bounds()`, qui rend parfois un rectangle par glyphe (PDF de
  `QPdfWriter`). Sans cet accrochage, le test de copie échoue. Une sélection reste dans une page.
- **Un document enfant de sa vue plante Qt (6.11 : PySide6 6.11.1, PyQt6 6.11.0)** : `QPdfDocument(vue)` puis `vue.setDocument(...)`
  fait planter la destruction de la vue (code 139, souvent à la sortie du programme). Pile relevée sous gdb :
  `~QWidget` détruit ses enfants → `~QPdfDocument` → `close()` émet `statusChanged` → le slot de la vue s'exécute sur un
  objet à moitié détruit (`~QPdfView` ne s'est pas désabonné). Aucun rapport trouvé sur bugreports.qt.io au 29/09/2026 ;
  les exemples de Qt donnent au document la fenêtre principale pour parent, jamais la vue. Contournement, dans le
  `QPdfView` natif de qtpy6 : `setDocument` détache de la vue un document qui en est l'enfant (`setParent(None)`) et le
  garde dans un attribut Python, si bien qu'il survit à la vue. Écarté : exiger un document sans parent, piège silencieux
  pour le cas le plus naturel. Test : `test_pdf_document_enfant_de_la_vue` (dans un processus à part, le plantage
  emportant pytest), qui échoue sans le contournement.
- **La sonde** : Firefox ne descend pas sous 500 px de large (une largeur de téléphone se mesure en natif hors écran, ou
  avec `--zoom`) ; Chromium n'ouvre pas sans socket Unix, ce qu'un bac à sable peut interdire. Selenium Manager tente de
  télécharger geckodriver avant de prendre celui du système : sans réseau, ses messages sont du bruit, pas une panne.

## Hébergement

Pyodide-Qt ne se versionne pas (PySide6 : 41 Mo, dont le `.wasm` de 35 : 11 en gzip, mesuré en local ; PyQt6 : 36 Mo,
dont 32 de `.wasm`) : `hebergement/telecharger.sh [pyside6|pyqt6]` rapporte la release épinglée dans
`qtpy6/web/versions.json` (`pyodide_pyside6` par défaut, `pyodide_qt` avec `pyqt6` ; `archive`, `sha256` vérifiée ; un
zip déjà téléchargé en argument, sans réseau) et la dépaquette, licence comprise, dans `exemple/pyodide-qt/`. Le zip
PySide6 se construit par `wasm/construire.sh paquet` (`wasm/README.md`) et se publie en release du dépôt ; son empreinte
change à chaque construction, à reporter dans `versions.json`. L'action `.github/workflows/pages.yml` fait la même chose et publie le
dossier sur GitHub Pages quand le script, `versions.json` ou elle-même changent (ou à la main, *Run workflow*) :

    indexURL: "https://smartaudiotools.github.io/qtpy6/pyodide-qt/"

Un hôte statique à part, avec CORS ouvert, est inévitable : la page importe `pyodide.mjs` par `import()` depuis une autre
origine, et l'application n'a alors plus à déployer le dossier avec sa page. Le dossier local (`./pyodide-qt/`) reste le
bon choix pour développer et pour la sonde : pas de réseau, et les mesures de temps ne comptent que le chargement.

Mise en service, une fois, avec `gh` authentifié (le jeton de l'action n'a pas le droit de créer le site : mesuré) :
`gh api -X POST repos/SmartAudioTools/qtpy6/pages -f build_type=workflow`, l'équivalent de réglages → Pages →
*Source : GitHub Actions* ; le push suivant, ou *Run workflow*, déploie. Puis, depuis n'importe où :

```bash
curl -sI https://smartaudiotools.github.io/qtpy6/pyodide-qt/pyodide.mjs | grep -i "access-control\|content-type"
curl -sI -H "Accept-Encoding: gzip, br" https://smartaudiotools.github.io/qtpy6/pyodide-qt/pyodide.asm.wasm | grep -i "content-encoding\|content-length"
```

La première doit rendre `access-control-allow-origin: *` (Pages l'envoie sur tout). La seconde dit si le `.wasm` part
compressé : sans `content-encoding`, ce sont 32 Mio à froid au lieu de 10, et il faut un hôte qui compresse le type
`application/wasm`. Mesuré au premier déploiement (26/09/2026, depuis l'ancien dépôt qtpy6web, même action) : `access-control-allow-origin: *` sur tout, `content-type:
application/wasm`, et le `.wasm` part en `content-encoding: gzip`, 10 516 295 octets pour 33 652 901 nus ; `pyodide.mjs`
aussi en gzip, `python_stdlib.zip` tel quel (2,4 Mo, déjà compressé). Aucun en-tête d'isolation (COOP/COEP)
n'est nécessaire : ce build est mono-fil. Le cache du navigateur garde le `.wasm` d'une visite à l'autre (`ETag`).

Changer de version : `versions.json` seul (`archive`, `sha256`, `version`, `abi`) ; `preparer()` compare la version
chargée à celle du fichier et l'écrit au journal si elles diffèrent. L'ABI des roues change avec le Python embarqué :
toute roue compilée pour la page est à reconstruire.

### La page de lancement : un script qtpy6, isolé du reste du site

La racine du site, `https://smartaudiotools.github.io/qtpy6/`, lance un script qtpy6 quelconque : ouvert depuis le disque
(un `.py` ou un `.zip`), ou désigné par l'adresse, `?script=URL&fichier=URL` (`fichier`, facultatif et répétable, est
passé en argument comme `python script.py fichier`). Une adresse `github.com/…/blob/…` est ramenée à
`raw.githubusercontent.com` ; le site qui sert le script doit ouvrir CORS (raw.githubusercontent.com et les gists le
font).

**Ce que le script peut importer** : la bibliothèque standard, PyQt6 (par qtpy6), qtpy6, serializejson et sa dépendance
apply, plus tout module en Python pur livré dans son `.zip` (le dossier du script est en tête de `sys.path`). Rien
d'autre ne s'installe : Pyodide-Qt n'a ni `pip`, ni `micropip`, ni catalogue de paquets, et une extension compilée
n'existe que si l'on en construit la roue WebAssembly. serializejson est la seule fournie : sa roue
(`serializejson/scripts/construit_wasm.sh`, ABI `pyemscripten_2025_0` de Pyodide-Qt 0.29.3, donc à reconstruire à
chaque changement de `versions.json`) et celle d'apply sont versionnées dans `hebergement/roues/`, et le cadre charge
toutes les roues de ce dossier avant le script (`roues.json`, écrit par `construire_site.py`). Coût mesuré le
27/09/2026 : 0,15 s au chargement, 0,4 s au premier `import serializejson`, payées seulement par qui l'importe pour la
seconde. Choix de l'utilisateur : serializejson sert à presque toutes ses applications, et la roue n'alourdit plus
chacun de leurs zip.

**Le script ne tourne pas dans la page, mais dans `cadre.html`, un `<iframe sandbox="allow-scripts allow-downloads">`
SANS `allow-same-origin`.** `smartaudiotools.github.io` est UNE origine pour toutes les Pages du compte : un script venu
d'une adresse quelconque, exécuté dans la page, lirait le stockage des autres (les copies d'élèves du lecteur de
SmartTeacher, par exemple). Dans le cadre, son origine est opaque : `localStorage`, cookies et la page parente lui sont
refusés (`SecurityError`), sans rien casser d'autre — Pyodide-Qt, les `exec()` suspendus, les Workers (créés par
`Blob`) y marchent. Mesuré dans Firefox le 27/09/2026 : un secret posé par la page parente, illisible du cadre ; la
même application, pompe comprise (3 µs par passage), qu'en page. La page de confiance télécharge ou lit les fichiers et
les passe au cadre par `postMessage` quand il se dit prêt ; elle n'écoute que lui. Deux conséquences : le cadre charge
ses propres fichiers (`qtpy6web.js`, `qtpy6.zip`, Pyodide-Qt) en mode CORS, que l'hôte doit donc ouvrir (Pages le
fait ; `http.server` non, d'où l'en-tête ajouté pour la sonde) ; et `qtpy6.web.stockage` n'y a pas de stockage, rien ne
reste d'une visite à l'autre.

`hebergement/construire_site.py [site]` assemble le site (page, cadre, chargeur, `qtpy6.zip`, roues, Pyodide-Qt et sa licence)
avec la seule bibliothèque standard : c'est ce que fait l'action, et ce qu'on sert en local pour essayer.

Le site ainsi publié distribue PyQt6, donc du GPL v3 : `hebergement/LICENSE-Pyodide-Qt.txt` est servi à côté, et
la page de lancement renvoie aux sources de la release (la recette de construction de Qt, PyQt6 et Pyodide). Le
dépôt ne contient de binaires que les deux roues de `hebergement/roues/`, chacune sous sa propre licence, que sa roue
embarque : serializejson (Prosperity Public License 3.0.0 pour l'usage non commercial, Patron License sinon) et apply
(BSD-2-Clause, roue refaite à l'identique des fichiers de la 2.0 installée, faute de réseau). Le code de qtpy6 reste MIT.

## Licence

MIT (`LICENSE.txt`). Le Pyodide avec Qt que la page charge et que l'hébergement distribue : par défaut Qt et PySide6,
LGPL v3 (`hebergement/LICENSE-Pyodide-PySide6.txt`, livrée dans le zip) ; en repli Pyodide-Qt (PyQt6), GPL v3
(`hebergement/LICENSE-Pyodide-Qt.txt`). Pyodide est MPL 2.0 ; la recette `wasm/` est MIT ; pdf.js
(`qtpy6/web/js/pdfjs/`) est Apache 2.0.
