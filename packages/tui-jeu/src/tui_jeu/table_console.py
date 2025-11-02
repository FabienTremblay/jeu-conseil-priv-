#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import curses
import locale

locale.setlocale(locale.LC_ALL, "")
import time
from typing import Optional

from .client_api import etat_table, table_ready, table_start, ApiErreur

HELP = [
    "[espace] basculer prêt/pas prêt",
    "[s] démarrer (hôte) ou si tous prêts",
    "[r] rafraîchir",
    "[q] quitter (retour lobby)",
]


def _fmt(maxw: int, s: str) -> str:
    s = s or ""
    return s[: maxw - 1] if len(s) >= maxw else s


def _safe_status_line(stdscr, y: int, text: str, attr=0):
    try:
        maxy, maxx = stdscr.getmaxyx()
        if y < 0:
            y = 0
        if y >= maxy:
            y = maxy - 1
        # une seule ligne, pas de retours
        s = (text or "").replace("\n", " ")
        # tronquer en tenant compte de la largeur
        if len(s) > maxx - 1:
            s = s[: maxx - 1]
        stdscr.move(y, 0)
        stdscr.clrtoeol()
        stdscr.addstr(y, 0, s, attr)
    except Exception:
        # en dernier recours : on n’affiche rien plutôt que crasher
        pass


def boucle_table(stdscr, tid: str, nom: str) -> Optional[str]:
    """Retourne pid si démarrée, sinon None si on quitte."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    message = ""
    last = 0.0
    data = {}

    while True:
        now = time.time()
        if now - last > 1.5:
            try:
                data = etat_table(tid)
                # auto-sortie si partie démarrée
                if data.get("demarree") and data.get("partie_id"):
                    return data["partie_id"]
            except ApiErreur as e:
                message = f"Erreur: {e}"
            last = now

        stdscr.erase()
        maxy, maxx = stdscr.getmaxyx()
        stdscr.addstr(
            0,
            0,
            _fmt(maxx, f"Table d’attente — {tid[:8]} | Vous: {nom}"),
            curses.A_BOLD,
        )

        # Infos
        host = data.get("host")
        joueurs = data.get("joueurs", {})  # {nom:ready}
        attendus_min = data.get("attendus_min", 2)
        ready_count = sum(1 for v in joueurs.values() if v)
        total = len(joueurs)

        stdscr.addstr(
            2,
            0,
            _fmt(
                maxx,
                f"Hôte: {host or '(non défini)'} | Joueurs: {total} | Prêts: {ready_count}/{total} | Seuil: {attendus_min}",
            ),
        )
        stdscr.addstr(3, 0, _fmt(maxx, "État des joueurs:"), curses.A_UNDERLINE)
        y = 4
        if not joueurs:
            stdscr.addstr(y, 2, "(en attente d’inscriptions depuis le lobby)")
            y += 1
        else:
            for jn, rd in joueurs.items():
                tag = "✅ prêt" if rd else "⏳ pas prêt"
                mark = " (vous)" if jn == nom else ""
                stdscr.addstr(y, 2, _fmt(maxx, f"- {jn}{mark} — {tag}"))
                y += 1

        # Bandeau “en attente”
        if total < attendus_min:
            stdscr.addstr(
                y + 1,
                0,
                _fmt(maxx, "🟡 En attente de joueurs supplémentaires…"),
                curses.A_BOLD,
            )
        elif ready_count < total:
            stdscr.addstr(
                y + 1,
                0,
                _fmt(maxx, "🟡 Tous les joueurs ne sont pas prêts…"),
                curses.A_BOLD,
            )
        else:
            stdscr.addstr(
                y + 1,
                0,
                _fmt(maxx, "🟢 Tous prêts — l’hôte peut démarrer (touche 's')."),
                curses.A_BOLD,
            )

        # Aide
        stdscr.addstr(y + 3, 0, "Aide :", curses.A_UNDERLINE)
        for i, h in enumerate(HELP):
            stdscr.addstr(y + 4 + i, 2, _fmt(maxx, f"- {h}"))

        if message:
            _safe_status_line(stdscr, stdscr.getmaxyx()[0] - 1, message, curses.A_BOLD)

        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            time.sleep(0.05)
            continue

        if ch in (ord("q"), ord("Q")):
            return None
        elif ch in (ord("r"), ord("R")):
            last = 0
        elif ch == ord(" "):  # bascule prêt
            try:
                cur = bool(joueurs.get(nom, False))
                _ = table_ready(tid, nom, not cur)
                last = 0
            except ApiErreur as e:
                message = f"Erreur prêt: {(e.payload or {}).get('reason') or e}"
        elif ch in (ord("s"), ord("S")):
            try:
                resp = table_start(tid, nom, joueurs)
                if isinstance(resp, dict) and resp.get("ok") and resp.get("pid"):
                    return resp["pid"]
                else:
                    message = "Start refusé"
            except ApiErreur as e:
                message = f"Erreur start: {(e.payload or {}).get('reason') or e}"
