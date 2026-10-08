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
