# packages/cabinet/moteur/metrics.py
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional
import csv, pathlib, time

@dataclass
class TourRow:
    partie_id: str
    tour: int
    axes_moyen: float
    axes_pondere: float
    solde: int
    dette: int
    cap_used: int
    prog_cards: int
    prog_mesures: int
    prog_amendements: int
    prog_procedures: int
    votes_oui: int
    votes_non: int
    scandales: int
    delta_cap_collectif: int

@dataclass
class GameSummary:
    partie_id: string
    tours: int
    fin: str
    cap_collectif_final: int
    duree_s: float
    # extensible: ajouter plus tard (ex: variance axes, nb rejets conseil, etc.)

class MetricsSink:
    """
    Collecteur de métriques “pull-friendly”.
    - on_event(event_dict): appelé à chaque journalisation moteur (si branché)
    - start_tour / end_tour: bornes d’un tour (pour reset/calculs delta)
    - flush_csv: exporte un CSV (un enregistrement par tour)
    """
    def __init__(self, partie_id: str):
        self.partie_id = partie_id
        self.rows: List[TourRow] = []
        self._t0 = time.time()
        # buffers/état de calcul sur un tour
        self._tour_start_cap = 0
        self._cap_used = 0
        self._votes_oui = 0
        self._votes_non = 0
        self._scandales = 0
        self._prog_cards = 0
        self._prog_mesures = 0
        self._prog_amendements = 0
        self._prog_procedures = 0
        self._axes_moyen_cache = 0.0
        self._axes_pondere_cache = 0.0
        self._revenus_cache = 0
        self._depenses_cache = 0
        self._solde_cache = 0
        self._dette_cache = 0

    # --- hooks de cycle ---
    def start_tour(self, etat) -> None:
        self._tour_start_cap = etat.capital_collectif
        # reset
        self._cap_used = 0
        self._votes_oui = 0
        self._votes_non = 0
        self._scandales = 0
        self._prog_cards = 0
        self._prog_mesures = 0
        self._prog_amendements = 0
        self._prog_procedures = 0
        self._axes_moyen_cache = self._calc_axes_moyen(etat)
        self._axes_pondere_cache = self._calc_axes_pondere(etat)

    def end_tour(self, etat) -> None:
        delta_cap = etat.capital_collectif - self._tour_start_cap
        self.rows.append(TourRow(
            partie_id=self.partie_id,
            tour=etat.tour,
            axes_moyen=self._axes_moyen_cache,
            axes_pondere=self._axes_pondere_cache,
            solde=self._solde_cache,
            dette=etat.eco.dette,
            cap_used=self._cap_used,
            prog_cards=self._prog_cards,
            prog_mesures=self._prog_mesures,
            prog_amendements=self._prog_amendements,
            prog_procedures=self._prog_procedures,
            votes_oui=self._votes_oui,
            votes_non=self._votes_non,
            scandales=self._scandales,
            delta_cap_collectif=delta_cap,
        ))

    # --- réception des événements moteur ---
    def on_event(self, ev: Dict[str, Any]) -> None:
        t = ev.get("type")
        if t == "programme_versionnee":
            # recompter le programme courant
            # (utile si tu ajoutes des rejets/retaits au Conseil)
            pass
        elif t == "programme_vote":
            self._votes_oui = int(ev.get("oui", 0))
            self._votes_non = int(ev.get("non", 0))
        elif t == "mesure_executee":
            # heuristique cap_used = nombre de mesures exécutées
            self._cap_used += 1
            self._prog_mesures += 1
            self._prog_cards += 1
        elif t == "programme_amende":
            # approximatif : compter les amendements présents
            self._prog_amendements = self._prog_amendements or 1
        elif t == "perturbateur":
            # rien à stocker ici; visible via axes_moyen
            pass
        elif t == "emit":
            if ev.get("kind") == "scandale":
                self._scandales += 1
        elif t == "cloture_comptable":
            self._revenus_cache = int(ev.get("revenus", 0))
            self._depenses_cache = int(ev.get("depenses", 0))
            self._solde_cache = int(ev.get("solde", 0))
            self._dette_cache = int(ev.get("dette", 0))
        elif t == "depot_rejete":
            # tu peux ajouter un compteur si utile
            pass
        elif t == "defausse_fin_tour":
            # compter les procédures déposées dans le programme :
            # si besoin, fais évoluer on_event pour recevoir l’état
            pass
        # extension: “programme_snapshot” pour compter précisément les types

    # --- exports ---
    def flush_csv(self, path: str | pathlib.Path) -> None:
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(asdict(self.rows[0]).keys()))
            w.writeheader()
            for r in self.rows:
                w.writerow(asdict(r))

    # --- helpers ---
    def _calc_axes_moyen(self, etat) -> float:
        if not etat.axes:
            return 0.0
        return sum(a.valeur for a in etat.axes.values()) / len(etat.axes)

    def _calc_axes_pondere(self, etat) -> float:
        if not etat.axes:
            return 0.0
        s = sum(a.valeur * a.poids for a in etat.axes.values())
        p = sum(a.poids for a in etat.axes.values())
        return (s / p) if p > 0 else 0.0
