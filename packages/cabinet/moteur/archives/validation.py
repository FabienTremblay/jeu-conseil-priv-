# packages/cabinet/moteur/validation.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from .etat import Etat, EntreeProgramme

def _sum_depenses_delta(entrees: List[EntreeProgramme]) -> int:
    total = 0
    for e in entrees:
        if e.type != "mesure":
            continue
        for eff in e.params.get("_effets_compile", e.params.get("effets", [])):
            if eff.get("type") == "depenses_poste_delta":
                total += int(eff["params"]["delta"])
    return total

def _proj_solde(etat: Etat, entrees: List[EntreeProgramme]) -> int:
    # Projection ultra simple : revenus inchangés, dépenses +Σ delta (service de la dette ignoré ici)
    from .phases import _revenus_annuels, _depenses_totales
    rev = _revenus_annuels(etat.eco)
    dep_act = _depenses_totales(etat.eco)
    dep_proj = dep_act + _sum_depenses_delta(entrees)
    return rev - dep_proj

# --- Nouveau: capacité par "charges" (optionnelle, rétro-compatible) ---------

def _charge_admin_for(etat: Etat, entree: EntreeProgramme) -> int:
    """
    Retourne la 'charge' d'implémentation d'une carte 'mesure'.
    Par défaut 1 si non précisé. Lit dans etat.cartes_def[cid].charge_admin si disponible.
    """
    if entree.type != "mesure":
        return 0
    cid = entree.carte_id
    defn = etat.cartes_def.get(cid, {}) if hasattr(etat, "cartes_def") else {}
    return int(defn.get("charge_admin", 1))

def _capacite_ok(etat: Etat, entrees_actuelles: List[EntreeProgramme], nouvelle: EntreeProgramme, cfg: Dict[str, Any]) -> Tuple[bool, str | None]:
    """
    Deux modes:
      - 'compter_mesures' (défaut, rétro-compat) : plafonne le NOMBRE de mesures.
      - 'charges' : plafonne la SOMME des charges (charge_admin, défaut 1).
    Le plafond utilisé = min(contraintes.capacite_admin_max, etat.eco.capacite_max)
    """
    contraintes = cfg.get("contraintes", {})
    cap_max_cfg = int(contraintes.get("capacite_admin_max", etat.eco.capacite_max))
    cap_mode = contraintes.get("capacite_admin_mode", "compter_mesures")
    cap_plafond = min(cap_max_cfg, getattr(etat.eco, "capacite_max", cap_max_cfg))

    if nouvelle.type != "mesure":
        return True, None

    if cap_mode == "charges":
        courant = sum(_charge_admin_for(etat, e) for e in entrees_actuelles if e.type == "mesure")
        added   = _charge_admin_for(etat, nouvelle)
        total   = courant + added
        if total > cap_plafond:
            return False, f"capacite_admin_charge depassee ({total}/{cap_plafond})"
        return True, None

    # défaut : nombre de mesures
    nb_mesures = sum(1 for e in entrees_actuelles if e.type == "mesure") + 1
    if nb_mesures > cap_plafond:
        return False, f"capacite_admin_max depassee ({nb_mesures}/{cap_plafond})"
    return True, None

def est_carte_admissible(
    etat: Etat, entrees_actuelles: List[EntreeProgramme], nouvelle: EntreeProgramme, cfg: Dict[str, Any]
) -> Tuple[bool, str | None]:
    # 1) capacité (mode rétro-compat par défaut)
    ok, why = _capacite_ok(etat, entrees_actuelles, nouvelle, cfg)
    if not ok:
        return False, why

    # 2) budget minimal projeté (si défini)
    contraintes = cfg.get("contraintes", {})
    budget_min = contraintes.get("budget_min_solde", None)
    if budget_min is not None:
        proj = _proj_solde(etat, [*entrees_actuelles, nouvelle])
        if proj < int(budget_min):
            return False, f"budget_min_solde violé (solde_proj={proj} < {budget_min})"

    return True, None

