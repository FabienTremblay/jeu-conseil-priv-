import pytest
from cabinet.moteur.rng import RngFacade

@pytest.mark.unit
def test_rng_deterministe_choice_weighted():
    r1, r2 = RngFacade(42), RngFacade(42)
    bag = ["A","B","C"]
    w   = [1.0, 2.0, 3.0]
    picks1 = [r1.choice_weighted(bag, w, name="test") for _ in range(20)]
    picks2 = [r2.choice_weighted(bag, w, name="test") for _ in range(20)]
    assert picks1 == picks2
