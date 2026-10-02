# `qtpy6.erreurs` : les exceptions non rattrapées en boîte de dialogue (02/10/2026)

## La demande

*« ne faudrait-il pas integrer "/DATA/Python/SmartFramework/ui/exceptionDialog.py" et
"…/exceptionDialog_mono_thread.py" à qtpy6 ? »*, puis *« peut tu l'integrer au différents outils de SmartTeacher,
pour ne plus avoir d'exception silencieuse ? »* (l'intégration côté SmartTeacher est notée dans son
`DONE/QCM - DONE.txt`).

## Ce qui a été livré

- `qtpy6/erreurs.py` : `installer()` et `boite(message)` (docstring du module pour le fonctionnement).
- `tests/test_erreurs.py` : 5 tests (crochet précédent appelé, QThread et `threading.Thread` affichés dans le fil
  principal, `SystemExit` d'un fil muet, second appel sans effet, style de l'application intact).
- SmartFramework `ui/exceptionDialog.py` et `ui/exceptionDialog_mono_thread.py` : réduits à un relais qui appelle
  `erreurs.installer()` à l'import. Une vingtaine de greffons `Qt_plugins/register~…` les importent pour cet effet,
  et personne n'utilise leurs noms (`exceptionDialog`, `old_excepthook`) : vérifié par grep sur /DATA/Python.

## Les choix

- **Un seul module** : la version à signal couvre le cas d'un seul fil (signal livré directement dans le fil de
  l'émetteur). La variante `_mono_thread` est écartée.
- **`installer()` explicite, pas à l'import** : une bibliothèque publiée ne remplace pas `sys.excepthook` parce
  qu'on l'importe. Seuls les relais de SmartFramework gardent l'effet à l'import, pour ne pas toucher ses greffons.
- **Le style de l'application n'est plus écrasé** : l'original faisait
  `qapp.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")`, qui remplaçait toute la feuille
  de style de l'application à la première exception. Désormais `setTextInteractionFlags` sur la boîte seule
  (mêmes drapeaux : 5 = sélection à la souris + liens).
- **`threading.excepthook` en plus** : ajouté après mesure. Une exception dans un `threading.Thread` ne passe pas
  par `sys.excepthook` et restait silencieuse, ce qui allait à l'encontre de la demande.
- **`RuntimeError` avalée dans `emettre`** : mesuré sous PyQt6, un fil qui lève pendant la fermeture de
  l'interpréteur trouve le relais C++ détruit, et l'erreur s'ajoutait à la trace. La trace d'origine est déjà passée
  au crochet précédent.
- Les textes de la boîte (« Critical Error », « An unexpected Exception has occured! ») sont gardés tels quels.

## Niveau de preuve

- Testé hors écran, PySide6 et PyQt6 : suite complète, 110 tests verts sur les deux. Dans un essai réel (vraie
  `QMessageBox`, fermée par une minuterie), une exception levée dans un slot, un `QThread` ou un `threading.Thread`
  ouvre la boîte dans le fil principal.
- **Le navigateur n'a pas été essayé** : `web/bloquant.py` appelle `sys.excepthook` depuis une tâche qui peut
  suspendre, donc `exec()` devrait y marcher, mais rien ne le prouve. C'est le premier point à regarder.
