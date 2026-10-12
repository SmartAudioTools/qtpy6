# TODO : le son de Pyxel dans SmartPythonEditor web (jeudi 15/10/2026 au soir, après la remise à zéro du quota)

Demande de l'utilisateur, 12/10/2026 : « je veux l'intégration de pixels complètes dans l'éditeur », puis, le quota
à 90 % : « ajoute au TODO pour jeudi soir ». Les images et le clavier sont faits (essai 28, commit 2aea235) ; contexte,
essais et pièges : `notes/2026-10-12 - Pyxel dans la page.md`.

- [ ] **Le son** : le pilote audio emscripten de SDL2 teste `AudioContext`, absent d'un Worker. Piste : doublure
  qtpy6, un `AudioContext` minimal dans le Worker dont le `ScriptProcessorNode` est pompé depuis
  `memoire_partagee.reconcilier()` (le sleep bloquant, comme pour les images) ; échantillons poussés dans un anneau
  `SharedArrayBuffer`, joués dans la page par un AudioWorklet. Vérification : la page compte les échantillons non nuls
  reçus. Rien du greffon ni de l'éditeur ne change.
- [ ] **`SystemError: Cannot enter a promising task…`** vu dans la console de l'essai 28 : à examiner.
- Les sondes se donnent en bloc NON vert à coller dans une Konsole tant que le relais `!` sudo est bloqué.
