# Outillage : sonde, test de bloquant, SystemError résiduels (W553, 12/11/2026)

Demande : item 16 du TODO Portage ; ordre du professeur (12/11 14:04) : « mets des workers sur tous les items qui peuvent
être traités indépendamment ». Sources : faisabilité, jalons 3 et 5 et « Points ouverts » ; Pyxel, « Point ouvert immédiat ».

## 1. `_fait` de la sonde par compare-and-set (`qtpy6/web/sonde.py`, `attendre`)

- **Fait** : la sonde n'écrit plus `window.etat = '<geste>_fait'` sans condition, mais
  `if (window.etat === '<geste>') window.etat = '<geste>_fait'`. La page qui a repris pendant le geste (sur l'événement
  d'un dialogue, jalon 5) et demandé déjà le suivant garde sa demande ; la sonde la sert au tour suivant.
- **Pourquoi** : course des jalons 3 (« taper » puis « cliquer ») et 5 (après chaque dialogue) : le `_fait` écrasait la
  nouvelle demande, chacun attendait l'autre jusqu'au délai (600 s). Les pages contournaient (`attendre("fichier", suite)`).
- **Écarté** : un compteur de gestes (`window.geste_n`) — change le protocole de toutes les pages ; le compare-and-set
  suffit, sur une seule ligne, sans rien changer côté page. Une page qui n'a pas repris reçoit exactement le même `_fait`.
- **Vérifié (mesuré)** : `test_sonde_fait_ne_recouvre_pas_le_geste_suivant` (page simulée : le geste « fichier » fait
  passer la page à « cliquer ») : passe ; ÉCHOUE sans le correctif (`'délai dépassé' == 'fini'`). Non relancé sous un
  vrai navigateur (le site était en reconstruction, ci-dessous).

## 2. Test de la règle « slot à QEvent sur place » (`bloquant._relayer`)

- **Fait** : `test_slot_a_qevent_sur_place` (simulation greenlet de JSPI, sur le modèle des tests de slots reportés) :
  un `QEvent` émis hors entrée promettante est traité AVANT le retour de `emit`, et l'émetteur lit son `accept()`.
  Aucun changement à `bloquant.py`.
- **Vérifié (mesuré)** : passe ; ÉCHOUE quand la clause `any(isinstance(a, QEvent) …)` est retirée (`apres emit` avant
  `recu`). Suite complète `tests/test_web.py` (fiche `testeur`, 14:13) : 58 passent, 3 échouent hors de ce travail
  (`test_application_persistant_dans_le_navigateur`, `test_police_fixe_dans_le_navigateur`, `test_coller_passe_par_qt` :
  `AttributeError: 'types.SimpleNamespace' object has no attribute 'window'` dans `boite_noire._boite`, appelée par
  `application()` depuis le commit 82f2793 ; le faux `js` des tests n'a pas de `window`). Signalé au Superviseur.

## 3. `SystemError: Cannot enter a promising task from inside another running promising task`

- **Relevé** (fiche `releve`) des captures du 12/10 : 9 consoles en contiennent (pyxel 15, monkey 2, m2 2, tri2 2, une
  dans pyxel_hors, controle, ref, gel8c, spe), 0 dans `capture_essai28` (12:43, la dernière de Pyxel). Pile identique
  partout : `tourner` (la pompe `pomper` de `qtpy6/web/js/qtpy6web.js`) → `callPromising` → `promisingApply` → wasm.
  Dans monkey, ref et tri2, suivie de `NoGilError: Attempted to use PyProxy when Python GIL not held` puis
  `RuntimeError: index out of bounds` : la chaîne de la corruption du tas décrite par la note Pyxel (« Suite 16:50 »),
  où ces messages étaient déjà lus comme « des suites de ce même état ».
- **Cause (lu, non mesuré)** : la pompe de la page entre en promettant alors que Pyodide croit une autre tâche
  promettante en cours ; l'état n'apparaît que dans les essais qui finissent sur la corruption GC (item 1, W545).
  Ni `preambule.py` ni `travailleur.py` dans la pile. Transmis à W545 avec les traces (SendMessage, 14:13).
- **Reproduction** : non obtenue. Deux sondes `spe_pyxel.py` (14:11, 14:12) arrêtées au chargement : `site/app.zip`
  en cours de reconstruction par un autre worker (`shutil.ReadError`, puis `BadZipFile`). Journaux
  `essais/spyder/sonde_w553.log`, `capture_w553.console.log`.
- **Reste** : relancer `spe_pyxel.py` et `spe_m4.py?…&bouton=1` une fois le site stable, et après le correctif GC de
  W545 ; si l'erreur survit sans corruption, garder la pompe tant qu'une tâche promettante court (drapeau tenu par
  `qtpy6web.js`, fichier hors de ce brief).
