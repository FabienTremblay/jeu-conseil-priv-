# packages/moteur-jeu/src/moteur_jeu/moteur.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
import uuid
import time
import random

# --- Événements --------------------------------------------------------------


@dataclass
class Evenement:
    type: str
    donnees: Dict[str, Any]
    ts: float = field(default_factory=lambda: time.time())


# --- Actions ----------------------------------------------------------------


@dataclass
class Action:
    type: str
    auteur_id: str
    payload: Dict[str, Any]


# --- État du jeu -------------------------------------------------------------


@dataclass
class Joueur:
    id: str
    nom: str
    role: str = "citoyen"
    attention: int = 3
    score: int = 0


@dataclass
class EtatJeu:
    id: str
    tour: int = 1
    # compat: tension peut être un int (anciens scénarios) ou un dict d'axes (nouveaux)
    tension: Union[int, Dict[str, int]] = field(default_factory=lambda: {
        "pauvrete": 0,
        "insecurite": 0,
        "maladie": 0,
        "cruaute": 0,
        "tolerance": 0,
        "guerre": 0
    })
    joueurs: Dict[str, Joueur] = field(default_factory=dict)
    pile_evenements: List[Evenement] = field(default_factory=list)
    contentieux: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # gestion de fin de partie
    partie_status: str = "en_cours"  # "en_cours" | "terminee"
    raison_fin: Optional[str] = None  # label de victoire/défaite/timeout
    max_tours: int = 8  # paramètre noyau minimal
    scores: Dict[str, int] = field(default_factory=dict)

    # journal des actions/événements
    journal: List[Dict[str, Any]] = field(default_factory=list)

    # Gestion des phases
    phase: str = "definition"

    # RNG déterministe + persistance des tirages
    rng_seed: int = 42
    rng_calls: int = 0

    # --- Helpers tensions ---
    def _assurer_axes(self):
        """Si la tension est encore un int (ancien sauvegarde/YAML), la convertir en axes."""
        if isinstance(self.tension, int):
            self.tension = {"general": self.tension}

    def tension_axis_delta(self, axis: str, delta: int) -> int:
        self._assurer_axes()
        self.tension[axis] = max(0, self.tension.get(axis, 0) + int(delta))
        return self.tension[axis]

    def tension_total(self, poids: Optional[Dict[str, float]] = None) -> float:
        self._assurer_axes()
        if not poids:
            # somme simple si pas de pondération fournie
            return float(sum(self.tension.values()))
        return float(sum(self.tension.get(a, 0) * w for a, w in poids.items()))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tour": self.tour,
            "tension": self.tension,
            "joueurs": {jid: vars(j) for jid, j in self.joueurs.items()},
            "contentieux": self.contentieux,
            "evenements": [vars(e) for e in self.pile_evenements[-10:]],
            "partie_status": self.partie_status,
            "raison_fin": self.raison_fin,
            "max_tours": self.max_tours,
        }

    def est_terminee(self) -> bool:
        return self.partie_status == "terminee"


Regle = Callable[[EtatJeu, Action], Optional[List[Evenement]]]

# --- Règles par défaut (on garde une fallback simple) ------------------------


def regle_tension_basique(etat: EtatJeu, action: Action) -> Optional[List[Evenement]]:
    if action.type in {"provoquer_controverse", "divulguer_scandale"}:
        etat.tension += 1
        return [
            Evenement(
                "tension_changee", {"delta": +1, "nouvelle_tension": etat.tension}
            )
        ]
    return None


REGLES_PAR_DEFAUT: List[Regle] = [
    regle_tension_basique,
]

# --- Moteur ------------------------------------------------------------------


class Moteur:
    def __init__(
        self, etat: Optional[EtatJeu] = None, regles: Optional[List[Regle]] = None
    ):
        self.etat = etat or EtatJeu(id=str(uuid.uuid4()))
        self.regles = regles or REGLES_PAR_DEFAUT
        setattr(self.etat, "_moteur", self)

    @staticmethod
    def creer_partie(noms_joueurs: List[str]) -> "Moteur":
        etat = EtatJeu(id=str(uuid.uuid4()))
        for nom in noms_joueurs:
            jid = str(uuid.uuid4())
            etat.joueurs[jid] = Joueur(id=jid, nom=nom)
            etat.scores[jid] = 0
        return Moteur(etat=etat)

    def ajouter_joueur(self, nom: str, role: Optional[str] = None):
        """Ajoute un joueur à chaud dans la partie (si non existant)."""
        # refuse doublon par nom
        for j in self.etat.joueurs.values():
            if j.nom == nom:
                return j

        # mini-assignation de rôle (reformateur/saboteur alternés pour l’exemple)
        if role is None:
            roles = ["reformateur", "saboteur"]
            deja = [j.role for j in self.etat.joueurs.values()]
            # essaie d'équilibrer
            if deja.count("reformateur") <= deja.count("saboteur"):
                role = "reformateur"
            else:
                role = "saboteur"

        jid = str(uuid.uuid4())
        j = Joueur(id=jid, nom=nom, role=role, attention=3, score=0)
        self.etat.joueurs[jid] = j
        return j

    def _journaliser(self, action: Action, evenements: List[Evenement]):
        self.etat.journal.append(
            {
                "ts": time.time(),
                "tour": self.etat.tour,
                "action": {
                    "type": action.type,
                    "auteur_id": action.auteur_id,
                    "payload": action.payload,
                },
                "evenements": [vars(e) for e in evenements],
            }
        )

    def _terminer(self, label: str):
        if not self.etat.est_terminee():
            self.etat.partie_status = "terminee"
            self.etat.raison_fin = label
            # NEW: scoring
            cfg = getattr(self.etat, "_cfg", None)
            if cfg:
                evts_scores = evaluer_scores(self.etat, cfg)
                self.etat.pile_evenements.extend(evts_scores)
                # journalise
                self.etat.journal.append(
                    {
                        "ts": time.time(),
                        "tour": self.etat.tour,
                        "action": {
                            "type": "_system_scoring",
                            "auteur_id": "_system",
                            "payload": {},
                        },
                        "evenements": [vars(e) for e in evts_scores],
                    }
                )
            ev = Evenement("fin_partie", {"label": label})
            self.etat.pile_evenements.append(ev)
            self.etat.journal.append(
                {
                    "ts": time.time(),
                    "tour": self.etat.tour,
                    "action": {
                        "type": "_system_fin",
                        "auteur_id": "_system",
                        "payload": {},
                    },
                    "evenements": [vars(ev)],
                }
            )

    def appliquer_action(self, action: Action) -> List[Evenement]:
        if self.etat.est_terminee():
            ev = Evenement("refus", {"msg": "partie_terminee"})
            self.etat.pile_evenements.append(ev)
            # Journalise le refus post-fin
            self._journaliser(action, [ev])
            return [ev]

        evenements: List[Evenement] = []
        for regle in self.regles:
            res = regle(self.etat, action)
            if res:
                evenements.extend(res)
                if any(e.type in ("refus", "refus_precondition") for e in res):
                    break

        # Fin de partie si une règle émet victoire/défaite
        if any(e.type == "victoire" for e in evenements):
            label = next(
                e.donnees.get("label", "victoire")
                for e in evenements
                if e.type == "victoire"
            )
            self._terminer(label)
        elif any(e.type == "defaite" for e in evenements):
            label = next(
                e.donnees.get("label", "defaite")
                for e in evenements
                if e.type == "defaite"
            )
            self._terminer(label)

        self.etat.pile_evenements.extend(evenements)
        # Journalisation de l'action
        self._journaliser(action, evenements)
        return evenements

    def debut_nouveau_tour(self):
        if self.etat.est_terminee():
            ev = Evenement("refus", {"msg": "partie_terminee"})
            self.etat.pile_evenements.append(ev)
            # Journalise le refus post-fin
            self.etat.journal.append(
                {
                    "ts": time.time(),
                    "tour": self.etat.tour,
                    "action": {
                        "type": "_system_nouveau_tour_refuse",
                        "auteur_id": "_system",
                        "payload": {},
                    },
                    "evenements": [vars(ev)],
                }
            )
            return

        for j in self.etat.joueurs.values():
            j.attention = 3

        self.etat.tour += 1
        ev = Evenement("nouveau_tour", {"tour": self.etat.tour})
        self.etat.pile_evenements.append(ev)
        # Journalise le passage de tour
        self.etat.journal.append(
            {
                "ts": time.time(),
                "tour": self.etat.tour,
                "action": {
                    "type": "_system_nouveau_tour",
                    "auteur_id": "_system",
                    "payload": {},
                },
                "evenements": [vars(ev)],
            }
        )

        # NEW: fin par limite de tours
        if self.etat.tour > self.etat.max_tours:
            self._terminer("limite_de_tours_atteinte")

    # helper RNG reproductible
    def _rng(self) -> random.Random:
        r = random.Random(self.etat.rng_seed)
        # avancer jusqu'à l'état courant
        for _ in range(self.etat.rng_calls):
            r.random()
        return r

    # choix pondéré reproductible
    def _rng_choice_weighted(self, items: List[Any], weights: List[float]):
        r = self._rng()
        total = sum(weights)
        x = r.random() * total
        self.etat.rng_calls += 1
        acc = 0.0
        for item, w in zip(items, weights):
            acc += w
            if x <= acc:
                return item
        return items[-1]

    # charger des règles YAML et initialiser contenu
    def charger_regles_yaml(self, path: str) -> None:
        from pathlib import Path
        from .regles_loader import (
            charger_yaml,
            construire_regle_generique,
            appliquer_etat_initial_contentieux,
            assigner_roles,
        )

        def _find_schema_upwards(start: Path) -> Path:
            for parent in [start] + list(start.parents):
                candidate = parent / "docs" / "schemas" / "regles.schema.json"
                if candidate.exists():
                    return candidate
            raise FileNotFoundError(
                "Impossible de localiser docs/schemas/regles.schema.json en remontant depuis "
                + str(start)
            )

        here = Path(__file__).resolve()
        schema_path = _find_schema_upwards(here)
        cfg = charger_yaml(path, schema_path=str(schema_path))

        appliquer_etat_initial_contentieux(self.etat, cfg)
        assigner_roles(self.etat, cfg)
        regle_yaml = construire_regle_generique(cfg)
        # on remplace pour éviter la double facturation et les doublons d'effets
        self.regles = [regle_yaml]


# --- Règles par défaut -------------------------------------------------------


def regle_depense_attention(etat: EtatJeu, action: Action):
    """Toute action consomme 1 point d’attention si possible."""
    j = etat.joueurs.get(action.auteur_id)
    if not j:
        return [
            Evenement(
                "erreur", {"msg": "joueur_introuvable", "joueur_id": action.auteur_id}
            )
        ]
    if j.attention <= 0:
        return [
            Evenement("refus", {"msg": "attention_insuffisante", "joueur_id": j.id})
        ]
    j.attention -= 1
    return [
        Evenement(
            "attention_depensee", {"joueur_id": j.id, "reste": j.attention, "cost": 1}
        )
    ]


def regle_tension_basique(etat: EtatJeu, action: Action):
    if action.type in {"provoquer_controverse", "divulguer_scandale"}:
        etat.tension += 1
        return [
            Evenement(
                "tension_changee", {"delta": +1, "nouvelle_tension": etat.tension}
            )
        ]
    return None


REGLES_PAR_DEFAUT: List[Regle] = [
    regle_depense_attention,  # <-- important: d’abord la dépense
    regle_tension_basique,
]
