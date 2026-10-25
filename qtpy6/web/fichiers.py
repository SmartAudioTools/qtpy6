"""Les fichiers du disque de l'utilisateur, relus à chaque ouverture.

Un fichier choisi (``QFileDialog.getOpenFileName``) ou déposé (glisser-déposer depuis l'explorateur) n'est, pour
Pyodide, qu'une copie faite à ce moment-là. Une application native qui le rouvre plus tard lit son contenu du moment :
un élève qui modifie son programme dans son éditeur, puis le soumet de nouveau, est corrigé sur sa dernière version.
Ici, chaque chemin copié garde sa source dans la page, et ``open`` en lecture la relit d'abord :
  - Chrome : un ``FileSystemFileHandle`` (``showOpenFilePicker``, ``DataTransferItem.getAsFileSystemHandle``), dont
    ``getFile()`` lit le disque de nouveau. Un ``File`` d'un ``<input type=file>`` ne se relit pas après une
    modification (``NotReadableError``, Chrome 140, mesuré le 25/10/2026).
  - Firefox : le ``File`` gardé relit le disque (Firefox 158, même jour) ; pas de ``showOpenFilePicker``.
Une source illisible (fichier modifié sous Chrome sans poignée, déplacé, supprimé) : la copie est retirée et ``open``
lève ``FileNotFoundError``, comme pour un fichier disparu en natif ; l'application le redemande.

La relecture suspend Python (JSPI) : hors entrée suspendable, ``open`` lit la copie telle quelle."""

import builtins
import errno
import io
import os

_sources = {}  # chemin dans Pyodide -> source dans la page (FileSystemFileHandle, sa promesse, ou File)
_open = []  # l'open d'origine
_lire_source = []  # la fonction JS qui rend les octets d'une source (ArrayBuffer), ou une chaîne si elle est illisible

DOSSIER_DEPOSES = "/qt/tmp"  # où Qt-WASM écrit un fichier déposé de l'extérieur (Qt 6.10, l'URL du mimeData)


def retenir(chemin, source):
    """``chemin`` (déjà écrit) se relira depuis ``source`` à chaque ouverture en lecture."""
    _sources[os.path.abspath(chemin)] = source


def oublier(chemin):
    _sources.pop(os.path.abspath(chemin), None)


def _lecture_seule(mode):
    return "r" in mode and not any(c in mode for c in "wax+")


def _relire(chemin, source):
    """Réécrit la copie ``chemin`` depuis sa source ; False si la source n'est plus lisible."""
    from .bloquant import _peut_suspendre, _suspendre  # noqa: PLC0415

    if not _peut_suspendre():
        return True
    import js  # noqa: PLC0415

    if not _lire_source:
        _lire_source.append(js.Function.new(
            "s", "return Promise.resolve(s).then(s => s.getFile ? s.getFile() : s).then(f => f.arrayBuffer())"
                 ".catch(e => String(e))"))
    contenu = _suspendre(lambda resoudre: _lire_source[0](source).then(resoudre))
    if isinstance(contenu, str):  # null ne revient pas en None (jsnull) : une chaîne, que Python reconnaît
        return False
    with _open[0](chemin, "wb") as sortie:
        sortie.write(js.Uint8Array.new(contenu).to_bytes())
    return True


def _ouvrir(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, os.PathLike)) and _sources:
        chemin = os.path.abspath(os.fspath(file))
        source = _sources.get(chemin)
        if source is not None:
            if not _lecture_seule(mode):
                del _sources[chemin]  # l'application écrit sa propre version : la copie fait foi
            elif not _relire(chemin, source):
                del _sources[chemin]
                if os.path.exists(chemin):
                    os.remove(chemin)
                raise FileNotFoundError(errno.ENOENT, "fichier à redonner (le navigateur ne peut plus le relire)",
                                        chemin)
    return _open[0](file, mode, *args, **kwargs)


def _au_depot(evenement):
    """``drop`` sur le document, en capture (avant Qt) : la source de chaque fichier déposé, retenue sous le chemin où
    Qt-WASM va l'écrire. Les deux appels se font pendant l'événement, après quoi ``dataTransfer`` est vidé."""
    transfert = evenement.dataTransfer
    if transfert is None:
        return
    for item in transfert.items:
        if item.kind != "file":
            continue
        f = item.getAsFile()
        if f is None:
            continue
        poignee = getattr(item, "getAsFileSystemHandle", None)  # Chrome ; une promesse, résolue plus tard
        retenir(os.path.join(DOSSIER_DEPOSES, f.name), poignee() if poignee is not None else f)


def installer():
    """``open`` (``builtins`` et ``io``, donc ``pathlib``) relit les sources retenues ; le dépôt de fichiers sur la page
    retient les leurs. Une seule fois."""
    if _open:
        return
    _open.append(builtins.open)
    builtins.open = io.open = _ouvrir
    try:
        import js  # noqa: PLC0415
        from pyodide.ffi import create_proxy  # noqa: PLC0415
    except ImportError:  # emscripten simulé par les tests, sans page
        return

    js.document.addEventListener("drop", create_proxy(_au_depot), True)
