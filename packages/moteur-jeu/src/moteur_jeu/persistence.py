from __future__ import annotations
from typing import Any, Dict
import json
from pathlib import Path
from .moteur import EtatJeu, Joueur, Evenement


def etat_to_dict(etat: EtatJeu) -> Dict[str, Any]:
    return {
        "id": etat.id,
        "tour": etat.tour,
        "tension": etat.tension,
        "joueurs": {
            jid: {"id": j.id, "nom": j.nom, "role": j.role, "attention": j.attention}
            for jid, j in etat.joueurs.items()
        },
        "contentieux": etat.contentieux,
        "pile_evenements": [
            {"type": e.type, "donnees": e.donnees, "ts": e.ts}
            for e in etat.pile_evenements
        ],
        "partie_status": etat.partie_status,
        "raison_fin": etat.raison_fin,
        "max_tours": etat.max_tours,
        "rng_seed": etat.rng_seed,
        "rng_calls": etat.rng_calls,
        "journal": etat.journal,  # déjà sérialisable
    }


def etat_from_dict(d: Dict[str, Any]) -> EtatJeu:
    joueurs = {jid: Joueur(**jd) for jid, jd in d.get("joueurs", {}).items()}
    evts = [
        Evenement(type=e["type"], donnees=e["donnees"], ts=e.get("ts", 0.0))
        for e in d.get("pile_evenements", [])
    ]
    etat = EtatJeu(
        id=d["id"],
        tour=d.get("tour", 1),
        tension=d.get("tension", 0),
        joueurs=joueurs,
        pile_evenements=evts,
        contentieux=d.get("contentieux", {}),
        partie_status=d.get("partie_status", "en_cours"),
        raison_fin=d.get("raison_fin"),
        max_tours=d.get("max_tours", 8),
        rng_seed=d.get("rng_seed", 42),
        rng_calls=d.get("rng_calls", 0),
        journal=d.get("journal", []),
    )
    return etat


def sauvegarder(etat: EtatJeu, path: str, meta: Dict[str, Any] | None = None) -> None:
    payload = {"etat": etat_to_dict(etat), "meta": meta or {}}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def charger(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def moteur_depuis_fichier(path: str) -> "Moteur":
    from .moteur import Moteur

    data = charger(path)
    etat = etat_from_dict(data["etat"])
    return Moteur(etat=etat)
