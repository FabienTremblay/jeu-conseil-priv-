#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import curses
import time
from typing import Any, Dict, List, Optional

from .client_api import (
    creer_partie,
    etat_partie,
    lister_actions_possibles,
    valider_action,
    jouer_action,
    debut_nouveau_tour,
    sauvegarder,
    charger,
    ApiErreur,
)

ACTIONS_CONNUES = ["proposer_reforme", "ouvrir_negociation", "faire_campagne"]

HELP = [
    "[↑/↓] sélectionner une action",
    "[Entrée] jouer l'action",
    "[r] rafraîchir",
    "[n] nouveau tour",
    "[v] sauvegarder  /tmp/partie-reforme.json",
    "[c] charger      /tmp/partie-reforme.json",
    "[q] quitter",
]


def _fmt(maxw: int, s: str) -> str:
    s = s or ""
    return s[: maxw - 1] if len(s) >= maxw else s


def _trouver_joueur_id(etat: Dict[str, Any], nom_joueur: Optional[str]) -> str:
    joueurs = etat.get("joueurs", {})
    if not joueurs:
        raise RuntimeError("Aucun joueur dans l'état de la partie")
    if nom_joueur:
        for j in joueurs.values():
            if j.get("nom") == nom_joueur:
                return j["id"]
        raise RuntimeError(f"Joueur '{nom_joueur}' introuvable")
    return next(iter(joueurs.keys()))


def _dessiner(
    stdscr,
    pid: str,
    jid: str,
    selection: int,
    actions: List[str],
    etat: Dict[str, Any],
    message: str,
):
    stdscr.erase()
    maxy, maxx = stdscr.getmaxyx()

    # En-tête
    titre = f"Jeu d'aventure politique — TUI | Partie: {pid[:8]}"
    stdscr.addstr(0, 0, _fmt(maxx, titre), curses.A_BOLD)

    tour = etat.get("tour")
    phase = etat.get("phase")
    en_inscription = phase == "inscription"
    tension = etat.get("tension")
    statut = etat.get("partie_status")
    contentieux = etat.get("contentieux", {}).get("reforme_x", {})
    soutien = contentieux.get("soutien", 0)

    joueur = etat.get("joueurs", {}).get(jid, {})
    j_nom = joueur.get("nom", "?")
    j_role = joueur.get("role", "?")
    j_attention = joueur.get("attention", 0)
    j_score = joueur.get("score", 0)

    stdscr.addstr(
        2,
        0,
        _fmt(
            maxx,
            f"Tour: {tour}   Phase: {phase}   Tension: {tension}   Statut: {statut}",
        ),
    )
    stdscr.addstr(
        3,
        0,
        _fmt(
            maxx,
            f"Joueur: {j_nom} ({j_role})   Attention: {j_attention}   Score: {j_score}",
        ),
    )
    stdscr.addstr(4, 0, _fmt(maxx, f"Contentieux: Réforme X   Soutien: {soutien}"))
    if en_inscription:
        stdscr.addstr(
            5,
            0,
            _fmt(
                maxx,
                "🟡 Phase d'inscription — en attente d'un second joueur pour démarrer.",
            ),
            curses.A_BOLD,
        )

    # Actions
    stdscr.addstr(6, 0, "Actions jouables :", curses.A_UNDERLINE)
    if not actions:
        stdscr.addstr(
            7, 2, "(aucune — vérifie la phase, l'attention ou les préconditions)"
        )

    for idx, act in enumerate(actions):
        prefix = "→ " if idx == selection else "  "
        attr = curses.A_REVERSE if idx == selection else curses.A_NORMAL
        stdscr.addstr(7 + idx, 0, _fmt(maxx, f"{prefix}{act}"), attr)

    # Aide
    y_help = 7 + max(len(actions), 1) + 1
    stdscr.addstr(y_help, 0, "Aide :", curses.A_UNDERLINE)
    for i, h in enumerate(HELP):
        stdscr.addstr(y_help + 1 + i, 2, _fmt(maxx, f"- {h}"))

    # Message
    if message:
        stdscr.addstr(maxy - 1, 0, _fmt(maxx, message), curses.A_BOLD)

    stdscr.refresh()


def boucle_tui(
    stdscr, pid: Optional[str], joueur_nom: Optional[str], joueur_id: Optional[str]
):
    curses.curs_set(0)
    stdscr.nodelay(True)  # non-bloquant
    selection = 0
    dernier_refresh = 0.0
    message = ""

    # Charger/créer
    if pid:
        etat = etat_partie(pid)
    else:
        data = creer_partie(["Alice", "Bob"])
        pid = data["id"]
        etat = etat_partie(pid)

    # Choix du joueur
    try:
        jid = joueur_id or _trouver_joueur_id(etat, joueur_nom)
    except Exception as ex:
        jid = next(iter(etat.get("joueurs", {}).keys()))
        message = f"⚠️ {ex} — défaut: {jid[:8]}"

    actions = lister_actions_possibles(pid, jid)

    while True:
        now = time.time()
        if now - dernier_refresh > 2.0:
            try:
                etat = etat_partie(pid)
                actions = lister_actions_possibles(pid, jid)
                # 👉 Verrou dur côté TUI
                if etat.get("phase") == "inscription":
                    actions = []  # aucune action clickable
                if selection >= len(actions):
                    selection = max(0, len(actions) - 1)
            except Exception as ex:
                message = f"Erreur rafraîchissement: {ex}"
            dernier_refresh = now

        _dessiner(stdscr, pid, jid, selection, actions, etat, message)
        message = ""

        try:
            ch = stdscr.getch()
        except Exception:
            ch = -1

        if ch == -1:
            time.sleep(0.05)
            continue

        if ch in (curses.KEY_UP, ord("k")):
            selection = max(0, selection - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            selection = min(max(0, len(actions) - 1), selection + 1)
        elif ch in (ord("\n"), curses.KEY_ENTER, 10, 13):
            if etat.get("phase") == "inscription":
                message = "Phase d'inscription — aucune action jouable."
            elif actions:
                act = actions[selection]
                try:
                    v = valider_action(pid, act, jid, {})
                    if not v.get("ok", False):
                        message = f"Refus: {v.get('reason', 'inconnu')}"
                    else:
                        r = jouer_action(pid, act, jid, {})
                        if isinstance(r, dict) and r.get("error") == "refus":
                            message = f"Refus: {r.get('reason', 'inconnu')}"
                        else:
                            message = f"Action jouée: {act}"
                            dernier_refresh = 0
                except ApiErreur as e:
                    reason = (e.payload or {}).get("reason") or str(e)
                    message = f"Erreur: {reason}"

        elif ch in (ord("r"), ord("R")):
            dernier_refresh = 0
        elif ch in (ord("n"), ord("N")):
            if etat.get("phase") == "inscription":
                message = "Phase d'inscription — patiente qu'un second joueur rejoigne."
            else:
                try:
                    _ = debut_nouveau_tour(pid)
                    message = "Nouveau tour."
                    dernier_refresh = 0
                except ApiErreur as e:
                    message = (
                        f"Erreur nouveau tour: {(e.payload or {}).get('reason') or e}"
                    )

        elif ch in (ord("v"), ord("V")):
            try:
                path = "/tmp/partie-reforme.json"
                s = sauvegarder(pid, path)
                if isinstance(s, dict) and s.get("ok"):
                    message = f"Sauvegardé: {path}"
                else:
                    message = "Réponse inattendue sauvegarde"
            except ApiErreur as e:
                message = f"Erreur sauvegarde: {(e.payload or {}).get('reason') or e}"
        elif ch in (ord("c"), ord("C")):
            try:
                path = "/tmp/partie-reforme.json"
                info = charger(path)
                pid = info.get("id", pid)
                message = f"Chargé: PID={pid[:8]} (phase={info.get('phase')})"
                etat = etat_partie(pid)
                if jid not in etat.get("joueurs", {}):
                    jid = _trouver_joueur_id(etat, joueur_nom)
                dernier_refresh = 0
            except ApiErreur as e:
                message = f"Erreur chargement: {(e.payload or {}).get('reason') or e}"
        elif ch in (ord("q"), ord("Q")):
            break
