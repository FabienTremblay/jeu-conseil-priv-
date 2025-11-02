import pytest
from cabinet.moteur.moteur import init_etat_from_cfg, fabriquer_entree_programme
from cabinet.moteur.phases import phase_conseil

@pytest.mark.unit
def test_capacite_par_charges_rejet_si_depassement():
    """
    Mode 'charges' : somme des charge_admin des mesures ne doit pas dépasser le plafond.
    On donne 3 comme plafond. Deux mesures de charge 2 chacune => la 2e est rejetée.
    """
    cfg = {
        "axes_tension": [{"id": "pauvrete", "valeur_init": 3, "seuil_crise": 8}],
        "economie_initiale": {
            "taux_impot_part": 0.2, "taux_impot_ent": 0.18, "taux_redevances": 0.1, "taux_interet": 0.03,
            "base_part": 100000, "base_ent": 80000, "base_ressources": 50000,
            "depenses_postes": {"social": 500}, "dette": 1000, "capacite_max": 3, "efficience": 1.0
        },
        "contraintes": {"capacite_admin_max": 3, "capacite_admin_mode": "charges"},
        # IMPORTANT: cartes avec charge_admin pour que validation lise etat.cartes_def
        "cartes": [
            {"id": "c1", "type": "mesure", "charge_admin": 2,
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
            {"id": "c2", "type": "mesure", "charge_admin": 2,
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
        ],
        "perturbateurs_tour": []
    }
    etat = init_etat_from_cfg(cfg, [{"id": "j1", "nom": "Alice"}])

    a1 = fabriquer_entree_programme(uid="m1", carte_id="c1", auteur_id="j1", type_="mesure")
    a2 = fabriquer_entree_programme(uid="m2", carte_id="c2", auteur_id="j1", type_="mesure")

    phase_conseil(etat, [a1, a2], cfg)

    mesures = [e for e in etat.programme.entrees if e.type == "mesure"]
    assert len(mesures) == 1  # la 2e a été rejetée
    # on vérifie que le rejet est bien dû à la charge
    raisons = [h.get("raison", "") for h in etat.historiques if h.get("type") == "depot_rejete"]
    assert any("capacite_admin_charge depassee" in r for r in raisons)


@pytest.mark.unit
def test_capacite_par_charges_accepte_si_sous_plafond():
    """
    Plafond 3, mesures de charges 1 et 2 => total 3 (OK).
    Les deux mesures doivent être acceptées.
    """
    cfg = {
        "axes_tension": [{"id": "pauvrete", "valeur_init": 3, "seuil_crise": 8}],
        "economie_initiale": {
            "taux_impot_part": 0.2, "taux_impot_ent": 0.18, "taux_redevances": 0.1, "taux_interet": 0.03,
            "base_part": 100000, "base_ent": 80000, "base_ressources": 50000,
            "depenses_postes": {"social": 500}, "dette": 1000, "capacite_max": 3, "efficience": 1.0
        },
        "contraintes": {"capacite_admin_max": 3, "capacite_admin_mode": "charges"},
        "cartes": [
            {"id": "c1", "type": "mesure", "charge_admin": 1,
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
            {"id": "c2", "type": "mesure", "charge_admin": 2,
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
        ],
        "perturbateurs_tour": []
    }
    etat = init_etat_from_cfg(cfg, [{"id": "j1", "nom": "Alice"}])

    a1 = fabriquer_entree_programme(uid="m1", carte_id="c1", auteur_id="j1", type_="mesure")
    a2 = fabriquer_entree_programme(uid="m2", carte_id="c2", auteur_id="j1", type_="mesure")

    phase_conseil(etat, [a1, a2], cfg)

    mesures = [e for e in etat.programme.entrees if e.type == "mesure"]
    assert len(mesures) == 2  # total charges = 3 => OK
    # pas de rejet pour charge
    raisons = [h.get("raison", "") for h in etat.historiques if h.get("type") == "depot_rejete"]
    assert all("capacite_admin_charge depassee" not in r for r in raisons)


@pytest.mark.unit
def test_capacite_mode_defaut_compter_mesures_reste_retro_compatible():
    """
    Sans capacite_admin_mode, on reste en mode rétro-compat 'compter_mesures'.
    Plafond = 1 => la 2e mesure est rejetée avec le message historique classique.
    """
    cfg = {
        "axes_tension": [{"id": "pauvrete", "valeur_init": 3, "seuil_crise": 8}],
        "economie_initiale": {
            "taux_impot_part": 0.2, "taux_impot_ent": 0.18, "taux_redevances": 0.1, "taux_interet": 0.03,
            "base_part": 100000, "base_ent": 80000, "base_ressources": 50000,
            "depenses_postes": {"social": 500}, "dette": 1000, "capacite_max": 3, "efficience": 1.0
        },
        "contraintes": {"capacite_admin_max": 1},  # pas de 'capacite_admin_mode'
        "cartes": [
            {"id": "c1", "type": "mesure",
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
            {"id": "c2", "type": "mesure",
             "effets": [{"type": "depenses_poste_delta", "params": {"poste": "social", "delta": 100}}]},
        ],
        "perturbateurs_tour": []
    }
    etat = init_etat_from_cfg(cfg, [{"id": "j1", "nom": "Alice"}])

    a1 = fabriquer_entree_programme(uid="m1", carte_id="c1", auteur_id="j1", type_="mesure")
    a2 = fabriquer_entree_programme(uid="m2", carte_id="c2", auteur_id="j1", type_="mesure")

    phase_conseil(etat, [a1, a2], cfg)

    mesures = [e for e in etat.programme.entrees if e.type == "mesure"]
    assert len(mesures) == 1
    raisons = [h.get("raison", "") for h in etat.historiques if h.get("type") == "depot_rejete"]
    assert any("capacite_admin_max depassee" in r for r in raisons)
