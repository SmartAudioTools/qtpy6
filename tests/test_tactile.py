"""``qtpy6.web.tactile`` en natif, avec un écran tactile simulé (``QTest.createTouchDevice``) : le même scénario que la
sonde du lecteur QCM de SmartTeacher au profil téléphone (scénario ``parsons`` de ``sonde_lecteur.html``).

Dans un processus à part : l'écran simulé reste recensé par Qt jusqu'à la fin du processus (aucune API pour le retirer),
et ``tactile.detecte()`` le verrait dans les tests suivants (``test_inerte_en_natif``)."""

import os
import subprocess
import sys

import pytest
from qtpy6.QtCore import QPoint, Qt
from qtpy6.QtGui import QInputDevice
from qtpy6.QtTest import QTest
from qtpy6.QtWidgets import QVBoxLayout, QWidget

from qtpy6.web import tactile
from qtpy6.web.defilement import ZoneDefilante

ISOLE = os.environ.get("QTPY6_TACTILE_ISOLE") == "1"


@pytest.mark.skipif(ISOLE, reason="déjà dans le processus à part")
def test_dans_un_processus_a_part():
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", __file__],
                       env={**os.environ, "QTPY6_TACTILE_ISOLE": "1"}, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


class Relais(QWidget):
    """Un widget qui agit au doigt comme à la souris : ``WA_AcceptTouchEvents`` + ``relayer_en_souris``."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(200)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.souris = 0

    def event(self, evenement):
        return tactile.relayer_en_souris(self, evenement) or super().event(evenement)

    def mousePressEvent(self, evenement):
        self.souris += 1

    mouseMoveEvent = mouseReleaseEvent = mousePressEvent


@pytest.fixture
def page(app, monkeypatch):
    if not ISOLE:
        pytest.skip("lancé par test_dans_un_processus_a_part")
    monkeypatch.setattr(tactile, 'ACTIF', True)  # ce que pose activer(), sans toucher à la feuille de style de l'application
    zone = ZoneDefilante()  # la zone et le QScroller que pose une application (lecteur QCM : modele.defilant)
    zone.resize(300, 400)
    contenu = QWidget()
    disposition = QVBoxLayout(contenu)
    disposition.addSpacing(300)
    zone.relais = Relais()
    disposition.addWidget(zone.relais)
    disposition.addSpacing(1500)
    zone.setWidget(contenu)
    zone.setWidgetResizable(True)
    tactile.defiler_au_doigt(zone)
    zone.show()
    QTest.qWaitForWindowExposed(zone)
    zone.verticalScrollBar().setValue(200)
    yield zone
    zone.close()


def glisser(zone, point):
    """Un doigt posé en ``point`` (coordonnées de la vue) qui remonte de 120 px en 15 pas, puis se lève."""
    ecran = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
    vue = zone.viewport()
    QTest.touchEvent(vue, ecran).press(0, point)
    QTest.qWait(20)
    for pas in range(1, 16):
        QTest.touchEvent(vue, ecran).move(0, point - QPoint(0, 8 * pas))
        QTest.qWait(16)
    QTest.touchEvent(vue, ecran).release(0, point - QPoint(0, 120))
    QTest.qWait(1500)  # la course d'inertie de QScroller


def test_glisse_hors_du_relais_fait_defiler(page):
    glisser(page, QPoint(140, 30))
    assert page.verticalScrollBar().value() > 300  # témoin : le doigt simulé mène bien QScroller (200 → ~440)


def test_glisse_sur_le_relais_ne_fait_pas_defiler(page):
    glisser(page, page.relais.mapTo(page.viewport(), page.relais.rect().center()))
    assert page.relais.souris > 0  # le relais reçoit bien le geste…
    assert page.verticalScrollBar().value() == 200  # …et la page ne défile pas (sans arreter_le_defilement : 200 → ~440)
