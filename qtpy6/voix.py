"""La lecture à voix haute d'un texte, le même appel en natif et dans le navigateur : ``dire`` lit (et coupe ce qui se
lisait), ``taire`` coupe.

Dans le navigateur, la synthèse vocale de la page (``speechSynthesis``, les voix du système que le navigateur expose). En
natif, ``QTextToSpeech`` de la liaison (module Qt TextToSpeech) s'il est installé et qu'un moteur démarre (speechd sous
Linux) ; sinon rien ne se lit et ``disponible`` le dit. Aucune dépendance nouvelle : le module Qt est optionnel."""
from __future__ import annotations

import importlib
import sys

from . import _binding

LANGUE = "fr-FR"
_moteur = None  # le QTextToSpeech natif, créé au premier appel ; False s'il n'y en a pas


def _natif():
    """Le moteur natif, ou None : module absent ou moteur en erreur (speechd absent, par exemple)."""
    global _moteur
    if _moteur is None:
        try:
            module = importlib.import_module(f"{_binding.API_NAME}.QtTextToSpeech")
            moteur = module.QTextToSpeech()
            _moteur = False if moteur.state() == module.QTextToSpeech.State.Error else moteur
        except (ImportError, AttributeError, RuntimeError):
            _moteur = False
    return _moteur or None


def _page():
    """La synthèse vocale du navigateur, ou None."""
    import js  # noqa: PLC0415

    return getattr(js.window, "speechSynthesis", None)


def disponible() -> bool:
    """Un texte peut se lire ici."""
    return (_page() if sys.platform == "emscripten" else _natif()) is not None


def dire(texte: str, langue: str = LANGUE) -> None:
    """Lit ``texte`` dans ``langue`` (« fr-FR »), après avoir coupé ce qui se lisait ; sans effet si rien ne sait lire."""
    if sys.platform == "emscripten":
        if (synthese := _page()) is None:
            return
        import js  # noqa: PLC0415

        synthese.cancel()
        enonce = js.SpeechSynthesisUtterance.new(texte)
        enonce.lang = langue
        synthese.speak(enonce)
        return
    if (moteur := _natif()) is None:
        return
    from qtpy6.QtCore import QLocale  # noqa: PLC0415

    moteur.stop()
    locale = QLocale(langue.replace("-", "_"))
    if any(l.name() == locale.name() for l in moteur.availableLocales()):
        moteur.setLocale(locale)
    moteur.say(texte)


def taire() -> None:
    """Coupe la lecture en cours, s'il y en a une."""
    if sys.platform == "emscripten":
        if (synthese := _page()) is not None:
            synthese.cancel()
    elif _moteur:
        _moteur.stop()


def parle() -> bool:
    """Une lecture est en cours."""
    if sys.platform == "emscripten":
        return bool((synthese := _page()) is not None and synthese.speaking)
    if not _moteur:
        return False
    return _moteur.state().name == "Speaking"
