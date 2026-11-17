"""W583 : le site des élèves ne sert aucun fichier de session. Jusqu'au 17/11/2026, essais/spyder/site/app.zip embarquait
qtpy6/.claude/conversations/*.jsonl (2 Mo de journal) et spyder_pyxel/.claude/, .mcp.json. Filtres : qtpy6/web/assembler.py
(paquets=, W577) et construire_site.py (fichiers=, W583)."""
import zipfile
from pathlib import Path

import pytest

ZIP = Path(__file__).resolve().parents[1] / "essais" / "spyder" / "site" / "app.zip"


@pytest.mark.skipif(not ZIP.exists(), reason="site non construit (essais/spyder/construire_site.py)")
def test_zip_du_site_sans_fichier_de_session():
    with zipfile.ZipFile(ZIP) as z:
        caches = [n for n in z.namelist()
                  if any(c.startswith(".") for c in n.split("/")) or n.endswith(".jsonl")]
    assert caches == []
