from __future__ import annotations
import pathlib
from cabinet.moteur.bootstrap import charger_etat_depuis_yaml

BASE = pathlib.Path(__file__).resolve().parents[2]

def test_end_to_end_yaml_schema_to_etat():
    skin = BASE / "skins" / "demo_minimal.yaml"
    schema = BASE / "schemas" / "regles.schema.json"
    etat = charger_etat_depuis_yaml(str(skin), schema_path=str(schema))

    # invariants simples
    assert etat.axes["sante"].seuil_crise <= 10
    assert etat.eco.efficience <= 1.0
    assert not etat.termine
    # programme bien chargé
    assert etat.programme.entrees and etat.programme.entrees[0].type == "mesure"
