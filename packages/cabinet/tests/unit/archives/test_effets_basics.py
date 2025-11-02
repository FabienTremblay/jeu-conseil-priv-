import pytest
from cabinet.moteur.etat import Etat, Axe, Economie
from cabinet.moteur.effets import appliquer_effets
from cabinet.moteur.rng import RngFacade

def _eco_min():
    return Economie(
        taux_impot_part=0.2, taux_impot_ent=0.18, taux_redevances=0.1, taux_interet=0.03,
        base_part=100000, base_ent=80000, base_ressources=50000,
        depenses_postes={"sante": 800, "securite": 700},
        dette=10000, capacite_max=3, efficience=1.0
    )

@pytest.mark.unit
def test_effet_tension_axis_delta_clamp():
    etat = Etat(id="t", tour=1,
                axes={"pauvrete": Axe("pauvrete", 9, seuil_crise=10)},
                eco=_eco_min(), joueurs={})
    rng = RngFacade(123)
    impacts = appliquer_effets(etat, [
        {"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":+5}},
        {"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":-20}},
        {"type":"tension_axis_delta","params":{"axis":"pauvrete","delta":+2}},
    ], rng)
    assert etat.axes["pauvrete"].valeur == 2  # 9 -> 10 -> 0 -> 2
    assert impacts[0]["event"] == "tension_axis_changee"
