"""Jouer un son embarqué (des octets en mémoire, pas un fichier de l'utilisateur) : ``QSoundEffect`` en natif — qui ne
lit qu'un fichier, d'où le passage par un temporaire — l'élément ``<audio>`` de la page dans le navigateur, en URI de
données (aucun fichier n'y existe). ``qtpy6.QtMultimedia`` est le module de la liaison choisie, pris tel quel par le
mécanisme générique de ``qtpy6._binding`` : rien à écrire pour l'avoir."""

import functools

_GARDES = {}  # nom -> QSoundEffect ou <audio>, gardé en vie tant qu'il peut rejouer


def jouer(nom, octets, extension, fini=None):
    """Joue ``octets`` (le contenu d'un fichier ``nom.extension``, ``nom`` unique par son). ``fini()``, si donné, est
    appelé une fois la lecture terminée."""
    from . import navigateur  # noqa: PLC0415

    (_jouer_navigateur if navigateur() else _jouer_natif)(nom, octets, extension, fini)


def _jouer_natif(nom, octets, extension, fini):
    import tempfile
    from pathlib import Path

    from qtpy6.QtCore import QUrl

    chemin = Path(tempfile.gettempdir()) / f"qtpy6-audio-{nom}.{extension}"
    if not chemin.exists() or chemin.stat().st_size != len(octets):
        chemin.write_bytes(bytes(octets))
    effet = _GARDES[nom] = _effet()(fini)
    effet.setSource(QUrl.fromLocalFile(str(chemin)))
    effet.play()


@functools.cache
def _effet():
    """La classe ``QSoundEffect`` qui appelle ``fini()`` quand la lecture s'arrête : une méthode branchée sur le signal, pas
    une lambda, qui garderait l'effet en vie par un cycle (PySide ne tient une méthode liée que faiblement)."""
    from qtpy6.QtMultimedia import QSoundEffect  # noqa: PLC0415 - en natif seulement, au premier son

    class Effet(QSoundEffect):
        def __init__(self, fini):
            super().__init__()
            self.fini = fini
            if fini is not None:
                self.playingChanged.connect(self._arret)

        def _arret(self):
            if not self.isPlaying():
                self.fini()

    return Effet


def _jouer_navigateur(nom, octets, extension, fini):
    import base64

    import js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    mime = {"mp3": "audio/mpeg", "ogg": "audio/ogg", "flac": "audio/flac", "m4a": "audio/mp4"}.get(extension, "audio/*")
    element = _GARDES[nom] = js.Audio.new(f"data:{mime};base64,{base64.b64encode(bytes(octets)).decode()}")
    if fini is not None:
        element.addEventListener("ended", create_once_callable(lambda _: fini()))
    element.play()
