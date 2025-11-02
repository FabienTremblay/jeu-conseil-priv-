# packages/cabinet/moteur/etat.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Literal, Optional, Any, Deque
from collections import deque
import copy

AxeId = str

@dataclass
class Axe:
    id: AxeId
    valeur: int              # 0..10
    seuil_crise: int
    poids: float = 1.0
    def clamp(self) -> None:
        self.valeur = max(0, min(10, self.valeur))

@dataclass
class Economie:
    taux_impot_part: float
    taux_impot_ent:  float
    taux_redevances: float
    taux_interet:    float
    base_part:       int
    base_ent:        int
    base_ressources: int
    depenses_postes: Dict[str, int]
    dette:           int
    capacite_max:    int    # plafond cartes exécutables/tour
    efficience:      float  # multiplicateur d’efficacité 0..1

@dataclass
class Joueur:
    id: str
    nom: str
    capital_politique: int = 0
    main: List[str] = field(default_factory=list)     # ids de cartes
    defausse: List[str] = field(default_factory=list) # pile personnelle

# --- Decks (DOIVENT être définis avant Etat) ---------------------------------

@dataclass
class DeckState:
    """Deck sans remise, avec défausse, pour cartes 'mesure/amendement/procedure'."""
    pioche: Deque[str] = field(default_factory=deque)
    defausse: Deque[str] = field(default_factory=deque)

@dataclass
class EventDeckState:
    """Deck d'événements mondiaux (perturbateurs) sans remise."""
    pioche: Deque[str] = field(default_factory=deque)
    defausse: Deque[str] = field(default_factory=deque)

# --- Programme ---------------------------------------------------------------

@dataclass
class EntreeProgramme:
    uid: str
    carte_id: str
    auteur_id: str
    type: Literal["mesure","amendement","procedure"]
    params: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

@dataclass
class ProgrammeTour:
    version: int = 1
    entrees: List[EntreeProgramme] = field(default_factory=list)
    votes: Dict[str, bool] = field(default_factory=dict)  # vote global binaire

# --- Etat principal ----------------------------------------------------------

@dataclass
class Etat:
    id: str
    tour: int
    axes: Dict[AxeId, Axe]
    eco: Economie
    joueurs: Dict[str, Joueur]
    programme: Optional[ProgrammeTour] = None
    capital_collectif: int = 0
    historiques: List[Dict[str, Any]] = field(default_factory=list)
    termine: bool = False
    raison_fin: Optional[str] = None

    # définitions et decks
    cartes_def: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    deck_global: DeckState = field(default_factory=DeckState)
    deck_events: EventDeckState = field(default_factory=EventDeckState)

    def clone(self) -> "Etat":
        return copy.deepcopy(self)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)

