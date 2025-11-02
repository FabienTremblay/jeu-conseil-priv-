#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import curses
from typing import Any, Dict, List, Optional

# 👉 nouveaux imports côté client API (tables)
from .client_api import (
    lister_tables_active_only,
    creer_table_tui,
    table_join,
    ApiErreur,
)

# 👉 quand on entre dans une table, on lance l'écran d'attente
from .table_console import boucle_table


HELP = [
    "[TAB] basculer zone (Nom / Liste / Création)",
    "[↑/↓] naviguer dans la liste des tables",
    "[Entrée] rejoindre la table (ou créer la table)",
    "[r] rafraîchir la liste",
    "[q] quitter",
]


class LobbyResult:
    """Résultat du lobby: PID de la partie démarrée + nom du joueur."""

    def __init__(self, pid: str, joueur_nom: str):
        self.pid = pid
        self.joueur_nom = joueur_nom


def _fmt(maxw: int, s: str) -> str:
    s = s or ""
    return s[: maxw - 1] if len(s) >= maxw else s


def boucle_lobby(stdscr) -> Optional[LobbyResult]:
    """
    Écran de Lobby TUI basé sur les Tables:
      1) l'utilisateur saisit son nom
      2) il choisit une table (liste) pour la rejoindre
      3) ou il crée une table (création)
      4) l'écran 'table_console' s'ouvre; dès que la table démarre, on récupère le PID
      5) on retourne (PID, nom) pour ouvrir la Table de jeu (ui_console)
    """
    curses.curs_set(1)
    stdscr.nodelay(False)
    maxy, maxx = stdscr.getmaxyx()

    # 3 zones éditables/navigables
    zone = "nom"  # "nom" | "liste" | "creation"
    nom = ""  # nom du joueur
    nom_table = ""  # pour la création de la table (facultatif)
    selection = 0

    tables_list: List[Dict[str, Any]] = []
    message = ""

    def refresh_list():
        nonlocal tables_list, selection, message
        try:
            tables_list = lister_tables_active_only()
            # entrée tolérante: s'assurer de certains champs
            norm = []
            for t in tables_list:
                norm.append(
                    {
                        "id": t.get("id"),
                        "nom_table": t.get("nom_table"),
                        "attendus_min": t.get("attendus_min", 2),
                        "joueurs": t.get("joueurs", {}),  # {nom: ready}
                        "host": t.get("host"),
                        "demarree": t.get("demarree", False),
                        "partie_id": t.get("partie_id"),
                    }
                )
            tables_list = sorted(norm, key=lambda p: p.get("id") or "")
            selection = min(selection, max(0, len(tables_list) - 1))
            message = f"{len(tables_list)} table(s)"
        except ApiErreur as e:
            message = f"Erreur API /tables: {e}"

    refresh_list()

    while True:
        stdscr.erase()
        maxy, maxx = stdscr.getmaxyx()
        stdscr.addstr(
            0, 0, _fmt(maxx, "Lobby — Jeu d'aventure politique (Tables)"), curses.A_BOLD
        )

        # Aide
        stdscr.addstr(2, 0, "Aide :", curses.A_UNDERLINE)
        for i, h in enumerate(HELP):
            stdscr.addstr(3 + i, 2, _fmt(maxx, f"- {h}"))

        # Zone Nom (identité joueur)
        y = 3 + len(HELP) + 1
        stdscr.addstr(y, 0, "Votre nom (identification):", curses.A_UNDERLINE)
        attr_nom = curses.A_REVERSE if zone == "nom" else curses.A_NORMAL
        stdscr.addstr(
            y + 1, 2, _fmt(maxx, nom if nom else "(entrez votre nom)"), attr_nom
        )

        # Liste des tables existantes
        yl = y + 3
        stdscr.addstr(yl, 0, "Tables existantes:", curses.A_UNDERLINE)
        if not tables_list:
            stdscr.addstr(yl + 1, 2, "(aucune)")
        else:
            for idx, t in enumerate(tables_list):
                joueurs = t.get("joueurs", {})
                ready_count = sum(1 for v in joueurs.values() if v)
                total = len(joueurs)
                line = (
                    f"{(t.get('id') or '')[:8]}  | "
                    f"nom:{t.get('nom_table') or '-'}  | "
                    f"joueurs:{total} (prêts:{ready_count})  | "
                    f"seuil:{t.get('attendus_min', 2)}  | "
                    f"{'DEMARRÉE' if t.get('demarree') else 'en attente'}"
                )
                attr = (
                    curses.A_REVERSE
                    if (zone == "liste" and idx == selection)
                    else curses.A_NORMAL
                )
                stdscr.addstr(yl + 1 + idx, 2, _fmt(maxx, line), attr)

        # Zone Création de table
        yc = yl + 2 + max(1, len(tables_list))
        stdscr.addstr(yc, 0, "Créer une table (nom facultatif) :", curses.A_UNDERLINE)
        attr_crea = curses.A_REVERSE if zone == "creation" else curses.A_NORMAL
        placeholder = (
            nom_table
            if nom_table
            else "(ex: 'Salon du samedi') — seuil=2, règles par défaut"
        )
        stdscr.addstr(yc + 1, 2, _fmt(maxx, placeholder), attr_crea)

        # Message bas
        if message:
            stdscr.addstr(maxy - 1, 0, _fmt(maxx, message), curses.A_BOLD)

        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (ord("q"), ord("Q")):
            return None
        elif ch == 9:  # TAB
            zone = (
                "liste" if zone == "nom" else ("creation" if zone == "liste" else "nom")
            )
            curses.curs_set(1 if zone in ("nom", "creation") else 0)

        elif zone == "nom":
            if ch in (10, 13):  # Enter => rien
                pass
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                nom = nom[:-1]
            elif 32 <= ch <= 126:
                nom += chr(ch)

        elif zone == "creation":
            if ch in (10, 13):  # Enter => créer table puis ouvrir écran d'attente
                if not nom:
                    message = "Entrez votre nom (zone Nom) avant de créer."
                    continue
                try:
                    resp = creer_table_tui(
                        nom_table=(nom_table or None), attendus_min=2, regles_file=None
                    )
                    tid = resp["table"]["id"]
                    # l'auteur rejoint comme joueur de la table
                    _ = table_join(tid, nom)
                    # ouvre l'écran d'attente; quand la table démarre → PID
                    pid = boucle_table(stdscr, tid, nom)
                    if pid:
                        return LobbyResult(pid, nom)
                    else:
                        # revenu du screen table sans démarrage
                        message = "Retour lobby."
                        curses.curs_set(1)
                except ApiErreur as e:
                    message = (
                        f"Création refusée: {(e.payload or {}).get('reason') or str(e)}"
                    )
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                nom_table = nom_table[:-1]
            elif 32 <= ch <= 126:
                nom_table += chr(ch)

        elif zone == "liste":
            if ch in (curses.KEY_UP, ord("k")):
                selection = max(0, selection - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                selection = min(max(0, len(tables_list) - 1), selection + 1)
            elif ch in (ord("r"), ord("R")):
                refresh_list()
            elif ch in (10, 13):  # Enter => rejoindre la table + ouvrir écran attente
                if not nom:
                    message = "Entrez votre nom (zone Nom) avant de rejoindre."
                    continue
                if not tables_list:
                    message = "Aucune table à rejoindre."
                    continue
                t = tables_list[selection]
                tid = t.get("id")
                if not tid:
                    message = "Table invalide."
                    continue
                try:
                    _ = table_join(tid, nom)
                    pid = boucle_table(stdscr, tid, nom)  # attend le démarrage
                    if pid:
                        return LobbyResult(pid, nom)
                    else:
                        message = "Retour lobby."
                        curses.curs_set(1)
                except ApiErreur as e:
                    message = (
                        f"Erreur join: {(e.payload or {}).get('reason') or str(e)}"
                    )
