"""Item 15 (W552, 12/11/2026) : le site des essais Spyder, construit à part pour les mesures sous Chrome.

construire_site.py prend le dossier essais/spyder ENTIER : les journaux et captures que les sondes des autres workers
écrivent pendant la construction (app.zip commun de 14:11, 6 719 membres sur 7 088 illisibles) et un essai en cours
d'édition (spe_monkey.py en erreur de syntaxe à 14:13) cassent l'archive. D'où : un instantané des sources (sans .log,
.png, site/, chrome/, __pycache__/) dans /DATA/Python/qtpy6_essais/chrome/src/spyder, les .py qui ne se compilent pas
écartés (et nommés), puis construire_site.py DE L'INSTANTANÉ, --sortie /DATA/Python/qtpy6_essais/chrome/site."""
import shutil
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent.parent
BASE = Path("/DATA/Python/qtpy6_essais/chrome")
SRC = BASE / "src" / "spyder"
if SRC.exists():
    subprocess.run(["/home/claude/.claude/hooks/claude-corbeille.sh", str(SRC)], check=True)
motifs = shutil.ignore_patterns("*.log", "*.png", "site", "chrome", "__pycache__", ".*")


def ignorer(dossier, noms):
    rendu = set(motifs(dossier, noms))
    for n in noms:
        if n.endswith(".py") and n not in rendu:
            try:
                compile((Path(dossier) / n).read_bytes(), n, "exec")
            except SyntaxError as e:
                print(f"écarté : {n} (ligne {e.lineno} : {e.msg})")
                rendu.add(n)
    return rendu


shutil.copytree(ICI, SRC, ignore=ignorer)
roues = SRC.parent / "roues"
if not roues.exists():
    roues.symlink_to(ICI.parent / "roues")
sys.exit(subprocess.run([sys.executable, str(SRC / "construire_site.py"), "--sortie", str(BASE / "site")]).returncode)
