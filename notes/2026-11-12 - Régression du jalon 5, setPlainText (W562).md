# Régression du jalon 5 : `CodeEditor.setPlainText` récurse sans fin (W562, 12/11/2026)

**Demande** (brief W562, item 15 du TODO Portage, ligne W552) : « `jalon5.py --pilote` […] arrêt sur erreur interne dans
`CodeEditor.setPlainText` […] IDENTIQUE sous Firefox et Chrome, donc régression de qtpy6 ou de l'essai depuis le 10/10 […]
Le commit fautif nommé, le correctif dans qtpy6 (doublure) […] test rouge puis vert ; jalon 5 phase 2 remesuré jusqu'au bout ».

## FAIT

1. **Pile** (`/DATA/Python/qtpy6_essais/chrome/logs/jalon5_firefox.console.log`, puis rejoué sur mon site
   `/DATA/Python/qtpy6_essais/w562/site`, journal `tete_firefox.console.log`) : `InternalError: too much recursion` dans le
   wasm, « Pyodide has suffered a fatal error », pile Python (faulthandler) arrêtée à `codeeditor.py:4316`
   (`super().setPlainText(txt)`) : la récursion est en C++, aucune frame Python au-dessus.
2. **Pas un commit de qtpy6** : le site construit depuis `76f4be4` (le commit où le jalon passait, arbre
   `/DATA/Python/qtpy6_essais/w562/arbre`) casse à l'identique (`r76f4be4_firefox.console.log`, 12,26 s). La bissection
   git demandée ne peut donc rien nommer : ce qui a changé est HORS du dépôt.
3. **Sonde minimale** (`essais/spyder/w562_pile.py`, dans mon arbre seulement, non commité) : `QPlainTextEdit.setPlainText`
   de 77 358 caractères passe (70 ms) ; `CodeEditor.set_text` de **100 lignes** (3 718 caractères) casse déjà, appelé dans
   une minuterie comme directement : ni la taille, ni la tâche JSPI de `bloquant`.
4. **Cause** (lu dans les sources, confirmé par un test natif rouge) : `class TextEditBaseWidget(QPlainTextEdit,
   BaseEditMixin, …)` (spyder/plugins/editor/widgets/base.py:38) ; `BaseEditMixin.cursor_position_changed` (base.py:430)
   vient APRÈS Qt dans la MRO. qtpy6 pose sur `QPlainTextEdit` l'alias snake_case du signal `cursorPositionChanged` en
   attribut simple (`qtpy6/_binding.py`, « signal … kept as is ») : il masque la méthode du mixin, et
   `self.cursorPositionChanged.connect(self.cursor_position_changed)` (base.py:76) connecte le signal À LUI-MÊME ; le
   premier déplacement du curseur de `setPlainText` émet sans fin. Le changement daté : le fork de Spyder avait renommé ces
   slots homonymes (commit du fork 591fdf005, 09/10) ; la reconstruction du fork du 11/10 l'a perdu (le contournement
   d'essai de `jalon7.py:67-75` le documente et retire l'alias à la main) — le jalon 5, qui ne l'avait pas, casse depuis.
   `adf75de` (12/10, « alias qui cèdent la place à l'application ») n'avait traité que les alias de MÉTHODES.
5. **Test** `tests/test_doublures.py::test_alias_signal_cede_au_mixin` : rouge (l'alias rend le `SignalInstance`, pas la
   méthode du mixin), aussi sur la version en cours de W547.
6. **Correctif** : dans `qtpy6/_binding.py`, fichier de W547 (item 3, D1, tranché par le professeur à 17:20 : alias de
   signal en descripteur `_SignalAlias`), qui cède au nom Python de la MRO comme `_Alias`. Commité par W547 en **4ca1a7f**,
   avec ma section de `tests/test_doublures.py` (un `git commit -- fichier` emporte tout le fichier : accord entre nous).
   Je n'ai pas touché `_binding.py`.
7. **Jalon 5 rejoué sur 4ca1a7f** (site `/DATA/Python/qtpy6_essais/w562/site`, md5 du `_binding.py` embarqué = celui du
   commit), `--pilote`, phases 1 et 2 jusqu'au bout : Firefox 158 — posé dans l'éditeur 718 ms, ouvert ok, enregistrer
   sous 510 ms, téléchargé `rendu.py` (47 octets), état fini (`j5_firefox.log`) ; Blink, QtWebEngine 6.11.2 / Chrome 140 —
   posé 815 ms, ouvert ok, téléchargé, enregistré ok, état fini (`j5_chromium.log`). Un premier rejeu « chromium » avait
   tourné sous Firefox (option `--chromium` non transmise par mon script de rejeu, vu à la ligne d'état) : refait.

## POURQUOI / alternative écartée

- Corriger dans qtpy6 et non dans l'essai ou le fork : la règle du dépôt (le code de l'application ne s'adapte pas), et
  le même masquage frappe tout mixin Python placé après une classe Qt. Écartés : retirer l'alias dans `jalon5.py` comme
  `jalon7.py` (une branche d'essai de plus), redemander le renommage au fork (chaque application refait le contournement).
- Pas de bissection git complète : le site de `76f4be4` casse déjà, la cause est hors dépôt (fork reconstruit) ; rejouer
  les 66 commits n'aurait rien appris.

## VÉRIFIÉ

- Mesuré : la récursion au jalon 5, à la tête et à `76f4be4` (Firefox 158) ; le seuil de 100 lignes ; le test rouge en natif.
- Lu dans les sources : MRO de `TextEditBaseWidget`, connexion base.py:76, commentaire de `jalon7.py`.
- Mesuré : test vert sur 4ca1a7f (W547) ; jalon 5 phase 2 jusqu'au bout sous Firefox et Blink (un passage chacun).
- Délégation : relevés faits moi-même (une quinzaine de commandes enchaînées, chacune dépendant de la précédente :
  la bissection a changé de direction trois fois).
