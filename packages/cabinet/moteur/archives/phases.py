# packages/cabinet/moteur/phases.py
from typing import Dict, Any, List, Tuple
from .etat import Etat, EntreeProgramme
from .rng import RngFacade
from .effets import EFFECTS
from .moteur import (
    cloture_comptable,
    recalcul_capacite_admin,
    retroactions,
    scoring,
    defausser_cartes,
    verifier_conditions_fin,
)
def _normalize_action(a: dict) -> dict:
    """
    Accepte 2 formes d'action 'deposer':
      - {"type":"deposer", "entree": {...}}
      - {"uid":..., "carte_id":..., "auteur_id":..., "type":..., "params":..., "tags":[...]}
    Retourne toujours le payload plat prêt pour EntreeProgramme.
    """
    if not isinstance(a, dict):
        return a
    if "entree" in a and isinstance(a["entree"], dict):
        e = dict(a["entree"])
        if "type" not in e and "type" in a:
            e["type"] = a["type"]
        return e
    return a

def _tirage_pondere(defs: List[Dict[str, Any]], rng: RngFacade, *, stream="world_events"):
    weights = [float(d.get("poids", 1.0)) for d in defs]
    return rng.choice_weighted(defs, weights, name=stream)

def _appliquer_effets(etat: Etat, effets: List[Dict[str, Any]], rng: RngFacade, *, stream="effects"):
    impacts = []
    for eff in effets or []:
        fn = EFFECTS[eff["type"]]
        impacts.append(fn(etat, eff.get("params", {}), rng))
    return impacts

def phase_monde(etat: Etat, cfg: Dict[str, Any], rng: RngFacade):
    defs = cfg.get("perturbateurs_tour", []) or []
    if not defs:
        return
    carte = _tirage_pondere(defs, rng, stream="world_events")
    imps = _appliquer_effets(etat, carte.get("effets", []), rng, stream="world_effects")
    etat.historiques.append({"type":"perturbateur", "id":carte["id"], "impacts": imps})

def _build_projet_depuis_actions(etat: "Etat", cfg: dict, actions: list):
    from .validation import est_carte_admissible  # évite import circulaire à l'import module
    projet = []
    rejets = []

    for raw in (actions or []):
        a = _normalize_action(raw)
        e = EntreeProgramme(
            uid=a["uid"],
            carte_id=a.get("carte_id", ""),
            auteur_id=a["auteur_id"],
            type=a.get("type", "mesure"),
            params=a.get("params", {}),
            tags=a.get("tags", []),
        )

        ok, raison = est_carte_admissible(etat, projet, e, cfg)
        if ok:
            projet.append(e)
        else:
            # >>>> IMPORTANT : journalise au format attendu par les tests
            etat.historiques.append({
                "type": "depot_rejete",
                "uid": e.uid,
                "carte_id": e.carte_id,
                "raison": raison or "",
            })
            rejets.append({"uid": e.uid, "carte_id": e.carte_id, "raison": raison})

    return projet, rejets


def phase_conseil(etat: Etat, actions_conseil: List[Dict[str, Any]] | List[Dict[str, Any]], cfg: Dict[str, Any]):
    # Supporte soit une liste d’actions directe, soit une liste de cycles {actions, votes}
    cycles = actions_conseil
    if cycles and isinstance(cycles, list) and cycles and isinstance(cycles[0], dict) and "actions" in cycles[0]:
        # mode cycles (amendements puis re-vote)
        etat.programme.temporaire = []  # sous-état
        etat.programme.version += 1
        for idx, cyc in enumerate(cycles, start=1):
            projet, rejets = _build_projet_depuis_actions(etat, cfg, cyc.get("actions", []))
            etat.programme.temporaire = projet
            etat.historiques.append({"type":"programme_amende","version": etat.programme.version, "cycle": idx, "rejets": rejets})
            votes = cyc.get("votes")
            if votes:
                etat.programme.votes = votes
                oui = sum(1 for v in votes.values() if v)
                non = sum(1 for v in votes.values() if not v)
                adopte = oui > non
                etat.historiques.append({"type":"programme_vote","adopte": adopte, "oui": oui, "non": non})
                if adopte:
                    etat.programme.entrees = list(etat.programme.temporaire)
                    etat.historiques.append({"type":"programme_amende","version": etat.programme.version})
                    return
        # aucun cycle abouti
        etat.programme.entrees = []
        etat.historiques.append({"type":"programme_rejete_definitif","version": etat.programme.version})
    else:
        # modèle simple (une seule passe d’actions, vote géré ensuite)
        projet, rejets = _build_projet_depuis_actions(etat, cfg, actions_conseil or [])
        etat.programme.entrees = projet
        etat.programme.version += 1
        etat.historiques.append({"type":"programme_amende","version": etat.programme.version, "rejets": rejets})

def phase_vote_global(etat: Etat, votes: Dict[str, bool]) -> bool:
    etat.programme.votes = votes or {}
    oui = sum(1 for v in etat.programme.votes.values() if v)
    non = sum(1 for v in etat.programme.votes.values() if not v)
    adopte = oui > non
    etat.historiques.append({"type":"programme_vote","adopte": adopte, "oui": oui, "non": non})
    if not adopte:
        # si rejet en mode simple, programme vide pour ce tour
        etat.programme.entrees = []
    return adopte

def phase_amendements(etat, cfg, rng):
    """
    Hook d’amendements entre le vote et l’exécution.
    Pour l’instant, no-op : les cycles d’amendements sont gérés dans phase_conseil().
    Gardé pour compatibilité et future extension (amendements procéduraux, négociations, etc.).
    """
    return None

# Les fonctions de clôture restent des wrappers; ton implémentation détaillée vit ailleurs
def phase_execution(etat: Etat, cfg: Dict[str, Any], rng: RngFacade, procedures_declares=None):
    # applique séquentiellement les effets des mesures adoptées
    for e in etat.programme.entrees:
        # auto-injection auteur pour effets capital_politique_delta
        setattr(etat, "_effet_auteur_id", e.auteur_id)
        impacts = _appliquer_effets(etat, e.params.get("_effets_compile", e.params.get("effets", [])), rng, stream="mesure")
        etat.historiques.append({"type":"mesure_executee","uid": e.uid, "carte_id": e.carte_id, "auteur_id": e.auteur_id, "impacts": impacts})
    if hasattr(etat, "_effet_auteur_id"):
        delattr(etat, "_effet_auteur_id")

def _revenus_annuels(eco) -> int:
    """
    Base très simple (alignée avec les tests) :
    revenus = impôt part + impôt ent + redevances.
    """
    imp_part = int(eco.base_part * eco.taux_impot_part)
    imp_ent  = int(eco.base_ent  * eco.taux_impot_ent)
    redev    = int(eco.base_ressources * eco.taux_redevances)
    return imp_part + imp_ent + redev

def _depenses_totales(eco) -> int:
    """
    Dépenses = somme des postes + service de la dette.
    NB : certains tests de projection ignorent le service de la dette ;
    pour la clôture éco, on le garde (comptable).
    """
    dep_postes = sum(eco.depenses_postes.values())
    service = int(eco.dette * eco.taux_interet)
    return dep_postes + service

def recalibrer_eco(etat, cfg):
    """
    Clôture économique : calcule solde, ajuste dette, recale efficience & capacité.
    Journalise 'cloture_economie' compatible tests.
    """
    eco = etat.eco

    revenus = _revenus_annuels(eco)
    dep_sans_service = sum(eco.depenses_postes.values())
    service = int(eco.dette * eco.taux_interet)
    dep_tot = dep_sans_service + service
    solde = revenus - dep_tot

    dette_avant = eco.dette
    if solde >= 0:
        eco.dette = max(0, eco.dette - solde)
    else:
        eco.dette += (-solde)

    # simple pénalité/rattrapage d'efficience suivant le solde
    eff_old = eco.efficience
    if solde < 0:
        eco.efficience = max(0.5, eff_old * 0.90)  # pénalise
    else:
        eco.efficience = min(1.0, eff_old / 0.99)  # rattrape un peu

    # recalcule capacite_max bornée (ex: de 1 à valeur initiale)
    eco.capacite_max = max(1, int(round(eco.capacite_max * eco.efficience)))

    etat.historiques.append({
        "type": "cloture_economie",
        "tour": etat.tour,
        "revenus": revenus,
        "depenses_sans_service": dep_sans_service,
        "service_dette": service,
        "depenses_totales": dep_tot,
        "solde": solde,
        "dette_avant": dette_avant,
        "dette_apres": eco.dette,
        "efficience_nouvelle": eco.efficience,
        "capacite_max_nouvelle": eco.capacite_max,
        "baseline_depenses": dep_sans_service,
        "diff_ratio": 0.0,
    })

def phase_cloture(etat: "Etat", cfg: dict, rng: "RngFacade") -> None:
    """
    Clôture canonique : comptable → capacité → rétroactions → scoring → défausse → clôture éco → fins
    (on appelle directement les fonctions locales, pas via moteur).
    """
    cloture_comptable(etat, cfg)          # existe déjà dans ce module
    recalcul_capacite_admin(etat, cfg)    # idem
    retroactions(etat, cfg)               # idem
    scoring(etat, cfg)                    # idem
    defausser_cartes(etat)                # idem
    recalibrer_eco(etat, cfg)             # << helper défini ici
    verifier_conditions_fin(etat, cfg)    # idem

