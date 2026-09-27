"""Ce que le navigateur offre à l'application pour ses fichiers : ``localStorage`` (du texte, quelques Mio, propre à
l'origine de la page, qui survit au rechargement) et le téléchargement (le seul chemin vers le disque de l'utilisateur).
Chaque fonction importe ``js`` à l'appel : le module s'importe en natif, où rien ici n'a de sens."""


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
