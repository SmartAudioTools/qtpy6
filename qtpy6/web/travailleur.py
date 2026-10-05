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
    ProcessusWeb                              ``QProcess`` dans le navigateur (``qtpy6.QtCore.QProcess`` le désigne) :
                                              ``start(sys.executable, ["-u", "script.py", …])`` lance le script en
                                              ``__main__`` dans un worker neuf, ``write`` est son stdin (JSPI)
    configurer(indexURL, roues, filtre)       le Pyodide du worker, s'il ne vient pas de ``versions.json`` ; ``roues`` :
                                              des URL de roues (.whl) chargées dans le worker d'un ``ProcessusWeb`` au
                                              premier ``import`` de leur module — pour un module absent de la
                                              distribution (le sqlite3 de Pyodide-Qt) ; un programme qui ne l'importe
                                              pas ne paie rien, ni octets ni délai ; ``filtre`` : quels fichiers copier
                                              dans le worker (voir ``configurer``)
    prechauffer()                             monte en réserve UN worker dont le Pyodide charge dès maintenant : le
                                              prochain ``ProcessusWeb.start()`` le consomme et épargne ``loadPyodide``
                                              (plusieurs secondes, l'essentiel du premier lancement)

Les arguments et les retours sont convertis entre Python et JavaScript (dict, list, str, nombres, None) : une fonction
du worker reçoit des listes et des dicts ordinaires et rend de même. Elle peut être ``async``.

Le worker est lu dans ce paquet (``js/travailleur.js``) et lancé depuis une URL ``blob:`` : ``indexURL`` et les URL des
archives sont rendues absolues ici, un worker né d'un blob n'ayant pas d'adresse à laquelle les rapporter."""

import importlib.resources
import io
import itertools
import json
import os
import tempfile
import zipfile

from qtpy6.QtCore import QObject, QTimer, Signal  # QtCore en cours de chargement : il importe ce module pour QProcess

REGLAGES = {}  # configurer() : indexURL, roues, filtre
_URL_WORKER = None
_RESERVE = None  # prechauffer() : (worker, indexURL) — un worker neuf dont le Pyodide charge, consommé par le prochain start()


def configurer(indexURL, roues=(), filtre=None):
    """Ce que ``ProcessusWeb()`` utilise : le Pyodide du worker (``indexURL`` ; sans appel, celui de ``versions.json``),
    des URL de roues (.whl) que le worker charge au premier ``import`` de leur module — le nom de distribution du
    fichier (``sqlite3-1.0.0-….whl`` → ``sqlite3``) ; paresseux : un script qui n'importe pas le module ne télécharge
    rien, le préchauffage n'en charge aucune. ``filtre`` : quels FICHIERS copier dans le worker —
    ``filtre(chemin absolu) -> bool``, appelé pour chaque fichier des dossiers embarqués (script, cwd, temporaire) ;
    ``None`` les copie tous. Les dossiers eux-mêmes sont toujours créés : l'application écarte ainsi ce que l'enfant
    n'importe jamais (polices, données du parent) au lieu de le zipper à chaque ``start``."""
    REGLAGES.update(indexURL=indexURL, roues=tuple(roues), filtre=filtre)


def prechauffer():
    """Monte en réserve UN worker neuf dont le Pyodide (``configurer``, sinon ``versions.json``) charge dès maintenant :
    le prochain ``ProcessusWeb.start()`` du même Pyodide le consomme au lieu de tout payer (``loadPyodide``, plusieurs
    secondes). À appeler aux moments calmes — le programme affiché, le précédent arrêté. Idempotent tant que la réserve
    n'est pas consommée ; un worker de réserve n'a JAMAIS exécuté de code, et un worker consommé n'y revient jamais.
    Si son chargement a échoué (Pyodide injoignable), l'échec ressort en erreur du ``start`` qui le consomme, et le
    ``start`` suivant repart à froid, comme sans réserve."""
    global _RESERVE
    import js  # noqa: PLC0415

    indexURL = _index_url()
    if _RESERVE is not None and _RESERVE[1] == indexURL:
        return
    if _RESERVE is not None:  # l'indexURL a changé (configurer) : ce worker ne servira plus
        _RESERVE[0].terminate()
    worker = js.Worker.new(_url_worker(), type="module")
    worker.postMessage(_objet({"prechauffer": {"indexURL": indexURL}}))
    _RESERVE = (worker, indexURL)


def _index_url():
    import js  # noqa: PLC0415

    return js.URL.new(REGLAGES.get("indexURL") or _pyodide(), js.location.href).href


def _roues():
    """``{module: url absolue}`` des roues de ``configurer`` — le module est le nom de distribution du fichier."""
    import js  # noqa: PLC0415

    return {url.rsplit("/", 1)[-1].partition("-")[0]: js.URL.new(url, js.location.href).href
            for url in REGLAGES.get("roues") or ()}


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
            minuteur.setProperty("numero", numero)
            minuteur.timeout.connect(self._expirer)
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

    def _expirer(self):
        numero = self.sender().property("numero")
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
    """La surface de ``QProcess`` dans le navigateur : ``start(sys.executable, ["-u", "enfant.py", ...])`` lance vraiment
    ``enfant.py`` dans un Web Worker, sous le Pyodide ordinaire (``versions.json``), avec une copie du dossier du script
    (au même chemin : ses imports et son ``__file__`` sont ceux du bureau), de son dossier de travail et du dossier
    temporaire (``tempfile`` : là qu'un parent dépose ce qu'il passe à l'enfant), et ``sys.argv``. Le worker n'a que ces
    copies : ce que l'enfant écrit ne revient pas. Ce que ``write`` envoie est son stdin, qu'il lit comme sur le bureau
    (``input()``, ``sys.stdin.readline()`` attendent : JSPI, ``run_sync``) ; ``closeWriteChannel`` lui donne la fin de
    fichier ; ce qu'il imprime se lit par ``readAllStandardOutput`` et ``readAllStandardError`` après les signaux
    ``readyRead…``, ou tout par la sortie standard avec ``MergedChannels`` ; ``finished(code)`` quand il se termine, ou
    après ``kill``. Un ``start`` après ``kill`` en relance un neuf, comme un vrai processus."""

    readyReadStandardOutput = Signal()
    readyReadStandardError = Signal()
    finished = Signal(int)

    class ProcessChannelMode:  # les valeurs de Qt
        SeparateChannels, MergedChannels = 0, 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker, self.dossier_travail = None, None
        self.tampons, self.fusion = {"sortie": b"", "sortie_erreur": b""}, False

    def setProcessChannelMode(self, mode):
        self.fusion = mode == self.ProcessChannelMode.MergedChannels

    def setWorkingDirectory(self, dossier):
        self.dossier_travail = dossier

    def start(self, programme="", arguments=(), *_):
        global _RESERVE
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy, to_js  # noqa: PLC0415

        cible, argv = _commande(arguments)
        cwd = os.path.abspath(self.dossier_travail or os.getcwd())
        dossier = os.path.dirname(os.path.abspath(cible)) if argv[0] != "-m" else cwd
        indexURL = _index_url()
        if _RESERVE is not None and _RESERVE[1] == indexURL:  # le worker préchauffé : son Pyodide charge depuis prechauffer()
            self.worker, _RESERVE = _RESERVE[0], None
        else:
            self.worker = js.Worker.new(_url_worker(), type="module")
        self._recepteur = create_proxy(self._recevoir)
        self.worker.onmessage = self._recepteur
        zip_ = to_js(_zipper([dossier, cwd, tempfile.gettempdir()], REGLAGES.get("filtre")))
        self.worker.postMessage(_objet({"lancer": {
            "indexURL": indexURL, "zip": zip_, "roues": _roues(),
            "dossier": dossier, "argv": argv, "cwd": cwd}}), [zip_.buffer])

    def write(self, octets):
        if self.worker is not None:
            self.worker.postMessage(_objet({"entree": bytes(octets).decode("utf-8")}))
        return len(octets)

    def closeWriteChannel(self):
        if self.worker is not None:
            self.worker.postMessage(_objet({"entree": None}))

    def readAllStandardOutput(self):
        return self._vider("sortie")

    def readAllStandardError(self):
        return self._vider("sortie_erreur")

    def _vider(self, canal):
        octets, self.tampons[canal] = self.tampons[canal], b""
        return octets

    def kill(self):
        if self.worker is None:
            return
        self.worker.terminate()
        self.worker = None
        QTimer.singleShot(0, lambda: self.finished.emit(0))  # comme QProcess : ``finished`` après le retour de ``kill``

    def _recevoir(self, evenement):
        m = evenement.data.to_py()
        for canal in ("sortie", "sortie_erreur"):
            if m.get(canal):  # le décodeur au fil de l'eau rend "" sur un caractère coupé
                self._arrive(canal, m[canal])
        if "fin" in m:
            self.worker.terminate()
            self.worker = None
            self.finished.emit(m["fin"])
        elif "erreur" in m:  # Pyodide injoignable, JSPI absent : le processus n'a pas pu naître
            self._erreur(0, m["erreur"])

    def _arrive(self, canal, texte):
        if self.fusion:
            canal = "sortie"
        self.tampons[canal] += texte.encode("utf-8")
        (self.readyReadStandardOutput if canal == "sortie" else self.readyReadStandardError).emit()

    def _erreur(self, _, texte):
        self._arrive("sortie_erreur", f"\n■ {texte}\n")
        self.kill()  # le worker ne servira plus : le prochain ``start`` en relance un


def _commande(arguments):
    """``(chemin du script ou nom du module, argv)`` d'une ligne de commande Python : les options d'une lettre sans
    argument (``-u``, ``-B``…) sont sans objet dans le worker ; ``-m module`` donne ``argv[0] == "-m"``."""
    args = list(arguments)
    while args and args[0].startswith("-") and args[0] != "-m":
        if args[0] in ("-c", "-X", "-W"):
            raise ValueError(f"ProcessusWeb : l'option {args[0]} n'est pas prise en charge")
        args.pop(0)
    if not args:
        raise ValueError("ProcessusWeb : ni script ni -m module à lancer")
    if args[0] == "-m":
        return args[1], args
    return args[0], [os.path.abspath(args[0]), *args[1:]]


def _zipper(dossiers, filtre=None):
    """Les ``dossiers``, zippés sans compression avec leurs chemins depuis la racine (le worker les dépaquette au même
    endroit) ; un fichier de deux dossiers imbriqués n'y est qu'une fois. Les dossiers aussi ont leur entrée : un dossier
    vide que le parent a créé pour l'enfant (``tempfile.mkdtemp``) doit exister de l'autre côté. ``filtre`` ne s'applique
    qu'aux fichiers : il écarte ceux pour lesquels il rend faux."""
    tampon, vus = io.BytesIO(), set()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as z:
        for dossier in dossiers:
            for racine, sous, fichiers in os.walk(dossier):
                sous[:] = [d for d in sous if d != "__pycache__"]
                retenus = [f for f in fichiers if filtre is None or filtre(os.path.join(racine, f))]
                for chemin in [racine, *(os.path.join(racine, f) for f in retenus)]:
                    if chemin not in vus:
                        vus.add(chemin)
                        z.write(chemin, os.path.relpath(chemin, "/"))
    return tampon.getvalue()


def _pyodide():
    return json.loads(importlib.resources.files(__package__).joinpath("versions.json").read_text())["pyodide"]["url"]


def _objet(message):
    import js  # noqa: PLC0415
    from pyodide.ffi import to_js  # noqa: PLC0415

    return to_js(message, dict_converter=js.Object.fromEntries)
