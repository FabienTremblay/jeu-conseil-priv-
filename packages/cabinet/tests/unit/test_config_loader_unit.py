# packages/cabinet/tests/unit/test_config_loader_unit.py
from __future__ import annotations
from pathlib import Path
import subprocess, types

import pytest

import cabinet.moteur.config_loader as cfgmod

def test_load_cfg_sans_schema(tmp_path):
    y = tmp_path / "x.yaml"
    y.write_text("meta:\n  id: demo\n", encoding="utf-8")
    data = cfgmod.load_cfg(y)  # schema_path=None
    assert data["meta"]["id"] == "demo"

def test_load_cfg_validation_ok(monkeypatch, tmp_path):
    y = tmp_path / "ok.yaml"
    y.write_text("meta:\n  id: ok\n", encoding="utf-8")

    # Simule la présence de check-jsonschema + retour 0
    monkeypatch.setattr(cfgmod.shutil, "which", lambda _: "/usr/bin/check-jsonschema")
    class R: returncode=0; stdout=""; stderr=""
    monkeypatch.setattr(cfgmod.subprocess, "run", lambda *a, **k: R)

    data = cfgmod.load_cfg(y, schema_path=tmp_path / "schema.json")
    assert data["meta"]["id"] == "ok"

def test_load_cfg_validation_ko(monkeypatch, tmp_path):
    y = tmp_path / "ko.yaml"
    y.write_text("meta:\n  id: ko\n", encoding="utf-8")

    monkeypatch.setattr(cfgmod.shutil, "which", lambda _: "/usr/bin/check-jsonschema")
    class R: returncode=1; stdout="OOPS"; stderr="bad"
    monkeypatch.setattr(cfgmod.subprocess, "run", lambda *a, **k: R)

    with pytest.raises(ValueError) as ei:
        cfgmod.load_cfg(y, schema_path=tmp_path / "schema.json")
    assert "ne respecte pas le schéma" in str(ei.value)
