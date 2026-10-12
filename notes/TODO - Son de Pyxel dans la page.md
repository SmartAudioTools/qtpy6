# TODO : le son de Pyxel dans SmartPythonEditor web (jeudi 15/10/2026 au soir, après la remise à zéro du quota)

Demande de l'utilisateur, 12/10/2026 : « je veux l'intégration de pixels complètes dans l'éditeur », puis, le quota
à 90 % : « ajoute au TODO pour jeudi soir ». Les images et le clavier sont faits (essai 28, commit 2aea235) ; contexte,
essais et pièges : `notes/2026-10-12 - Pyxel dans la page.md`.

- [ ] **Le son** : le pilote audio emscripten de SDL2 teste `AudioContext`, absent d'un Worker. Piste : doublure
  qtpy6, un `AudioContext` minimal dans le Worker dont le `ScriptProcessorNode` est pompé depuis
  `memoire_partagee.reconcilier()` (le sleep bloquant, comme pour les images) ; échantillons poussés dans un anneau
  `SharedArrayBuffer`, joués dans la page par un AudioWorklet. Vérification : la page compte les échantillons non nuls
  reçus. Rien du greffon ni de l'éditeur ne change.
- [ ] **`SystemError: Cannot enter a promising task…`** : c'est `ast.parse` dans le noyau, appelé par `%runfile`
  (triangle « Exécuter », F5) — le noyau plante, un jeu d'élève ne se lance pas par le bouton. Isolé le 12/10
  (`notes/2026-10-12 - Pyxel dans la page.md`, essai `spe_monkey.py`). Piste : doublure qtpy6 dans le Worker.
- [ ] La fenêtre d'erreur fugitive vue par l'utilisateur au lancement de `spe_monkey.py` : à identifier.
- Les sondes se donnent en bloc NON vert à coller dans une Konsole tant que le relais `!` sudo est bloqué.
