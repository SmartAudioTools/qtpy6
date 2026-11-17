# Démarrage de spe.py dans la page : profil et corrections (W577, 17/11/2026)

Item 22 du TODO Portage de SmartPythonEditor.

## Demandes du professeur

- 12/11/2026 19:49 : « le démarrage est horriblement long ».
- 17/11/2026 02:46 : « il faudrait aussi lancer des worker pour avancer sur le portage de SmartPythonEditor sur le web,
  en essayant de ne toucher qu'à qtpy6 ».

## Prémisse corrigée

Les « 48,7 s de `post_visible_setup` » (W566) sont le temps CUMULÉ depuis l'entrée dans Python : `etape()` de
`preparer.py` imprime `time.monotonic() - T0`. La durée propre de `post_visible_setup` est de 1,5 à 7,7 s ; le gros
est `setup` (inscription des plugins) et, avant Python, le dépaquetage de l'archive.

## Profil (niveau de preuve : mesuré hors écran, sonde Firefox, 2 passes, machine CHARGÉE)

Machine jamais calme : six workers ouverts à 02:55, charge 28 à 70 sur 20 cœurs ; variance énorme d'une passe à
l'autre. Logs : `qtpy6_essais/equipe/w577/passe1.log`, `passe2.log`, `profil1.log` (cProfile, `&profil=1`, double
les temps).

| Étape (durée propre)        | passe 1 (charge 32→56) | passe 2 (charge 56→48) |
|-----------------------------|-----------:|-----------:|
| setup (plugins inscrits)    | 21,6 s | 7,09 s |
| dépaquetage d'`app.zip`     | ≈ 7,4 s | 2,54 s |
| post_visible_setup          | 7,68 s | 1,52 s |
| imports (Spyder, qtpy6)     | 6,15 s | 2,28 s |
| chargement de Pyodide       | 4,63 s | 2,07 s |
| roues + entrée dans Python  | —      | 1,22 s |
| pre_visible_setup           | 0,52 s | 0,24 s |
| show                        | 0,28 s | 0,08 s |
| SpyderApplication           | 0,12 s | 0,04 s |
| **durée totale**            | **54,3 s** | **17,4 s** |

Postes de qtpy6 du profil (cumulé / propre, temps profilés) : `_binding._Alias.__get__` 11,7 / 3,8 s (appelé par
`traitlets.getmembers`, 11,9 s, à chaque classe de qtconsole) ; `bloquant._relayer` 6,2 s ; filtre `PleinEcran`
(`web/__init__.py:171`) 1,7 s pour 40 463 événements + `QEvent.type` 2,0 s ; `_pyside6_class` 1,4 s ;
`_signal_masked` 1,4 s.

## FAIT

1. `_binding._Alias.__get__` : le côté Python du MRO (classes, noms, `__getattr__`) se calcule une fois par classe
   (`_python_side`), relu quand la taille d'un dict du MRO change ; le `_Signe` d'un alias lu sur la classe est gardé.
   Natif : 5,06 → 1,39 µs par alias (camelCase 0,16–0,18) ; parcours des alias d'une classe neuve 1,41 → 0,72 ms.
2. `_signal_masked` (`QObject.__init_subclass__`) ne remonte le MRO que pour un nom d'alias de signal
   (`_SIGNAL_ALIASES`). Sous-classe de QPlainTextEdit à 300 méthodes : 664 → 81 µs (classe Python : 23 µs).
3. `web/assembler.py` : fichiers et dossiers cachés SOUS un paquet exclus (`qtpy6/.claude`, 1,9 Mio dans chaque
   archive). SmartTeacher (`QCM/web/construire.py:140`, `paquets=["qtpy6", …]`) en profite sans changement d'API.

Mesure dans la page, même sonde, paires ALTERNÉES avant (`site_avant`) / après (`site`), charge 37–44 :

| paire | setup avant → après | post_visible_setup cumulé | durée totale |
|---|---|---|---|
| 1 | 7,03 → 5,39 s | 10,74 → 8,84 s | 19,2 → 15,0 s |
| 2 | 9,53 → 8,25 s | 15,83 → 13,05 s | 26,0 → 21,7 s |
| 3 | 6,70 → 5,72 s | 10,80 → 9,61 s | 17,9 → 15,7 s |

Gain : 2,2 à 4,3 s sur 18 à 26 s (≈ 15 à 20 %). Cible du brief (post_visible_setup divisé par deux) NON atteinte :
le reste est hors de mes fichiers (ci-dessous). Log `qtpy6_essais/equipe/w577/mesures.txt`, `m_*.log`.

Non fait, confié : filtre `PleinEcran` → W573 (diff `w577/w573_plein_ecran.diff`, une ligne envoyée) ;
`bloquant._relayer` → W578 (fichier à lui) ; dépaquetage (`qtpy6web.js` à W573, contenu de l'archive dans
`construire_site.py`). Fork : TODO item 22.

## POURQUOI

`traitlets` lit sur la CLASSE tous ses noms à chaque classe de qtconsole créée : chacun des ≈ 400 alias faisait
trier le MRO (`partition`, `vars`, `isinstance` en tête des fonctions natives du profil). Un cache par classe le
fait une fois ; la taille des dicts suffit à voir un mixin modifié après coup (test 2).

## Alternative écartée

- Retirer les alias de signal / tous les alias (décision D1 du TODO) : change l'API servie, hors de cet item.
- Cache sans invalidation : un mixin modifié après la première lecture ne masquerait plus l'alias (test 2 rouge).
- Corriger traitlets ou qtconsole dans le fork : la consigne est de ne toucher qu'à qtpy6.

## VÉRIFIÉ

- `tests/test_demarrage_web.py` : 4 tests, 4 rouges sur une copie de HEAD, 4 verts après (mesuré, natif offscreen).
- Suites `test_demarrage_web`, `test_qtpy6`, `test_doublures`, `test_paresse`, `test_web` : 125 réussis, 0 échec
  (sous-agent testeur, après la correction 1 ; correction 2 et assembleur couverts par `test_demarrage_web`).
- Page : spe.py ouvert après correction, capture `w577/verif_div.png` (mesuré hors écran).
- `w577/ecran_professeur.sh` : Firefox VISIBLE impossible depuis le bac à sable (« Process unexpectedly closed
  with status 1 ») ; même page hors écran affiche « W577 démarrage : 25,2 s » en haut à droite. Non vérifié à l'écran.
