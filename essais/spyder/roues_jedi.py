"""Bâtit, depuis le SmartPython du bureau, les deux roues pures que le Worker du jalon 4 installe (`travailleur.configurer(
roues=…)`) : parso telle quelle, jedi sans `third_party/typeshed/stubs/` (les stubs de paquets tiers, django, requests… :
25 Mo sur disque, 4 000 fichiers à dépaqueter à chaque Worker, inutiles à un élève — la version locale `+sansstubs` le dit).
Rangées dans `essais/roues/` (non suivi par git, comme les roues téléchargées) ; `construire_site.py` les copie dans `site/`.

    $P roues_jedi.py"""

import os
import re
import sys
import zipfile
from pathlib import Path

SITE_PACKAGES = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
ROUES = Path(__file__).resolve().parent.parent / "roues"
EXCLURE = ("__pycache__", "jedi/third_party/typeshed/stubs/")


def batir(paquet, suffixe_version=""):
    dist_info = next(SITE_PACKAGES.glob(f"{paquet}-*.dist-info"))
    version = dist_info.name[len(paquet) + 1:-len(".dist-info")] + suffixe_version
    info_neuf = f"{paquet}-{version}.dist-info"
    roue = ROUES / f"{paquet}-{version}-py3-none-any.whl"
    enregistrements = []
    with zipfile.ZipFile(roue, "w", zipfile.ZIP_DEFLATED) as z:
        for racine, dossiers, fichiers in os.walk(SITE_PACKAGES / paquet):
            for f in sorted(fichiers):
                chemin = Path(racine) / f
                nom = str(chemin.relative_to(SITE_PACKAGES))
                if any(e in f"{nom}/" for e in EXCLURE):
                    continue
                z.write(chemin, nom)
                enregistrements.append(nom)
        for f in sorted(dist_info.iterdir()):
            if f.name == "RECORD":
                continue
            texte = f.read_bytes()
            if f.name == "METADATA":
                texte = re.sub(rb"^Version: .*$", f"Version: {version}".encode(), texte, count=1, flags=re.M)
            z.writestr(f"{info_neuf}/{f.name}", texte)
            enregistrements.append(f"{info_neuf}/{f.name}")
        z.writestr(f"{info_neuf}/RECORD", "".join(f"{n},,\n" for n in enregistrements + [f"{info_neuf}/RECORD"]))
    print(f"{roue.name} : {roue.stat().st_size // 1024} Kio, {len(enregistrements)} fichiers")
    return roue


if __name__ == "__main__":
    ROUES.mkdir(exist_ok=True)
    batir("parso")
    batir("jedi", "+sansstubs")
