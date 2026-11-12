# Doublure GC du Worker (W545), 12/11/2026

## Demande
Item 1 de `TODO - Portage de SmartPythonEditor.md` : appliquer la doublure du ramasse-miettes dans le Worker
(`notes/2026-10-12 - doublure gc (preambule, non appliquée).diff`) pour que le triangle F5 (`%runfile`) ne tue plus le
noyau, en la factorisant avec `_ramasser` de la page, après mesure sur la console de code du lecteur QCM. Le 12/11 à
14:01, l'utilisateur a tranché D2 (au Superviseur) : « ma préférence est pour D : correction de Pyodide et JSPI » ;
la parade n'est plus qu'un secours provisoire (item 1 bis).

## FAIT — puis RETIRÉ de la copie de travail (consigne du Superviseur, 14:13)
La parade ci-dessous est conservée en patch, `notes/2026-10-12 - doublure gc (preambule, non appliquée).diff` (remplacé :
136 lignes, nouveau module compris, `git apply --check` passe sur le tip) ; les fichiers sont revenus à l'état commité.
- `qtpy6/web/ramasse_miettes.py` : `couper()` (GC automatique coupé, `gc.enable/disable/isenabled` doublés — parso
  rallume le GC dans un `finally` —, idempotent) et `passer(complete, seuil)`.
- `qtpy6/web/__init__.py` `_ramasser` : appelle ce module (QTimer 500 ms inchangé). Effet de bord voulu : la doublure
  de `gc.enable` vaut aussi pour la page, où parso tourne (l'éditeur).
- `qtpy6/web/preambule.py` `_doubler_gc` (réveil asyncio de 2 s, passe complète au-delà de 20 000 objets), appelé par
  `installer` ; `travailleur._FICHIERS_WORKER` += `ramasse_miettes.py`.
- Existant appelé, pas dupliqué : la logique de `_ramasser` (compteurs, seuils, génération) est passée dans le module
  commun ; seule l'horloge diffère (QTimer côté page, `call_later` côté Worker sans Qt).

## VÉRIFIÉ
- Tests `tests/test_doublures.py tests/test_noyau_web.py`, Python du projet (SmartPython 3.13) : 34/34. Avec
  `/usr/bin/python` 3.14 : 6 échecs `RuntimeError: There is no current event loop` — identiques sur le tip 29517a0 sans
  ces modifications (git archive) : préexistants.
- Lecteur QCM (racine à part, lecteur.zip copié puis patché, SmartTeacher non modifié ; ⚠ les `.pyc` non vérifiés
  d'assembler masquent une source patchée : les retirer) : `console`, `soumettre`, `fin_epreuve&sujet=python_tp`
  (3 codes Python corrigés dans le Worker, notés 1/1/1) donnent la MÊME sortie avec et sans doublure (16,0 s / 16,7 s).
  Preuve : mesure comparée, une passe par variante.
- **Triangle sans affichage (`spe_m4.py &bouton=1`) : la parade NE suffit PAS.** Build d'aujourd'hui et archive du 12/10
  18:45 (parade d'origine) meurent 3/3 au triangle, `unreachable executed` pyodide.asm.wasm:5614267, même signature que
  le m4 sans parade du 12/10 18:42 (`capture_m4.console.log`). La seule preuve du 12/10 était le triangle VISIBLE de
  l'utilisateur à 19:45 : intermittence, ou cause autre que le GC. Témoins (sans parade ; GC coupé sans passe) non
  concluants : chargements perturbés par 8 sessions lançant Firefox en même temps, et `site/app.zip` reconstruit au
  même moment par Worker 553 (BadZipFile chez lui à 14:12) — le site de `essais/spyder` est PARTAGÉ : un essai le copie.
- Relevé de W553 (14:12) : les « SystemError: Cannot enter a promising task » de 9 captures du 12/10 ont tous la pile
  `pomper` (qtpy6web.js) → callPromising → promisingApply ; dans monkey, ref et tri2 ils précèdent « NoGilError: PyProxy
  when GIL not held » puis « index out of bounds ». Piste pour la repro minimale.

## Écarté
- Option C (GC suspendu pendant chaque `run_sync`) : non mesurée ; à la lecture, `_garde_vie.run_forever` reste dans
  `run_sync` toute la vie du noyau, donc « pendant une suspension » = toujours, C se réduit à « GC coupé ».
- Commit de la parade : écarté tant qu'elle n'est pas prouvée sur la repro.

## Reste
Outils : `/DATA/Python/qtpy6_essais/equipe/w545/` (`tri.sh <étiquette> [n]`, `variante_app.py A|sans|coupe`,
`lecteur_patche.py`, `mesurer.sh`). Rejouer les témoins machine calme ; puis item 1 bis (repro minimale, cause dans les
sources de Pyodide/CPython, patch). Décider du sort de la copie de travail (commit sous réglage ou retrait).
