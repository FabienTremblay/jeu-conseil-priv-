# packages/cabinet/tests/integration/test_schema_cli.py
from __future__ import annotations
import pathlib, shutil, subprocess
import pytest

BASE = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = BASE / "schemas" / "regles.schema.json"
SKIN   = BASE / "skins" / "demo_minimal.yaml"

@pytest.mark.skipif(shutil.which("check-jsonschema") is None, reason="check-jsonschema non installé")
def test_skin_valide_selon_schema_cli():
    cmd = [
        "check-jsonschema",
        "--schemafile", str(SCHEMA),
        str(SKIN),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        pytest.fail(f"validation échouée:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
