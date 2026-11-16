# TODO - Supprimer les doublures web : même comportement en natif et dans le navigateur

Demande du professeur (16/11/2026 20:05, via Worker 712 SmartTeacher) : « j'aimerais supprimer toutes les doublures,
pour vraiment avoir le même comportement en natif et web » ; puis « oui » à une étude chiffrée, sans code.
Étude d'origine, sources et mesures : `/DATA/Python/SmartTeacher_essais/lecteur/w712/ETAT.md`. Liste des doublures :
`web.md`, table « Nom Qt / Dans le navigateur ». Rien n'est commencé ; le classement ci-dessous est À VÉRIFIER.

## 1. Étude chiffrée (à faire en premier, sans code)
Pour chacune des 7 doublures : le vrai Qt-WASM peut-il la remplacer, à quel coût (points de quota, heures machine,
Mo téléchargés), et que perd-on ? Rendu : une note `notes/AAAA-MM-JJ - Suppression des doublures, étude.md`.

## 2. Remplaçables a priori par le vrai Qt compilé
- [ ] **`QPdfDocument` / `QPdfView`** (aujourd'hui pdf.js, `qtpy6.web.pdf`). QtPdf = PDFium, absent de Qt-WASM 6.10
  et 6.12. Plan : compiler PDFium avec notre emsdk 4.0.9 (depot_tools, gn, sans V8 ni XFA, correctifs de
  bblanchon/pdfium-binaries), patcher qtwebengine pour lier ce PDFium externe, liaisons PySide6 QtPdf/QtPdfWidgets
  sur le modèle des modules à la demande (`notes/2026-10-10 - Modules Qt à la demande.md`), puis reprendre
  `setPageLimit`, `setMasks`, sélection et liens. Coût estimé 8 à 15 points, échec possible à la compilation de PDFium.
  Taille mesurée : pdfium.wasm 4,6 Mo bruts (≈ 2,7 Mo compressé, non vérifié) contre pdf.js 0,50 Mo gzip, une fois par
  poste (cache de `sw.js`). Perdu : la couche de texte de pdf.js (sélection, copie) à redessiner côté Qt.
  Recommandation de W712 : garder la doublure tant qu'aucun défaut d'affichage n'est constaté chez les élèves.
- [ ] **`exec()`** des dialogues, menus, boucles, `QDrag.exec` (aujourd'hui `qtpy6.web.bloquant`, `boucles_qt`) :
  vérifier si le mode JSPI/asyncify propre à Qt 6 pour WebAssembly couvre les mêmes cas, dont `QDrag.exec` et les
  sélecteurs de fichiers ; si oui, retirer notre couche.
- [ ] **`QFontDatabase.systemFont(FixedFont)`** : embarquer une police à chasse fixe dans Qt plutôt que prendre la
  première chargée par l'application.

## 3. Impossibles par nature dans un navigateur (à confirmer, puis l'écrire dans `web.md`)
- [ ] `QProcess` : aucun processus dans une page (reste `ProcessusWeb` sur Web Worker).
- [ ] `QThread`, `QThreadPool`, `QRunnable`, verrous, `time.sleep` : Pyodide est construit sans pthreads.
- [ ] `ThreadPoolExecutor`, `os.cpu_count()` : même raison.
- [ ] Sélecteurs de fichiers : le navigateur rend un contenu, pas un chemin.
Pour ceux-là, « même comportement » ne peut venir que de la doublure : l'objectif devient de réduire les écarts
observables, mesurés, et de les lister.
