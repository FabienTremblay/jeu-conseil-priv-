import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade

@pytest.mark.it
def test_conseil_rejet_puis_adoption_cycle_suivant():
    cfg = {
        "axes_tension":[{"id":"axe","valeur_init":3,"seuil_crise":9,"poids":1.0}],
        "economie_initiale":{
            "taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
            "base_part":80000,"base_ent":60000,"base_ressources":30000,
            "depenses_postes":{"social":500},"dette":1000,"capacite_max":3,"efficience":1.0
        },
        "regle_vote": {"type":"majorite_simple"},
        "perturbateurs_tour": []
    }
    joueurs = [{"id":"j1","nom":"Alice"},{"id":"j2","nom":"Bob"}]
    etat = init_etat_from_cfg(cfg, joueurs, partie_id="conseil-cycles")
    rng = RngFacade(9)

    # Cycle 1 : une mesure déposée, mais votes CONTRA (rejet)
    c1_actions = [
        fabriquer_entree_programme(uid="m1", carte_id="c1", auteur_id="j1", type_="mesure",
                                   effets=[{"type":"tension_axis_delta","params":{"axis":"axe","delta":-1}}])
    ]
    c1_votes = {"j1": False, "j2": False}

    # Cycle 2 : nouvelle mesure (amendement), cette fois votes POUR (adoption)
    c2_actions = [
        fabriquer_entree_programme(uid="m2", carte_id="c2", auteur_id="j2", type_="mesure",
                                   effets=[{"type":"tension_axis_delta","params":{"axis":"axe","delta":-2}}])
    ]
    c2_votes = {"j1": True, "j2": True}

    cycles = [{"actions": c1_actions, "votes": c1_votes},
              {"actions": c2_actions, "votes": c2_votes}]

    etat2 = run_tour(etat, cfg, rng, actions_conseil=cycles, votes=None, procedures_declares=[])

    # le programme adopté doit contenir UNIQUEMENT la mesure du cycle 2
    ids = [e.uid for e in etat2.programme.entrees]
    assert ids == ["m2"], f"programme doit refléter le dernier projet adopté (m2), pas {ids}"
    # l'effet -2 s'est appliqué
    assert etat2.axes["axe"].valeur == 1
    # historique contient le rejet puis l'adoption
    types = [h.get("type") for h in etat2.historiques]
    assert "programme_rejete_definitif" not in types
    assert types.count("programme_vote") >= 2

@pytest.mark.it
def test_conseil_rejet_definitif_si_aucun_cycle_naboutit():
    cfg = {
        "axes_tension":[{"id":"axe","valeur_init":3,"seuil_crise":9,"poids":1.0}],
        "economie_initiale":{
            "taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
            "base_part":80000,"base_ent":60000,"base_ressources":30000,
            "depenses_postes":{"social":500},"dette":1000,"capacite_max":3,"efficience":1.0
        },
        "regle_vote": {"type":"majorite_simple"},
        "perturbateurs_tour": []
    }
    joueurs = [{"id":"j1","nom":"Alice"},{"id":"j2","nom":"Bob"}]
    etat = init_etat_from_cfg(cfg, joueurs, partie_id="conseil-cycles-2")
    rng = RngFacade(11)

    c1 = [{"actions":[
                fabriquer_entree_programme(uid="m1", carte_id="c1", auteur_id="j1", type_="mesure",
                                           effets=[{"type":"tension_axis_delta","params":{"axis":"axe","delta":-1}}])
            ], "votes":{"j1": False, "j2": False}}]
    c2 = [{"actions":[
                fabriquer_entree_programme(uid="m2", carte_id="c2", auteur_id="j2", type_="mesure",
                                           effets=[{"type":"tension_axis_delta","params":{"axis":"axe","delta":-2}}])
            ], "votes":{"j1": False, "j2": False}}]

    etat2 = run_tour(etat, cfg, rng, actions_conseil=c1 + c2, votes=None, procedures_declares=[])

    # Aucun projet adopté -> programme reste vide
    assert etat2.programme.entrees == []
    # L'historique signale un rejet définitif
    assert any(h.get("type") == "programme_rejete_definitif" for h in etat2.historiques)
