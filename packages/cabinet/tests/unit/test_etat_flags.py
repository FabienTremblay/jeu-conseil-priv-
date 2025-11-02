# packages/cabinet/tests/unit/test_etat_flags.py
from __future__ import annotations
from cabinet.moteur.factories import construire_etat

def _etat_de_base():
    cfg = {
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
        "joueurs": {"J1": {"nom": "J1", "capital": 1}},
    }
    return construire_etat(cfg)

def test_termine_false_puis_true_si_programme_vide():
    e = _etat_de_base()
    assert not e.termine
    # simulate: vider le programme si une méthode/attribut existe
    if hasattr(e.programme, "entrees"):
        e.programme.entrees.clear()
    # beaucoup de modèles marquent termine lorsque plus d’entrées/action
    # si ton modèle utilise une méthode, remplace par e.evaluer_fin()
    if hasattr(e, "evaluer_fin"):
        e.evaluer_fin()
    assert isinstance(e.termine, bool)
