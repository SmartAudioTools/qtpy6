"""Le site de essais/spyder construit dans essais/fsmodel/site_spe (W550) : même script, autre dossier de sortie, pour
ne pas toucher le site partagé que d'autres workers sondent. Archive vérifiée (testzip) : un journal écrit pendant
l'emballage la corrompt."""
import sys
import zipfile
from pathlib import Path

SPYDER = Path("/DATA/Python/qtpy6/essais/spyder")
source = (SPYDER / "construire_site.py").read_text(encoding="utf-8")
assert source.count('SITE = ICI / "site"') == 1
source = source.replace('SITE = ICI / "site"', 'SITE = Path("/DATA/Python/qtpy6_essais/w550/site_spe")')
sys.path.insert(0, str(SPYDER))
exec(compile(source, str(SPYDER / "construire_site.py"), "exec"), {"__file__": str(SPYDER / "construire_site.py"),
                                                                      "__name__": "__main__"})
mauvais = zipfile.ZipFile("/DATA/Python/qtpy6_essais/w550/site_spe/app.zip").testzip()
print("archive", "intacte" if mauvais is None else f"CORROMPUE ({mauvais})")
