from __future__ import annotations
from typing import Dict, Any, List, Deque, Tuple, Callable
from collections import deque
from .etat import Etat, DeckState, EventDeckState, Joueur
from .rng import RngFacade

# ------------------ Helpers ---------------------------------------------------

def _repeat_ids(elem: Dict[str, Any]) -> List[str]:
    cid = elem["id"]
    copies = int(elem.get("copies", 1))
    return [cid] * max(1, copies)

def _weights_for(ids: List[str], defs: Dict[str, Dict[str, Any]]) -> List[float]:
    out = []
    for cid in ids:
        d = defs.get(cid, {})
        out.append(float(d.get("poids", 1.0)))
    return out

# ------------------ Build decks ----------------------------------------------

def build_decks_from_cfg(etat: Etat, cfg: Dict[str, Any], rng: RngFacade) -> None:
    """
    Construit le deck global 'cartes' et le deck d'événements 'perturbateurs_tour'
    à partir du skin, puis enregistre les définitions dans etat.cartes_def.
    """
    # definitions
    cartes_def = {}
    for c in cfg.get("cartes", []) or []:
        cartes_def[c["id"]] = c
    # stocke pour lookup rapide lors de l'exécution
    etat.cartes_def = cartes_def

    # deck global
    ids = []
    for c in cfg.get("cartes", []) or []:
        ids.extend(_repeat_ids(c))
    # mélange initial déterministe
    rng.shuffle_inplace(ids, name="deck_global_init")
    etat.deck_global = DeckState(pioche=deque(ids), defausse=deque())

    # deck events
    ev_ids = []
    ev_defs = {}
    for e in cfg.get("perturbateurs_tour", []) or []:
        ev_defs[e["id"]] = e
        ev_ids.extend(_repeat_ids(e))
    rng.shuffle_inplace(ev_ids, name="deck_events_init")
    etat.deck_events = EventDeckState(pioche=deque(ev_ids), defausse=deque())

    # garder aussi les defs d'événements pour accès pendant tirage monde
    # on les range dans etat.cartes_def sous clé spéciale si tu préfères, mais
    # on peut les relire depuis cfg au moment du tirage (simple).

# ------------------ Draw / discard -------------------------------------------

def draw_from_deck(deck: DeckState, defs: Dict[str, Dict[str, Any]], rng: RngFacade, *, stream="deck.draw", etat=None, cfg=None) -> str | None:
    if not deck.pioche and deck.defausse:
        deck.pioche = deque(list(deck.defausse)); deck.defausse.clear()
    if not deck.pioche:
        return None
    ids = list(deck.pioche)
    ws  = _weights_for(ids, defs)
    if etat is not None and cfg is not None:
        ws = _modulated_weights(ids, defs, ws, etat, cfg, key="cartes")
    pick = rng.choice_weighted(ids, ws, name=stream)
    new_pioche, removed = deque(), False
    for x in deck.pioche:
        if not removed and x == pick: removed = True; continue
        new_pioche.append(x)
    deck.pioche = new_pioche
    return pick

def discard_to_deck(deck: DeckState, card_id: str) -> None:
    deck.defausse.append(card_id)

def draw_event(deck: EventDeckState, ev_defs: Dict[str, Dict[str, Any]] | None, rng: RngFacade, *, stream="events.draw", etat=None, cfg=None) -> str | None:
    if not deck.pioche and deck.defausse:
        deck.pioche = deque(list(deck.defausse)); deck.defausse.clear()
    if not deck.pioche:
        return None
    ids = list(deck.pioche)
    ws = [1.0] * len(ids) if not ev_defs else _weights_for(ids, ev_defs)
    if etat is not None and cfg is not None and ev_defs is not None:
        ws = _modulated_weights(ids, ev_defs, ws, etat, cfg, key="events")
    pick = rng.choice_weighted(ids, ws, name=stream)
    new_pioche, removed = deque(), False
    for x in deck.pioche:
        if not removed and x == pick: removed = True; continue
        new_pioche.append(x)
    deck.pioche = new_pioche
    return pick

# ------------------ Deal aux joueurs -----------------------------------------

def deal_initial_hands(etat: Etat, cfg: Dict[str, Any], rng: RngFacade) -> None:
    rules = cfg.get("pioche", {})
    n = int(rules.get("main_taille_init", 4))
    for j in etat.joueurs.values():
        while len(j.main) < n:
            cid = draw_from_deck(etat.deck_global, etat.cartes_def, rng, stream="deck.deal_init")
            if cid is None:
                break
            j.main.append(cid)

def draw_per_turn(etat: Etat, cfg: Dict[str, Any], rng: RngFacade) -> None:
    rules = cfg.get("pioche", {})
    per_turn = int(rules.get("cartes_par_tour", 1))
    main_max = int(rules.get("main_max", 7))
    for j in etat.joueurs.values():
        for _ in range(per_turn):
            if len(j.main) >= main_max:
                break
            cid = draw_from_deck(etat.deck_global, etat.cartes_def, rng, stream="deck.turn_draw")
            if cid is None:
                break
            j.main.append(cid)


def _test_cond(etat, axis: str, op: str, value: float) -> bool:
    v = etat.axes[axis].valeur
    return (
        (op == ">=" and v >= value) or
        (op == ">"  and v >  value) or
        (op == "<=" and v <= value) or
        (op == "<"  and v <  value) or
        (op == "==" and v == value)
    )

def _match_applies(defs: Dict[str, Dict[str, Any]], cid: str, applies: Dict[str, Any]) -> bool:
    d = defs.get(cid, {})
    if "ids" in applies and cid in applies["ids"]:
        return True
    if "tags" in applies:
        tags = set(d.get("tags", []))
        return bool(tags.intersection(applies["tags"]))
    return False

def _modulated_weights(
    base_ids: List[str],
    base_defs: Dict[str, Dict[str, Any]],
    base_weights: List[float],
    etat,
    cfg: Dict[str, Any],
    key: str,  # 'events' | 'cartes'
) -> List[float]:
    mods = (cfg.get("ponderations_dynamiques", {}) or {}).get(key, []) or []
    if not mods:
        return base_weights
    out = base_weights[:]
    for i, cid in enumerate(base_ids):
        for m in mods:
            cond = m.get("when", {})
            applies = m.get("applies_to", {})
            if cond and _match_applies(base_defs, cid, applies):
                axis = cond.get("axis"); op = cond.get("op", ">="); val = cond.get("value", 0)
                if axis in etat.axes and _test_cond(etat, axis, op, val):
                    out[i] *= float(m.get("factor", 1.0))
    return out

