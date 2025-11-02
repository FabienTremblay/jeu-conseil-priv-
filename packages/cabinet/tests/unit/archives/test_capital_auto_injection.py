import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade

@pytest.mark.unit
def test_capital_politique_delta_cible_auteur_auto_injection():
    """
    Vérifie que l'auteur de la mesure reçoit bien le delta individuel
    même si l'effet 'capital_politique_delta' n'inclut PAS explicitement 'auteur_id'.
    """
    cfg = {
        "axes_tension": [{"id":"axe1","valeur_init":3,"seuil_crise":9,"poids":1.0}],
        "economie_initiale": {
            "taux_impot_part":0.2,"taux_impot_ent":0.18,"taux_redevances":0.1,"taux_interet":0.03,
            "base_part":100000,"base_ent":80000,"base_ressources":50000,
            "depenses_postes":{"social":500},"dette":1000,"capacite_max":3,"efficience":1.0
        },
        # On neutralise l'attribution automatique issue des axes pour isoler l'effet explicite :
        "politique": {"sensibilite_axes": 0.0, "attribution": "aucune"},
        "perturbateurs_tour": []
    }
    joueurs = [{"id":"j1","nom":"Alice"}]
    etat = init_etat_from_cfg(cfg, joueurs)
    rng = RngFacade(123)

    # Effet explicite vers l'auteur SANS 'auteur_id' fourni :
    actions = [
        fabriquer_entree_programme(
            uid="m1", carte_id="mesure_test", auteur_id="j1", type_="mesure",
            effets=[{"type": "capital_politique_delta", "params": {"cible": "auteur", "delta": 3}}]
        )
    ]
    votes = {"j1": True}

    etat2 = run_tour(etat, cfg, rng, actions_conseil=actions, votes=votes, procedures_declares=[])

    assert etat2.joueurs["j1"].capital_politique >= 3, (
        "L'auteur n'a pas reçu le capital individuel attendu. "
        "L'auto-injection de l'auteur_id pour 'cible: auteur' ne semble pas active."
    )
