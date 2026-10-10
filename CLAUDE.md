# qtpy6

## Le code de l'application ne sait pas où il tourne : c'est qtpy6 qui prévoit, par des doublures

Règle générale posée par l'utilisateur le 10/10/2026, pour tout ce qu'il codera avec qtpy6 (SmartTeacher, SmartPythonEditor,
les suivants) : « j'aimerais avoir le même code pour les versions natives et web […]. C'est à qtpy6 de rendre le code
agnostique en créant des doublures » ; « c'est une règle générale à tout ce que je vais coder avec qtpy6 : je veux que ce
soit qtpy6 qui prévoit ce qu'il faut dans le backend, plutôt que de forcer l'utilisateur de qtpy6 à adapter son code ».

⚠ Déclencheur, c'est un GESTE : au moment d'écrire, dans le code d'une APPLICATION qtpy6, `if sys.platform == "emscripten"`,
un import de `qtpy6.web`, de `js` ou de `pyodide`, ou un appel qui n'existe que d'un côté (`travailleur.configurer`,
`prechauffer`, `stockage.*`, un `waitForFinished` absent du web…) : s'arrêter, c'est un MANQUE DE QTPY6, pas une
adaptation à faire dans l'application. Le combler ici :
  - **une doublure sous le nom de l'API Qt que le natif emploie** (`QProcess`, `QFileDialog`, `QPdfView`… : `web.md`, « Ce que
    fait qtpy6.web ») — en natif la vraie classe, ou une méthode sans effet (un processus démarre en 60 ms : préchauffer
    ne fait rien) ; en web, ce qu'il faut. Le code appelant écrit la même ligne des deux côtés ;
  - **ce qui ne peut pas se cacher** (la liste des roues à installer dans un worker, le dossier à persister) devient un
    RÉGLAGE donné une fois — au `construire`, dans la page, ou par une fonction de configuration de qtpy6 sans effet en
    natif — jamais une branche dans le code appelant ;
  - **la liste « Rendre une application qtpy6 compatible » de `web.md`** est ce qui reste différent du bureau, mesuré : une
    liste À RÉDUIRE à chaque occasion, pas une consigne d'adaptation pour l'application.

L'alternative écartée : la branche `if WEB` dans l'application. Elle coûte deux codes à tenir, et chaque application
refait le même contournement. *Mesure, jalon 4 du portage de SmartPythonEditor (10/10/2026) : quatre branches propres au
web recensées dans un seul essai (réglages du worker, worker de réserve, `waitForFinished`, dossier de l'élève),
`notes/2026-10-09 - Portage de SmartPythonEditor dans le navigateur, faisabilité.md`, « Même code natif et web ».*

Un essai (`essais/`) peut porter l'instrumentation du navigateur (état de la page pour la sonde, tas, captures) : ce n'est
pas le code de l'application. Mais tout ce qui y reste propre au web HORS instrumentation est la liste de ce que qtpy6
doit encore doubler, et se note comme telle dans la note de l'essai, avec le coût de la doublure.

Vérification avant de rendre compte d'un port ou d'un widget : `grep -n "emscripten\|qtpy6\.web\|import js\b\|pyodide"` sur
le code de l'application rend zéro ligne hors instrumentation.
