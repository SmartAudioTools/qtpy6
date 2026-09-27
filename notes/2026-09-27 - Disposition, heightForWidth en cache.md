# `Disposition` : `heightForWidth` en cache (27/09/2026)

## Le symptôme

L'utilisateur, en ouvrant dans le lecteur QCM de SmartTeacher la révision NSI Terminale (85 questions, chacune
rangée par des `Rangee`) : *« le redimensionnement horizontal et le scrolling … laguent complètement »*.

## La cause, mesurée

Profil `cProfile` hors écran (`QT_QPA_PLATFORM=offscreen`) sur une copie du `.qcm`, 20 pas de redimensionnement :
`Disposition._disposer` arrivait en tête. `heightForWidth` le rappelait à chaque demande de Qt, et Qt la demande
**des centaines de fois par redimensionnement** pour la même largeur (chaque ancêtre qui négocie sa taille la
redemande à ses enfants).

## Le correctif

`heightForWidth` garde sa réponse par largeur dans `self.hauteurs`, vidé dans `invalidate()`. C'est le point où Qt
signale lui-même que la disposition a changé : item ajouté, montré, caché, ou dont le `sizeHint` bouge. Aucun
appel explicite à ajouter du côté de l'application.

Piège rencontré : Qt appelle `invalidate()` dès `setContentsMargins`, dans `__init__`. Le dictionnaire doit donc
être créé **avant**, sinon « Error calling Python override of QLayout::invalidate(): 'Rangee' object has no
attribute 'hauteurs' ».

## Niveau de preuve

- Mesuré hors écran, 20 redimensionnements : 4 507 ms → 1 665 ms (225 → 83 ms par pas). Ce correctif et celui
  des voiles de SmartTeacher (ci-dessous) comptent ensemble dans ces chiffres. Le reste est la mise en page de
  Qt elle-même, plus `_disposer` pour les largeurs nouvelles : ces échecs de cache sont inévitables.
- `tests/test_web.py::test_rangee_recalcule_apres_changement` : la hauteur change après un `set_text` qui élargit
  un bouton, puis après avoir caché trois boutons. Le test **échoue** avec un cache jamais vidé (mutation vérifiée),
  et passe avec le correctif. Suite complète : 19 tests passent.
- Pas encore mesuré sur un vrai écran, ni dans le navigateur.

## Côté SmartTeacher (pour mémoire, commité là-bas)

Le défilement laguait pour une autre raison : chaque `Question` du lecteur recalculait son voile à chaque `Move`
du contenu défilant (85 recalculs par cran de molette). `modele.py` ignore désormais ce `Move`, puisque le voile
défile avec le contenu. Les autres événements sont regroupés en un seul calcul au tour de boucle suivant.
Mesure : 40 crans de molette, 616 → 175 ms. Sans l'exclusion du `Move`, le regroupement seul reste à 621 ms :
l'exclusion n'est pas redondante.
