# Jalons sous Chrome (W552, item 15 du TODO Portage)

Demande (brief W552, ordre du professeur 12/11 14:04 : « mets des workers sur tous les items qui peuvent être traités
indépendamment ») : rejouer sous Chrome/Chromium ce qui n'a été mesuré que sous Firefox ; verdict par jalon.

## FAIT

- Moteur : **Blink de QtWebEngine 6.11.2 (Chrome 140)**, par `qtpy6.web.sonde --chromium`, DANS le bac à sable. Le
  Chromium du système ne démarre pas dans le bac (mesuré 14:08 : `process_singleton_posix.cc: socket() failed`, core
  dump) ; le relais par le professeur n'a pas été nécessaire. Alternative écartée : faire lancer Chromium hors bac au
  professeur — un geste humain pour une mesure que la sonde fait seule. Limite : ce n'est pas un Chrome de bureau avec GPU
  (WebGL en SwiftShader).
- Site à part, `/DATA/Python/qtpy6_essais/chrome/site`, construit par `essais/spyder/chrome/construire_chrome.py` :
  instantané des sources d'`essais/spyder` (sans .log, .png, site/, chrome/), puis `construire_site.py --sortie`. Pourquoi :
  le site commun `essais/spyder/site/app.zip` reconstruit à 14:11:59 par un autre worker était corrompu (6 719 membres sur
  7 088 illisibles) — `construire_site.py` zippe le dossier entier, journaux et captures que les sondes des autres
  écrivent pendant la construction compris ; et `spe_monkey.py` était en erreur de syntaxe à 14:13 (édition en cours).
  Signalé au Superviseur. Existant : `--sortie` (ajouté le jour même par un autre worker) ; pas d'option d'instantané.
- Passes : `essais/spyder/chrome/rejouer.sh chromium|firefox [essai…]`, journaux et captures dans
  `/DATA/Python/qtpy6_essais/chrome/logs/` (`bilan.log`, `<essai>_<moteur>.log/.png`). Contrôle Firefox 158 sur le MÊME
  site pour chaque écart, afin de séparer Blink d'une régression du dépôt.

## Verdicts sous Blink (Chrome 140)

| Jalon | Essai | Blink | Firefox, même site | Verdict |
|---|---|---|---|---|
| 5 phase 1 + phase 2 | `jalon5.py --pilote` | phase 1 ok, geste « recharger » ok, 2 fichiers retrouvés et relus identiques ; puis arrêt sur erreur interne dans `CodeEditor.setPlainText` (codeeditor.py:4316, appelé par `jalon5.py:238`), page rouge, délai dépassé | même arrêt, même pile | **IDBFS après rechargement : passe** ; la suite (gestes cliquer/fichier/taper, téléchargement) **non mesurable** : régression COMMUNE aux deux moteurs depuis le 10/10, pas Blink |
| 7 (avec noyau) | `jalon7.py` | 39 passe, 0 casse, « -6 non mesuré », état fini | identique | **passe** ; écart propre à Blink : `RuntimeError: cannot join current thread` (`threading_web.py:174` ← `jupyter_client/threaded.py:297` ← `stop_channels`) à la fermeture, après les verdicts |
| 8a | `jalon8a.py` | 6/6, 24,9 s | (Firefox 10/10 : 6/6) | **passe** |
| 8b | `jalon8b.py` | 7/7, 62,4 s | (Firefox 10/10 : 7/7, 27-47 s) | **passe** (plus lent ; un passage) |
| 8c | `jalon8c.py`, `panneaux.py` | 5 passe sur 5 (les deux) | panneaux : 5/5 | **passe** |
| QWebEngineView (doublure) | `panneaux.py` | 32 passe, 0 casse, 1 non mesuré | identique | **passe** (aucun essai dédié n'existe) |
| Pyxel | `spe_pyxel.py`, état `pyxel-fini` | état atteint, verdicts 33/0/0 | identique (17:20 : 33/0/0, mêmes 2 Traceback) | **passe**, comme Firefox ; bannière IPython et `In [1]:` absentes des DEUX journaux (critère de la note Pyxel non relevable par la sonde ici) |

Communs aux deux moteurs, donc hors Blink : `ImportError QNetworkInterface` (qtpy.QtNetwork), `socket.SO_REUSEADDR`
absent (boîte d'erreur de Spyder dans panneaux), avertissements `shibokensupport … QSocketNotifier`.

## VÉRIFIÉ

Mesuré (sonde, journaux ci-dessus, captures `jalon5_chromium.png` relue : « L'application s'est arrêtée sur une erreur
interne »). Le message de l'erreur fatale du jalon 5 n'est pas dans le journal (seule la pile faulthandler). Non mesuré :
Chrome de bureau avec GPU, Edge, dossier autorisé de Chrome (jalon 5 bis), contrôle Firefox de Pyxel sur ce site.
