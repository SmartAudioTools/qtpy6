"""L'archive que ``preparer`` (js/qtpy6web.js) ou un ``Travailleur`` dépaquette dans le navigateur : le code de
l'application, les paquets purs Python dont elle dépend, ses données, ses polices. À relancer après toute modification
(un dérivé, à ne pas versionner)."""

import importlib
import importlib.metadata
import json
import py_compile
import sys
import tempfile
import zipfile
from pathlib import Path


def assembler(archive, fichiers=(), paquets=(), distributions=(), polices=(), dossier_polices="polices", pyc=None,
              exclure=(), compression=zipfile.ZIP_DEFLATED):
    """Écrit le zip ``archive``. ``fichiers`` : ``{nom_dans_le_zip: chemin}``. ``paquets`` : des noms de modules
    importables, dont le dossier entier (``.py`` et données, sans ``__pycache__``) est pris là où il est, ce qui vaut pour
    une installation éditable. ``distributions`` : des paquets installés pris avec leurs métadonnées, pour ceux dont les
    points d'entrée servent (les extensions de ``markdown``). ``polices`` : des fichiers ``.ttf``/``.otf``, sous
    ``dossier_polices`` (ce qu'``application(polices=…)`` charge). ``pyc`` : chaque ``.py`` accompagné de son
    ``__pycache__/<nom>.cpython-3XX.pyc``, compilé par CET interpréteur, que Pyodide n'a plus à compiler à l'import
    (mesures : notes/2026-09-30 - PySide6 en WebAssembly.md, « Démarrage »). Sans contrôle de la source
    (UNCHECKED_HASH : le dépaquetage change les dates) ; un autre Python que celui du navigateur ne les lit pas et
    compile la source, gardée pour cela et pour les traces d'erreur. Par défaut, ``pyc`` vaut vrai quand cet interpréteur a
    la version de Python de Pyodide-Qt (``versions.json``) : d'une autre version, les ``.pyc`` seraient un poids mort. ``exclure`` : des débuts de noms dans le zip
    laissés dehors, ``qtpy6/web/js/pdfjs/`` typiquement (1,7 Mo, servis à côté de ``qtpy6web.js``, d'où
    ``qtpy6.web.pdf`` les charge à la première ouverture d'un PDF). ``compression`` : ``zipfile.ZIP_STORED`` pour une archive
    servie compressée en Brotli (``jumeaux`` de ``preparer``), qui ne tire presque rien d'un zip déjà dégonflé. Rend la
    taille en octets."""
    archive = Path(archive)
    if pyc is None:
        attendue = json.loads((Path(__file__).parent / "versions.json").read_text())["pyodide_qt"]["python"]
        pyc = f"{sys.version_info.major}.{sys.version_info.minor}" == attendue
    with zipfile.ZipFile(archive, "w", compression) as z, tempfile.TemporaryDirectory() as tmp:
        def ecrire(chemin, nom):
            if nom.startswith(tuple(exclure)):
                return
            z.write(chemin, nom)
            if pyc and nom.endswith(".py"):
                nom = Path(nom)
                cible = nom.parent / "__pycache__" / f"{nom.stem}.{sys.implementation.cache_tag}.pyc"
                py_compile.compile(chemin, f"{tmp}/c.pyc", str(nom), doraise=True,
                                   invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
                z.write(f"{tmp}/c.pyc", cible.as_posix())

        for nom, chemin in dict(fichiers).items():
            ecrire(chemin, nom)
        for nom in paquets:
            racine = Path(importlib.import_module(nom).__file__).parent
            for p in sorted(racine.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    ecrire(p, f"{nom}/{p.relative_to(racine).as_posix()}")
        for nom in distributions:
            d = importlib.metadata.distribution(nom)
            for f in d.files:
                if f.suffix != ".pyc" and not str(f).startswith(".."):
                    ecrire(d.locate_file(f), f.as_posix())
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
