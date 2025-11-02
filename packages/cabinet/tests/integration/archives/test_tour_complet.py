import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade

@pytest.mark.it
def test_tour_complet_minimal():
    # Config minimale en mémoire (équivalente au skin demo)
    cfg = {
        "axes_tension": [
            {"id":"pauvrete","valeur_init":4,"seuil_crise":8,"poids":1.0},
            {"id":"insecurite","valeur_init":3,"seuil_crise":8,"poids":1.0},
            {"id":"maladie","valeur_init":2,"seuil_crise":8,"poids":1.0},
        ],
        "economie_initiale": {
            "taux_impot_part":0.20,"taux_impot_ent":0.18,"taux_redevances":0.10,"taux_interet":0.03,
            "base_part":120000,"base_ent":90000,"base_ressources":40000,
            "depenses_postes":{"sante":900,"securite":700,"social":600},
            "dette":12000,"capacite_max":3,"efficience":1.0
        },
        "regle_vote": {"type":"majorite_simple"},
        "contraintes": {"budget_min_solde":-3,"capacite_admin_max":3},
        "perturbateurs_tour": [
            {"id":"hausse_prix_energie","poids":1.0,
             "effets":[
                 {"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":+1}},
                 {"type":"tension_axis_delta","params":{"axis":"insecurite","delta":+1}}
             ]},
        ],
    }
    joueurs = [{"id":"j1","nom":"Alice"}, {"id":"j2","nom":"Bob"}]
    etat = init_etat_from_cfg(cfg, joueurs, partie_id="p-1")
    rng = RngFacade(42)

    # Conseil: dépôt d'une mesure simple (réduit pauvreté, coûte au social)
    actions = [
        fabriquer_entree_programme(
            uid="m1", carte_id="aide_aux_familles", auteur_id="j1", type_="mesure",
            tags=["realloc","social"],
            effets=[
                {"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":-2}},
                {"type":"depenses_poste_delta","params":{"poste":"social","delta":+150}},
            ]
        )
    ]
    votes = {"j1": True, "j2": True}

    etat2 = run_tour(etat, cfg, rng, actions_conseil=actions, votes=votes, procedures_declares=[])

    # Assertions de base (le test vérifie le flux complet)
    assert etat2.tour == 2
    # Perturbateur (+1/+1) puis mesure (-2 pauvreté) => pauvreté: 4+1-2 = 3
    assert etat2.axes["pauvrete"].valeur == 3
    assert "cloture_comptable" in {e["type"] for e in etat2.historiques}
    assert not etat2.termine
