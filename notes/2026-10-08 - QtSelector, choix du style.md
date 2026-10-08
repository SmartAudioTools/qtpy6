# QtSelector : choix du style (Fusion au lieu de Breeze)

## Demande
« serait-il pertinent d'ajouter un menu pour choisir le thème des applications qtpy6 qui utilisent
le thème par défaut ? », précisé : « un menu uniquement dans QtSelector, qui permet de choisir
Fusion au lieu de Breeze ».

## Livré
- `qtpy6/__init__.py` : réglage de session `QT_STYLE` (défaut `default`), lu à l'import comme les autres.
- `qtpy6/QtWidgets.py` : le crochet de `QApplication.__init__` (renommé `_init_with_settings`) appelle
  `setStyle(QT_STYLE)` hors `default`, avant la police.
- `qtpy6/QtSelector.py` : `QtStyleSelector`, liste `default` + `QStyleFactory.keys()`.
- README (tableau des réglages) et CHANGELOG.

## Choix
- **Variable propre `QT_STYLE` plutôt que `QT_STYLE_OVERRIDE` de Qt** : cette dernière, lue par Qt
  lui-même, aurait suffi sans une ligne dans `__init__`, mais écrite dans `QtEnvironment.sh` elle
  s'appliquerait à TOUTES les applications Qt de la session Plasma (Dolphin, Kate…). La demande vise
  les applications qtpy6.
- Une application qui appelle `setStyle` elle-même garde le dernier mot (elle le fait après le constructeur).
- Choix proposés = `QStyleFactory.keys()` de la machine, pas une liste en dur ; une valeur inconnue
  déjà écrite reste affichée (mécanisme commun `_SettingComboBox`).

## Niveau de preuve
Testé en offscreen (variables d'environnement, pas la config réelle) : `QT_STYLE=Fusion` → style
`fusion`, police 13 pt conservée ; le sélecteur liste `default, Breeze, Windows, Fusion` et affiche la
valeur courante. Vérifié que `setStyle` ne réinitialise pas la police (un commentaire qui l'affirmait
a été retiré). Fenêtre non ouverte (pas de lancement graphique depuis le bac à sable). Non testé sous
Windows ; PyQt6 testé (`QT_STYLE=Windows` → style `windows`, QtSelector construit).

## Suite : le menu ne s'affichait pas
« je ne vois pas le menu dans QtSelector » : l'entrée de menu lance `~/.scripts/QtSelector.sh`, qui
appelait encore `python -m qtpy.QtSelector` (l'ancien paquet). Corrigé dans SmartOS
(`Commun/scripts/QtSelector.sh`, rév. 264, poussée), copié par l'utilisateur dans `~/.scripts`.

## Suite : `get_env` lit le fichier de session avant l'environnement (Linux)
Question : « SmartTeacher prend-il immédiatement les changements des variables d'environnement en
compte comme SmartFaceEditor ? » — Non : SmartFaceEdit.sh, QtSelector.sh et une vingtaine de lanceurs
SmartOS font `source QtEnvironment.sh` avant Python, mais les `.desktop` de SmartTeacher lancent Python
directement. Ils héritent de l'environnement exporté par Plasma À LA CONNEXION, que `get_env`
consultait en premier : un réglage déjà présent à la connexion restait figé jusqu'à la suivante (un
réglage absent à la connexion, lui, était lu dans le fichier, donc à jour).

Correctif (accord de l'utilisateur : « oui fait cette correction ») : sous Linux, `get_env` lit
`QtEnvironment.sh` d'abord, l'environnement seulement pour un réglage absent du fichier.
- Écarté : ajouter un lanceur `source …` à chaque application (SmartTeacher a quatre `.desktop`,
  et toute application future aurait le même piège) ; corriger dans qtpy6 couvre tout d'un coup.
- (Remplacé par la section suivante : la ligne de commande ne pouvait plus forcer un réglage.)

Tests : `test_env_file` (le fichier gagne ; l'environnement sert pour un réglage absent),
`test_font_settings` (variable d'environnement contraire au fichier → valeur du fichier),
`test_style_setting` (nouveau : `QT_STYLE` par l'environnement, puis le fichier qui l'emporte),
`test_selector` (5 listes ; le commit précédent l'avait cassé, la suite n'ayant pas été lancée).
54 tests verts sous SmartPython (PySide6 + PyQt6). Que le nouveau test échoue sans le correctif :
vérifié par lecture seulement (l'ancien `get_env` rendait la variable d'environnement).

## Suite : la copie de connexion `QTPY6_LOGIN_<clé>` (Linux et Windows)
Question : « il n'est pas possible de détecter le changement de QT_STYLE quand on lance
QT_STYLE=Fusion python app.py, […] en regardant si le style […] est différent de celui par défaut
au démarrage de la session ? » — puis « QtSelector ne peut forcer une mise à jour des variables
d'environnement de la session ? », « on ne peut pas faire écrire un nouveau fichier, pris en compte
seulement s'il est plus récent que le démarrage de la session ? », et « réfléchis à la meilleure
solution en explorant plusieurs options ». Accord : « oui » (copie de connexion, sur les deux systèmes).

Livré (`qtpy6/_env.py`) : `set_env` écrit `export KEY=v QTPY6_LOGIN_KEY=v` (Windows : deux `setx`)
et pose les deux dans `os.environ`. `get_env`, commun aux deux systèmes : la variable si elle
existe et diffère de sa copie (posée après la connexion), sinon le réglage de session (fichier ou
registre), sinon la variable, sinon `default`. Le mécanisme Windows `_redefined_in_python`
(comparaison avec `nt.environ`) disparaît : il ne voyait qu'une variable changée dans le code
Python, pas un `set QT_STYLE=…` tapé avant de lancer le programme.

Options comparées et écartées :
- le fichier d'abord (section précédente) : la ligne de commande ne force plus rien, alors que le
  dépôt SmartOS s'en sert (`QT_API=pyqt6 paru -Syu` dans `mise_a_jour.sh`) ;
- mettre à jour l'environnement de la session : impossible pour un processus déjà lancé
  (`plasmashell`, Konsole ouvertes) ; `dbus-update-activation-environment` ne touche que les
  services activés par D-Bus/systemd (de mémoire, non testé : pas de bus de session ici) ;
- un fichier daté, pris s'il est plus récent que l'ouverture de session : la date ne dit pas qui a
  posé la variable (après un changement, la ligne de commande perd de nouveau), et l'heure
  d'ouverture se retrouve mal ;
- lire l'environnement de `plasmashell` dans `/proc` : retrouver le processus est fragile, KDE seul ;
- un fichier de réglages non exporté pour QT_FONT/QT_FONT_SIZE/QT_STYLE : modèle propre, mais
  `QT_API` doit rester exporté (qtpy, matplotlib, lanceurs) : deux mécanismes au lieu d'un.

Limites connues : une ligne écrite sans copie (par l'installateur SmartOS, ou avant ce changement)
se comporte comme avant tout ceci (l'environnement hérité gagne) jusqu'à ce que QtSelector la
réécrive. Poser exprès la valeur qu'avait le réglage à la connexion, alors qu'il a changé depuis, est
pris pour une valeur héritée. `QT_API`, que qtpy6 pose dans `os.environ` à l'import, passe pour
« posé exprès » aux processus enfants : ils suivent le binding du parent, ce qui est le comportement
voulu.

Tests : `test_env_file` (héritée → fichier ; différente de sa copie, ou sans copie → environnement ;
contenu du fichier), `test_env_file_written_by_hand`, `test_font_settings` et `test_style_setting`
(processus neufs : valeur de connexion → fichier ; posée exprès → elle gagne), `test_env_windows.py`
(même règle face au registre ; deux `setx`). Suite complète sous SmartPython : 134 verts, 2 ignorés.
Niveau de preuve : testé sous Linux en processus réels ; Windows testé seulement contre des
`winreg`/`setx` simulés, pas sur une vraie machine. Une ligne `export A=… B=…` sourcée par `sh`
exporte bien les deux variables (vérifié) ; dans une vraie ouverture de session Plasma : non vérifié.
