# packages/cabinet/moteur/factories.py
from __future__ import annotations
from typing import Any, Dict, Deque, List, Optional
from collections import deque
from .etat import (
    Etat, Axe, AxeId, Economie, Joueur,
    DeckState, EventDeckState, ProgrammeTour, EntreeProgramme
)

# --------- Helpers de validation/coercition ----------------------------------

def _as_int(x: Any, *, min_: int | None = None, max_: int | None = None) -> int:
    if isinstance(x, bool):
        raise ValueError("booléen reçu là où un entier est attendu")
    try:
        v = int(x)
    except Exception:
        raise ValueError(f"entier invalide: {x!r}")
    if min_ is not None and v < min_:
        raise ValueError(f"{v} < min {min_}")
    if max_ is not None and v > max_:
        raise ValueError(f"{v} > max {max_}")
    return v

def _as_float(x: Any, *, min_: float | None = None, max_: float | None = None) -> float:
    try:
        v = float(x)
    except Exception:
        raise ValueError(f"nombre invalide: {x!r}")
    if min_ is not None and v < min_ - 1e-12:
        raise ValueError(f"{v} < min {min_}")
    if max_ is not None and v > max_ + 1e-12:
        raise ValueError(f"{v} > max {max_}")
    return v

def _as_str(x: Any) -> str:
    if not isinstance(x, str):
        raise ValueError(f"chaîne attendue, reçu: {type(x).__name__}")
    s = x.strip()
    if not s:
        raise ValueError("chaîne vide")
    return s

def _as_deque_str(xs: Any) -> Deque[str]:
    if xs is None:
        return deque()
    if not isinstance(xs, (list, tuple)):
        raise ValueError("liste attendue pour constituer une file")
    return deque(_as_str(e) for e in xs)

# --------- Constructions unitaires -------------------------------------------

def construire_axes(cfg: Dict[str, Any]) -> Dict[AxeId, Axe]:
    axes_cfg = cfg["axes_tension"]
    axes: Dict[AxeId, Axe] = {}
    for item in axes_cfg:
        axe_id = _as_str(item["id"])
        valeur = _as_int(item["valeur"], min_=0, max_=10)
        seuil = _as_int(item["seuil_crise"], min_=0, max_=10)
        poids = _as_float(item.get("poids", 1.0), min_=0.0)
        axes[axe_id] = Axe(id=axe_id, valeur=valeur, seuil_crise=seuil, poids=poids)
        axes[axe_id].clamp()
    return axes

def construire_economie(cfg: Dict[str, Any]) -> Economie:
    eco_cfg = cfg["economie_initiale"]
    return Economie(
        taux_impot_part=_as_float(eco_cfg["taux_impot_part"], min_=0.0, max_=1.0),
        taux_impot_ent=_as_float(eco_cfg["taux_impot_ent"], min_=0.0, max_=1.0),
        taux_redevances=_as_float(eco_cfg["taux_redevances"], min_=0.0, max_=1.0),
        taux_interet=_as_float(eco_cfg["taux_interet"], min_=0.0, max_=1.0),
        base_part=_as_int(eco_cfg["base_part"], min_=0),
        base_ent=_as_int(eco_cfg["base_ent"], min_=0),
        base_ressources=_as_int(eco_cfg["base_ressources"], min_=0),
        depenses_postes={
            _as_str(k): _as_int(v, min_=0) for k, v in dict(eco_cfg["depenses_postes"]).items()
        },
        dette=_as_int(eco_cfg["dette"], min_=0),
        capacite_max=_as_int(eco_cfg["capacite_max"], min_=0),
        efficience=_as_float(eco_cfg["efficience"], min_=0.0, max_=1.0),
    )

def construire_joueurs(cfg: Dict[str, Any]) -> Dict[str, Joueur]:
    """
    Schéma canonique (propre) attendu :
      joueurs: {
        "<id>": { nom: str, capital: int, main?: [], defausse?: [] },
        ...
      }
    """
    raw = cfg.get("joueurs") or {}
    if not isinstance(raw, dict):
        raise ValueError("Schéma invalide pour 'joueurs' : mapping {id: {...}} attendu.")

    joueurs: Dict[str, Joueur] = {}
    for jid, jd in raw.items():
        jd = jd or {}
        nom = _as_str(jd.get("nom", jid))
        # YAML propre: 'capital' ; on l’injecte dans le dataclass sous 'capital_politique'
        cap = _as_int(jd.get("capital", 0), min_=0)
        main = list(jd.get("main") or [])
        defausse = list(jd.get("defausse") or [])
        joueurs[_as_str(jid)] = Joueur(
            id=_as_str(jid),
            nom=nom,
            capital_politique=cap,
            main=main,
            defausse=defausse,
        )
    return joueurs

def construire_decks(cfg: Dict[str, Any]) -> tuple[DeckState, EventDeckState]:
    deck_cfg = cfg.get("deck_global", {})
    ev_cfg = cfg.get("deck_events", {})

    deck = DeckState(
        pioche=_as_deque_str(deck_cfg.get("pioche")),
        defausse=_as_deque_str(deck_cfg.get("defausse")),
    )
    deck_ev = EventDeckState(
        pioche=_as_deque_str(ev_cfg.get("pioche")),
        defausse=_as_deque_str(ev_cfg.get("defausse")),
    )
    return deck, deck_ev

def construire_programme(cfg: Dict[str, Any]) -> ProgrammeTour:
    """
    Construit un ProgrammeTour **si** une section 'programme' est fournie.
    Retourne None sinon : le programme n'est pas requis au démarrage.
    """
    p = cfg.get("programme")
    if not p:
        return None
    entrees_cfg = p.get("entrees") or []
    entrees: List[EntreeProgramme] = []
    for e in entrees_cfg:
        entrees.append(
            EntreeProgramme(
                uid=_as_str(e["uid"]),
                carte_id=_as_str(e["carte_id"]),
                auteur_id=_as_str(e["auteur_id"]),
                type=_as_str(e["type"]),  # "mesure" | "amendement" | "procedure"
                params=dict(e.get("params") or {}),
                tags=list(map(_as_str, e.get("tags") or [])),
            )
        )
    votes = { _as_str(k): bool(v) for k, v in dict(p.get("votes") or {}).items() }
    return ProgrammeTour(version=int(p.get("version", 1)), entrees=entrees, votes=votes)

# --------- Construction d’un Etat complet ------------------------------------

def construire_etat(cfg: Dict[str, Any]) -> Etat:
    """
    Construit un Etat cohérent à partir d’un dict de configuration (déjà validé).
    Attend typiquement les clés suivantes:
      - axes_tension (list)
      - economie_initiale (dict)
      - perturbateurs_tour (list) [optionnel pour l’etat, mais utile aux événements]
      - joueurs (list) [optionnel]
      - deck_global / deck_events (dict) [optionnels]
      - programme (dict) [optionnel]
      - cartes_def (dict) [optionnel]
    """
    axes = construire_axes(cfg)
    eco = construire_economie(cfg)
    joueurs = construire_joueurs(cfg)
    deck_global, deck_events = construire_decks(cfg)
    programme = construire_programme(cfg)

    return Etat(
        # ordre: partie_id > meta.id > "partie-1"
        id=_as_str(cfg.get("partie_id") or (cfg.get("meta") or {}).get("id") or "partie-1"),
        tour=_as_int(cfg.get("tour_initial", 1), min_=0),
        axes=axes,
        eco=eco,
        joueurs=joueurs,
        programme=programme,
        capital_collectif=_as_int(cfg.get("capital_collectif", 0), min_=0),
        historiques=list(cfg.get("historiques") or []),  # tu peux typer plus strictement si besoin
        termine=bool(cfg.get("termine", False)),
        raison_fin=cfg.get("raison_fin"),
        cartes_def=dict(cfg.get("cartes_def") or {}),
        deck_global=deck_global,
        deck_events=deck_events,
    )

