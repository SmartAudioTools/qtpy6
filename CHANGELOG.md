# Changelog

## Non publié

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
  ne dit rien de son écran (Firefox sous Linux), et `tactile.detecte` lit aussi `navigator.maxTouchPoints`.
- `qtpy6.web.sonde --visible` : une vraie fenêtre sur l'écran, avec la synchronisation verticale du compositeur,
  pour mesurer la fluidité (hors écran, Firefox cadence ses images seul).
- `qtpy6.web.defilement.ZoneDefilante` : une QScrollArea qui, dans le navigateur, défile comme en natif. Qt-WASM n'a
  pas de défilement de surface et repeint tout le viewport à chaque pas (12 ms par image à l'échelle 2 sur le lecteur
  QCM, pour 16,7 d'écran) ; ici le contenu est déplacé sans rien salir, les lignes de l'image du backing store sont
  décalées à l'`UpdateRequest`, et seule la bande qui entre est peinte : 2 ms par image, à l'identique au pixel près.
  En natif, une QScrollArea ordinaire.
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
