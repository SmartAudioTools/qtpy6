# Lenteur du rendu dans le navigateur : profil (10/11/2026)

Demandes de l'utilisateur, 10/11/2026 : « je trouve que qtpy6 est beaucoup plus lent sur le web qu'en natif, le problème
viendrait du passage par le canvas HTML ? » ; « on ne peut vraiment pas court-circuiter le canevas HTML ? » ; « la page
d'accueil de SmartTeacher avec une page pleine de TP / révision rame particulièrement. Après utilise le test qui te
permettra d'itérer le plus vite ».

## Conclusion

**Le canevas n'est pas le coupable** : ce qui part au canevas (`putImageData`, chronométré en JS) coûte 0,5 à 1 ms par
image à l'échelle 1, 2,2 ms en HiDPI (échelle 2). **Le temps part dans le dessin raster de Qt compilé en WebAssembly**,
3 à 8 fois plus lent qu'en natif, et dans Python (×2,5 à 3).

Court-circuiter le canevas n'est pas possible : une page web n'a pas d'autre surface d'affichage, et WebGL (le seul accès à
la carte graphique) passe lui aussi par un canevas. Ce ne serait de toute façon pas le bon levier : il pèse moins de 10 % du
temps d'une image.

**Cause principale du défilement, trouvée** (question de l'utilisateur : « lors d'un scroll ce n'est pas une simple image à
translater ? ») : si, en natif — mais **Qt-WASM ne sait pas translater**. `QWasmBackingStore`
(`outils_wasm/pyside6/src/qtbase/src/plugins/platforms/wasm/qwasmbackingstore.h`) dérive de `QPlatformBackingStore` sans
redéfinir `scroll()`, dont la version de base ne fait rien et rend `false` (`qplatformbackingstore.cpp:363`) : Qt repeint
alors toute la zone. Mesuré (`analyse.zone_repeinte`, pas de 6 px sur le tableau SECONDE 3) : **100 % du viewport repeint
par pas dans Firefox, 34 % en natif**. Correctif : un `scroll()` dans `QWasmBackingStore` qui décale `m_image` en place
(comme `QRasterBackingStore::scroll`, `qt_scrollRectInImage`), puis reconstruire qtbase-WASM et Pyodide-Qt.

**Correctif fait le 10/11/2026** (demande : « écris le scroll dans QWasmBackingStore et recompile ») :
`wasm/patches/qtbase-wasm-defilement.patch`, appliqué par la phase `qt` de `wasm/construire.sh` ; reconstruit par
`construire.sh qt dynamique` (`journaux/defilement.log`), l'ancien `dist/` gardé dans `build/dist-avant-defilement`.
Mesuré par `SmartTeacher_essais/profil_tableau/comparer.sh` (même page, même molette de 80 crans, seul `pyodide-qt` change) :

| | avant | après |
|---|---|---|
| zone repeinte par pas de 6 px | 100 % | 34 % (= natif) |
| dessin Qt pendant la molette, échelle 1 (pompe `setInterval`) | 975 ms | 95 ms |
| idem en HiDPI (échelle 2) | 2316 ms | 119 ms |
| images au-delà de 25 ms, HiDPI | 75 | 2 |
| durée de la molette, HiDPI | 6,1 s | 2,4 s |

Justesse : le canevas après la molette, comparé au même après un repaint complet, 0 pixel différent aux échelles 1 et
2 (`MESURE justesse`). Niveau de preuve : Firefox sans interface ; contrôle fait à la position finale seulement (la
molette revient en haut), aucun défaut visible dans les captures. **Pas encore déployé** : SmartTeacher et
`exemple/pyodide-qt` portent toujours l'ancien Pyodide-Qt (10/10) ; il faut la phase `paquet`, le sha256 dans
`web/versions.json` et la release. Le manque vaut aussi pour Qt amont (6.10.2) : un rapport de bogue à Qt est possible.

Lien avec `qtpy6.web.defilement.ZoneDefilante` (CHANGELOG) : elle faisait déjà ce décalage en Python, mais seulement
là où l'application l'emploie (le lecteur QCM, `SmartTeacher/QCM/modele.py`) ; la page d'accueil (`tableau_eleves.Tableau`,
une `QScrollArea` ordinaire) n'en profitait pas, d'où sa lenteur. Avec le correctif dans Qt-WASM, toute zone défilante
en profite ; une fois le nouveau Pyodide-Qt déployé, `ZoneDefilante` devient un candidat à la simplification (à mesurer
avant de la retirer).

**Mesuré ensuite** (question de l'utilisateur : « du coup on a toujours besoin du décalage en python ? »), lecteur QCM,
scénario `defilement_rapide` de `sonde_lecteur.html`, échelle 2, 60 pas de 8 px, `SmartTeacher_essais/profil_tableau/lecteur.sh` :

| | période | peinture médiane |
|---|---|---|
| ZoneDefilante, ancien Qt | 26,3 ms | 11 ms |
| Qt seul, ancien Qt | 63,0 ms | 48 ms |
| ZoneDefilante, nouveau Qt | 22,3 ms | 9 ms |
| Qt seul, nouveau Qt | 64,1 ms | 47 ms — **aucun gain** |
| Qt seul, nouveau Qt, contenu `WA_OpaquePaintEvent` (`?opaque=1`) | **16,7 ms** | **4 ms** |

Pourquoi : Qt ne décale (`moveRect`, `scrollRect` : `accelerateScroll = … && isOpaque`) que si le widget déplacé est
OPAQUE ; le contenu du lecteur (`modele.py`, `QWidget#contenu`) a son fond par feuille de style (`WA_StyledBackground`),
ce que Qt ne compte pas pour opaque : tout est repeint, en natif aussi (où cela ne se voit pas). La page d'accueil, elle,
avait un contenu opaque, d'où ses 34 %. Justesse (`?opaque=1`) : contre un repeint complet, 249 pixels différents, tous
dans des éléments animés (le chronomètre « Temps écoulé », passé de 08 à 09 s, et un indicateur d'attente en arc), aucun
dans le décalage. À savoir : ZoneDefilante ET contenu opaque ensemble sur le nouveau Qt donnent 557 659 pixels faux : les
deux mécanismes ne se cumulent pas.

Donc, une fois le nouveau Pyodide-Qt déployé, le décalage Python n'est plus utile ; il faut en revanche que le contenu
soit opaque. Par la règle de qtpy6 (c'est à qtpy6 de le prévoir), `ZoneDefilante` se réduirait à poser
`WA_OpaquePaintEvent` sur son contenu quand son fond est opaque — non fait, à décider.

**Seconde piste, non essayée** : Qt-WASM est compilé SANS `wasm-simd128` (`outils_wasm/pyside6/qt-wasm/mkspecs/qconfig.pri` :
`wasm-simd128` dans `disabled_features`, avec `trivial_auto_var_init_pattern` et `libcpp_hardening` activés). En natif, les
opérations par pixel de Qt (remplissage, mélange alpha, dégradés) passent par SSE2/AVX ; ici elles passent par le code
scalaire. Les micro-mesures concordent (tableau ci-dessous) : opérations par pixel ×2,6 à ×6, texte ×1,5 à ×3. Reconstruire
Qt-WASM avec `-feature-wasm-simd128` est le levier à mesurer ensuite (Safari le gère depuis 16.4). Que Qt emploie alors
ses chemins SSE2 par l'émulation d'Emscripten est une HYPOTHÈSE, à vérifier dans les sources de qdrawhelper avant la
reconstruction.

## Mesures

Firefox 158 sans interface (bac à sable, rendu logiciel, sans synchronisation verticale), contre le natif hors écran
(`offscreen`, raster, aucun envoi à l'écran), même machine. Python 3.13, PyQt6 ; Qt 6.11.1 natif, 6.10.2 WASM.

`essais/profil_rendu/` (natif.log, sonde_firefox.log, sonde_firefox2.log) — médianes, ms :

| phase | natif | web (2 passes) |
|---|---|---|
| Python pur | 38 | 99–114 |
| QPainter, C++ dominant (chemin + texte) | 32 | 41–51 |
| 3000 drawLine depuis Python | 49 | 60–108 |
| repaint QTableWidget 1000×800 | 8 | 27–29 |
| paintEvent Python (800 lignes, 100 textes) | 21 | 28–44 |
| canevas pendant 60 pas de défilement | — | 49–62 ms en tout, 0,8–1 ms par image |

Page d'accueil de SmartTeacher (`tableau_eleves.construire`, SECONDE 3, vraies données du dossier Dropbox),
`/DATA/Python/SmartTeacher_essais/profil_tableau/` :

  - natif (`sonde.py`) : construction 104 ms à chaud (757 ms la première fois, dont 751 ms au premier QLabel riche :
    chargement des polices, propre au natif) ; repaint complet 2,2 ms ;
  - web (`racine/sonde_tableau.html`, `molette.py`) : construction 180–330 ms, affichage 60–230 ms ; repaint complet
    17–19 ms (×8), 39,5 ms en HiDPI ; vraie molette WebDriver (80 crans fins) : à l'échelle 1, aucune image au-delà de
    25 ms, mais ~10 ms de dessin Qt par pas (dans la pompe `setInterval` de qtpy6) ; **en HiDPI, ~25 ms par pas, 60 images
    sur 220 au-delà de 25 ms** : c'est là que ça rame ; le canevas, 2,2 ms par image ;
  - feuilles du tableau (repaint isolé) : 1,8 ms natif, 14,7 ms web, presque tout dans les QLabel en texte riche
    (`TitreDeSujet`, titres) ;
  - un QLabel : 0,08 → 0,5 ms (×6,5) alors que son texte seul (`drawText`, `QTextDocument.drawContents`) ne prend que
    ×1,5 à ×3 : le reste est le chemin de peinture d'un widget (fonds, style, composition du backing store) ;
  - opérations par pixel, 1000×800 : remplissage opaque 0,23 → 0,60 ; translucide 0,27 → 1,40 ; dégradé 0,24 → 1,50 ;
    drawImage alpha 0,62 → 1,90 ; 40 rectangles arrondis antialiasés 2,51 → 4,50.

Niveau de preuve : mesuré dans Firefox sans interface, sans GPU ni vsync ; un navigateur réel avec écran peut différer
(composition GPU du canevas, cadence de l'écran). Le gain de `wasm-simd128` est déduit, pas mesuré.

## Rejouer

    P=/DATA/Python/SmartPython/CachyOS/versions/SmartPython/bin/python
    cd /DATA/Python/SmartTeacher_essais/profil_tableau
    XDG_CONFIG_HOME=$TMPDIR/cfg QT_QPA_PLATFORM=offscreen QT_API=pyqt6 $P sonde.py "SECONDE 3" [--lignes|--profil defilement]
    $P molette.py --dy 3 --racine racine "racine/sonde_tableau.html?classe=SECONDE 3" web_z1.png [--zoom 2] \
        --delai 300 --etat glisser --glisser page > web_firefox_z1.log 2>&1

`racine/` : liens vers `SmartTeacher/QCM/web/pyqt6` (lecteur.zip déjà construit) et copie de `echeances.csv`/`tableau.json`.
La même page servira à mesurer un Qt-WASM reconstruit avec SIMD : seul `pyodide-qt` change.

## Sonde complète du lecteur, ancien et nouveau Qt (10/11/2026, 02 h)

Demandée par le Superviseur SmartTeacher avant de joindre le nouveau Pyodide-Qt au lot. Script
`SmartTeacher_essais/profil_tableau/scenarios.py` : les 24 scénarios web de `tests_modele.py` (sans les
`validees_*`), chacun sur `dist-avant-defilement` puis `dynamique/dist`, Firefox et Chromium (96 essais), bilan
dans `scenarios.log`, captures et journaux dans `captures/`.

- **0 écart** entre ancien et nouveau Qt sur 48 couples. 46 passent des deux côtés.
- `escalade` échoue des DEUX côtés, dans les deux moteurs (`AssertionError: attendu en vain : appel 1 de A`) :
  préexistant, sans lien avec Qt ; signalé au Superviseur SmartTeacher.
- Zoom de la loupe à 2 (`--loupe 2` : `localStorage["qtpy6|loupe"]` posé avant `preparer`, donc
  `QT_SCALE_FACTOR=2` comme après `qtpy6.loupe.zoomer`), sur affichage, defilement_rapide, molette_menu,
  redimensionner, glisser : **0 écart** sur 10 couples, capture « Zoom 200 % » nette
  (`captures/apres_loupe2_firefox_defilement_rapide.png`). `glisser` échoue des deux côtés sous loupe 2 :
  préexistant (le scénario vise des coordonnées à l'échelle 1).

## Archive à publier (pas publiée)

`construire.sh paquet` produit maintenant `pyodide-pyside6-0.29.3.7.zip` (le nom suivant ; 0.29.3.6 reste
intact) : 26 586 773 octets, sha256 `3d695c024fa1c5b55bd02dd364291b3f12843cb0868700dd2a17ef63962c2701`,
`pyside_agrege.so` de 26 862 137 octets daté 10/11 01:34. L'empreinte change à chaque reconstruction (pyc datés) :
si le paquet est refait, reprendre celle qu'il affiche.

Le lecteur en ligne charge Qt depuis `https://smartaudiotools.github.io/qtpy6/pyodide-qt/` (`construire.py`,
`PYODIDE_QT`) : publier le nouveau Qt, c'est publier qtpy6, pas SmartTeacher. Étapes, au professeur :

1. Créer la release `pyodide-pyside6-0.29.3.7` du dépôt qtpy6 sur GitHub avec ce zip.
2. Dans `qtpy6/web/versions.json`, `pyodide_pyside6` : `archive` → `.../pyodide-pyside6-0.29.3.7/pyodide-pyside6-0.29.3.7.zip`,
   `sha256` → celui ci-dessus ; commiter, pousser qtpy6 (l'action Pages lance `hebergement/telecharger.sh`).
3. Recopier le `dist` dans `SmartTeacher/QCM/web/pyqt6/pyodide-qt/` (copie locale, « même version que la
   publiée », dont `construire.py` lit les tailles), puis `SmartTeacher/QCM/web/pousser_et_deployer.sh`.

Ce que le professeur doit voir : l'accueil d'un élève (page de TP pleine) qui défile à la molette sans saccade
(mesuré : 2,4 s au lieu de 6,1 pour 80 crans, 2 images lentes au lieu de 75), sans trace ni bande décalée en
haut ou en bas du tableau ; le lecteur de QCM inchangé (ZoneDefilante toujours active, 9 à 11 ms par image).
Aucune modification de ZoneDefilante avant la détection du Qt qui sait décaler (condition du Superviseur).

## SIMD essayé : aucun gain (10/11/2026, 02 h 10)

Qt-WASM reconstruit avec `-DFEATURE_wasm_simd128=ON` (`outils_wasm/pyside6/simd.sh`, dist dans `build/dist-simd`),
mesuré contre `dist-defilement` (scroll() seul), même page, même molette :

| | scroll() seul | + SIMD |
|---|---|---|
| accueil, échelle 2 : intervalle médian, images > 25 ms | 17,0 ms, 0 | 17,1 ms, 0 |
| accueil, échelle 2 : putImageData sur 80 crans | 122 ms | 139 ms |
| lecteur, repeint complet (contenu non opaque) : peinture médiane, période | 17 ms, 20,6 ms | 20 ms, 24,3 ms |
| lecteur, ZoneDefilante : peinture médiane | 3 ms | 4 ms |

L'hypothèse était fausse, vérifiée dans les sources : `qdrawhelper_sse2.cpp` n'est compilé qu'avec la détection SSE2
(x86) et `qsimd.h:117` exige `Q_PROCESSOR_X86` : sur wasm32, Qt n'emploie jamais ses chemins SSE2, `-msimd128` ne
sert qu'à la vectorisation automatique du compilateur, sans effet mesurable ici. Écarté.

**Pistes que j'avais laissées de côté** (relevées le 10/11 à la demande de l'utilisateur, « je me demande si tu n'as
pas écarté d'autres pistes un peu vite ») : qtbase est compilé en `-O2` (`optimize_full` OFF, sans LTO) avec
`trivial_auto_var_init_pattern` (chaque variable locale remplie d'un motif ; qdrawhelper emploie des tampons de pile
de plusieurs kilo-octets par segment dessiné) et `libcpp_hardening` (contrôles de bornes de libc++). Essai en cours :
les trois retournés ensemble (`options.sh rapide`), puis une à une si gain. Et `QWasmWindow::paint` envoie l'image
ENTIÈRE (`putImageData(image, 0, 0)`) à chaque rafraîchissement, quelle que soit la zone changée.

## -O3, sans motif de pile, sans durcissement libc++ : aucun gain (10/11/2026, 02 h 20)

`options.sh rapide` : `optimize_full` ON, `trivial_auto_var_init_pattern` OFF, `libcpp_hardening` OFF, SIMD OFF
(`build/dist-rapide`). Machine chargée (charge 28 à 35 sur 20 cœurs, autres sessions), donc cinq passes du lecteur
EN ALTERNANCE avec `dist-defilement` (`SmartTeacher_essais/profil_tableau/alternance_rapide.log`), peinture médiane
à l'échelle 2 :

| passe | ZoneDefilante : actuel / rapide | repeint complet : actuel / rapide |
|---|---|---|
| 1 à 5 | 9, 8, 7, 10, 10 / 11, 11, 8, 15, 13 ms | 39, 45, 34, 49, 61 / 49, 50, 38, 54, 41 ms |

Le Qt « rapide » n'est pas plus rapide (plus lent dans 4 passes sur 5). Le temps de dessin n'est donc pas dans le
code C++ de qtbase que ces options touchent ; il reste Python et les liaisons PySide (×2,5 à 3, mesuré plus haut).
Écarté. Les options d'origine sont remises (`options.sh retour`) pour que `construire.sh` retrouve un arbre conforme ;
le dist validé (scroll() seul, archive 0.29.3.7) n'a pas bougé (`build/dist-defilement` = `dynamique/dist`).

Reste non mesuré : l'envoi de l'image entière par `QWasmWindow::paint` (putImageData : 1,5 à 2 ms par image à
l'échelle 2, soit au plus ce gain), à mesurer machine au repos. Le levier mesuré le plus fort reste l'opacité du
contenu (lecteur : 47 → 4 ms), sous la condition du Superviseur (détecter le Qt qui sait décaler).

## Déploiement demandé (10/11/2026, 02 h 51)

L'utilisateur : « peut on déjà deployer ce qui a prouvé un gain de vitesse ? et reprendre les tests demain sur une
machine moins chargée ? ». Seul le scroll() a prouvé un gain (accueil) : `qtpy6/web/versions.json` pointe maintenant
`pyodide-pyside6-0.29.3.7` (sha256 `3d695c02…62c2701`, recontrôlé par `sha256sum`), commité avec le patch, `construire.sh`,
son README et cette note. ZoneDefilante inchangée ; SIMD et options de compilation non retenus (à remesurer machine au
repos, la charge ne permettait de voir qu'un gain du simple au double).

⚠ **Release GitHub AVANT tout push de qtpy6** (y compris par `pousser_et_deployer.sh`) : sinon l'action Pages lit un
`versions.json` qui pointe une archive absente. `gh` n'est pas connecté dans les sessions : la release est au professeur.
