"""``qtpy6.web.sonde.raccourci`` sous Blink : toute lettre avec Ctrl part au clavier, pas seulement Ctrl+C/X/V (le
scénario ``recherche_clavier`` du lecteur SmartTeacher tape Ctrl+F ; une KeyError l'arrêtait au délai dépassé, W942)."""

import pytest

from qtpy6.web import sonde


class FauxBlink(sonde.Blink):
    def __init__(self, touche):  # sans navigateur : ``raccourci`` ne lit que ``window.touche`` et envoie en CDP
        self.touche, self.envois = touche, []

    def execute_script(self, code):
        return self.touche

    def cdp(self, methode, **params):
        self.envois.append(params)


@pytest.mark.parametrize("touche, commandes", [("c", ["copy"]), ("v", ["paste"]), ("f", [])])
def test_raccourci_blink(touche, commandes):
    navigateur = FauxBlink(touche)
    sonde.raccourci(navigateur)
    appui, relache = navigateur.envois
    assert appui["type"] == "rawKeyDown" and appui["commands"] == commandes and appui["key"] == touche
    assert relache["type"] == "keyUp" and relache["modifiers"] == 2
