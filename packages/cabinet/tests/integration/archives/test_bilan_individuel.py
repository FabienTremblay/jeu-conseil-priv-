import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade

@pytest.mark.it
def test_bilan_individuel_generation_complete():
    cfg = {
        "axes_tension":[{"id":"pauvrete","valeur_init":4,"seuil_crise":8,"poids":1.0}],
        "economie_initiale":{
            "taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
            "base_part":80000,"base_ent":60000,"base_ressources":30000,
            "depenses_postes":{"social":500},"dette":2000,"capacite_max":3,"efficience":1.0
        },
        "politique":{"bonus_collectif":5,"malus_collectif":-5,"seuil_fin_collectif":100},
        "perturbateurs_tour": []
    }
    joueurs = [{"id":"j1","nom":"Alice"},{"id":"j2","nom":"Bob"}]
    etat = init_etat_from_cfg(cfg, joueurs, partie_id="bilan-1")
    rng = RngFacade(1)

    # tour simple : une mesure de j1
    actions = [
        fabriquer_entree_programme(
            uid="m1", carte_id="plan_social", auteur_id="j1", type_="mesure",
            effets=[{"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":-1}}]
        )
    ]
    votes = {"j1": True, "j2": True}

    etat2 = run_tour(etat, cfg, rng, actions_conseil=actions, votes=votes, procedures_declares=[])

    assert hasattr(etat2, "resultats")
    res = etat2.resultats
    assert "individuels" in res
    assert "collectif" in res
    assert "j1" in res["individuels"]
    assert res["individuels"]["j1"]["score_total"] != 0
