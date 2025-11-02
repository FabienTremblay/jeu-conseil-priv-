#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from typing import Any, Dict, List

import requests

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8080")


class ApiErreur(Exception):
    """Erreur applicative renvoyée par l'API FastAPI (erreurs normalisées)."""

    def __init__(self, message: str, payload: Dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {}


def _get(path: str) -> Dict[str, Any]:
    r = requests.get(f"{API_BASE}{path}", timeout=5)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        raise
    if r.status_code >= 400:
        raise ApiErreur(data.get("error", "http_error"), data)
    return data


def _post(path: str, payload: Any) -> Any:
    headers = {"Content-Type": "application/json"}
    r = requests.post(
        f"{API_BASE}{path}", headers=headers, data=json.dumps(payload), timeout=5
    )
    text = r.text
    try:
        return r.json()
    except Exception:
        if r.status_code >= 400:
            # remonte une erreur applicative avec le corps brut pour debug
            raise ApiErreur(f"http_error_{r.status_code}", {"raw": text})
        # tolérance: certains endpoints peuvent répondre "OK" / vide
        if (text or "").strip().lower() in ("ok", "true", ""):
            return {"ok": True, "raw": text}
        # à défaut, on renvoie une erreur claire au lieu de crasher
        raise ApiErreur("invalid_non_json_success", {"raw": text})


# --- Endpoints principaux ------------------------------------------------------
def lister_parties() -> list[dict]:
    """Attend que l'API GET /parties renvoie une liste de parties.
    Chaque item peut être un dict minimal: {"id":..., "tour":..., "phase":..., "partie_status":...}
    """
    data = _get("/parties")
    # tolérant: si l'API renvoie un dict {id: etat,...}, on adapte
    if isinstance(data, dict):
        return [
            {"id": k, **(v if isinstance(v, dict) else {})} for k, v in data.items()
        ]
    return data if isinstance(data, list) else []


def creer_partie(noms: List[str]) -> Dict[str, Any]:
    return _post("/parties", noms)


def inscrire_joueur(pid: str, nom: str) -> dict:
    """Renvoie: {"ok": True, "joueur": {...}} ou lève ApiErreur."""
    return _post(f"/parties/{pid}/inscrire", {"nom": nom})


def etat_partie(pid: str) -> Dict[str, Any]:
    return _get(f"/parties/{pid}")


def lister_actions_possibles(pid: str, joueur_id: str) -> List[str]:
    try:
        data = _get(f"/parties/{pid}/actions/possibles?joueur_id={joueur_id}")
        return data.get("possibles", [])
    except ApiErreur:
        return []


def valider_action(
    pid: str, type_action: str, joueur_id: str, payload: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    body = {"type": type_action, "auteur_id": joueur_id, "payload": payload or {}}
    return _post(f"/parties/{pid}/actions/valider", body)


def jouer_action(
    pid: str, type_action: str, joueur_id: str, payload: Dict[str, Any] | None = None
) -> Any:
    body = {"type": type_action, "auteur_id": joueur_id, "payload": payload or {}}
    return _post(f"/parties/{pid}/actions", body)


def debut_nouveau_tour(pid: str) -> Any:
    return _post(f"/parties/{pid}/tour/debut", {})


def sauvegarder(pid: str, path: str) -> Any:
    return _post(f"/parties/{pid}/save", {"path": path})


def charger(path: str) -> Any:
    return _post("/parties/load", {"path": path})


def lister_tables() -> list[dict]:
    return _get("/tables")


def creer_table_tui(
    nom_table: str | None = None, attendus_min: int = 2, regles_file: str | None = None
) -> dict:
    return _post(
        "/tables",
        {
            "nom_table": nom_table,
            "attendus_min": attendus_min,
            "regles_file": regles_file,
        },
    )


def table_join(tid: str, nom: str) -> dict:
    return _post(f"/tables/{tid}/join", {"nom": nom})


def table_ready(tid: str, nom: str, ready: bool) -> dict:
    return _post(f"/tables/{tid}/ready", {"nom": nom, "ready": ready})


def table_start(tid: str, nom: str, joueurs: dict[str, bool]) -> dict:
    """
    Lance la partie à partir d'une table.
    On envoie tous les noms inscrits (les clés du dict joueurs).
    """
    noms = list(joueurs.keys())
    body = {"host": nom, "joueurs": noms}
    return _post(f"/tables/{tid}/start", body)


def etat_table(tid: str) -> dict:
    return _get(f"/tables/{tid}")


def lister_tables_active_only() -> list[dict]:
    return _get("/tables?active_only=1")
