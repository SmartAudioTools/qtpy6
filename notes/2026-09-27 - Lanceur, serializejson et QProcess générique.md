# Lanceur, serializejson et QProcess générique (27/09/2026)

Ce qui a été fait après la fusion de qtpy6web (note « qtpy6.web, fusion et trous comblés »), les choix faits et leurs
raisons, ce qui a été écarté, et le niveau de preuve de chaque affirmation. La doc de référence reste `web.md` : cette
note dit POURQUOI. Commit : `98269d4` (git, non poussé à l'écriture de la note).

---

## 1. Le fil des demandes

1. *Le lecteur de QCM de SmartTeacher tourne-t-il dans la page de lancement du site ?* — Il fallait d'abord y charger
   serializejson, extension compilée, que Pyodide-Qt n'a pas.
2. *« on ne peut pas inclure serializejson compilé dans le dépôt qtpy6 ? »* — J'ai déconseillé (voir 2.1), l'utilisateur
   a tranché : *« je souhaite intégrer serializejson compilé dans qtpy6, car je l'utilise tout le temps et je souhaite
   limiter la taille des zip d'applications »*.
3. *« pas de questions de code ? pourquoi ? »*, *« en local on a deux python avec un seul interpréteur ? »* — Les
   questions de code exécutent le programme de l'élève dans un sous-processus (`QProcess`), que le lanceur ne savait pas
   fournir.
4. *« on ne peut pas faire en sorte que comme pour qtpy6 on ait un portage de cette fonctionnalité pour le web dans
   qtpy6 ? »*, puis *« est-ce que cela va obliger à modifier le code python de l'application chargée ? »* — Contrainte
   retenue : **aucune modification** du code de l'application.

---

## 2. Ce qui a été livré, et pourquoi sous cette forme

### 2.1 Les roues serializejson et apply servies par le site

`hebergement/roues/` (serializejson 0.4.0 compilé `pyemscripten_2025_0_wasm32`, copié de `serializejson/dist_wasm/`,
880 Ko ; apply 2.0, sa dépendance, Python pur) ; `construire_site.py` les copie dans `site/roues/` et écrit
`roues.json` ; `cadre.html` les passe à `preparer(…, roues)` avant tout script.

- **Mon avis initial, écarté par l'utilisateur** : laisser chaque application livrer ses roues dans son zip, pour que
  qtpy6 ne devienne pas l'hébergeur des dépendances de toutes les applications, et parce que la roue est liée à la
  version de Pyodide-Qt (à reconstruire à chaque montée). Ces deux coûts restent vrais ; l'utilisateur les a acceptés en
  échange de zip plus petits pour une bibliothèque qu'il utilise partout. **À surveiller** : une montée de Pyodide-Qt
  exige de reconstruire la roue (`serializejson/scripts/construit_wasm.sh`) — rien ne le rappelle automatiquement.
- **Une liste `roues.json` plutôt qu'un nom écrit en dur dans `cadre.html`** : le nom de fichier d'une roue porte sa
  version ; déposer une nouvelle roue dans le dossier suffit, sans retoucher la page.
- **Coût mesuré** (Firefox, local) : 0,15 s pour charger les deux roues, à chaque script ; 0,4 s de plus au premier
  `import serializejson`, pour les seuls scripts qui l'importent.
- `index.html` dit maintenant ce qu'un script peut importer (stdlib, PyQt6, qtpy6, serializejson, Python pur du zip) :
  l'ancienne formule « n'importe quel script » promettait trop.

### 2.2 `lanceur.point_d_entree` ignore les bibliothèques livrées

`lecteur.zip` embarque markdown et pygments, qui ont chacun un `__main__.py` : le lanceur refusait le zip
(« plusieurs points d'entrée possibles »). Tout dossier nommé dans le `RECORD` d'un `*.dist-info` du zip est écarté.

- **Pourquoi le RECORD et pas une liste de noms connus** : c'est la marque standard d'un paquet installé, que
  `qtpy6.web.assembler` pose déjà ; aucun nom à maintenir.
- Preuve : `test_point_d_entree` passe ; le lecteur démarre dans le lanceur (accueil Nom/Prénom en 1,7 s, capture relue).
  **Pas de test dédié** au cas dist-info : `tests/test_web.py` était alors tenu par une autre instance. À ajouter.

### 2.3 `QProcess` générique dans le navigateur

`qtpy6.QtCore.QProcess` est `ProcessusWeb` dans le navigateur. Avant : il fallait un `travailleur.configurer(…, module,
fonction)`, et ce qui tournait dans le sous-processus devait être réécrit en module dont une fonction recevait chaque
ligne (SmartTeacher avait pour cela un `web/enfant.py` réécrit, qui abandonne et rejoue le programme à chaque
`input()`). Maintenant, `start(sys.executable, ["-u", "enfant.py", …])` lance le script tel quel.

Le mécanisme (`travailleur.py` : `ProcessusWeb.start`, `_commande`, `_zipper` ; `js/travailleur.js` : `lancer`) :

1. Le dossier du script est zippé (sans compression, sans `__pycache__`) et transféré à un **Web Worker neuf** chargé
   d'un Pyodide ordinaire, qui le dépaquette **au même chemin** : `__file__`, les imports relatifs au dossier et les
   chemins écrits en dur se comportent comme sur le bureau.
2. `sys.argv` et le dossier de travail sont ceux du bureau ; le script tourne par `runpy` en `__main__`.
3. **stdin bloquant par JSPI** : un `RawIOBase` dont `readinto` attend la prochaine écriture de la page par
   `pyodide.ffi.run_sync(js.prochaine_entree())`, le tout exécuté sous `runPythonAsync`. `input()`, `readline()`,
   `for ligne in sys.stdin` marchent sans changement ; `closeWriteChannel` donne la fin de fichier.
4. stdout et stderr fusionnés arrivent par `readyReadStandardOutput` ; `finished(code)` porte le code de `sys.exit`.

Les choix, et ce qui a été écarté :

- **JSPI plutôt que `SharedArrayBuffer` + `Atomics.wait`** (la voie classique d'un stdin bloquant dans un worker) : le
  cadre du lanceur est un `iframe sandbox` sans `allow-same-origin`, et GitHub Pages n'envoie pas COOP/COEP. Mesuré dans
  le cadre : `crossOriginIsolated` faux, pas de `SharedArrayBuffer`. JSPI n'en a pas besoin. Mesuré : `run_sync`
  fonctionne dans un worker module né d'un `blob:`, Pyodide 314.0.7, Firefox 155 — à condition de tourner sous
  `runPythonAsync` (sous `runPython`, `can_run_sync()` est faux).
- **Rejouer le programme à chaque `input()` (l'approche de `web/enfant.py`)** : écarté, c'est ce qui imposait de
  réécrire le code de l'enfant, et un programme à effets de bord (impression, fichier écrit) les répète.
- **Un Pyodide par `start`, pas un worker partagé** : c'est un processus — état global, `sys.modules`, `sys.exit` ne
  doivent pas fuir d'un lancement au suivant, et `kill` = `terminate()` du worker est le seul arrêt fiable d'une boucle
  infinie. Coût : ~1,4 s par lancement (local). Un pool de workers pré-chargés est possible plus tard si ce coût gêne.
- **Zipper le dossier du script plutôt que de lister ses imports** : on ne sait pas ce que le script lira (données,
  modules voisins) ; le dossier entier est la même hypothèse que sur le bureau. Limite : pour `-m module`, c'est le
  dossier de travail qui est zippé, potentiellement gros.
- **Options de la ligne de commande** : les options d'une lettre (`-u`, `-B`…) sont ignorées, sans objet dans le worker ;
  `-c`, `-X`, `-W` lèvent `ValueError` plutôt que d'être ignorées en silence (leur argument serait pris pour le script).
- **L'ancien contrat est gardé** (`configurer` avec `module`) : SmartTeacher l'utilise encore ; le retirer est le
  point 3 de la section 4.
- Le Pyodide du worker vient de `versions.json` (jsdelivr, CORS mesuré), ou de `configurer(indexURL)` — c'est ainsi que
  l'essai local le sert depuis `site/pyodide/` (le shell du bac à sable n'a pas le réseau).

Preuve : **testé dans le cadre isolé du lanceur** (sonde Firefox, `index.html?script=app.zip`). Parent Qt :
`QProcess.start(sys.executable, ["-u", "enfant.py", "arg1"])`, trois `write` (dont deux avant que le worker soit prêt :
la file les garde), `closeWriteChannel`. Enfant : `input()`, `sum(int(l) for l in sys.stdin)`, `sys.exit(3)`. Sortie
identique au bureau (`argv ['arg1']`, `bonjour Alice`, `total 5`, code 3). `tests/test_web.py` : 19 passent. L'ancien
contrat : **vérifié par lecture seulement**, le lecteur SmartTeacher n'a pas été relancé.

Défaut trouvé et corrigé pendant l'essai : le décodeur UTF-8 au fil de l'eau rend `""` sur un caractère coupé entre deux
écritures ; un `readyReadStandardOutput` vide était émis. Filtré dans `_recevoir`.

---

## 3. Ce qui mérite l'attention d'un relecteur

- `_Entree.readinto` vide stdout/stderr avant d'attendre : sans cela, une invite `input("nom ? ")` (sans `\n`) resterait
  dans le tampon pendant l'attente.
- `kill` émet `finished(0)` par `QTimer.singleShot(0)`, comme `QProcess` émet après le retour de `kill` ; un vrai
  `QProcess` tué donne `CrashExit` — non reproduit.
- Aucune gestion de `stdin` binaire (`sys.stdin.buffer` existe, mais `write` décode en UTF-8 côté parent).

---

## 4. Les trois points ouverts à la date de la note

1. `subprocess.run` (utilisé par `verifier.py` de SmartTeacher pour corriger) n'est pas doublé : synchrone, il bloque le
   fil de la page, où JSPI n'a pas été essayé.
2. JSPI sur Safari : non mesuré ; sans JSPI, le lancement échoue avec un message sur la sortie du processus.
3. SmartTeacher peut abandonner `web/enfant.py`, `python.zip` et l'appel à `configurer` avec `module`.
