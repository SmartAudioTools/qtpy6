"""Un Web Worker Pyodide piloté depuis l'application Qt : ce qui tient lieu de sous-processus dans le navigateur, qui n'en
a pas. Qt-WASM tourne dans le fil de la page ; un calcul long, un programme de l'utilisateur, une boucle infinie y
gèleraient l'écran. Le worker les prend dans un fil à part, sans mémoire partagée : il ne se suspend pas et ne se
reprend pas, ``tuer()`` le termine (le seul « Arrêter » qu'un navigateur connaisse) et le suivant en relance un, Pyodide
compris (quelques secondes).

    Travailleur(indexURL, archives, module)   le worker : Pyodide (``indexURL``, le Pyodide ORDINAIRE, pas Pyodide-Qt),
                                              des archives zip dépaquetées dans le système de fichiers, un module importé
        appeler(fonction, *args, delai=None)  ``module.fonction(*args)`` dans le worker ; rend un numéro, la réponse
                                              revient par les signaux ``termine(numero, retour)``, ``erreur(numero, texte)``,
                                              ``expire(numero)`` (rien au bout de ``delai`` secondes) ; ce que la fonction
                                              imprime arrive au fil de l'eau par ``sortie(numero, texte)``
        tuer()                                termine le worker ; le prochain ``appeler`` en démarre un autre
    ProcessusWeb                              la surface de ``QProcess`` (start, write, readAllStandardOutput, kill,
                                              readyReadStandardOutput, finished) sur un Travailleur : chaque ligne écrite
                                              est passée à ``module.fonction(ligne)``, ce qu'il imprime est la sortie ;
                                              c'est lui que ``qtpy6.QtCore.QProcess`` désigne dans le navigateur
    configurer(indexURL, archives, module, fonction, cwd)   ce que ProcessusWeb, construit sans argument comme QProcess,
                                              utilise : à appeler une fois, par la page ou le pont de l'application

Les arguments et les retours sont convertis entre Python et JavaScript (dict, list, str, nombres, None) : une fonction
du worker reçoit des listes et des dicts ordinaires et rend de même. Elle peut être ``async``.

Le worker est lu dans ce paquet (``js/travailleur.js``) et lancé depuis une URL ``blob:`` : ``indexURL`` et les URL des
archives sont rendues absolues ici, un worker né d'un blob n'ayant pas d'adresse à laquelle les rapporter."""

import importlib.resources
import itertools

from qtpy6.QtCore import QObject, QTimer, Signal  # QtCore en cours de chargement : il importe ce module pour QProcess

REGLAGES = {}  # configurer() : indexURL, archives, module, fonction, cwd
_URL_WORKER = None


def configurer(indexURL, archives, module, fonction="ligne", cwd="/home/pyodide"):
    """Ce que ``ProcessusWeb()`` utilise : le Pyodide du worker (``indexURL``), ``archives`` = ``[(url_du_zip, dossier)]``
    dépaquetées dans le worker, ``module`` importé après (avec ``cwd`` pour dossier courant et chaque dossier d'archive dans
    ``sys.path``), ``fonction`` celle qui reçoit chaque ligne écrite."""
    REGLAGES.update(indexURL=indexURL, archives=list(archives), module=module, fonction=fonction, cwd=cwd)


def _url_worker():
    global _URL_WORKER
    if _URL_WORKER is None:
        import js  # noqa: PLC0415

        source = importlib.resources.files(__package__).joinpath("js/travailleur.js").read_text(encoding="utf-8")
        _URL_WORKER = js.URL.createObjectURL(js.Blob.new([source], type="text/javascript"))
    return _URL_WORKER


class Travailleur(QObject):
    pret = Signal()
    sortie = Signal(int, str)
    termine = Signal(int, object)
    erreur = Signal(int, str)
    expire = Signal(int)

    def __init__(self, indexURL, archives, module, cwd="/home/pyodide", parent=None):
        super().__init__(parent)
        self.indexURL, self.archives, self.module, self.cwd = indexURL, list(archives), module, cwd
        self.worker, self.numeros, self.en_cours = None, itertools.count(1), {}  # en_cours : numéro -> minuteur ou None

    @property
    def actif(self):
        return self.worker is not None

    def demarrer(self):
        """Le worker : Pyodide, les archives, le module. Le signal ``pret`` quand il peut répondre ; les appels faits avant
        attendent dans sa file."""
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy  # noqa: PLC0415

        absolu = lambda url: js.URL.new(url, js.location.href).href  # noqa: E731
        self.worker = js.Worker.new(_url_worker(), type="module")
        self._recepteur = create_proxy(self._recevoir)  # gardé : un proxy sans référence Python est détruit
        self.worker.onmessage = self._recepteur
        self._poster({"init": {"indexURL": absolu(self.indexURL), "module": self.module, "cwd": self.cwd,
                               "archives": [{"url": absolu(url), "dossier": dossier} for url, dossier in self.archives]}})

    def appeler(self, fonction, *args, delai=None):
        """``module.fonction(*args)`` dans le worker (démarré au besoin) ; rend le numéro de l'appel, sous lequel les signaux
        répondent. ``delai`` en secondes : passé, ``expire(numero)`` est émis et la réponse qui arriverait ensuite est ignorée."""
        if self.worker is None:
            self.demarrer()
        numero = next(self.numeros)
        self.en_cours[numero] = None
        if delai:
            minuteur = self.en_cours[numero] = QTimer(self, singleShot=True, interval=int(delai * 1000))
            minuteur.timeout.connect(lambda: self._expirer(numero))
            minuteur.start()
        self._poster({"appel": {"id": numero, "fonction": fonction, "args": list(args)}})
        return numero

    def tuer(self):
        """Termine le worker (et ce qu'il exécutait) ; les appels en cours n'auront pas de réponse."""
        if self.worker is not None:
            self.worker.terminate()
            self.worker = None
            for numero in list(self.en_cours):
                self._clore(numero)

    def _poster(self, message):
        import js  # noqa: PLC0415
        from pyodide.ffi import to_js  # noqa: PLC0415

        self.worker.postMessage(to_js(message, dict_converter=js.Object.fromEntries))

    def _clore(self, numero):
        """L'appel est fini, quelle qu'en soit l'issue ; False s'il ne l'attendait plus (expiré, ou worker tué)."""
        if numero not in self.en_cours:
            return False
        minuteur = self.en_cours.pop(numero)
        if minuteur is not None:
            minuteur.stop()
        return True

    def _expirer(self, numero):
        if self._clore(numero):
            self.expire.emit(numero)

    def _recevoir(self, evenement):
        m = evenement.data.to_py()
        numero = m.get("id")
        if m.get("pret"):
            self.pret.emit()
        elif "sortie" in m:
            self.sortie.emit(numero, m["sortie"])
        elif numero is None:  # le worker lui-même est tombé (Pyodide injoignable, archive introuvable) : tout appel échoue
            en_cours = list(self.en_cours) or [0]
            self.tuer()
            for n in en_cours:
                self.erreur.emit(n, m["erreur"])
        elif self._clore(numero):
            if "retour" in m:
                self.termine.emit(numero, m["retour"])
            else:
                self.erreur.emit(numero, m["erreur"])


class ProcessusWeb(QObject):
    """La surface de ``QProcess`` qu'un code écrit pour un sous-processus utilise, sur un ``Travailleur`` : ``write`` passe
    chaque ligne à ``module.fonction(ligne)`` (les ``REGLAGES`` de ``configurer``), ce que le worker imprime se lit par
    ``readAllStandardOutput`` après ``readyReadStandardOutput``, ``kill`` termine le worker et émet ``finished``. Un
    ``start`` après ``kill`` en relance un neuf, comme un vrai processus."""

    readyReadStandardOutput = Signal()
    finished = Signal(int)

    class ProcessChannelMode:
        MergedChannels = None  # le worker n'a qu'un canal : rien à fusionner

    def __init__(self, parent=None):
        super().__init__(parent)
        self.travailleur, self.tampon = None, b""

    def setProcessChannelMode(self, *_):
        pass

    def start(self, *_):
        r = REGLAGES
        self.travailleur = Travailleur(r["indexURL"], r["archives"], r["module"], r["cwd"], parent=self)
        self.travailleur.sortie.connect(lambda _, texte: self._arrive(texte.encode("utf-8")))
        self.travailleur.erreur.connect(self._erreur)
        self.travailleur.demarrer()

    def write(self, octets):
        for ligne in bytes(octets).decode("utf-8").splitlines():
            if ligne:
                self.travailleur.appeler(REGLAGES["fonction"], ligne)

    def readAllStandardOutput(self):
        octets, self.tampon = self.tampon, b""
        return octets

    def kill(self):
        if self.travailleur is not None:
            self.travailleur.tuer()
            self.travailleur = None
            QTimer.singleShot(0, lambda: self.finished.emit(0))  # comme QProcess : ``finished`` après le retour de ``kill``

    def _arrive(self, octets):
        self.tampon += octets
        self.readyReadStandardOutput.emit()

    def _erreur(self, _, texte):
        self._arrive(f"\n■ {texte}\n".encode("utf-8"))
        self.kill()  # le worker ne servira plus : le prochain ``start`` en relance un

