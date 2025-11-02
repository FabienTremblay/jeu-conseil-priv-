from __future__ import annotations
from typing import List, Dict, Any
from .moteur import Moteur, Action


def rejouer_actions(moteur: Moteur, journal: List[Dict[str, Any]]) -> None:
    """
    Rejoue les 'vraies' actions utilisateur (on ignore les actions _system_*).
    Suppose que le moteur a déjà ses règles YAML chargées et un état initial correspondant.
    """
    for entry in journal:
        act = entry.get("action", {})
        t = act.get("type")
        if not t or t.startswith("_system"):
            continue
        auteur_id = act.get("auteur_id")
        payload = act.get("payload", {})
        moteur.appliquer_action(Action(type=t, auteur_id=auteur_id, payload=payload))
        # si l’entrée représente un changement de tour système, on peut appeler le tour suivant;
        # mais on préfère laisser l’état reconduire via actions utilisateur.
