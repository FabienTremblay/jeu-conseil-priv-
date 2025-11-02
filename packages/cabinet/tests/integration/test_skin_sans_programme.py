from cabinet.moteur.bootstrap import charger_etat_depuis_yaml

def test_skin_minimal_sans_programme_charge_ok():
    etat = charger_etat_depuis_yaml("packages/cabinet/skins/demo_minimal_sans_programme.yaml")
    assert etat.programme is None
