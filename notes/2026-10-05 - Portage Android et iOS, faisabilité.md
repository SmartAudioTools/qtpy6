# Portage Android et iOS de qtpy6 : étude de faisabilité

Note du 05/10/2026. C'est une ÉTUDE : rien n'a été écrit dans le paquet, rien n'a été compilé, rien n'a tourné sur
un téléphone. Tout ce qui suit vient de la lecture du dépôt et de sources en ligne ouvertes ce jour-là ; le niveau de
preuve est donné section par section.

## Les demandes, citées

- « maintenant qu'on a prouvé pouvoir ajouter un portage sur le web de qtpy, pourrais-tu etudier la faisabilité d'un
  portage sous android et ios ? »
- « si possible le plus proche possible du natif ! et sans technologies web ! »

La seconde borne l'étude : la voie qui aurait coûté le moins (emballer le portage web existant dans une WebView ou
une PWA) est écartée par décision de l'utilisateur, et n'est pas instruite ici.

## Conclusion en quatre lignes

| | Android | iOS |
|---|---|---|
| Faisable | oui, dès maintenant | oui, à partir de PySide6 6.12, pas encore publiée au 05/10/2026 |
| Voie | `pyside6-android-deploy` officiel, roues PySide6 6.11.2 | `pyside6-ios-deploy` officiel (6.12) |
| Depuis cette machine | oui (hôte Linux accepté) | non : hôte macOS + Xcode complet exigés |
| Risque principal | les extensions C tierces, `QProcess` | idem, plus la LGPL en lien statique sur l'App Store |

« Proche du natif » se lit ainsi : c'est le vrai Qt compilé pour la plateforme (ARM64, rendu par le GPU, vrais fils,
boucles `exec()` bloquantes, polices du système), sans navigateur ni WebAssembly. Ce n'est PAS l'interface native de
l'OS : Qt Widgets dessine lui-même ses contrôles, sur Android comme sur iOS, comme il le fait sur le bureau.

## Ce qui a été relevé

### Android

Source : la doc de l'outil, branche `dev` du miroir GitHub
(`https://raw.githubusercontent.com/qtproject/pyside-pyside-setup/dev/sources/pyside6/doc/deployment/deployment-pyside6-android-deploy.rst`,
lue le 05/10/2026 ; la page rendue sur doc.qt.io ne se lit pas par l'outil web, elle n'a donc pas été recoupée).

- hôte Unix seulement (Linux ou macOS) ; Python 3.10 ou plus sur l'hôte ;
- l'outil enveloppe buildozer et python-for-android ; il épingle `p4a.branch` et `p4a.commit` dans le
  `buildozer.spec` qu'il génère, et c'est cet épinglage qui fixe le CPython embarqué (« currently CPython 3.14 » sur
  `dev`) ;
- le script d'entrée DOIT s'appeler `main.py` ;
- NDK r28c (28.2.13676358), JDK 17 ou plus ;
- les roues se passent par `--wheel-pyside` et `--wheel-shiboken`, ou se téléchargent par
  `qtpip download PySide6 --android --arch aarch64`.

Roues : `https://download.qt.io/official_releases/QtForPython/pyside6/` (listé le 05/10/2026) porte
`pyside6-6.11.2-6.11.2-cp311-cp311-android_aarch64.whl` et son pendant `x86_64`, datés du 18/08/2026. Aucune roue
Android sur PyPI. ⚠ Incohérence non résolue : ces roues sont étiquetées cp311 alors que la doc `dev` annonce un
CPython 3.14 embarqué. La doc `dev` décrit vraisemblablement la 6.12 ; avec la 6.11.2 il faut s'attendre à
Python 3.11 sur l'appareil. À trancher par un essai, pas par lecture.

Architectures : aarch64 et x86_64 (le 32 bits a été retiré d'après les notes de développement du wiki Qt for Python,
entrée du 20/08/2026).

### iOS

Sources : le billet du blog Qt du 30/07/2026 « Python Mobile App Development: Bringing PySide6 on iOS », et la doc
de l'outil sur `dev`
(`https://raw.githubusercontent.com/qtproject/pyside-pyside-setup/dev/sources/pyside6/doc/deployment/deployment-pyside6-ios-deploy.rst`,
lue le 05/10/2026).

- macOS seulement (« A Windows or Linux host is rejected ») ; Xcode complet avec le SDK iOS, les Command Line Tools
  ne suffisent pas ; un identifiant d'équipe développeur Apple pour construire vers un appareil ;
- lien STATIQUE uniquement : PySide6 et shiboken en `.a`, liés dans un projet Xcode avec les frameworks statiques de
  Qt et le `Python.xcframework` de BeeWare ; la version de Python est celle de ce xcframework, pas celle de l'hôte ;
- l'outil génère le projet (main.mm, Info.plist, project.pbxproj) ; la compilation et la signature se font dans
  Xcode ; ajouter un fichier Python oblige à relancer l'outil ;
- paquets tiers : le pur Python fonctionne s'il est copié dans le dossier du projet ; une extension C doit être
  compilée depuis ses sources pour iOS, contre le même xcframework ;
- les six greffons de permissions Darwin sont tous liés, sans réglage par application.

⚠ Deux sources se contredisent sur le simulateur : le billet du 30/07 dit qu'il n'est pas pris en charge, la doc
`dev` liste des roues `ios_arm64_simulator` et `ios_x86_64_simulator`. La doc est plus récente ; non vérifié.

Calendrier : le wiki Qt for Python note « Finalized iOS for release » (24/09/2026) puis « Final details on the 6.12
release, before announcing » (01/10/2026). La dernière version sur PyPI reste la 6.11.2 (18/08/2026) : la 6.12 est
imminente, pas sortie. Aucune date de sortie de PySide6 6.12 n'a été trouvée. Qt 6.12.0 lui-même (LTS) est sorti
le 30/09/2026, après un report depuis le 22/09 (`https://wiki.qt.io/Qt_6.12_Release`, lu le 05/10/2026) ; PySide6
suit d'ordinaire Qt de quelques jours, ce qui est un usage constaté et non un engagement.

### Outillage de cette machine

Vérifié le 05/10/2026 dans le shell de la session : ni `adb`, ni `buildozer`, ni `sdkmanager`, ni émulateur, pas de
SDK Android. Le shell n'a pas de réseau. Un premier essai Android demande donc des téléchargements lancés par
l'utilisateur (SDK, NDK, roues), comme `wasm/telecharger_sources.sh` pour le portage web.

## Ce que qtpy6 aurait à faire

qtpy6 est du pur Python au-dessus de PySide6 : il devrait s'importer tel quel sur les deux plateformes (analyse,
non mesuré). Le travail est dans ce que le bureau permet et que le téléphone refuse.

| Point | Constat (lecture du dépôt) | Piste |
|---|---|---|
| `QProcess(sys.executable, script)` | pas d'exécutable python dans un APK p4a ; aucun sous-processus sur iOS | une doublure, pendant de `ProcessusWeb` : un sous-interpréteur dans un fil (`concurrent.interpreters`, Python 3.14). Pas de « tuer » : limite à assumer |
| Fichiers | sur Android, `QFileDialog` rend des URI `content://` que `open()` ne lit pas ; `QFile` les lit | passer par `QFile` dans les chemins d'ouverture, ou copier dans le bac à sable de l'application |
| Stockage | bac à sable de l'application | `QStandardPaths`, rien à doubler |
| `tactile`, `dispositions` | vivent sous `qtpy6.web` mais ne dépendent pas du navigateur (`detecte()` passe par `QInputDevice`) | les remonter d'un cran, `qtpy6.web` les réexporte |
| Interrupteurs | `sys.platform == 'emscripten'` dans QtCore, QtGui, QtWidgets, QtPdf, QtPdfWidgets ; `navigateur()` dans `paresse.py` | ajouter le cas `android` / `ios` là où une doublure existe, pas ailleurs |
| Mode paresseux | repose sur `Shiboken.setTypeCreationHook`, un patch de la recette wasm absent des roues officielles | mode « eager », déjà le repli ; temps de démarrage à mesurer |
| `scaled()` | `QT_SCALE` auto = DPI logique / 192, avec `QT_ENABLE_HIGHDPI_SCALING=0` | à vérifier sur un écran de téléphone, c'est le premier défaut visible attendu |
| `_env.py` | écrit un fichier Plasma, seulement dans `set_env` | rien, tant que `set_env` n'est pas appelé |
| QtPdf | le wiki annonce une roue séparée (10/09 et 01/10/2026) | présence sur Android et iOS non vérifiée ; pas de doublure pdf.js possible, puisque sans technologie web |
| Construction | l'outil officiel veut `main.py` et ses propres options | un `python -m qtpy6.mobile.construire`, pendant de celui du web, qui prépare le dossier et appelle l'outil |

Hors qtpy6 mais décisif pour SmartTeacher : toute dépendance en C (serializejson en a une) doit exister pour la
cible. Sur Android, cela passe par une recette python-for-android ; sur iOS, par une compilation statique à la
main. Ni l'une ni l'autre n'a été vérifiée, et c'est probablement le plus gros poste.

## Plan proposé, par étapes

1. **Android, fumée.** Une fenêtre PySide6 nue déployée par l'outil officiel sur un téléphone ou un émulateur
   x86_64. Lève l'incohérence cp311 / 3.14 et prouve la chaîne. Faisable sur cette machine.
2. **Android, qtpy6.** La même fenêtre par `import qtpy6` ; relevé de ce qui casse (DPI, `scaled()`, tactile).
3. **Android, les doublures** : `QProcess`, fichiers `content://`, puis le constructeur.
4. **Android, une vraie application** avec ses dépendances C.
5. **iOS, fumée**, à la sortie de la 6.12, sur un Mac. Puis les mêmes étapes 2 à 4, la doublure `QProcess` étant
   commune.

Chaque étape a un critère d'arrêt : si l'étape 1 échoue sur la chaîne officielle elle-même, la suite ne vaut rien.

## Choix, et ce qui est écarté

- **PySide6 officiel plutôt que PyQt6 + pyqtdeploy.** pyqtdeploy vise Android et iOS, mais son support de Qt 6 n'est
  pas établi (discussions de forum, pas de doc officielle trouvée), et PyQt6 est sous GPL ou licence commerciale.
  Écarté ; non essayé.
- **Attendre la 6.12 pour iOS plutôt que compiler PySide6 soi-même en statique.** La recette wasm montre que c'est
  faisable (c'est le même exercice), mais l'amont livre le travail dans les semaines qui viennent, et il faut de
  toute façon un Mac. Écarté ; non essayé.
- **WebView, PWA, Pyodide embarqué.** Écarté par l'utilisateur (« sans technologies web »). Mon avis initial était
  de l'instruire en premier, parce que le portage web existe déjà. Le coût accepté : un travail par plateforme, un
  Mac pour iOS, et aucune réutilisation des doublures web hors `tactile` et `dispositions`.
- **Kivy, BeeWare/Toga, Flutter.** Hors sujet : ce ne sont pas des portages de qtpy6, il faudrait réécrire les
  interfaces.

## Points ouverts, et par où commencer la relecture

1. **La LGPL v3 sur iOS.** Le lien est statique : il faut fournir de quoi re-lier l'application avec une autre
   version de Qt, et la distribution par l'App Store rend cela difficile en pratique. La question est juridique, elle
   n'est pas tranchée ici. Android n'a pas ce problème (bibliothèques partagées dans l'APK). C'est le point qui peut
   à lui seul décider d'une licence commerciale Qt ou d'un abandon d'iOS.
2. **Le matériel.** iOS exige un Mac, Xcode et un compte développeur Apple. Rien ne peut se faire d'ici.
3. **Les extensions C** des applications visées, sur les deux plateformes.
4. **cp311 ou 3.14 sur Android** : conditionne la piste `concurrent.interpreters` de la doublure `QProcess`, qui
   n'existe qu'à partir de Python 3.14.
5. **Qt Widgets sur petit écran** : la chaîne officielle met en avant Qt Quick. Les widgets fonctionnent sur mobile
   d'après la doc de Qt, mais aucune source lue ici ne dit ce que valent les roues PySide6 sur ce point. À voir à
   l'étape 1.
6. Non lu : les notes de version de PySide6 (la page ne se rend pas par l'outil web).
