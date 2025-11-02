# packages/cabinet/tests/unit/test_decks_basic.py
import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade

@pytest.mark.unit
def test_deck_draw_and_defausse():
    cfg = {
        "axes_tension":[{"id":"pauvrete","valeur_init":3,"seuil_crise":8}],
        "economie_initiale":{"taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
                             "base_part":100000,"base_ent":80000,"base_ressources":50000,
                             "depenses_postes":{"social":500},"dette":1000,"capacite_max":3,"efficience":1.0},
        "pioche":{"main_taille_init":2,"cartes_par_tour":1,"main_max":5},
        "cartes":[
            {"id":"c1","type":"mesure","copies":2,"effets":[{"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":-1}}]},
            {"id":"c2","type":"procedure","copies":1,"effets":[{"type":"emit_event","params":{"kind":"noop"}}]}
        ],
        "perturbateurs_tour":[]
    }
    etat = init_etat_from_cfg(cfg, [{"id":"j1","nom":"Alice"}], partie_id="g1")
    rng = RngFacade(42)
    # la main initiale contient 2 cartes tirées du deck
    assert len(etat.joueurs["j1"].main) == 2
    # déposer la 1ère carte
    cid = etat.joueurs["j1"].main[0]
    actions = [fabriquer_entree_programme(uid="m1", carte_id=cid, auteur_id="j1", type_="mesure",
                effets=[{"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":-1}}])]
    votes = {"j1": True}
    etat2 = run_tour(etat, etat._cfg_for_phases, rng, actions_conseil=actions, votes=votes)
    # carte jouée => défause globale > 0
    assert len(etat2.deck_global.defausse) >= 1
