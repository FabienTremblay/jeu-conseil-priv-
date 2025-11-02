from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import yaml
import json
from jsonschema import validate

from .moteur import EtatJeu, Evenement, Action, Joueur  # types existants

Regle = Callable[[EtatJeu, Action], Optional[List[Evenement]]]


@dataclass
class ReglesConfig:
    actions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    contentieux_init: List[Dict[str, Any]] = field(default_factory=list)
    victoires: List[Dict[str, Any]] = field(default_factory=list)
    phases: List[str] = field(default_factory=list)
    perturbations: List[Dict[str, Any]] = field(default_factory=list)
    roles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evaluation: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


def _load_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_schema(schema_path: str) -> Dict[str, Any]:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def charger_yaml(path: str, schema_path: Optional[str] = None) -> ReglesConfig:
    data = _load_file(path)
    if schema_path:
        schema = _load_schema(schema_path)
        validate(instance=data, schema=schema)

    # après validate(instance=data, schema=schema)
    actions_cfg = {}
    for a in data.get("actions", []):
        aid = a.get("id") or a.get("name")
        if not aid:
            raise ValueError("Action sans id/name dans le YAML")

        actions_cfg[aid] = {
            "id": aid,
            "name": a.get("name", aid),
            "attention_cost": a.get("attention_cost", 1),
            "allowed_phases": a.get("allowed_phases", []),
            # compat: accepte preconditions (nouveau) ou conditions (ancien)
            "preconditions": (a.get("preconditions") or a.get("conditions") or {}),
            "effects": a.get("effects", []) or [],
        }

    roles = {r["id"]: r for r in data.get("roles", [])}
    phases = [p["name"] for p in data.get("phases", [])]
    perts = data.get("perturbations", []) or []
    evalo = data.get("evaluation", {}) or {}

    return ReglesConfig(
        actions=actions_cfg,
        contentieux_init=data.get("contentieux", []) or [],
        victoires=data.get("victoires", []) or [],
        phases=phases,
        perturbations=perts,
        roles=roles,
        evaluation=evalo,
        raw=data,
    )


def appliquer_etat_initial_contentieux(etat: EtatJeu, cfg: ReglesConfig) -> None:
    if not hasattr(etat, "contentieux"):
        setattr(etat, "contentieux", {})
    for c in cfg.contentieux_init:
        cid = c["id"]
        etat_initial = c.get("etat_initial", {}) or {}
        etat.contentieux[cid] = {
            "id": cid,
            "titre": c.get("titre", cid),
            **etat_initial,
        }


def _check_preconditions(
    etat: EtatJeu, action: Action, a_cfg: Dict[str, Any]
) -> Optional[Evenement]:
    cond = a_cfg.get("preconditions", {}) or {}

    # allowed_phases
    allowed = a_cfg.get("allowed_phases", [])
    if allowed and etat.phase not in allowed:
        return Evenement(
            "refus_precondition",
            {"msg": "phase_interdite", "phase": etat.phase, "allowed": allowed},
        )

    # requires_phase
    req_phase = cond.get("requires_phase")
    if req_phase and etat.phase != req_phase:
        return Evenement(
            "refus_precondition",
            {"msg": "requires_phase", "need": req_phase, "have": etat.phase},
        )

    # rôles
    j = etat.joueurs.get(action.auteur_id)
    if not j:
        return Evenement(
            "erreur", {"msg": "joueur_introuvable", "joueur_id": action.auteur_id}
        )

    req_role = cond.get("requires_role")
    if req_role and j.role != req_role:
        return Evenement(
            "refus_precondition",
            {"msg": "requires_role", "need": req_role, "have": j.role},
        )

    req_tag = cond.get("requires_role_tag")
    if req_tag:
        # récupérer tags du rôle via cfg
        cfg = getattr(etat, "_cfg", None)
        tags = (
            cfg.roles.get(j.role, {}).get("tags")
            if (cfg and hasattr(cfg, "roles"))
            else []
        ) or []
        if req_tag not in tags:
            return Evenement(
                "refus_precondition",
                {"msg": "requires_role_tag", "need": req_tag, "have": tags},
            )

    # requires_event: doit exister dans la pile d'événements
    req_ev = cond.get("requires_event")
    if req_ev:
        if not any(e.type == req_ev for e in etat.pile_evenements):
            return Evenement(
                "refus_precondition", {"msg": "requires_event", "event": req_ev}
            )

    # requires_contentieux_gte: contentieux[id][field] >= value
    rcg = cond.get("requires_contentieux_gte")
    if rcg:
        cid = rcg["id"]
        field = rcg["field"]
        value = int(rcg["value"])
        cont = getattr(etat, "contentieux", {})
        curv = int(cont.get(cid, {}).get(field, 0))
        if curv < value:
            return Evenement(
                "refus_precondition",
                {
                    "msg": "requires_contentieux_gte",
                    "id": cid,
                    "field": field,
                    "need": value,
                    "have": curv,
                },
            )

    # min_attention (au-dessus de cost si précisé)

    j = etat.joueurs.get(action.auteur_id)
    if not j:
        return Evenement(
            "erreur", {"msg": "joueur_introuvable", "joueur_id": action.auteur_id}
        )
    min_attention = int(cond.get("min_attention", 0))
    cost = int(a_cfg.get("attention_cost", 1))
    if j.attention < max(min_attention, cost):
        return Evenement("refus", {"msg": "attention_insuffisante", "joueur_id": j.id})
    return None


from typing import List, Optional  # si pas déjà présent


def _apply_effects(
    etat: "EtatJeu",
    effects: List[Dict[str, Any]],
    evts: List["Evenement"],
    *,
    moteur: Optional[Any] = None,
    cfg: Optional["ReglesConfig"] = None,
    auteur_id: Optional[str] = None,
) -> None:
    """
    Applique une liste d'effets au jeu. Peut utiliser le RNG du moteur (via etat._moteur)
    et le catalogue de perturbations de cfg.
    """
    for eff in effects:
        etype = eff.get("type")
        params = eff.get("params", {}) or {}

        if etype == "tension_delta":
            delta = int(params.get("delta", 0))
            etat.tension += delta
            evts.append(
                Evenement(
                    "tension_changee",
                    {"delta": delta, "nouvelle_tension": etat.tension},
                )
            )

        elif etype == "emit_event":
            etype_ev = params.get("event_type", "evenement")
            data = params.get("data", {}) or {}
            evts.append(Evenement(etype_ev, data))

        elif etype == "contentieux_delta":
            cid = params["id"]
            field = params["field"]
            delta = int(params.get("delta", 0))
            if not hasattr(etat, "contentieux") or cid not in etat.contentieux:
                evts.append(
                    Evenement("erreur", {"msg": "contentieux_introuvable", "id": cid})
                )
            else:
                cont = etat.contentieux[cid]
                cont[field] = int(cont.get(field, 0)) + delta
                evts.append(
                    Evenement(
                        "contentieux_modifie",
                        {
                            "id": cid,
                            "field": field,
                            "delta": delta,
                            "valeur": cont[field],
                        },
                    )
                )

        elif etype == "phase_set":
            name = params.get("name")
            if not name:
                evts.append(Evenement("erreur", {"msg": "phase_invalide"}))
            else:
                etat.phase = name
                evts.append(Evenement("phase_changee", {"phase": name}))

        elif etype == "attention_delta":
            target = params.get("target", "auteur")
            delta = int(params.get("delta", 0))
            jid = params.get("joueur_id") if target != "auteur" else auteur_id
            j = etat.joueurs.get(jid) if jid else None
            if not j:
                evts.append(
                    Evenement("erreur", {"msg": "joueur_introuvable", "cible": target})
                )
            else:
                j.attention = max(0, j.attention + delta)
                evts.append(
                    Evenement(
                        "attention_changee",
                        {"joueur_id": j.id, "delta": delta, "valeur": j.attention},
                    )
                )

        elif etype == "random_perturbation":
            if moteur is None and hasattr(etat, "_moteur"):
                moteur = getattr(etat, "_moteur")
            cfg = cfg  # déjà reçu
            if moteur is None or cfg is None or not cfg.perturbations:
                evts.append(Evenement("erreur", {"msg": "aucune_perturbation"}))
                continue

            auteur = etat.joueurs.get(auteur_id) if auteur_id else None
            items = []
            weights = []
            for p in cfg.perturbations:
                ok = True
                if auteur:
                    only_roles = p.get("only_roles") or []
                    only_tags = p.get("only_role_tags") or []
                    if only_roles and auteur.role not in only_roles:
                        ok = False
                    if ok and only_tags:
                        role_tags = (
                            cfg.roles.get(auteur.role, {}).get("tags")
                            if cfg.roles
                            else []
                        ) or []
                        if not any(t in role_tags for t in only_tags):
                            ok = False
                if ok:
                    items.append(p)
                    weights.append(float(p.get("weight", 1.0)))

            if not items:
                evts.append(
                    Evenement("erreur", {"msg": "aucune_perturbation_applicable"})
                )
                continue

            choice = moteur._rng_choice_weighted(items, weights)
            pid = choice.get("id")
            evts.append(Evenement("perturbation_tiree", {"id": pid}))
            sub_effects = choice.get("effects", []) or []
            _apply_effects(
                etat, sub_effects, evts, moteur=moteur, cfg=cfg, auteur_id=auteur_id
            )

        elif etype == "apply_perturbation":
            pid = params.get("id")
            found = None
            for p in cfg.perturbations if cfg else []:
                if p.get("id") == pid:
                    found = p
                    break
            if not found:
                evts.append(
                    Evenement("erreur", {"msg": "perturbation_introuvable", "id": pid})
                )
            else:
                evts.append(Evenement("perturbation_appliquee", {"id": pid}))
                sub_effects = found.get("effects", []) or []
                _apply_effects(
                    etat, sub_effects, evts, moteur=moteur, cfg=cfg, auteur_id=auteur_id
                )

        else:
            evts.append(Evenement("erreur", {"msg": "effet_inconnu", "type": etype}))


def _check_victory(etat: EtatJeu, cfg: ReglesConfig, evts: List[Evenement]) -> None:
    for rule in cfg.victoires:
        t = rule["type"]
        p = rule.get("params", {}) or {}
        label = rule.get("label", t)
        if t == "contentieux_gte":
            cid = p["id"]
            field = p["field"]
            value = int(p["value"])
            cur = int(getattr(etat, "contentieux", {}).get(cid, {}).get(field, 0))
            if cur >= value:
                evts.append(
                    Evenement(
                        "victoire",
                        {
                            "label": label,
                            "id": cid,
                            "field": field,
                            "seuil": value,
                            "valeur": cur,
                        },
                    )
                )
        elif t == "tension_gte":
            value = int(p["value"])
            if etat.tension >= value:
                evts.append(
                    Evenement(
                        "defaite",
                        {"label": label, "seuil": value, "valeur": etat.tension},
                    )
                )


def construire_regle_generique(cfg: ReglesConfig) -> Regle:
    def regle(etat: EtatJeu, action: Action) -> Optional[List[Evenement]]:
        a_cfg = cfg.actions.get(action.type)
        if not a_cfg:
            return None

        # Vérifier préconditions et ressources
        pre = _check_preconditions(etat, action, a_cfg)
        if pre:
            return [pre]

        # Paiement de l'attention
        j: Optional[Joueur] = etat.joueurs.get(action.auteur_id)
        if not j:
            return [
                Evenement(
                    "erreur",
                    {"msg": "joueur_introuvable", "joueur_id": action.auteur_id},
                )
            ]
        cost = int(a_cfg.get("attention_cost", 1))
        j.attention -= cost

        evts: List[Evenement] = [
            Evenement(
                "attention_depensee",
                {"joueur_id": j.id, "reste": j.attention, "cost": cost},
            )
        ]

        # Appliquer effets
        # >>> IMPORTANT: on récupère le moteur via closure? pas direct. On l'injecte par setattr temporaire
        moteur = getattr(etat, "_moteur", None)

        _apply_effects(
            etat,
            a_cfg.get("effects", []),
            evts,
            moteur=moteur,
            cfg=cfg,
            auteur_id=action.auteur_id,
        )

        # Vérifier conditions de victoire/échec
        _check_victory(etat, cfg, evts)
        return evts

    return regle


def assigner_roles(etat: "EtatJeu", cfg: ReglesConfig) -> None:
    """MVP: assigne cycliquement les rôles déclarés, sinon 'citoyen'."""
    role_ids = list(cfg.roles.keys())
    if not role_ids:
        return
    i = 0
    for j in etat.joueurs.values():
        j.role = role_ids[i % len(role_ids)]
        i += 1


def evaluer_scores(etat: EtatJeu, cfg: ReglesConfig) -> List[Evenement]:
    evts: List[Evenement] = []
    for j in etat.joueurs.values():
        score = 0
        role = cfg.roles.get(j.role, {})
        for obj in role.get("objectifs", []) or []:
            typ = obj.get("type")
            pts = int(obj.get("points", 0))
            params = obj.get("params", {}) or {}
            ok = False
            if typ == "contentieux_gte":
                c = etat.contentieux.get(params.get("id", ""), {})
                ok = int(c.get(params.get("field", ""), 0)) >= int(
                    params.get("value", 0)
                )
            elif typ == "contentieux_lte":
                c = etat.contentieux.get(params.get("id", ""), {})
                ok = int(c.get(params.get("field", ""), 0)) <= int(
                    params.get("value", 0)
                )
            elif typ == "tension_gte":
                ok = etat.tension >= int(params.get("value", 0))
            elif typ == "tension_lte":
                ok = etat.tension <= int(params.get("value", 0))
            elif typ == "phase_is":
                ok = etat.phase == params.get("value")
            elif typ == "victoire_label_is":
                ok = etat.raison_fin == params.get("value")
            elif typ == "defaite_label_is":
                ok = etat.raison_fin == params.get("value")

            if ok:
                score += pts

        j.score = score
        etat.scores[j.id] = score
        evts.append(
            Evenement(
                "score_attribue", {"joueur_id": j.id, "role": j.role, "score": score}
            )
        )
    return evts
