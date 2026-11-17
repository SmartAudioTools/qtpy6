"""W572 : les images de Pyxel web calées sur les balayages de la page (``pyxel_web.attendre_balayages``), simulées hors
navigateur : une horloge fictive, une page qui compte un balayage toutes les 1/hz s, un ``draw`` de durée variable."""

import bisect
import random

import pytest

from qtpy6.web.pyxel_web import attendre_balayages


class Page:
    """``lire(0)`` : balayages comptés ; ``lire(1)`` : période en µs ; ``lire(2)`` : instant du dernier balayage (s)."""

    def __init__(self, hz: float) -> None:
        self.t, self.periode = 0.0, 1 / hz

    def lire(self, i: int) -> float:
        k = int(self.t / self.periode + 1e-9)
        return k if i == 0 else round(self.periode * 1e6) if i == 1 else k * self.periode

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


def _muette(i: int) -> float:
    return 7 if i == 0 else 16_667 if i == 1 else -1.0  # dernier balayage il y a une seconde


def test_page_qui_ne_compte_plus_rend_faux() -> None:
    etat, t = {"fps": 60}, [0.0]

    def dormir(s: float) -> None:
        t[0] += s
    assert not attendre_balayages(_muette, etat, dormir, lambda: t[0])
    assert t[0] < 0.2 and "balayage" not in etat


def test_page_muette_ne_fait_attendre_qu_une_fois() -> None:
    etat, t = {"fps": 60}, [0.0]

    def dormir(s: float) -> None:
        t[0] += s
    for _ in range(10):
        assert not attendre_balayages(_muette, etat, dormir, lambda: t[0])
    assert t[0] < 0.2  # une seule attente de repli, pas dix


class PageChargee(Page):
    """W573 : une page dont le fil principal manque des balayages (rappels ``requestAnimationFrame`` sautés) ; l'écran,
    lui, balaie toujours : le compteur n'avance qu'aux balayages servis, l'instant est celui du dernier servi."""

    def __init__(self, hz: float, sautes: float, graine: int = 573) -> None:
        super().__init__(hz)
        hasard = random.Random(graine)
        self.servis, suite = [0], 0
        for k in range(1, 200_000):  # au plus trois sautés de suite : au-delà de 100 ms, c'est le repli (autre test)
            if suite < 3 and hasard.random() < sautes:
                suite += 1
            else:
                self.servis.append(k)
                suite = 0

    def lire(self, i: int) -> float:
        k = int(self.t / self.periode + 1e-9)
        j = bisect.bisect_right(self.servis, k) - 1
        return j if i == 0 else round(self.periode * 1e6) if i == 1 else self.servis[j] * self.periode


@pytest.mark.parametrize("sautes", [0.0, 0.4])
def test_page_qui_saute_des_balayages_ne_ralentit_pas_le_jeu(sautes: float) -> None:
    """Écran réel du professeur (17/11, W572) : la page servait ≈ 36 balayages sur 59, le noyau calé sur le COMPTEUR
    tournait à 35 i/s au lieu de 60. Calé sur la grille des balayages (instant + période), il garde ``fps``, et chaque
    image part sur un balayage de l'écran."""
    page, etat, hasard = PageChargee(60, sautes), {"fps": 60}, random.Random(5730)
    instants = []
    for _ in range(600):
        assert attendre_balayages(page.lire, etat, page.dormir, lambda: page.t)
        instants.append(page.t)
        page.dormir(hasard.uniform(0.0005, 0.006))
    duree = instants[-1] - instants[1]
    assert duree == pytest.approx(598 / 60, rel=0.01)
    assert all(abs(t * 60 - round(t * 60)) < 1e-3 for t in instants[1:])  # sur un balayage (période lue au µs près)
