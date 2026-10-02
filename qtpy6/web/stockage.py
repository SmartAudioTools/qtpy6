"""Ce que le navigateur offre à l'application pour ses fichiers : ``localStorage`` (du texte, quelques Mio, propre à
l'origine de la page, qui survit au rechargement), un dossier rangé dans IndexedDB (``monter`` : des fichiers ordinaires,
binaires compris, sans autre limite que le quota de l'origine) et le téléchargement (le seul chemin vers le disque de
l'utilisateur). Chaque fonction importe ``js`` à l'appel : le module s'importe en natif, où rien ici n'a de sens."""

_synchro = {"etat": None, "attente": []}  # etat : None, "en cours" ou "encore" (une écriture est venue pendant la copie)


def lire(cle):
    """Le texte rangé sous ``cle``, ou None (le ``null`` de JavaScript arrive en ``jsnull`` sous Pyodide, pas en None)."""
    import js  # noqa: PLC0415

    texte = js.localStorage.getItem(cle)
    return texte if isinstance(texte, str) else None


def ecrire(cle, texte):
    """Range ``texte`` sous ``cle`` ; False si le navigateur refuse (stockage plein ou interdit : l'application continue)."""
    import js  # noqa: PLC0415

    try:
        js.localStorage.setItem(cle, texte)
    except Exception:  # noqa: BLE001 - QuotaExceededError, SecurityError : la raison n'y change rien
        return False
    return True


def effacer(cle):
    import js  # noqa: PLC0415

    js.localStorage.removeItem(cle)


def telecharger(nom, contenu, mime="application/octet-stream", lien=None):
    """Offre ``contenu`` (str ou bytes) au téléchargement sous le nom ``nom``. Sans ``lien``, le téléchargement part tout
    de suite ; avec un élément ``<a>`` de la page, celui-ci reçoit le fichier (href, download) et devient visible : c'est
    l'utilisateur qui clique, autant de fois qu'il veut, et un fichier suivant remplace le précédent."""
    import js  # noqa: PLC0415
    from pyodide.ffi import to_js  # noqa: PLC0415

    octets = contenu.encode("utf-8") if isinstance(contenu, str) else bytes(contenu)
    blob = js.Blob.new(to_js([to_js(octets)]), type=mime)
    a = js.document.createElement("a") if lien is None else lien
    if a.href and a.href.startswith("blob:"):
        js.URL.revokeObjectURL(a.href)
    a.href = js.URL.createObjectURL(blob)
    a.download = nom
    if lien is None:
        a.click()
    else:
        lien.hidden = False


def monter(dossier):
    """Range le dossier ``dossier`` dans IndexedDB (IDBFS d'Emscripten) et y remet ce qu'une visite précédente y avait
    laissé : l'application continue d'y lire et d'y écrire des fichiers ordinaires, et ``synchroniser()`` les recopie
    dans IndexedDB après ses écritures. Le dossier doit être vide ou absent (le montage cache ce qu'il contenait : les
    fichiers livrés avec l'application vont ailleurs, et l'application les recopie au premier lancement). Demande aussi
    au navigateur de ne pas effacer ce stockage quand la place manque (``navigator.storage.persist``, que Firefox
    soumet à l'utilisateur). Suspend jusqu'à la fin de la restauration : à appeler d'une entrée suspendable (le script
    lancé par ``lancer``, un slot) ; ``OSError`` si IndexedDB refuse (navigation privée de certains navigateurs)."""
    import os  # noqa: PLC0415

    import js  # noqa: PLC0415
    import pyodide_js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    from . import bloquant  # noqa: PLC0415

    fs = pyodide_js.FS
    os.makedirs(dossier, exist_ok=True)
    fs.mount(fs.filesystems.IDBFS, js.Object.new(), str(dossier))
    if getattr(js.navigator, "storage", None) and getattr(js.navigator.storage, "persist", None):
        js.navigator.storage.persist()
    erreur = bloquant._suspendre(lambda resoudre: fs.syncfs(True, create_once_callable(lambda e=None: resoudre(e))))
    if erreur:
        raise OSError(f"IndexedDB : {erreur}")


def synchroniser(attendre=False):
    """Recopie dans IndexedDB les dossiers montés par ``monter``, après une écriture. La copie part tout de suite et
    l'application continue ; une écriture qui arrive pendant une copie en relance une seule à sa fin. Avec ``attendre``,
    suspend jusqu'à ce que tout soit copié (entrée suspendable). Un refus d'IndexedDB est écrit au journal."""
    from . import bloquant  # noqa: PLC0415

    if _synchro["etat"]:
        _synchro["etat"] = "encore"
    else:
        _copier()
    if attendre:
        bloquant._suspendre(_synchro["attente"].append)


def _copier():
    import pyodide_js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    _synchro["etat"] = "en cours"
    pyodide_js.FS.syncfs(False, create_once_callable(_copie_finie))


def _copie_finie(erreur=None):
    if erreur:
        print(f"qtpy6.web.stockage : IndexedDB a refusé la copie ({erreur})")
    if _synchro["etat"] == "encore":
        _copier()
        return
    _synchro["etat"] = None
    attente, _synchro["attente"] = _synchro["attente"], []
    for reprendre in attente:
        reprendre()
