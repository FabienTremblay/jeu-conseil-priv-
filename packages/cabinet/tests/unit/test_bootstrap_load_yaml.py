from pathlib import Path
from cabinet.moteur.bootstrap import charger_etat_depuis_yaml

def test_charger_yaml_sans_programme(tmp_path: Path):
    yaml_p = tmp_path / "skin.yaml"
    yaml_p.write_text("""
partie_id: p3
tour_initial: 0
axes_tension:
  - { id: cohesion, valeur: 5, seuil_crise: 2, poids: 1.0 }
economie_initiale:
  taux_impot_part: 0.20
  taux_impot_ent: 0.20
  taux_redevances: 0.00
  taux_interet: 0.02
  base_part: 0
  base_ent: 0
  base_ressources: 0
  depenses_postes: {}
  dette: 0
  capacite_max: 3
  efficience: 1.0
joueurs:
  eva: { nom: "Eva", capital: 0 }
""", encoding="utf-8")

    etat = charger_etat_depuis_yaml(str(yaml_p))  # pas de schema_path
    assert etat.programme is None
    assert "cohesion" in etat.axes
    assert "eva" in etat.joueurs
