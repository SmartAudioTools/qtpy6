# Essais sans branche web, suite (W559, 12/11/2026)

Brief : reste des items 4 et 13 du TODO Portage (D4, D6, 4c, 4d, Interpréteur), reprise de W555.

## Demandes citées

- D4 et D6 posées (AskUserQuestion), le professeur a d'abord fait préciser la règle : « pourquoi claude interdir la branche
  sys.platform == "emscripten" ? », puis (18:00) « je ne suis pas sur qu'il faille interdire absolument sys.platform ==
  "emscripten", il faut mieux l'eviter au maximum, mais pas obligatoirement, si ça reste la solution la plus élégante »,
  et « oui » (18:01) à : inscrire cette nuance dans `CLAUDE.md` et coder mes deux recommandations.
- Ce qu'il a demandé en chemin, relevé dans le fork (lu, non mesuré) : dans la page, `WIN`, `MAC` et `LINUX` de Spyder
  sont faux ; ~130 tests Windows et ~100 Mac tombent dans leur `else` (écrit pour Linux/posix) ; les 20 tests Linux
  explicites ne s'exécutent pas : terminal externe, détection KDE/GNOME/Ubuntu, dossiers XDG (sans effet, SPYDER_CONFDIR
  est imposé), pyxdg ; trois différences d'aspect seulement (facteur des icônes d'attributs, `COMPLETION_DELTA_FOR_SCROLLBAR`,
  collage au clic du milieu).

## FAIT

- **`CLAUDE.md`** : la nuance du professeur, citée ; la vérification grep admet une branche justifiée dans la note.
- **D4** : le Worker d'un `QProcess` prend par défaut le Pyodide et les roues de la PAGE. `preparer` (qtpy6web.js) pose
  `window.qtpy6Pyodide` et `window.qtpy6Roues` ; `qtpy6.web.lancer()` les met en défaut de `travailleur.REGLAGES`
  (`_reglages_du_worker`, `setdefault`) ; un `configurer` du script les remplace. `spe.py:66-68` retiré.
  Écarté : un réglage sur `QProcess` sans effet en natif (une ligne propre au web par application, et l'application doit
  savoir où sont les roues du site). `travailleur.py` (W561) non touché : le défaut est posé depuis `lancer`.
  Effet sur les autres applications : leur Worker prend le Pyodide de la page au lieu de celui en ligne de `versions.json`
  (même version garantie).
- **D6** : `qtpy6/web/chardet_web.py` (neuf), posé par `lancer()` : `chardet.detect` rend utf-8 (ascii si ascii) sans
  charger chardet quand les octets se décodent en utf-8 ; sinon le vrai chardet de l'archive remplace la doublure dans
  `sys.modules` et répond. Écartés : utf-8 toujours (latin-1 mal lu en silence), chardet réel (+63 Mio, faisabilité 09/10).
  Existant : le fork renvoie déjà « ascii » pour un texte ASCII (`encoding.py:152`, ajout SmartOS) ; la doublure couvre
  l'utf-8 accentué. Natif : rien.
- **4c** : `jalon4.py` appelle `waitForFinished(1000)` sans `if not WEB` (ProcessusWeb le rend vrai une fois tué).

## VÉRIFIÉ

- Mesuré, natif : doublure seule → `detect('héllo')` utf-8, `b'abc'` ascii, latin-1 → vrai chardet (WINDOWS-1252),
  `UniversalDetector` servi, `sys.modules['chardet']` devenu le vrai.
- Relecture (relecteur, 18:04), corrigé : le vide et les octets NUL (utf-16/32 sans BOM, utf-8 valide en apparence)
  rendaient « ascii » ; ils passent désormais au vrai chardet (`b''` → None, vérifié en natif) ; confiance 1.0 pour
  l'ascii, comme chardet. D4, 4c, ordre d'exécution, imports : aucun défaut.
- Mesuré, page (Firefox, testeur, site `/DATA/Python/qtpy6_essais/w559/site`, essai temporaire = jalon8c avec
  `travailleur.configurer` neutralisé, jeté ensuite) : REGLAGES = `{'indexURL': 'http://127.0.0.1:…/pyodide-qt/',
  'roues': (jedi, parso)}` sans aucun appel ; noyau prêt 16,6 s, `1+1 → Out[1]: 2`, jalon 8c 5/5
  (`qtpy6_essais/w559/sonde_d4_w559.log`). La doublure chardet n'est pas exercée par 8c ; 4c non relancé dans la page.

## 4d, par cas (18:25)

Relevé (releve) : importeurs dans le fork (hors tests) et `essais/roues/lib`, dépendances déclarées.
- **jellyfish, bcrypt** : déclarés (`setup.py:277,290`), importés par AUCUN module → doublures retirées de `preparer.py`.
  Mesuré, natif : `walk_packages(spyder)` importé en entier, 5 échecs dont aucun ne les nomme, ni l'un ni l'autre dans
  `sys.modules` après.
- **pickleshare** (`module_completion.py:16`), **three_merge** (`lsp_mixin.py:28`), **inflection** (`qstylizer/style.py:6`) :
  importés au niveau module sans try ; pur Python → **roue dans l'archive** (`essais/roues/`, comme qstylizer), puis
  doublure retirée. Bloqué : PyPI injoignable depuis le bac (`RemoteDisconnected` sur `/simple/pickleshare/`) et aucune
  copie sur le disque ; le professeur doit télécharger (commande dans l'ETAT).
- **keyring** : 9 importeurs, dont `config/manager.py:530,549,649` sans try (options `secure`) et
  `remoteclient/widgets/container.py:16` au niveau module. Un navigateur n'a pas de trousseau : la vraie roue (et ses
  jaraco.*) lèverait `NoKeyringError` à la première option secrète. Choix : **doublure qtpy6** `keyring` en mémoire de
  la page (`qtpy6/web/`, posée par `lancer()`, comme chardet_web) — non codé ; en natif, le vrai keyring de
  SmartPythonEditor (la doublure de `preparer.py` ne sert que le SmartPython de l'essai, qui ne l'a pas).
- **métadonnées de pylint** : non traité.

## 4d fini, Interpréteur, spe.py sans capture (18:30-19:00)

- **Roues** : le professeur a téléchargé pickleshare 0.7.5, three_merge 0.1.1, inflection 0.5.1 (« je l'ai fait ») ;
  dépaquetées dans `essais/roues/lib` (non suivi par git), ajoutées à `construire_site.py` (PAQUETS ; pickleshare,
  module à un fichier, dans DISTRIBUTIONS) ; doublures retirées de `preparer.py`. Mesuré, natif : `walk_packages(spyder)`
  mêmes 5 échecs, les trois servis par `essais/roues/lib`. Page : présents dans app.zip.
- **keyring** : `qtpy6/web/keyring_web.py` (neuf), posé par `lancer()` : `get/set/delete_password` en mémoire de la page
  (rien de persisté), `get_keyring()` rend ce trousseau (pas une `backends.fail.Keyring` : le client distant le croit
  utilisable), `keyring.errors`. Mesuré hors page (set/get/delete, `PasswordDeleteError`) ; page : la doublure de
  `preparer.py` ne s'imprime plus (keyring déjà servi). La doublure de `preparer.py` reste pour le SmartPython natif de
  l'essai, qui n'a pas keyring (le vrai SmartPythonEditor l'a).
- **pylint** : doublure de métadonnées gardée dans `preparer.py` : elle n'est pas propre au web (elle sert aussi le
  SmartPython natif sans pylint) ; la vraie roue (astroid, dill, isort…) n'apporterait rien tant que le greffon est coupé.
- **Interpréteur** : `qtpy6.web._executable`, appelé par `lancer()` : quand `sys.executable` n'est pas un fichier
  (Pyodide : `/home/pyodide/this.program`), un fichier vide `/home/pyodide/versions/3.13/bin/python` le remplace (chemin
  pyenv : le combo du fork le nomme « 3.13 » ; nom en `python` : `sous_processus._PYTHONS` le reconnaît). `spe.py` écrit
  `sys.executable` comme `update_spyder_interpreters.py` sur le bureau, plus de chemin factice. Écarté : laisser le
  chemin dans spe.py (une ligne propre au web). Mesuré, page : `custom_interpreters_list` =
  `['/home/pyodide/versions/3.13/bin/python']` gardée par Spyder (fichier valide) ; le combo lui-même n'est pas vu
  (capture de 1000 px, barre coupée).
- **spe.py sans capture, cause établie** : spe.py définit `SUITE`, jalon7 n'arme donc pas `rapport()`, et `SUITE` ne
  l'appelle pas (la fenêtre reste ouverte) : `window.etat` ne devient jamais « fini », la sonde attend son délai. Ce n'est
  pas un défaut de la page (journal : post_visible_setup 16 s, durée totale 27 s). Remède d'instrumentation : `SUITE`
  pose `fin("ouvert")` 2 s après ; `--etat ouvert` capture (`qtpy6_essais/w559/capture_spe_c.png`, sonde 0).
- **Défaut trouvé, hors de mon item** : à l'ouverture de spe.py, le rapporteur d'erreur de Spyder s'affiche :
  `mainwindow.py:1526 start_open_files_server` → `AttributeError: module 'socket' has no attribute 'SO_REUSEADDR'`
  (le `socket` de Pyodide). Manque de qtpy6 (doublure de socket ou serveur sans effet dans la page), signalé au
  Superviseur.
- **Page, jalon 8c** (site reconstruit 18:43 avec tout ceci) : 5/5, noyau prêt 20,4 s. Un essai précédent (18:35, avant
  keyring/executable, machine chargée : noyau 34,6 s) : 4/5, redémarrage « rien en 180 s » et `ZMQError: Not a socket`
  à la fermeture ; la ZMQError revient au 5/5 aussi, après le jalon : non lié, non traité.
- **Hors brief, à la demande de W565** : `_garder_le_focus` (focus clavier après clic sur un widget non-texte, item 8),
  son code tel qu'il l'a mesuré, appelé par `application()`.

## RESTE

- Alias qtpy en natif : cinq lignes au professeur (SmartPythonEditor natif est en PyQt5 et Python 3.12, qtpy6 absent
  de son environnement ; l'alias ne sert que PySide6/PyQt6).
- `socket.SO_REUSEADDR` dans la page (ci-dessus).
