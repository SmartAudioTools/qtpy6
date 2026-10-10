# Changelog

## Non publié

- Dans le navigateur, `concurrent.futures.ThreadPoolExecutor` est doublé sur les fils coopératifs : N `subprocess.run`
  soumis au pool font tourner N Web Workers en même temps, au lieu de lever `RuntimeError` (pas de fils dans Pyodide).
  `os.cpu_count()` y rend le nombre de cœurs du navigateur. Une application garde son pool natif tel quel : SmartTeacher
  corrige 3 codes en fin d'épreuve en 29 s au lieu de 54 s l'un après l'autre (`web.md`).
- Un réglage de session changé dans QtSelector vaut pour une application lancée du bureau sans relire
  `QtEnvironment.sh` (SmartTeacher), sans reconnexion : `set_env` écrit avec chaque réglage sa copie
  `QTPY6_LOGIN_<clé>`, et `get_env` ne préfère l'environnement que s'il diffère de cette copie, donc
  s'il a été posé après la connexion (`QT_STYLE=Fusion python app.py`). Sous Linux et sous Windows.
- Réglage de session `QT_STYLE` (`default`, `Fusion`, `Breeze`…), choisi dans QtSelector : le style de
  `QApplication` des applications qtpy6, sans toucher aux autres applications Qt de la session.
- Dans le navigateur, `QDrag.exec` est une vraie boucle de Qt, suspendue par JSPI, y compris ouverte par une minuterie ou un signal (appui long au doigt) : le glisser-déposer des vues d'éléments (`QListWidget`, `QTreeView`, `QTableView`…) déplace, comme en natif. Le contournement `qtpy6.web.glisser` est retiré (`web.md`, « Pièges »).
- `qtpy6.erreurs.installer()` : les exceptions non rattrapées s'affichent dans une boîte de dialogue, depuis
  n'importe quel fil (`QThread`, `threading.Thread`), en plus de la trace en console. Repris de SmartFramework
  (`ui/exceptionDialog.py`), sans l'installation à l'import ni la feuille de style de l'application écrasée.
- `Rangee` : plusieurs `addStretch()` d'une même ligne s'en partagent la place libre à parts égales, comme dans
  un `QHBoxLayout` (un seul poussait à droite ce qui le suivait, les suivants étaient ignorés) : un ressort entre
  chaque widget les espace régulièrement.
- `assembler(..., exclure=[...])` laisse des fichiers hors de l'archive, `qtpy6/web/js/pdfjs/` typiquement (1,7 Mo) :
  `qtpy6.web.pdf` charge alors pdf.js à côté de `qtpy6web.js` (`window.qtpy6Js`), au premier PDF ouvert seulement.
- Dans le navigateur, PySide6 par défaut : un Pyodide 0.29.3 où Qt 6.10.2 et PySide6 6.10.2 sont liés en
  WebAssembly, construit par la recette `wasm/` (LGPL v3, licence dans `pyodide-qt/LICENSE.txt`) ;
  `hebergement/telecharger.sh pyqt6` garde Pyodide-Qt (PyQt6) en repli. Sa bibliothèque standard est en `.pyc` :
  Pyodide chargé en 0,6 s au lieu de 1,6 s. `assembler(..., pyc=True)` fait de même pour l'archive de
  l'application (import du lecteur QCM 0,55 s au lieu de 0,9 s, archive 40 % plus lourde).
- `qtpy6.QtCore.QPropertyAnimation` est menée par les images de l'écran, sans rien changer à son API ni au
  code des applications. Qt Widgets avance ses animations à une minuterie de 16 ms que rien ne cale sur le
  rafraîchissement : une image reçoit parfois deux pas (le premier jamais affiché), la suivante aucun. Dès que la
  cible est un widget dont la fenêtre existe, `start()` retire l'animation de cette minuterie et la propriété
  prend, à chaque `UpdateRequest` de la fenêtre (`QWindow.requestUpdate` : rappel d'image du compositeur sur
  Wayland, `requestAnimationFrame` dans le navigateur), la valeur de l'heure de l'image ; `finished`, `stop`,
  `pause`/`resume`, `state` se comportent comme en natif. `par_image = False` (classe ou instance) rend celle de
  Qt. Mesuré en natif avec le même mécanisme (Wayland, 60 Hz, défilement de 1833 ms) : peintures perdues 4 → 0 ou 1,
  pas réguliers de 8 px au lieu d'alterner 7 et 8. Dans le navigateur (Firefox hors écran, 60 Hz, même défilement,
  trois passes par mode) : chaque image reçoit un envoi au canevas, pas de 8 px, contre 25 à 29 images sans envoi sur
  109 et des pas doublés de 14-17 px avec la minuterie de Qt (`qtpy6.animation`).
- Dans le navigateur : ce qui change à l'écran est envoyé au canevas dans l'image où cela change
  (`qtpy6.web._dessiner_aussitot` ; pendant un défilement, une image sur deux restait sans envoi) ; la molette
  défile autant qu'en natif (`qtpy6web.js`, `molette`) ; `preparer` reçoit `progres` et `tailles`, l'avancement
  du chargement de 0 à 1 ; `tactile.activer_au_doigt` active le tactile au premier doigt posé quand le navigateur
  ne dit rien de son écran (Firefox sous Linux), une fois ce doigt levé (appliquée sous le doigt, la remise en page
  déplaçait ce qu'il visait : le premier appui long d'une ligne Parsons ne prenait rien), et `tactile.detecte` lit aussi `navigator.maxTouchPoints`.
- Dans le navigateur, le canevas de chaque fenêtre Qt est créé avec `willReadFrequently` (`qtpy6web.js`) : tenu en
  mémoire, il reçoit l'image de chaque peinture en 1,5 ms au lieu de 8,3 à 1800 px (Intel HD, mesuré par
  SmartTeacher) ; `?lecture=0` dans l'adresse rend le comportement d'origine.
- Le `connect` enveloppé de `qtpy6.web` compte les arguments d'un `functools.partial` sur sa fonction, sans
  `inspect.signature` : à l'ouverture d'un sujet du lecteur QCM (218 questions, 948 connexions), 15 ms au lieu de 64.
- `qtpy6.web.sonde --visible` : une vraie fenêtre sur l'écran, avec la synchronisation verticale du compositeur,
  pour mesurer la fluidité (hors écran, Firefox cadence ses images seul).
- `qtpy6.web.defilement.ZoneDefilante` : une QScrollArea qui, dans le navigateur, défile comme en natif. Qt-WASM n'a
  pas de défilement de surface et repeint tout le viewport à chaque pas (12 ms par image à l'échelle 2 sur le lecteur
  QCM, pour 16,7 d'écran) ; ici le contenu est déplacé sans rien salir, les lignes de l'image du backing store sont
  décalées à l'`UpdateRequest` (celle du widget de fenêtre, la seule que Qt-WASM envoie quand un widget est sali), et
  seule la bande qui entre est peinte (par le contenu et chacun de ses descendants qu'elle touche : Qt n'y propage pas
  la région à ses enfants opaques, un en-tête de tableau restait vide), puis le viewport décalé est envoyé au
  canevas (`backingStore().flush` : Qt-WASM n'envoie que ce qu'il peint) : 2 ms par image, à l'identique au pixel près.
  La bande est salie par `QWidget.update(w, rect)`, jamais par la méthode du widget : un `update()` redéfini sans
  argument par l'application (une toile qui s'y redispose) levait TypeError à chaque pas.
  Un seul relais par fenêtre voit passer les événements, et ne visite que les zones en cours de décalage. Il remplace
  un filtre d'application par zone, soit un appel Python par événement et par page. Le décalage des lignes se fait en
  JavaScript (`copyWithin` sur une vue de l'image) : 0,4 ms par image au lieu de 1,2 en Python. L'image est relevée
  dès l'affichage, au repos (le filtre d'application posé le temps d'un Paint seulement) : sinon les deux premières
  images de la première descente montaient à 30-80 ms.
  En natif, une QScrollArea ordinaire.
- `qtpy6.paresse` : une longue page défilante paresseuse. `Paresse(zone, elements)` désactive la disposition des
  éléments à plus d'une hauteur de vue (un redimensionnement ne remet en page que ceux de l'écran), bâtit un élément
  né vide (`batie`, `batir()`) quand il entre dans la vue, et compense le défilement pour que l'écran ne bouge pas ;
  `Chantier(parent, elements)` bâtit le reste en tâche de fond par tranches de 20 ms, en pause tant qu'une page
  défile. Lecteur QCM de SmartTeacher : 20 redimensionnements 968 → 480 ms, ouverture 2,2 s plus courte dans le
  navigateur, saut de la première descente 27-69 px → 8 px.
- `qtpy6.peinture.en_image(peintre, rect, cle, dessiner)` : un dessin coûteux (`QSvgRenderer.render`, réduction
  d'image) peint une fois dans une `QImage` à la taille des pixels, avec le même décalage sous le pixel, puis posé tel
  quel aux peintures suivantes ; moteur raster seulement (un `QPdfWriter` garde les vecteurs), plafond de 48 Mo.
  Figures SVG du lecteur QCM (repeint complet) : 30-48 → 15-18 ms en natif, 47-50 → 23-29 ms dans le navigateur à ×2.
- Dans le navigateur, `deleteLater` détruit enfin : la pompe (`qtpy6.web.bloquant`) n'appelait
  que `processEvents`, qui ne traite jamais `DeferredDelete` hors d'une boucle `exec()`. Un widget
  ainsi « détruit » restait à l'écran et, son objet Python libéré, se peignait en widget natif.
- `qtpy6.QtPdf` et `qtpy6.QtPdfWidgets`. Dans le navigateur, où Qt-WASM n'a pas QtPdf,
  `QPdfDocument` et `QPdfView` sont doublés par pdf.js 6.2.108 (vendu, Apache 2) dans un `<div>`
  de la page calé sur le widget, texte sélectionnable et copiable (`qtpy6.web.pdf`). En natif,
  `QPdfView` gagne la sélection à la souris et Ctrl+C, et contourne un plantage de Qt 6.11 quand le
  document est enfant de la vue (`web.md`, « Pièges »).
- `QPdfView.setPageLimit(n)` / `pageLimit()` (ajout de qtpy6, natif et navigateur) : seules les `n`
  premières pages se voient et défilent. Les liens internes du PDF (un sommaire) se suivent au clic,
  des deux côtés ; dans le navigateur, `setDocumentMargins` et `setPageSpacing` sont doublés.
- `QPdfView.setMasks({page: [QRectF]})` / `masks()` (ajout de qtpy6, natif et navigateur) : des zones
  de page, en points, peintes en pavés unis de 12 points (illisibles à tout zoom), et leur texte
  exclu de la sélection, de la copie et, dans le navigateur, de la recherche. C'est un affichage,
  pas une protection : le PDF entier reste dans le programme ou le navigateur.

## 0.2.0 — 2026-09-27

- `qtpy6.web` : l'application dans le navigateur, sous Pyodide-Qt (fusion de l'ancien
  paquet `qtpy6web`, dont c'était tout le contenu) ; `web.md`, `exemple/`, `hebergement/`.
- Dans le navigateur seulement, `QtCore.QProcess` est un Web Worker Pyodide
  (`qtpy6.web.travailleur.ProcessusWeb`) et `QFontDatabase.systemFont(FixedFont)` rend la
  première police à chasse fixe chargée par l'application. `qtpy6web.police_fixe` et
  `qtpy6web.travailleur.Processus` disparaissent : les noms Qt les remplacent.
- Une application de bureau tourne telle quelle dans le navigateur :
  `python -m qtpy6.web.construire app.py site/` (page, chargeur, archive) et `qtpy6.web.lancer`,
  qui exécute le script comme `python app.py`, `sys.exit(app.exec())` compris.
- Dans le navigateur, `exec()` de `QApplication`, `QDialog`, `QMenu`, `QEventLoop` et les boîtes
  statiques de `QMessageBox`, `QInputDialog`, `QColorDialog`, `QFontDialog`, `QFileDialog` suspendent
  jusqu'à leur fin (JSPI, `qtpy6.web.bloquant`), y compris depuis un slot ou un
  `QTimer.singleShot` ; `QThread`, `QThreadPool`, `QMutex`,
  `QWaitCondition`, `QSemaphore` et `time.sleep` sont coopératifs (`qtpy6.web.fils`) ; une pompe
  fait tourner la boucle d'événements de Qt-WASM, dont les minuteries s'arrêtaient sinon.
- `Rangee` et les autres `Disposition` gardent `heightForWidth` en cache jusqu'au prochain
  `invalidate()` : Qt la redemandait des centaines de fois par redimensionnement.
- Extras `sonde` (selenium) et, dans `test`, `greenlet`.

## 0.1.0 — 2026-09-19

Première version.

- API de PySide6 (`Signal`/`Slot`/`Property`, `exec`/`print`, énumérations
  scopées et non scopées, `QFileDialog.…(dir=)`) sur PySide6 ou PyQt6.
- Alias snake_case de chaque méthode, méthode statique et signal, selon la règle
  de shiboken ; le camelCase reste disponible.
- Tout module du binding est servi (`qtpy6.QtNetwork`, `qtpy6.QtTest`…).
- Réglages de session `QT_API`, `QT_SCALE`, `QT_FONT`, `QT_FONT_SIZE`
  (`get_env`/`set_env`, `scaled`), fenêtre `qtselector`.
- Bindings Qt5 (PySide2, PyQt5) non pris en charge.
- `QTimer.single_shot(msec, receiver, slot)`, forme à trois arguments de PySide6
  (tir abandonné si `receiver` est détruit avant), émulée sur PyQt6 par un `QTimer`
  enfant du récepteur.
- `QtWidgets.QFileSystemModel` sur PyQt6, qui l'a rangé dans `QtGui` (PySide6 le garde
  dans `QtWidgets`).
