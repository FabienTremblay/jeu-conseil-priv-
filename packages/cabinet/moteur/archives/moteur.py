# packages/cabinet/moteur/moteur.py
from __future__ import annotations
from typing import Dict, Any, List
from .etat import Etat, Axe, Economie, Joueur
from .phases import (
    phase_monde, phase_conseil, phase_vote_global,
    phase_amendements, phase_execution, phase_cloture
)
from .decks import build_decks_from_cfg, deal_initial_hands, draw_per_turn
from .rng import RngFacade
from .metrics import MetricsSink

def _materialize_cfg_dict(cfg: Any) -> Dict[str, Any]:
    """
    Unifie la config en dict pour les phases, que 'cfg' soit un dict YAML brut
    ou un objet normalisé (avec attributs .rules/.world/.extras).
    """
    if isinstance(cfg, dict):
        return {
            "regle_vote":        cfg.get("regle_vote", {"type": "majorite_simple"}),
            "contraintes":       cfg.get("contraintes", {}),
            "perturbateurs_tour":cfg.get("perturbateurs_tour", []),
            "cartes":            cfg.get("cartes", []),
            "pioche":            cfg.get("pioche", {}),
        }
    # objet : on essaie via attributs (duck typing)
    rules = getattr(cfg, "rules", None)
    world = getattr(cfg, "world", None)
    extras = getattr(cfg, "extras", None)

    regle_vote  = getattr(rules, "regle_vote", getattr(cfg, "regle_vote", {"type": "majorite_simple"}))
    contraintes = getattr(rules, "contraintes", getattr(cfg, "contraintes", {}))
    perturbs    = getattr(world, "perturbateurs_tour", getattr(cfg, "perturbateurs_tour", []))
    cartes      = getattr(extras, "cartes", getattr(cfg, "cartes", []))
    pioche      = getattr(extras, "pioche", getattr(cfg, "pioche", {}))

    return {
        "regle_vote": regle_vote,
        "contraintes": contraintes,
        "perturbateurs_tour": perturbs,
        "cartes": cartes,
        "pioche": pioche,
    }

# --- API publique -------------------------------------------------------------

def fabriquer_entree_programme(
    *,
    uid: str,
    carte_id: str,
    auteur_id: str,
    type_: str,                 # "mesure" | "amendement" | "procedure"
    effets: List[Dict[str, Any]] | None = None,
    params: Dict[str, Any] | None = None,
    tags: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Fabrique une action 'deposer' conforme à la phase Conseil.
    Retourne un dict de la forme:
    {
      "type": "deposer",
      "entree": {
        "uid": "...", "carte_id": "...", "auteur_id": "...",
        "type": "mesure|amendement|procedure",
        "params": {"effets":[...], ...},
        "tags": [...]
      }
    }
    """
    p = dict(params or {})
    if effets:
        # convention: les tests/engine lisent 'params.effets' si présent
        p.setdefault("effets", effets)
    return {
        "type": "deposer",
        "entree": {
            "uid": uid,
            "carte_id": carte_id,
            "auteur_id": auteur_id,
            "type": type_,
            "params": p,
            "tags": list(tags or []),
        },
    }

def init_etat_from_cfg(cfg: Any, joueurs_meta: List[Dict[str, str]], *, partie_id: str = "demo") -> Etat:
    """Construit un Etat minimal à partir d’un dict de config (ou objet normalisé) + liste de joueurs."""
    axes = {
        a["id"]: Axe(
            id=a["id"],
            valeur=int(a.get("valeur_init", a.get("start", 3))),
            seuil_crise=int(a["seuil_crise"]),
            poids=float(a.get("poids", 1.0)),
        )
        for a in (cfg.get("axes_tension", []) if isinstance(cfg, dict) else getattr(cfg, "axes_tension", []))
    }

    eco_cfg = (cfg["economie_initiale"] if isinstance(cfg, dict) else getattr(cfg, "economie_initiale"))
    eco = Economie(
        taux_impot_part=float(eco_cfg["taux_impot_part"]),
        taux_impot_ent=float(eco_cfg["taux_impot_ent"]),
        taux_redevances=float(eco_cfg["taux_redevances"]),
        taux_interet=float(eco_cfg["taux_interet"]),
        base_part=int(eco_cfg["base_part"]),
        base_ent=int(eco_cfg["base_ent"]),
        base_ressources=int(eco_cfg["base_ressources"]),
        depenses_postes=dict(eco_cfg["depenses_postes"]),
        dette=int(eco_cfg["dette"]),
        capacite_max=int(eco_cfg["capacite_max"]),
        efficience=float(eco_cfg.get("efficience", 1.0)),
    )

    joueurs = { j["id"]: Joueur(id=j["id"], nom=j.get("nom", j["id"])) for j in joueurs_meta }

    etat = Etat(id=partie_id, tour=1, axes=axes, eco=eco, joueurs=joueurs)

    ver = getattr(cfg, "version", None)
    if ver is None:
        ver = (cfg.get("version", 3) if isinstance(cfg, dict) else 3)
    etat.historiques.append({"type": "engine_config_loaded", "version": ver})

    # dict de config pour les phases et les decks
    cfg_dict = _materialize_cfg_dict(cfg)
    etat._cfg_for_phases = cfg_dict

    # decks + mains initiales (seeds dédiées pour ne pas “polluer” rng de partie)
    build_decks_from_cfg(etat, cfg_dict, RngFacade(999_123))
    deal_initial_hands(etat, cfg_dict, RngFacade(111_777))
    return etat

def run_tour(
    etat: Etat,
    cfg: Dict[str, Any],
    rng: RngFacade,
    *,
    actions_conseil: List[Dict[str, Any]] | None = None,
    votes: Dict[str, bool] | None = None,
    procedures_declares: List[Dict[str, Any]] | None = None,
    metrics=None,
) -> Etat:
    if etat.termine:
        return etat

    if metrics is not None:
        etat._metrics = metrics
        metrics.start_tour(etat)

    # pioche du tour
    draw_per_turn(etat, cfg, rng)

    phase_monde(etat, cfg, rng)


    if actions_conseil:
         phase_conseil(etat, actions_conseil, cfg)

    is_cycles = bool(actions_conseil and isinstance(actions_conseil, list)
                     and len(actions_conseil) > 0 and isinstance(actions_conseil[0], dict)
                     and ("actions" in actions_conseil[0]))

    adopte = False
    if votes and not is_cycles:
        adopte = phase_vote_global(etat, votes)
    elif is_cycles:
        # le Conseil a déjà voté : adopté ssi un projet existe et des votes y sont attachés
        adopte = (len(etat.programme.entrees) > 0) and bool(etat.programme.votes)

    if adopte:
        phase_amendements(etat, cfg, rng)
        phase_execution(etat, cfg, rng, procedures_declares or [])

    phase_cloture(etat, cfg, rng)

    if metrics is not None:
        metrics.end_tour(etat)

    etat.tour += 1
    return etat

