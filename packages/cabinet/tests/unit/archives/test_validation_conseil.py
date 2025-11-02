import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade
from cabinet.moteur.phases import phase_conseil

@pytest.mark.unit
def test_depot_rejete_par_capacite():
    cfg = {
        "axes_tension": [{"id":"pauvrete","valeur_init":4,"seuil_crise":8,"poids":1.0}],
        "economie_initiale": {
            "taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
            "base_part":100000,"base_ent":80000,"base_ressources":50000,
            "depenses_postes":{"social":500},"dette":1000,"capacite_max":3,"efficience":1.0
        },
        "contraintes": {"capacite_admin_max": 1},
        "perturbateurs_tour": []
    }
    etat = init_etat_from_cfg(cfg, [{"id":"j1","nom":"Alice"}])
    # deux dépôts "mesure": le second doit être rejeté (capacité max 1)
    a1 = fabriquer_entree_programme(uid="m1",carte_id="c1",auteur_id="j1",type_="mesure",
                                    effets=[{"type":"depenses_poste_delta","params":{"poste":"social","delta":100}}])
    a2 = fabriquer_entree_programme(uid="m2",carte_id="c2",auteur_id="j1",type_="mesure",
                                    effets=[{"type":"depenses_poste_delta","params":{"poste":"social","delta":100}}])
    phase_conseil(etat, [a1, a2], cfg)
    # programme ne contient qu'une mesure (la 2e a été rejetée)
    assert len([e for e in etat.programme.entrees if e.type=="mesure"]) == 1
    assert any(h["type"]=="depot_rejete" for h in etat.historiques)
