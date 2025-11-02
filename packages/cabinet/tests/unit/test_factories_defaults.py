# packages/cabinet/tests/unit/test_factories_defaults.py
from __future__ import annotations
import pytest
from cabinet.moteur.factories import construire_etat

def test_construire_etat_valeurs_par_defaut_minimales():
    # cfg minimaliste pour activer les defaults du factory
    cfg = {
        "meta": {"id": "cfg-min"},
        "axes_tension": [
            {"id": "sante", "valeur": 5, "seuil_crise": 2, "poids": 1.0},
            {"id": "securite", "valeur": 5, "seuil_crise": 2, "poids": 1.0},
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
        "joueurs": {"J1": {"nom": "J1", "capital": 0}},
        "programme": {"version": 1, "entrees": [{"uid": "u1", "carte_id": "M1", "auteur_id": "J1", "type": "mesure"}], "votes": {}},
        "deck_global": { "pioche": ["C003", "C004", "C005"], "defausse": [] },
        "deck_events": { "pioche": [], "defausse": [] }
    }
    etat = construire_etat(cfg)

    assert etat.id == "cfg-min"
    assert etat.tour == 1
    # defaults plausibles
    assert "sante" in etat.axes and "securite" in etat.axes
    assert etat.eco.capacite_max == 3
    assert etat.eco.efficience == 1.0
    assert "J1" in etat.joueurs
    assert etat.joueurs["J1"].capital_politique >= 0
    assert etat.programme is not None
    # deck initial correctement construit
    assert list(etat.deck_global.pioche)[:2] == ["C003", "C004"]
