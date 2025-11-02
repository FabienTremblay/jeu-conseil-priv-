# packages/cabinet/tests/integration/test_yaml_schema.py
import pathlib
from cabinet.moteur.config_loader import load_cfg

def test_skins_demo_minimal_yaml_valide():
    path = pathlib.Path(__file__).resolve().parents[2] / "skins" / "demo_minimal.yaml"
    cfg = load_cfg(path)
    assert "axes_tension" in cfg and "economie_initiale" in cfg
