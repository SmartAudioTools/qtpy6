"""L'archive que ``preparer`` (js/qtpy6web.js) ou un ``Travailleur`` dépaquette dans le navigateur : le code de
l'application, les paquets purs Python dont elle dépend, ses données, ses polices. À relancer après toute modification
(un dérivé, à ne pas versionner)."""

import importlib
import importlib.metadata
import zipfile
from pathlib import Path


def assembler(archive, fichiers=(), paquets=(), distributions=(), polices=(), dossier_polices="polices"):
    """Écrit le zip ``archive``. ``fichiers`` : ``{nom_dans_le_zip: chemin}``. ``paquets`` : des noms de modules
    importables, dont le dossier entier (``.py`` et données, sans ``__pycache__``) est pris là où il est, ce qui vaut pour
    une installation éditable. ``distributions`` : des paquets installés pris avec leurs métadonnées, pour ceux dont les
    points d'entrée servent (les extensions de ``markdown``). ``polices`` : des fichiers ``.ttf``/``.otf``, sous
    ``dossier_polices`` (ce qu'``application(polices=…)`` charge). Rend la taille en octets."""
    archive = Path(archive)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, chemin in dict(fichiers).items():
            z.write(chemin, nom)
        for nom in paquets:
            racine = Path(importlib.import_module(nom).__file__).parent
            for p in sorted(racine.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, f"{nom}/{p.relative_to(racine)}")
        for nom in distributions:
            d = importlib.metadata.distribution(nom)
            for f in d.files:
                if f.suffix != ".pyc" and not str(f).startswith(".."):
                    z.write(d.locate_file(f), str(f))
        for p in polices:
            z.write(p, f"{dossier_polices}/{Path(p).name}")
    return archive.stat().st_size


def polices(*motifs):
    """Les fichiers que désignent des motifs absolus (``/usr/share/fonts/noto/NotoSans-Regular.ttf``,
    ``/usr/share/fonts/liberation/LiberationMono-*.ttf``), triés ; une erreur si un motif ne trouve rien."""
    trouves = []
    for motif in motifs:
        motif = Path(motif)
        lot = sorted(motif.parent.glob(motif.name))
        if not lot:
            raise FileNotFoundError(motif)
        trouves += lot
    return trouves
