#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import signal
import curses
from typing import Optional

from .lobby_console import boucle_lobby
from .ui_console import boucle_tui


def _run_lobby_then_table(stdscr, force_pid, force_nom, force_jid):
    if force_pid and (force_nom or force_jid):
        return boucle_tui(stdscr, force_pid, force_nom, force_jid)

    res = boucle_lobby(stdscr)  # attend que la table démarre -> renvoie PID & nom
    if res is None:
        return
    return boucle_tui(stdscr, res.pid, res.joueur_nom, None)


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(
        description="TUI (texte) — Lobby + Table pour le Jeu d'aventure politique."
    )
    parser.add_argument(
        "--partie",
        help="ID de la partie (si fourni et --joueur/--joueur-id, saute le lobby)",
        default=None,
    )
    parser.add_argument("--joueur", help="Nom du joueur", default=None)
    parser.add_argument(
        "--joueur-id", help="ID du joueur (prioritaire sur --joueur)", default=None
    )
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, lambda *_: exit(0))
    curses.wrapper(_run_lobby_then_table, args.partie, args.joueur, args.joueur_id)


if __name__ == "__main__":
    main()
