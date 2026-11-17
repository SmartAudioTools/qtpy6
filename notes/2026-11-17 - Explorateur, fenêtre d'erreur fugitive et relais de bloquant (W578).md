# Explorateur, fenêtre d'erreur fugitive et relais de bloquant (W578, 17/11/2026)

Item 10 du TODO Portage. Remplace la note que W570 devait écrire (`2026-11-12 - Explorateur, modele None dans _relayer
(W570).md`, jamais écrite : W570 fermé le 12/11 à 00:29, correctif posé mais non lancé ni commité).

## Demande

- Le professeur, 12/11/2026 19:52 (fenêtre de W566) : pile de la fenêtre d'erreur vue au simple démarrage de spe.py dans
  son Firefox, `qtpy6_essais/equipe/w566/trace_professeur_explorateur_1952.txt` (`bloquant.py:354 __call__` →
  `_relayer:368` → `executer:377` → `explorer.py:1009` lambda `resizeColumnToContents(0)` → `initStyleOption:193`
  `'NoneType' object has no attribute 'isDir'`).
- Le professeur, 17/11/2026 02:46 (fenêtre du Superviseur) : « il faudrait aussi lancer des worker pour avancer sur le
  portage de SmartPythonEditor sur le web, en essayant de ne toucher qu'à qtpy6 ». Brief `briefs/Worker_578.md`.

## Reproduction (écrite avant le code, `qtpy6_essais/equipe/w578/ETAT.md`)

W550 n'avait pas reproduit (quatre essais). La condition manquante, trouvée en lisant `QTreeViewPrivate::layout` (Qt 6.8) :

| Essai `essais/fsmodel/page.py`, site depuis HEAD | Résultat |
|---|---|
| dossier déplié avant la mise en page, montage au niveau du module | OK : le relais REPORTE le slot |
| montage depuis un slot (entrée promettante : le relais exécute sur place) | OK : le sous-dossier n'avait pas encore de lignes |
| idem, sous-dossier `tot` déjà listé (`setRootPath(tot)`, jamais `fetchMore`) puis déplié pendant que la mise en page attend | **ÉCHEC, 5 sur 5** : même message que chez le professeur, index invalide (ligne -1) |

Mécanisme : `layout(-1)` agrandit `viewItems` d'entrées vides, les remplit une à une et, pour un dossier déplié, descend
dans `layout(last)`, qui appelle `fetchMore(tot)` (« fetchMore first »). Qt wasm n'a pas de fil (`QT_FEATURE_thread -1`,
relevé par W570) : `QFileInfoGatherer::fetchExtendedInformation` → `getFileInfos` émet `directoryLoaded` SUR PLACE. Le
relais de `bloquant`, dans une entrée promettante, exécute le slot de Spyder tout de suite : `resizeColumnToContents` →
`sizeHintForColumn` parcourt `viewItems`, dont les entrées après `tot` sont encore vides → le délégué reçoit
`QModelIndex()` → `index.model()` None. Les lignes de `tot` étant déjà connues, aucun `rowsInserted` ne pose de mise en
page différée qui l'aurait évité. En natif, le fil du gatherer livre `directoryLoaded` en connexion différée : jamais
pendant `layout`. Chez Spyder : `restore_directory_state` (`setExpanded` de l'état gardé dans la configuration du
professeur, absente d'un profil neuf : d'où W550) et les `setRootPath` successifs de `chdir` au démarrage.
La piste du brief (modèle remplacé par `setModel` avant le relais) est écartée par la mesure : le modèle ne change
jamais, c'est l'INDEX qui est vide.

## FAIT

`qtpy6/web/bloquant.py` (correctif de W570, repris tel quel après preuve) : `_est_destroyed` devient `_mode(signal)` —
True sur place (`destroyed`), **None toujours reporté (`directoryLoaded`)**, False selon l'entrée ; `_relayer` :
`r.direct or (r.direct is False and _peut_suspendre())`. Le slot de `directoryLoaded` passe donc après l'émission,
comme la connexion différée native, quel que soit l'endroit d'où Qt l'émet (`fetchMore` pendant la mise en page,
`setRootPath`). Rien à changer dans l'application ni dans `explorer.py`.

Tests : `tests/test_explorateur_web.py` (neuf) — le vrai QTreeView natif avec un `QFileSystemModel` dont `fetchMore`
émet sur place comme Qt wasm, délégué de Spyder, montage dans une entrée promettante : rouge sur HEAD (même
`AttributeError`), vert après ; déconnexion d'un slot de `directoryLoaded` (Spyder déconnecte `restore_directory_state`).
`tests/test_web.py::test_directory_loaded_reporte_comme_en_natif` (W570) : rouge sur HEAD, vert après.

## POURQUOI le relais, alternative écartée

Écartée : une doublure `QFileSystemModel` qui réémettrait `directoryLoaded` en différé (ou un `fetchMore` reporté).
Elle doublerait un signal C++ par un signal Python homonyme (masquage fragile sous PySide6 et PyQt6) pour faire ce que
le relais fait déjà : il est le seul endroit qui décide QUAND un slot passe (`destroyed` y avait déjà son cas). Un
`fetchMore` reporté imiterait aussi l'arrivée tardive des lignes, mais ferait passer chaque mise en page de la vue par
Python et ne couvrirait pas `setRootPath`, qui liste sans `fetchMore`.
Écartée aussi : un garde dans le délégué ou un `index.isValid()` dans le relais — contournement côté symptôme.

## VÉRIFIÉ

- Mesuré, essai réduit (sonde Firefox 158 du bac) : 5 ÉCHEC sur 5 depuis HEAD, 5 OK sur 5 avec le correctif
  (`w578/rouge1-5.log`, `vert1-5.log`).
- Mesuré, tests : `tests/test_web.py` entière + `tests/test_explorateur_web.py`, 67 réussis, 0 échec (testeur).
  Relecteur : aucun défaut (clés du relais cohérentes entre connect et disconnect, receveur mort sûr).
- spe.py entier (site `w578/site`, HEAD + correctif) : fenêtre ouverte, explorateur peuplé, aucune erreur. Dans le bac (profil neuf), l'erreur ne se montrait
  déjà pas : la preuve dans la condition du professeur est `w578/ecran_professeur.sh`, à lancer par lui (son Firefox,
  son état d'explorateur gardé).
- Règle du dépôt : aucune ligne propre au web ajoutée hors `qtpy6/web/` (application inchangée).
