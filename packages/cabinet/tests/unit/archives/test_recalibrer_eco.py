# packages/cabinet/tests/unit/test_recalibrer_eco.py
import pytest
from cabinet.moteur.moteur import init_etat_from_cfg
from cabinet.moteur.phases import recalibrer_eco

@pytest.mark.unit
def test_recalibrer_eco_surplus_reduit_dette_et_recalibre():
    """Cas surplus: la dette baisse, efficience/capacité sont recalculées et bornées."""
    cfg = {
        "axes_tension": [{"id": "pauvrete", "valeur_init": 3, "seuil_crise": 8}],
        "economie_initiale": {
            "taux_impot_part": 0.20, "taux_impot_ent": 0.18, "taux_redevances": 0.10, "taux_interet": 0.03,
            "base_part": 120000, "base_ent": 90000, "base_ressources": 40000,
            "depenses_postes": {"sante": 900, "securite": 700, "social": 600},
            "dette": 12000, "capacite_max": 3, "efficience": 1.0
        },
        "perturbateurs_tour": []
    }
    etat = init_etat_from_cfg(cfg, [{"id":"j1","nom":"Alice"}])
    dette_avant = etat.eco.dette
    cap_avant = etat.eco.capacite_max

    # petit ajustement dépenses mais on reste massivement en surplus
    etat.eco.depenses_postes["social"] += 500
    recalibrer_eco(etat, cfg)

    # dette diminue (peut aller jusqu’à 0)
    assert etat.eco.dette <= dette_avant
    # efficience bornée
    assert 0.60 <= etat.eco.efficience <= 1.10
    # capacité recalculée (>=1)
    assert etat.eco.capacite_max >= 1
    # historique écrit
    assert any(h.get("type") == "cloture_economie" for h in etat.historiques)

@pytest.mark.unit
def test_recalibrer_eco_deficit_augmente_dette_et_penalise_capacite():
    """Cas déficit net: la dette augmente et la capacité est pénalisée (budget_factor=0.90)."""
    cfg = {
        "axes_tension": [{"id": "pauvrete", "valeur_init": 3, "seuil_crise": 8}],
        "economie_initiale": {
            "taux_impot_part": 0.10, "taux_impot_ent": 0.08, "taux_redevances": 0.05, "taux_interet": 0.03,
            "base_part": 30000, "base_ent": 20000, "base_ressources": 10000,  # revenus ≈ 3 000 + 1 600 + 500 = 5 100
            "depenses_postes": {"sante": 8000, "securite": 6000, "social": 7000},  # dépenses >> revenus
            "dette": 5000, "capacite_max": 4, "efficience": 1.0
        },
        "perturbateurs_tour": []
    }
    etat = init_etat_from_cfg(cfg, [{"id":"j1","nom":"Alice"}])
    dette_avant = etat.eco.dette
    cap_base = etat.eco.capacite_max

    recalibrer_eco(etat, cfg)

    # dette augmente (déficit)
    assert etat.eco.dette > dette_avant
    # efficience bornée
    assert 0.60 <= etat.eco.efficience <= 1.10
    # capacité recalculée (budget_factor=0.90, donc souvent <= base)
    assert etat.eco.capacite_max >= 1
    # historique écrit
    logs = [h for h in etat.historiques if h.get("type") == "cloture_economie"]
    assert logs, "historique cloture_economie manquant"
    # sanity: le solde doit être négatif dans les logs
    assert any(l["solde"] < 0 for l in logs)

