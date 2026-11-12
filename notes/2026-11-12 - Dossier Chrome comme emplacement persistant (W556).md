# Dossier autorisé de Chrome comme troisième emplacement de `persistant` (W556, 12/11/2026)

**Demande.** Item 13 du TODO Portage, tiret « dossier autorisé de Chrome comme troisième emplacement de `persistant`, bouton
« Réautoriser » » ; ordre du professeur (12/11 14:04) : « mets des workers sur tous les items qui peuvent être traités
indépendamment ». Source : faisabilité du 09/10, jalon 5 bis (l. 381-440) : mesuré dans son Chrome 153, la permission est
mémorisée au rechargement mais PAS après fermeture de Chrome → « un bouton « Réautoriser le dossier » par séance ».

## FAIT

- `application(persistant=chemin, disque=True)` (`qtpy6/web/__init__.py`) → `stockage.monter(chemin, disque)`. En natif :
  sans effet (dossier du disque, `os.makedirs`). Sous Firefox (pas de `showDirectoryPicker`) : IDBFS, sans rien demander.
- `stockage._monter_sur_disque` (Chrome, Edge) : boutons HTML par-dessus le canevas (le sélecteur et `requestPermission`
  exigent un geste réel dans la page) :
  - premier lancement : « Où ranger vos fichiers ? » → « Choisir un dossier sur le disque » / « Garder dans le navigateur » ;
  - poignée retrouvée, permission `granted` (rechargement) : aucun bouton ;
  - poignée retrouvée, `prompt` (Chrome relancé) : « Réautoriser le dossier » / « Choisir un autre dossier » / « Garder dans
    le navigateur ».
  Poignée gardée dans IndexedDB (base `qtpy6`, magasin `dossiers`, clé = point de montage). « Garder dans le navigateur »
  est mémorisé (`localStorage`, clé `qtpy6.disque:<chemin>`) : la question ne revient pas. Refus, Échap, montage en échec :
  IDBFS pour la séance.
- Recopie sur le disque : `NATIVEFS_ASYNC` n'a pas l'`autoPersist` d'IDBFS (lu dans `pyodide.mjs`) ; les fonctions `close`
  (fichier ouvert en écriture), `unlink`, `rename`, `mkdir`, `rmdir`, `symlink` de `FS` sont enveloppées en JavaScript : une
  écriture sous un dossier du disque relance une minuterie de 200 ms, à l'échéance `synchroniser()` (existant). Cent
  fichiers écrits → une recopie, pas cent (condition du Superviseur). La liste des dossiers est un tableau JS : aucun
  appel de Python au milieu d'un appel système.

## POURQUOI, alternatives écartées

- **Opt-in `disque=True`** (accordé par le Superviseur, 14:31) plutôt qu'automatique sur tout Chrome : l'automatique
  changerait toutes les applications qtpy6 (une question au lancement que personne n'a demandée) ; `disque=True` est la
  forme « réglage donné une fois » de `CLAUDE.md`, sans effet en natif, aucune branche dans l'application.
- **`synchroniser()` réutilisé** (Existant : `stockage.synchroniser`, sérialise `FS.syncfs(false)`) plutôt que le `syncfs`
  rendu par `pyodide.mountNativeFS` : lu dans `pyodide.asm.js`, ce dernier est `Module.FS.syncfs(false, …)` lui-même
  (`syncLocalToRemote` → `Ir(t,!1)`), qui parcourt tous les montages et appelle `NATIVEFS_ASYNC.syncfs`. Même appel ;
  `synchroniser()` y ajoute la sérialisation. Mesure demandée par le Superviseur : sous Chrome, par le professeur (ci-dessous).
- **Recopie différée de 200 ms** plutôt qu'à chaque fermeture (30-70 ms chacune au jalon 5 bis : cent fichiers = 5 s).
  La « recopie immédiate à la fin du programme de l'élève » demandée par le Superviseur est sans objet : le programme de
  l'élève tourne dans un Worker qui reçoit `cwd` zippé et n'écrit pas dans les fichiers du parent (`travailleur.py:274`,
  `:296`) ; ce sont les enregistrements de l'éditeur, dans le fil principal, que la minuterie couvre.
- **Boutons HTML** plutôt qu'un QMessageBox : le montage a lieu dans `application()`, avant toute fenêtre ; un clic sur le
  canevas de Qt n'arrive à Python qu'après un tour de boucle (geste peut-être expiré).

## Limites connues

- Passer d'IDBFS à un dossier du disque (ou l'inverse) ne déplace pas les fichiers déjà rangés : l'autre emplacement garde
  les siens. Un élève qui a choisi « Garder dans le navigateur » ne se voit plus proposer le disque (effacer la clé
  `localStorage`) : pas de bouton pour revenir, à décider si l'usage le demande.
- Fermer l'onglet dans les 200 ms qui suivent un enregistrement perd cette recopie (l'écouteur de fermeture était déjà
  écarté pour IDBFS, faisabilité l. 499).

## VÉRIFIÉ

- Firefox 158, sonde (`/DATA/Python/qtpy6_essais/w556/page.py`, site à moi `w556/site`) : **mesuré** — montage IDBFS, 0
  bouton dans la page, `showDirectoryPicker` absent, 101 écritures en 21 ms, `essai_fini`.
- Blink du bac (`sonde --chromium`, QtWebEngine 6.11 / Chrome 140) : **mesuré** — la boîte « Où ranger vos fichiers ? » et
  ses deux boutons s'affichent (capture `w556/chromium.png`), la page attend le clic (sans geste possible dans la sonde).
- Natif : `tests/test_doublures.py::test_disque_sans_effet_en_natif` (échoue sans le correctif : `disque` inconnu).
- Chromium du professeur (12/11, 15:10-15:18, `w556/essai_chrome.sh`, profil neuf, deux passages séparés par la
  fermeture complète de Chromium ; journal `w556/dossier_chrome/journal_w556.txt`) : **mesuré**.
  - Passage 1, « Choisir un dossier sur le disque » : montage `NATIVEFS_ASYNC`, 0 fichier retrouvé ; 101 écritures en
    146 ms ; **une seule recopie** pour les 101 (en plus de la lecture initiale, 37 ms) ; les 101 fichiers présents sur
    le disque après coup (`ls`), donc `synchroniser()` → `FS.syncfs(false)` recopie bien le montage natif (condition (a)
    du Superviseur) ; le journal écrit dans un slot après coup est arrivé aussi (minuterie de 200 ms).
  - Passage 2, Chromium relancé : « Réautoriser le dossier » d'un clic, 101 fichiers retrouvés, 8,8 s clic compris
    (lecture initiale 1,2 s pour 102 fichiers, contre 37 ms dossier vide).
  - Premier essai (15:03-15:08, autre profil) : le professeur a cliqué « Garder dans le navigateur » ; au second passage
    aucune question : la mémorisation `localStorage` fonctionne.
  Non mesuré : Edge, Windows, un dossier Dropbox, deux onglets.
