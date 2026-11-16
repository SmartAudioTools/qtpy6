"""W572 : les images de Pyxel web calées sur les balayages de la page (``pyxel_web.attendre_balayages``), simulées hors
navigateur : une horloge fictive, une page qui compte un balayage toutes les 1/hz s, un ``draw`` de durée variable."""

import random

import pytest

from qtpy6.web.pyxel_web import attendre_balayages


class Page:
    def __init__(self, hz: float) -> None:
        self.t, self.periode = 0.0, 1 / hz

    def lire(self, i: int) -> int:
        return int(self.t / self.periode) if i == 0 else round(self.periode * 1e6)

    def dormir(self, s: float) -> None:
        self.t += s


@pytest.mark.parametrize(("hz", "fps"), [(60, 60), (60, 30), (120, 60), (144, 30), (59.95, 60)])
def test_chaque_image_dure_hz_sur_fps_balayages(hz: float, fps: int) -> None:
    page, etat, hasard = Page(hz), {"fps": fps}, random.Random(572)
    vus = []
    for _ in range(600):
        assert attendre_balayages(page.lire, etat, page.dormir, lambda: page.t)
        vus.append(page.lire(0))
        page.dormir(hasard.uniform(0.0005, 0.6 / fps))  # update + draw, toujours plus court qu'une image
    attendu = max(1, round(hz / fps))
    assert {b - a for a, b in zip(vus[1:], vus[2:])} == {attendu}


def test_image_en_retard_repart_du_balayage_courant() -> None:
    page, etat = Page(60), {"fps": 60}
    attendre_balayages(page.lire, etat, page.dormir, lambda: page.t)
    page.dormir(0.05)  # une image lourde : trois balayages
    attendre_balayages(page.lire, etat, page.dormir, lambda: page.t)
    avant = page.lire(0)
    attendre_balayages(page.lire, etat, page.dormir, lambda: page.t)
    assert page.lire(0) == avant + 1


def test_page_qui_ne_compte_plus_rend_faux() -> None:
    etat, t = {"fps": 60}, [0.0]

    def dormir(s: float) -> None:
        t[0] += s
    assert not attendre_balayages(lambda i: 7 if i == 0 else 16_667, etat, dormir, lambda: t[0])
    assert t[0] < 0.2 and "balayage" not in etat


def test_page_muette_ne_fait_attendre_qu_une_fois() -> None:
    etat, t = {"fps": 60}, [0.0]

    def dormir(s: float) -> None:
        t[0] += s
    for _ in range(10):
        assert not attendre_balayages(lambda i: 7 if i == 0 else 16_667, etat, dormir, lambda: t[0])
    assert t[0] < 0.2  # une seule attente de repli, pas dix
