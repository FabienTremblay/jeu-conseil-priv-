import pytest
from cabinet.moteur.factories import construire_etat

def test_construction_etat_sans_programme_minimal():
    cfg = {
        "partie_id": "p1",
        "tour_initial": 0,
        "axes_tension": [
            {"id": "legitimite", "valeur": 5, "seuil_crise": 2, "poids": 1.0}
        ],
        "economie_initiale": {
            "taux_impot_part": 0.20,
            "taux_impot_ent": 0.20,
            "taux_redevances": 0.00,
            "taux_interet": 0.02,
            "base_part": 0,
            "base_ent": 0,
            "base_ressources": 0,
            "depenses_postes": {},
            "dette": 0,
            "capacite_max": 3,
            "efficience": 1.0,
        },
        "joueurs": {"alice": {"nom": "Alice", "capital": 0}},
        # pas de section "programme"
    }
    etat = construire_etat(cfg)
    assert etat.programme is None
    assert "legitimite" in etat.axes
    assert "alice" in etat.joueurs
