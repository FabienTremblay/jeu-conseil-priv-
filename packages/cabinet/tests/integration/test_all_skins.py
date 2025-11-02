# packages/cabinet/tests/integration/test_all_skins.py
from __future__ import annotations
import pathlib, shutil, subprocess, pytest

BASE = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = BASE / "schemas" / "regles.schema.json"
SKINS_DIR = BASE / "skins"

def _iter_skins(root: pathlib.Path):
    for p in root.rglob("*.y*ml"):
        if "archives" in p.parts:
            continue
        yield p

@pytest.mark.skipif(shutil.which("check-jsonschema") is None, reason="check-jsonschema non installé")
@pytest.mark.parametrize("skin", sorted(_iter_skins(SKINS_DIR)))
def test_skin_valide(skin: pathlib.Path):
    res = subprocess.run(
        ["check-jsonschema", "--schemafile", str(SCHEMA), str(skin)],
        capture_output=True, text=True
    )
    assert res.returncode == 0, f"{skin} invalide:\n{res.stdout}\n{res.stderr}"

