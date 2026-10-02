"""``qtpy6.paresse`` : mises en page endormies loin de la vue, éléments bâtis en tâche de fond ou en entrant dans la vue."""

from qtpy6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from qtpy6.paresse import Chantier, Paresse


class Element(QWidget):
    HAUTEUR = 100

    def __init__(self, batie=True):
        super().__init__()
        self.disposition, self.batie = QVBoxLayout(self), False
        self.disposition.setContentsMargins(0, 0, 0, 0)
        if batie:
            self.batir()

    def batir(self):
        if not self.batie:
            self.batie = True
            w = QWidget()
            w.setFixedHeight(self.HAUTEUR)
            self.disposition.addWidget(w)
            w.show()  # sinon montré par un appel en file (``addChildWidget``), et compté de hauteur nulle d'ici là


def page(elements):
    zone, contenu = QScrollArea(), QWidget()
    zone.setWidgetResizable(True)
    d = QVBoxLayout(contenu)
    d.setSpacing(0)
    for e in elements:
        d.addWidget(e)
    d.addStretch()
    zone.setWidget(contenu)
    zone.resize(300, 200)
    Paresse(zone, elements)
    return zone


def test_endormis_loin_de_la_vue_eveilles_a_l_approche(app):
    elements = [Element() for _ in range(30)]
    zone = page(elements)
    zone.show()
    app.processEvents()
    zone.paresse.rafraichir()
    assert elements[0].layout().isEnabled() and not elements[-1].layout().isEnabled()
    zone.verticalScrollBar().setValue(zone.verticalScrollBar().maximum())
    assert elements[-1].layout().isEnabled() and not elements[0].layout().isEnabled()
    zone.close()


def test_chantier_bati_en_fond_hors_defilement_et_la_vue_d_abord(app):
    elements = [Element(batie=False) for _ in range(30)]
    zone = page(elements)
    zone.show()
    app.processEvents()
    zone.paresse.rafraichir()
    assert elements[0].batie and not elements[-1].batie, "la vue d'abord, le reste attend le chantier"
    chantier = Chantier(zone, elements)
    assert elements[0] not in chantier.reste
    zone.verticalScrollBar().setValue(1)  # un défilement : le chantier attend
    avant = len(chantier.reste)
    chantier.tranche()
    assert len(chantier.reste) == avant, "une tranche est bâtie pendant le défilement"
    Paresse.defile -= Chantier.REPOS
    finis = []
    chantier.fini.connect(lambda: finis.append(1))
    while chantier.reste:
        chantier.tranche()
    assert finis and all(e.batie for e in elements)
    zone.close()


def test_batir_au_dessus_de_la_vue_ne_bouge_pas_l_ecran(app):
    elements = [Element(batie=i < 10 or i >= 20) for i in range(30)]
    zone = page(elements)
    zone.show()
    app.processEvents()
    barre = zone.verticalScrollBar()
    barre.setValue(barre.maximum())
    app.processEvents()
    repere = elements[25]
    avant = zone.paresse._haut(repere)
    reste = [e for e in elements if not e.batie]
    zone.paresse.batir(reste)
    assert not reste and zone.paresse._haut(repere) == avant
    zone.close()


def test_hors_de_toute_page_bati_seul(app):
    cache = Element(batie=False)
    chantier = Chantier(None, [cache])
    Paresse.defile = 0.0
    chantier.tranche()
    assert cache.batie and not chantier.reste
