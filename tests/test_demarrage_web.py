"""Démarrage de SmartPythonEditor dans la page (item 22 du TODO Portage, W577) : ce que qtpy6 y coûte, vérifié en natif.
Le profil de la page (notes/2026-11-17 - Démarrage de spe.py dans la page, profil et corrections (W577).md) met en tête
de l'import de Spyder ``traitlets.getmembers`` : à chaque classe de qtconsole créée, il lit sur la CLASSE tous ses noms,
dont les quelque 400 alias snake_case de qtpy6, chacun sur un propriétaire neuf."""

import sys
import time

from qtpy6 import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])


class _Melange:
    """Un mixin Python placé après la classe Qt, avec ``__getattr__`` (le cas que ``_Alias`` doit encore servir)."""

    def __getattr__(self, nom):
        raise AttributeError(nom)


def _parcours(bases, noms):
    """Durée de la lecture de ``noms`` sur une classe NEUVE, comme ``traitlets.getmembers`` à la création d'une classe."""
    classe = type("Neuve", bases, {})
    t = time.perf_counter()
    for nom in noms:
        getattr(classe, nom, None)
    return time.perf_counter() - t


def test_alias_sur_une_classe_neuve_coute_comme_le_nom_qt():
    """Lire les alias d'une classe neuve ne refait pas, alias par alias, le tri de son MRO : avant W577, 5,1 µs par
    alias contre 0,16 µs par nom camelCase (×32, mesuré) ; 1,4 contre 0,18 après (×8 : l'appel d'un descripteur
    Python seul coûte 0,19 µs). Borne à ×14 : rouge avant, vert après (minimum sur 15 classes neuves)."""
    from qtpy6._binding import _Alias
    qt = QtWidgets.QPlainTextEdit
    alias = [n for n in dir(qt) if isinstance(_attribut(qt, n), _Alias)]
    camel = [_attribut(qt, n).qt.__name__ for n in alias if hasattr(_attribut(qt, n).qt, "__name__")]
    assert len(alias) > 200 and len(camel) > 200
    for bases in ((qt,), (qt, _Melange)):
        t_alias = min(_parcours(bases, alias) / len(alias) for _ in range(15))
        t_camel = min(_parcours(bases, camel) / len(camel) for _ in range(15))
        assert t_alias < 14 * t_camel, (bases, t_alias * 1e6, t_camel * 1e6)


def _attribut(classe, nom):
    for c in classe.__mro__:
        if nom in vars(c):
            return vars(c)[nom]
    return None


def test_alias_cede_encore_au_mixin_ajoute_apres_lecture():
    """Le cache par propriétaire ne fige pas l'application : une méthode posée sur le mixin APRÈS une première lecture
    de l'alias le masque bien (comme le nom le ferait sans qtpy6)."""
    class Mixin:
        pass

    classe = type("Neuve", (QtWidgets.QPlainTextEdit, Mixin), {})
    assert classe.move_cursor is not None  # première lecture : la méthode Qt
    Mixin.move_cursor = lambda self: "mixin"
    assert classe().move_cursor() == "mixin"


def test_sous_classe_qt_ne_parcourt_pas_le_mro_pour_chaque_methode():
    """``QObject.__init_subclass__`` (``_signal_masked``, l'avertissement d'un alias de signal masqué) ne remonte le MRO
    que pour un nom qui est celui d'un alias de signal : avant W577, une sous-classe de QPlainTextEdit à 300 méthodes
    coûtait 664 µs contre 23 µs pour une classe Python (×29, mesuré) ; 81 µs après (×3,7). Borne à ×12."""
    corps = {f"methode_{i}": (lambda self: None) for i in range(300)}

    def une(base):
        t = time.perf_counter()
        type("Neuve", (base,), dict(corps))
        return time.perf_counter() - t

    qt = min(une(QtWidgets.QPlainTextEdit) for _ in range(30))
    python = min(une(object) for _ in range(30))
    assert qt < 12 * python, (qt * 1e6, python * 1e6)


def test_assembler_laisse_les_dossiers_caches(tmp_path, monkeypatch):
    """Un paquet pris par ``assembler(paquets=…)`` n'emporte pas ses dossiers cachés : celui de qtpy6 portait le
    ``.claude`` d'une session (1,9 Mio dans chaque app.zip, dépaqueté à chaque ouverture de la page, W577). Un dossier
    caché AU-DESSUS du paquet (``~/.local/lib/…``) ne l'exclut pas."""
    import zipfile

    from qtpy6.web.assembler import assembler
    racine = tmp_path / ".local" / "site"
    (racine / "paquet_w577" / ".claude").mkdir(parents=True)
    (racine / "paquet_w577" / "__init__.py").write_text("")
    (racine / "paquet_w577" / ".claude" / "journal.jsonl").write_text("{}")
    (racine / "paquet_w577" / ".cache").write_text("")
    monkeypatch.syspath_prepend(str(racine))
    archive = tmp_path / "app.zip"
    assembler(archive, paquets=["paquet_w577"], pyc=False)
    assert zipfile.ZipFile(archive).namelist() == ["paquet_w577/__init__.py"]
