import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, run_tour, fabriquer_entree_programme
from cabinet.moteur.rng import RngFacade

@pytest.mark.it
def test_flux_complet_capacite_par_charges():
    """
    Intégration: capacite_admin_mode='charges', plafond=3.
    - Deux mesures proposées: charge 2 puis charge 2 => la seconde est rejetée au Conseil.
    - Vote adopte le programme (1 mesure).
    - Exécution: n'applique qu'une seule fois depenses_poste_delta (+100).
    - Historique: contient 'capacite_admin_charge depassee'.
    """
    cfg = {
        "version": 3,
        "axes_tension": [
            {"id": "pauvrete", "valeur_init": 3, "seuil_crise": 8},
        ],
        "economie_initiale": {
            "taux_impot_part": 0.2, "taux_impot_ent": 0.18, "taux_redevances": 0.1, "taux_interet": 0.03,
            "base_part": 100000, "base_ent": 80000, "base_ressources": 50000,
            "depenses_postes": {"social": 500},
            "dette": 1000, "capacite_max": 3, "efficience": 1.0
        },
        "contraintes": {
            "capacite_admin_max": 3,
            "capacite_admin_mode": "charges"
        },
        # aucun perturbateur pour stabiliser la trajectoire
        "perturbateurs_tour": [],
        # defs de cartes pour que validation lise les charges
        "cartes": [
            {"id": "c1", "type": "mesure", "charge_admin": 2,
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
            {"id": "c2", "type": "mesure", "charge_admin": 2,
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
        ],
        # pas de pioche imposée ici: tests souhaitent déposer directement
    }

    joueurs = [{"id": "j1", "nom": "Alice"}]
    etat = init_etat_from_cfg(cfg, joueurs, partie_id="charges-it-1")
    rng = RngFacade(123)

    # Programme proposé: deux mesures (la 2e doit être rejetée au Conseil par dépassement de charges)
    actions = [
        fabriquer_entree_programme(uid="m1", carte_id="c1", auteur_id="j1", type_="mesure",
                                   effets=[{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]),
        fabriquer_entree_programme(uid="m2", carte_id="c2", auteur_id="j1", type_="mesure",
                                   effets=[{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]),
    ]
    votes = {"j1": True}

    dep_social_avant = etat.eco.depenses_postes["social"]

    etat2 = run_tour(etat, cfg, rng, actions_conseil=actions, votes=votes, procedures_declares=[])

    # Le tour a avancé
    assert etat2.tour == 2

    # Seule la première mesure subsiste dans le programme exécuté
    mesures = [h for h in etat2.historiques if h.get("type") == "mesure_executee"]
    assert len(mesures) == 1
    assert mesures[0]["carte_id"] == "c1"

    # Les dépenses sociales n'ont augmenté que de +100 (et non +200)
    dep_social_apres = etat2.eco.depenses_postes["social"]
    assert dep_social_apres - dep_social_avant == 100

    # Historique: rejet explicite pour dépassement de charges
    rejets = [h for h in etat2.historiques if h.get("type") == "depot_rejete"]
    assert len(rejets) >= 1
    assert any("capacite_admin_charge depassee" in (r.get("raison") or "") for r in rejets)
