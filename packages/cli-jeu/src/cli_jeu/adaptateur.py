from __future__ import annotations
from typing import Any, TypedDict, Optional
from .persistence import save_engine, load_engine, append_event, now_iso

from moteur_jeu import Moteur, Action, Joueur


class ActionSpec(TypedDict, total=False):
    id: str
    nom: str
    description: str
    cout_attention: int
    phase: str
    roles: list[str]
    params: dict


class FiltreActions(TypedDict, total=False):
    joueur: Optional[str]  # id ou nom
    phase_only: bool


# helper souple: tente d’extraire les actions depuis etat._cfg si présent
def _extract_actions_from_cfg(cfg: dict) -> list[ActionSpec]:
    actions = []
    # formalisme probable: cfg["actions"] = [{id/nom/phase/roles/params/cout_attention}, ...]
    for a in cfg.get("actions", []):
        spec: ActionSpec = {
            "id": a.get("id") or a.get("type") or a.get("nom") or "action",
            "nom": a.get("nom") or a.get("id"),
            "description": a.get("description", ""),
            "cout_attention": int(a.get("cout_attention", 1)),
            "phase": a.get("phase", ""),
            "roles": a.get("roles", []) or a.get("role", []),
            "params": a.get("params", {}) or a.get("payload_schema", {}),
        }
        actions.append(spec)
    return actions


class SessionLocale:
    def __init__(self):
        self.engine: Moteur | None = None

    # --- lifecycle -----------------------------------------------------------
    def nouvelle_partie(self, joueurs: list[str]) -> None:
        self.engine = Moteur.creer_partie(joueurs)
        save_engine(self.engine)
        append_event({"ts": now_iso(), "type": "nouvelle_partie", "joueurs": joueurs})

    def charger_regles(self, chemin_yaml: str) -> None:
        self._ensure_loaded()
        self.engine.charger_regles_yaml(chemin_yaml)
        save_engine(self.engine)
        append_event(
            {"ts": now_iso(), "type": "charger_regles", "fichier": chemin_yaml}
        )

    # --- joueurs -------------------------------------------------------------
    def ajouter_joueur(self, nom: str, role: str | None = None) -> None:
        """Ton moteur n’a pas d’API add; on modifie l’état proprement."""
        self._ensure_loaded()
        import uuid

        etat = self.engine.etat
        jid = str(uuid.uuid4())
        j = Joueur(id=jid, nom=nom, role=role or "citoyen")
        etat.joueurs[jid] = j
        etat.scores[jid] = 0
        save_engine(self.engine)
        append_event(
            {
                "ts": now_iso(),
                "type": "ajouter_joueur",
                "nom": nom,
                "role": j.role,
                "joueur_id": jid,
            }
        )

    # --- jeu ----------------------------------------------------------------

    def actions_possibles(
        self, filtre: FiltreActions | None = None
    ) -> list[ActionSpec]:
        """Retourne les actions jouables selon l'état courant.
        - Si etat._cfg présent: lit la liste des actions à partir du YAML.
        - Sinon: fallback = actions reconnues par les règles par défaut.
        - Applique quelques filtres simples (phase, role, attention > 0).
        """
        self._ensure_loaded()
        e = self.engine.etat
        cfg = getattr(e, "_cfg", None)

        if cfg:
            actions = _extract_actions_from_cfg(cfg)
        else:
            # Fallback: celles qui ont un effet via tes règles par défaut
            actions = [
                ActionSpec(
                    id="provoquer_controverse",
                    nom="provoquer_controverse",
                    description="Augmente la tension",
                    cout_attention=1,
                ),
                ActionSpec(
                    id="divulguer_scandale",
                    nom="divulguer_scandale",
                    description="Augmente la tension",
                    cout_attention=1,
                ),
            ]

        # Filtres
        joueur_id: str | None = None
        joueur_role: str | None = None
        attention_dispo: int | None = None
        phase_courante = e.phase

        if filtre and filtre.get("joueur"):
            joueur_id = self._resolve_joueur_id(filtre["joueur"])  # accepte nom ou id
            j = e.joueurs[joueur_id]
            joueur_role = j.role
            attention_dispo = j.attention

        phase_only = bool(filtre and filtre.get("phase_only"))

        def _ok(spec: ActionSpec) -> bool:
            # attention minimale
            if attention_dispo is not None:
                cout = int(spec.get("cout_attention", 1) or 1)
                if attention_dispo < cout:
                    return False
            # role
            roles = spec.get("roles") or []
            if roles and joueur_role and (joueur_role not in roles):
                return False
            # phase = si demandé, respecter la phase courante
            if phase_only:
                sp = spec.get("phase") or ""
                if sp and sp != phase_courante:
                    return False
            return True

        return [s for s in actions if _ok(s)]

    def jouer_action(self, auteur: str, type_action: str, **payload: Any):
        self._ensure_loaded()
        jid = self._resolve_joueur_id(auteur)
        act = Action(type=type_action, auteur_id=jid, payload=payload)
        evts = self.engine.appliquer_action(act)
        save_engine(self.engine)
        append_event(
            {
                "ts": now_iso(),
                "type": "action",
                "joueur": auteur,
                "joueur_id": jid,
                "action": type_action,
                "payload": payload,
                "evenements": [e.type for e in evts],
            }
        )
        return [vars(e) for e in evts]

    def tour_suivant(self):
        self._ensure_loaded()
        self.engine.debut_nouveau_tour()
        save_engine(self.engine)
        append_event(
            {"ts": now_iso(), "type": "nouveau_tour", "tour": self.engine.etat.tour}
        )

    # --- lecture -------------------------------------------------------------
    def etat_public(self) -> dict:
        self._ensure_loaded()
        e = self.engine.etat
        # on s’appuie sur snapshot() + quelques champs utiles
        snap = e.snapshot()
        snap.update(
            {
                "phase": e.phase,
                "partie_status": e.partie_status,
                "raison_fin": e.raison_fin,
                "rng_seed": e.rng_seed,
                "rng_calls": e.rng_calls,
                "joueurs_liste": [
                    {
                        "id": j.id,
                        "nom": j.nom,
                        "role": j.role,
                        "attention": j.attention,
                        "score": j.score,
                    }
                    for j in e.joueurs.values()
                ],
                "taille_journal": len(e.journal),
            }
        )
        return snap

    # --- helpers -------------------------------------------------------------
    def _ensure_loaded(self):
        if self.engine is None:
            self.engine = load_engine()
            if self.engine is None:
                raise RuntimeError(
                    "Aucune partie en cours. Lance `avpol init-partie` d’abord."
                )

    def _resolve_joueur_id(self, auteur: str) -> str:
        """Accepte un nom ou un id; résout vers id."""
        e = self.engine.etat
        # id direct
        if auteur in e.joueurs:
            return auteur
        # par nom
        for j in e.joueurs.values():
            if j.nom == auteur:
                return j.id
        raise ValueError(f"Joueur introuvable: {auteur}")
