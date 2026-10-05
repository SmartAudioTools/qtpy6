"""Bâtit exemple/app.zip : qtpy6 (pris là où il est installé, qtpy6.web compris), compteur.py, echo.py, boucle_qt.py, une police d'interface
et une police fixe. À relancer après toute modification. Puis :
    python -m qtpy6.web.sonde --racine . exemple/index.html capture.png   (ou servir la racine du dépôt et ouvrir la page)"""

from pathlib import Path

from qtpy6.web.assembler import assembler, polices

ICI = Path(__file__).resolve().parent
taille = assembler(ICI / "app.zip", fichiers={"compteur.py": ICI / "compteur.py", "echo.py": ICI / "echo.py", "boucle_qt.py": ICI / "boucle_qt.py"},
                   paquets=("qtpy6",),
                   polices=polices("/usr/share/fonts/noto/NotoSans-Regular.ttf", "/usr/share/fonts/liberation/LiberationMono-Regular.ttf"))
print(f"app.zip : {taille // 1024} Kio")
