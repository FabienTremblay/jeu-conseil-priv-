import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour
from cabinet.moteur.rng import RngFacade

@pytest.mark.it
def test_fin_de_partie_par_seuil_capital_collectif_parametrable():
    """
    Configure un seuil de fin collectif (ex.: 40).
    Avec 6 axes à 10 (poids 1), le scoring = 100 - (sens * somme_axes) = 100 - 60 = 40.
    => Comme capital_collectif <= seuil (40), la partie doit se terminer par renversement.
    """
    cfg = {
        "axes_tension": [
            {"id":"a1","valeur_init":10,"seuil_crise":12,"poids":1.0},
            {"id":"a2","valeur_init":10,"seuil_crise":12,"poids":1.0},
            {"id":"a3","valeur_init":10,"seuil_crise":12,"poids":1.0},
            {"id":"a4","valeur_init":10,"seuil_crise":12,"poids":1.0},
            {"id":"a5","valeur_init":10,"seuil_crise":12,"poids":1.0},
            {"id":"a6","valeur_init":10,"seuil_crise":12,"poids":1.0},
        ],
        "economie_initiale": {
            "taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
            "base_part":80000,"base_ent":60000,"base_ressources":30000,
            "depenses_postes":{"sante":600,"securite":600,"social":600},
            "dette":2000,"capacite_max":3,"efficience":1.0
        },
        "politique": {
            "sensibilite_axes": 1.0,
            "capital_base": 100,
            "capital_min": -100,
            "seuil_fin_collectif": 40
        },
        "perturbateurs_tour": []
    }
    joueurs = [{"id":"j1","nom":"Alice"}]
    etat = init_etat_from_cfg(cfg, joueurs, partie_id="seuil-collectif-40")
    rng = RngFacade(42)

    # Aucun programme (on vérifie seulement le scoring/clôture et la règle de fin)
    etat2 = run_tour(etat, cfg, rng, actions_conseil=[], votes={"j1": True}, procedures_declares=[])

    assert etat2.termine is True, "La partie aurait dû se terminer via le seuil de capital collectif."
    assert etat2.raison_fin and "renversement:capital_collectif<=" in etat2.raison_fin
    assert etat2.capital_collectif <= 40
