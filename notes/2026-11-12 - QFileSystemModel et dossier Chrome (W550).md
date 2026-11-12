# QFileSystemModel et dossier Chrome (W550, 12/11/2026)

Demande : ordre du professeur, 12/11 14:04 : « mets des workers sur tous les items qui peuvent être traités
indépendamment » ; brief `qtpy6_essais/equipe/briefs/Worker_550.md` : items 10 et 13 (tiret « dossier autorisé de
Chrome ») du TODO Portage.

## Item 10 — fenêtre d'erreur fugitive de l'explorateur : NON REPRODUITE, cause non prouvée

Pile relevée par l'utilisateur (TODO son, avant-dernier item) : `fsmodel.directoryLoaded` → `resizeColumnToContents(0)`
(`explorer.py:1008`, relayé par `bloquant.py`) → `DirViewItemDelegate.initStyleOption` (`explorer.py:178`) reçoit un index
dont `index.model()` vaut None → `'NoneType' object has no attribute 'isDir'`.

FAIT : quatre essais par la sonde (Firefox 158 du bac), aucun ne montre l'erreur :

| Essai | Condition | Résultat |
|---|---|---|
| `essais/fsmodel/page.py`, natif offscreen | QTreeView + QFileSystemModel + délégué de Spyder, `directoryLoaded` → `resizeColumnToContents(0)`, tri, sous-dossier déplié | OK, 2 `directoryLoaded`, 0 erreur |
| même essai, page | script au niveau du module (slot appelé sur place par le relais) | OK, idem |
| même essai, page, script suspendu dans `QEventLoop.exec()` | comme Spyder : le relais de `bloquant` REPORTE le slot (`_plus_tard`) | OK, idem |
| `spe.py` (Spyder entier, 33 greffons) | site à moi, `qtpy6_essais/w550/site_spe` | pas d'erreur d'explorateur (fenêtre ouverte, délai attendu) |
| `spe_monkey.py`, `bouton=1` puis jeu lancé | jeu `exercice_02`, dossier Monkey | fichier ouvert, explorateur peuplé, pas d'erreur `isDir` ; le lancement échoue sur `SystemError: Cannot enter promising task…` (item 1, W545) |

POURQUOI non reproduite : la condition de l'utilisateur est le jeu QUI TOURNE (Chrome, WebGL) ; dans le bac, Firefox n'a
pas WebGL et le lancement casse avant (SystemError JSPI, item 1). La piste du TODO son (« QFileSystemModel sans fils émet
`directoryLoaded` avant que ses lignes soient valides ») n'est pas confirmée : sur le modèle seul, les lignes sont
valides au moment du signal (4 puis 3 lignes comptées dans le slot), report ou non.

Pas de doublure écrite : sans pile reproduite, une doublure de `QFileSystemModel` (ou un garde dans le relais) serait un
contournement sans cause — écarté (méthode : « qui PRODUIT ? »). Ce qui reste à faire pour prouver la cause :
reproduire avec le jeu lancé, donc après l'item 1 (W545) ou dans Chrome par le professeur, en relevant la pile ENTIÈRE
(qui appelle `initStyleOption` : `sizeHintForColumn` depuis le relais reporté, ou un `paint` après un `modelReset` du
changement de dossier de travail).

Écart constaté en route, signalé au Superviseur : `essais/spyder/site/app.zip` corrompu à 14:11 (le site emballe les
journaux que les sondes écrivent pendant la construction). Mon site Spyder est construit à part par
`essais/fsmodel/construire_site_spe.py` (même script, autre sortie, `testzip` à la fin) ; il emballe aussi `site/` du
dossier partagé (132 Mio au lieu de 45) — sans effet sur la mesure, à ne pas réutiliser tel quel.

VÉRIFIÉ : mesuré (quatre sondes, journaux et captures dans `/DATA/Python/qtpy6_essais/w550/`) ; la cause, elle, reste
supposée. Délégation : relevés faits par moi (lectures liées à l'écriture de l'essai, pas un relevé pur).

## Item 13, dossier autorisé de Chrome : NON COMMENCÉ

Seuil de contexte du worker atteint (61 %) pendant l'item 10 : cet item ne partage ni fichiers ni lectures avec le
précédent, il revient à un worker neuf. Point d'entrée : `qtpy6/web/stockage.py:59` (`monter`, IDBFS autoPersist),
jalon 5 bis de la faisabilité (mesures Chrome 153 : `granted` au rechargement, `prompt` après fermeture de Chrome →
bouton « Réautoriser », `syncfs` 30–70 ms à faire à l'enregistrement).
