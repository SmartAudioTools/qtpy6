"""Ce que fait tourner la page de lancement du site de qtpy6 (``hebergement/``) : un script ``.py``, ou un ``.zip`` dont
il faut trouver le point d'entrée, lancé comme sur un bureau avec les fichiers donnés en arguments.

Dans un zip, le point d'entrée est cherché dans cet ordre (``point_d_entree``) :

    __main__.py à la racine            une application zipapp            python app.zip
    paquet/__main__.py                 un paquet exécutable               python -m paquet
    paquet/paquet.py, nom.py           le script du nom du paquet ou du zip   python paquet/paquet.py
    un seul .py à la racine            le script                          python script.py

Un zip dont la racine n'est qu'un dossier sans ``__init__.py`` (le « Download ZIP » de GitHub : ``depot-main/``) est
lu depuis ce dossier, et une bibliothèque livrée dans le zip avec son ``*.dist-info`` (``qtpy6.web.assembler``,
``distributions``) n'est jamais prise pour le point d'entrée."""

import os
import zipfile
from pathlib import Path


def point_d_entree(dossier, nom):
    """``(script, module)`` : le fichier à exécuter dans ``dossier`` (un zip dépaqueté dont ``nom`` est le nom sans
    extension), et le nom du module quand il se lance par ``-m`` (``None`` sinon). ``ValueError`` si rien ne convient,
    ou si le choix est ambigu."""
    racine = Path(dossier)
    entrees = [p for p in racine.iterdir() if not p.name.startswith((".", "__MACOSX"))]
    if len(entrees) == 1 and entrees[0].is_dir() and not (entrees[0] / "__init__.py").exists():
        return point_d_entree(entrees[0], nom)
    if (racine / "__main__.py").is_file():
        return racine / "__main__.py", None
    # une bibliothèque livrée avec l'application (son *.dist-info à côté, dont le RECORD la nomme) n'est pas l'application,
    # même quand elle a un __main__.py (markdown, pygments)
    livrees = {ligne.split("/")[0] for info in racine.glob("*.dist-info") if (info / "RECORD").is_file()
               for ligne in (info / "RECORD").read_text().splitlines()}
    dossiers = sorted(p for p in entrees if p.is_dir() and p.name not in livrees)
    for regle in ((lambda d: d / "__main__.py", True), (lambda d: d / f"{d.name}.py", False)):
        trouves = [d for d in dossiers if regle[0](d).is_file()]
        if len(trouves) > 1:
            trouves = [d for d in trouves if d.name == nom] or trouves
        if len(trouves) == 1:
            return regle[0](trouves[0]), trouves[0].name if regle[1] else None
        if trouves:
            raise ValueError(f"plusieurs points d'entrée possibles : {', '.join(str(regle[0](d).relative_to(racine)) for d in trouves)}")
    scripts = sorted(p for p in entrees if p.suffix == ".py" and p.is_file())
    for s in scripts:
        if s.stem == nom:
            return s, None
    if len(scripts) == 1:
        return scripts[0], None
    raise ValueError("aucun point d'entrée : ni __main__.py, ni paquet/__main__.py, ni script du nom du paquet ou du zip, "
                     f"ni un seul .py à la racine ({len(scripts)} .py)")


def executer(chemin, args=(), pret=None):
    """Lance ``chemin`` (un ``.py``, ou un ``.zip`` dépaqueté à côté puis résolu par ``point_d_entree``) par
    ``qtpy6.web.lancer`` ; rend le code de sortie."""
    from . import lancer  # noqa: PLC0415

    chemin = Path(chemin)
    if chemin.suffix.lower() != ".zip":
        return lancer(str(chemin), args, pret)
    dossier = chemin.with_suffix("")
    with zipfile.ZipFile(chemin) as z:
        z.extractall(dossier)
    script, module = point_d_entree(dossier, chemin.stem)
    print(f"point d'entrée : {'-m ' + module if module else os.path.relpath(script, dossier)}")
    return lancer(str(script), args, pret, module=module)
