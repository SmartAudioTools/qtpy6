# Changelog

## Non publié

- `qtpy6.QtPdf` et `qtpy6.QtPdfWidgets`. Dans le navigateur, où Qt-WASM n'a pas QtPdf,
  `QPdfDocument` et `QPdfView` sont doublés par pdf.js 6.2.108 (vendu, Apache 2) dans un `<div>`
  de la page calé sur le widget, texte sélectionnable et copiable (`qtpy6.web.pdf`). En natif,
  `QPdfView` gagne la sélection à la souris et Ctrl+C, et contourne un plantage de Qt 6.11 quand le
  document est enfant de la vue (`web.md`, « Pièges »).

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
