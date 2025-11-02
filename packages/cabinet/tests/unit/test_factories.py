from __future__ import annotations
import pathlib
from cabinet.moteur.config_loader import load_cfg
from cabinet.moteur.factories import construire_etat

BASE = pathlib.Path(__file__).resolve().parents[2]  # …/packages/cabinet

def test_construction_etat_minimal():
    skin = BASE / "skins" / "demo_minimal.yaml"
    schema = BASE / "schemas" / "regles.schema.json"
    cfg = load_cfg(skin, schema_path=schema)
    etat = construire_etat(cfg)

    assert etat.id == "demo-001"
    assert etat.tour == 1
    assert "sante" in etat.axes and "securite" in etat.axes
    assert 0 <= etat.axes["sante"].valeur <= 10
    assert etat.eco.capacite_max >= 1
    assert list(etat.deck_global.pioche)[:2] == ["C003","C004"]
    assert "J1" in etat.joueurs and etat.joueurs["J1"].capital_politique == 3

def test_construction_etat_avec_programme_si_fourni():
    cfg = {
        "partie_id": "p2",
        "tour_initial": 1,
        "axes_tension": [
            {"id": "stabilite", "valeur": 6, "seuil_crise": 3, "poids": 1.0}
        ],
        "economie_initiale": {
            "taux_impot_part": 0.20,
            "taux_impot_ent": 0.20,
            "taux_redevances": 0.00,
            "taux_interet": 0.02,
            "base_part": 2,
            "base_ent": 0,
            "base_ressources": 10,
            "depenses_postes": {},
            "dette": 0,
            "capacite_max": 3,
            "efficience": 1.0,
        },
        "joueurs": {"bob": {"nom": "Bob", "capital": 0}},
        "programme": {  # optionnel, mais si présent on l’honore
            "version": 1,
            "entrees": [{
                "uid": "e1",
                "carte_id": "c-001",
                "auteur_id": "bob",
                "type": "mesure",
                "params": {"x": 1},
                "tags": ["budget"]
            }],
            "votes": {"bob": True}
        },
    }
    etat = construire_etat(cfg)
    assert etat.programme is not None
    assert etat.programme.version == 1
    assert len(etat.programme.entrees) == 1
    assert etat.programme.votes.get("bob") is True
