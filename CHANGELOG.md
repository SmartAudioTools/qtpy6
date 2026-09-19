# Changelog

## Non publié

- `QTimer.single_shot(msec, receiver, slot)`, forme à trois arguments de PySide6
  (tir abandonné si `receiver` est détruit avant), émulée sur PyQt6 par un `QTimer`
  enfant du récepteur.
- `QtWidgets.QFileSystemModel` sur PyQt6, qui l'a rangé dans `QtGui` (PySide6 le garde
  dans `QtWidgets`).

## 0.1.0 — 2026-09-18

Première version.

- API de PySide6 (`Signal`/`Slot`/`Property`, `exec`/`print`, énumérations
  scopées et non scopées, `QFileDialog.…(dir=)`) sur PySide6 ou PyQt6.
- Alias snake_case de chaque méthode, méthode statique et signal, selon la règle
  de shiboken ; le camelCase reste disponible.
- Tout module du binding est servi (`qtpy6.QtNetwork`, `qtpy6.QtTest`…).
- Réglages de session `QT_API`, `QT_SCALE`, `QT_FONT`, `QT_FONT_SIZE`
  (`get_env`/`set_env`, `scaled`), fenêtre `qtselector`.
- Bindings Qt5 (PySide2, PyQt5) non pris en charge.
