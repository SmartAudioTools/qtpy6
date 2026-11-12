# Jalon 7 sans contournement d'essai (W547) — items 3, 5 et 12 du TODO Portage

Demande : ordre du professeur, 12/11 14:04, « mets des workers sur tous les items qui peuvent être traités indépendamment » ;
brief `qtpy6_essais/equipe/briefs/Worker_547.md` : `jalon7.py` sans `delattr` (l. 67-75) ni `--new-instance` (l. 79), fermeture
mesurée jusqu'au bout. Mesures et scripts : `/DATA/Python/qtpy6_essais/equipe/w547/`.

## Item 3 — D1, alias snake_case des signaux : EN ATTENTE DU PROFESSEUR

Relevé du 12/11 (`noms_alias_signaux.py`, `appels.txt`) : 279 alias de signaux posés par `_binding._pyside6_class`
(l. 152-155). Appelants d'un alias de signal (`.<alias>.connect|emit|disconnect`) dans qtpy6, SmartTeacher et `FORKS/` :
`qtpy6/QtSelector.py:28,66` et `tests/test_qtpy6.py:29` seulement ; les 18 autres lignes sont des signaux que Spyder
(`focus_changed`, `return_pressed`, `visibility_changed`) et qtconsole (`font_changed`, `copy_available`) déclarent
eux-mêmes. Zéro dans SmartTeacher (45 fichiers importent qtpy6). Mesuré.

Témoin : `essais/alias_signal_slot.py` plante, code 139 (mesuré 12/11, PySide6 offscreen).
Cause : l'alias est l'objet `Signal` lui-même posé sous un second nom ; une méthode homonyme d'une classe fille
connectée au signal fait planter PySide6 (lu dans le code et mesuré, mécanisme interne de PySide non lu).

Options posées au professeur (14:12 à 14:31) :
- A : plus d'alias de signal (camelCase seul) — aucun risque ; API incohérente avec les méthodes snake_case.
- B : renommer les 3 slots dans le générateur du fork (`FORKS/SmartPythonEditor_generator/spyder_patch/`, un
  `patch_spyder_slots_homonymes.py` neuf déclaré dans `appliquer_correctifs_spyder.sh`, 6 lignes dans 3 fichiers du
  fork) — ne soigne que ce symptôme ; le renommage a déjà été perdu une fois.
- C : l'alias en DESCRIPTEUR qui rend le signal camelCase de l'objet (comme `_Alias` des méthodes). Mesuré
  (`essai_alias_descripteur.py`) : plus de plantage, le slot homonyme reçoit, l'alias marche sur la classe de base.
  Défaut : une sous-classe à méthode homonyme masque l'alias (`obj.x_changed.connect` → AttributeError, bruyant),
  comme le masquage de nom en C++. Avis du Superviseur : C, avec trois conditions (tests de non-régression, accès
  par la classe identique au signal camelCase, même mécanisme côté web).
- D : C + avertissement à la définition d'une sous-classe qui masque un signal (`QObject.__init_subclass__`) — mesuré
  faisable (`essai_init_subclass.py`). Ma recommandation.
- E : alias préfixés `sig_` (convention de Spyder) — pas de collision, s'écarte du nommage Qt des méthodes.

## Item 5 — `--new-instance` retiré : FAIT, mesuré avec la doublure socket_web de W548

**Correction (14:42, signalée par W548)** : les deux premiers essais ci-dessous ne tournaient PAS sur le même site :
« sans » sur un app.zip de 14:14 (ancien `socket_web.py`, 1 618 octets, sans `listen`/`accept`), « avec » sur un
app.zip de 14:29 (nouveau, 19 035 octets). La différentielle ne valait donc rien. Rejoué sans `--new-instance` sur un
site reconstruit à 14:40 (même `socket_web.py` de 19 035 octets que « avec ») : `post_visible_setup` passe,
`closing` → `closing fini` en 0,4 s, `sortie de exec()`, état « fini » (`sonde_sans2.log`). Mesuré. Le gel décrit
ci-dessous était celui de l'ancien `socket_web.py` ; il ne se reproduit pas avec le nouveau. Item 5 fait.

Premiers essais (historique, conclusion retirée) :

Site privé (`construire_site.py --sortie`, consigne du Superviseur 14:14). Sonde, `jalon7.py` sans `--new-instance`
(`sonde_jalon7.log`) : `post_visible_setup` passe (19,4 s), aucun « can't start new thread » ; 39 plugins passent.
Puis `closing : 23.87 s` et plus rien : délai de 800 s dépassé, état « fermeture ». Mesuré.
Même site, avec `--new-instance` (`sonde_avec.log`) : `closing fini` en 3 s, `sortie de exec()`, état « fini ». Mesuré.
Donc le gel vient du serveur d'instance unique (`MainWindow.start_open_files_server`, fork `mainwindow.py:1524`) :
sa boucle `while 1: accept()` tourne dans `threading_web.Thread`, coopératif sur le fil unique ; à la fermeture,
une attente de `closing` pompe la file et donne la main à ce fil, dont l'`accept()` ne rend jamais (ou boucle).
Niveau : la cause « serveur d'instance » est mesurée (différentielle) ; le mécanisme exact (accept bloquant ou
boucle sur EAGAIN) est supposé, sans trace Python : la page est figée. Pas de modification de `threading_web.py`
(domaine de W548, brief) : signalé à W548.
`jalon7.py` garde `get_options([])` : l'essai mesure maintenant ce gel ; tant qu'il n'est pas corrigé, la sonde
expire sur « fermeture ».

## Item 12 — fermeture mesurée ; l'`InvalidStateError` n'est pas de superqt

`jalon7.py` pose l'état « fermeture » avant `main.closing`, les étapes `closing` / `closing fini`, et « fini »
seulement après la sortie de `exec()` : la fermeture est mesurée jusqu'au bout. Avec `--new-instance` : 3 s.
L'`InvalidStateError` vue pendant `closing` vient de `jupyter_client/manager.py:111` (`self._ready.set_result` sur un
futur déjà résolu), appelé par `restarter.py:144 poll` → `_async_restart_kernel` : le redémarreur du noyau
(`qtconsole/manager.py:27`, minuterie Qt) tire PENDANT l'arrêt du noyau, voit le noyau mort et le relance.
Supposé : sur le bureau l'arrêt bloque le fil Qt et la minuterie ne tire pas ; dans la page, les attentes
coopératives de qtpy6 (`bloquant.py`) pompent les minuteries. Sans effet sur la fermeture (elle finit). Correctif
côté qtpy6 non posé : à mesurer (minuteries suspendues pendant une attente de fermeture ?).

## ETAT / reste
D1 en attente du professeur ; puis `_binding.py`, test dans `tests/test_doublures.py`, retrait du `delattr` de
`jalon7.py`, `web.md`, TODO Portage, commit.
