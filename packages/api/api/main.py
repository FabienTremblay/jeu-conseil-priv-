import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import uuid
import time

# Import du moteur existant
from moteur_jeu.moteur import Moteur, Action
from moteur_jeu.persistence import sauvegarder, charger, moteur_depuis_fichier
from moteur_jeu.regles_loader import charger_yaml, _check_preconditions


# --- Configuration globale ---
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = PROJECT_ROOT / "docs" / "regles"
YAML_DEFAULT = DOCS_DIR / "reforme-x.yaml"

app = FastAPI(title="Jeu Aventure Politique API", version="0.1.0")

# Stocke les parties actives en mémoire (clé = partie_id)
parties: Dict[str, Moteur] = {}


# ===============================
# MODELES Pydantic pour l'API
# ===============================


class InscriptionRequest(BaseModel):
    nom: str


class PartieInfo(BaseModel):
    id: str
    joueurs: List[str]
    tour: int
    phase: str
    tension: int
    partie_status: str


class ActionInput(BaseModel):
    type: str
    auteur_id: str
    payload: Dict[str, Any] = {}


class ValidationInput(BaseModel):
    type: str
    auteur_id: str
    payload: Dict[str, Any] = {}


class ValidationResult(BaseModel):
    ok: bool
    reason: Optional[str] = None


# --- Tables (salle d’attente) -------------------------------------------------


class TableEtat(BaseModel):
    id: str
    cree_a: float
    nom_table: Optional[str] = None
    attendus_min: int = 2  # seuil de départ
    joueurs: Dict[str, bool] = {}  # {nom: ready?}
    host: Optional[str] = None
    regles_file: Optional[str] = None
    demarree: bool = False
    partie_id: Optional[str] = None


class TableCreateRequest(BaseModel):
    nom_table: Optional[str] = None
    attendus_min: int = 2
    regles_file: Optional[str] = None


class TableJoinRequest(BaseModel):
    nom: str


class TableReadyRequest(BaseModel):
    nom: str
    ready: bool


tables: Dict[str, TableEtat] = {}

# ===============================
# ROUTES HTTP
# ===============================


@app.get("/parties")
def lister_parties():
    """Retourne la liste des parties actives."""
    data = []
    for pid, moteur in parties.items():
        e = moteur.etat
        data.append(
            {
                "id": e.id,
                "joueurs": [j.nom for j in e.joueurs.values()],
                "tour": e.tour,
                "phase": e.phase,
                "tension": e.tension,
                "partie_status": e.partie_status,
            }
        )
    return JSONResponse(data)


@app.post("/parties")
def creer_partie(joueurs: List[str] = Body(...)):
    """Crée une nouvelle partie avec la règle 'reforme-x.yaml'."""
    if not YAML_DEFAULT.exists():
        raise HTTPException(
            status_code=500, detail=f"Fichier règles introuvable: {YAML_DEFAULT}"
        )
    moteur = Moteur.creer_partie(joueurs)
    moteur.charger_regles_yaml(str(YAML_DEFAULT))
    parties[moteur.etat.id] = moteur

    # 👉 Phase verrouillée d'inscription
    m.etat.phase = "inscription"

    e = moteur.etat
    return {
        "id": e.id,
        "joueurs": [j.nom for j in e.joueurs.values()],
        "tour": e.tour,
        "phase": e.phase,
        "tension": e.tension,
        "partie_status": e.partie_status,
    }


@app.post("/parties/{pid}/inscrire")
def inscrire_joueur(pid: str, req: InscriptionRequest):
    m = parties.get(pid)
    if not m:
        return JSONResponse(
            {"error": "not_found", "reason": "partie introuvable"}, status_code=404
        )

    # existe déjà ?
    jid = _trouver_joueur_id_par_nom(m.etat, req.nom)
    if jid:
        j = m.etat.joueurs[jid]
        return {
            "ok": True,
            "joueur": {
                "id": j.id,
                "nom": j.nom,
                "role": j.role,
                "attention": j.attention,
                "score": j.score,
            },
        }

    # sinon on l’ajoute
    try:
        j = m.ajouter_joueur(req.nom)  # (méthode ajoutée côté moteur, voir plus bas)
    except Exception as e:
        return JSONResponse(
            {"error": "inscription_failed", "reason": str(e)}, status_code=400
        )

    # Déverrouiller si assez de joueurs
    if len(m.etat.joueurs) >= 2 and m.etat.phase == "inscription":
        m.etat.phase = "definition"
        # journal minimal (optionnel)
        m._log(
            action={
                "type": "_system_phase_unlock",
                "auteur_id": "_system",
                "payload": {},
            },
            evenements=[Evenement("phase_changee", {"phase": "definition"})],
        )

    return {
        "ok": True,
        "joueur": {
            "id": j.id,
            "nom": j.nom,
            "role": j.role,
            "attention": j.attention,
            "score": j.score,
        },
    }


@app.get("/parties/{partie_id}")
def obtenir_etat(partie_id: str):
    """Retourne l’état complet d’une partie."""
    moteur = parties.get(partie_id)
    if not moteur:
        return JSONResponse({"error": "partie introuvable"}, status_code=404)
    e = moteur.etat
    return JSONResponse(
        {
            "id": e.id,
            "joueurs": {j.id: j.__dict__ for j in e.joueurs.values()},
            "tour": e.tour,
            "phase": e.phase,
            "tension": e.tension,
            "contentieux": e.contentieux,
            "partie_status": e.partie_status,
            "journal": e.journal[-10:],  # les 10 derniers événements
        }
    )


@app.post("/parties/{partie_id}/actions")
def appliquer_action(partie_id: str, action: ActionInput):
    moteur = parties.get(partie_id)
    if not moteur:
        return JSONResponse({"error": "partie introuvable"}, status_code=404)

    # dry-run rapide pour fournir une raison utile
    vr = valider_action(partie_id, ValidationInput(**action.model_dump()))
    if not vr.ok:
        return JSONResponse({"error": "refus", "reason": vr.reason}, status_code=400)

    act = Action(type=action.type, auteur_id=action.auteur_id, payload=action.payload)
    evts = moteur.appliquer_action(act) or []
    return JSONResponse([e.__dict__ for e in evts])


@app.get("/parties/{partie_id}/actions/possibles")
def actions_possibles(partie_id: str, joueur_id: str):
    moteur = parties.get(partie_id)
    if not moteur:
        return JSONResponse({"error": "partie introuvable"}, status_code=404)

    cfg = getattr(moteur.etat, "_cfg", None)
    if not cfg:
        # fallback: recharger la config de règles SANS toucher à l’état
        try:
            schema_path = PROJECT_ROOT / "docs" / "schemas" / "regles.schema.json"
            cfg = charger_yaml(str(YAML_DEFAULT), schema_path=str(schema_path))
            setattr(moteur.etat, "_cfg", cfg)
        except Exception as ex:
            return JSONResponse(
                {"error": f"regles non chargees: {ex}"}, status_code=500
            )

    possibles = []
    from moteur_jeu.regles_loader import _check_preconditions
    from moteur_jeu.moteur import Action as A

    for name, a_cfg in cfg.actions.items():
        act = A(type=name, auteur_id=joueur_id, payload={})
        pre = _check_preconditions(moteur.etat, act, a_cfg)
        if pre is None:
            possibles.append(name)
    return {"possibles": possibles}


@app.post("/parties/{partie_id}/tour/debut")
def debut_nouveau_tour(partie_id: str):
    moteur = parties.get(partie_id)
    if not moteur:
        return JSONResponse({"error": "partie introuvable"}, status_code=404)

    evts = moteur.debut_nouveau_tour()
    if evts is None:
        evts = []  # fallback si le moteur ne renvoie rien

    # Toujours renvoyer du JSON strict
    return JSONResponse(
        [{"type": e.type, "donnees": e.donnees, "ts": e.ts} for e in evts]
    )


@app.post("/parties/{partie_id}/save")
def sauvegarder_partie(partie_id: str, path: str = Body(..., embed=True)):
    """
    Sauvegarde l'état de la partie dans un fichier JSON (path absolu conseillé).
    """
    moteur = parties.get(partie_id)
    if not moteur:
        return JSONResponse({"error": "partie introuvable"}, status_code=404)
    sauvegarder(moteur.etat, path, meta={"regles": "reforme-x.yaml"})
    return {"ok": True, "path": path}


@app.post("/parties/load")
def charger_partie(path: str = Body(..., embed=True)):
    # 1) Charger l’état + meta (utilise ton noyau)
    data = charger(path)  # retourne le dict serialisé
    # Recréer un moteur avec cet état
    from moteur_jeu.moteur import Moteur

    etat_data = data["etat"]
    # Si ton noyau fournit moteur_depuis_fichier, tu peux l'utiliser.
    # Sinon, on reconstruit EtatJeu via une fonction existante (tu l'as dans les tests).
    m2 = moteur_depuis_fichier(path)  # préférable si dispo et testé
    moteur = Moteur(etat=m2.etat, regles=m2.regles)

    # 2) Re-attacher moteur
    setattr(moteur.etat, "_moteur", moteur)

    # 3) Re-attacher cfg SANS ré-initialiser l’état
    regles_name = (data.get("meta") or {}).get("regles", "reforme-x.yaml")
    schema_path = PROJECT_ROOT / "docs" / "schemas" / "regles.schema.json"
    cfg = charger_yaml(
        str((PROJECT_ROOT / "docs" / "regles" / regles_name)),
        schema_path=str(schema_path),
    )
    setattr(moteur.etat, "_cfg", cfg)

    # 4) Enregistrer la partie en mémoire
    parties[moteur.etat.id] = moteur

    e = moteur.etat
    return {"id": e.id, "tour": e.tour, "phase": e.phase, "tension": e.tension}


@app.post("/parties/{partie_id}/actions/valider", response_model=ValidationResult)
def valider_action(partie_id: str, data: ValidationInput):
    moteur = parties.get(partie_id)
    if not moteur:
        raise HTTPException(404, "partie introuvable")

    cfg = getattr(moteur.etat, "_cfg", None)
    if not cfg:
        # petit fallback si _cfg a sauté (ex: après /load)
        schema_path = PROJECT_ROOT / "docs" / "schemas" / "regles.schema.json"
        cfg = charger_yaml(str(YAML_DEFAULT), schema_path=str(schema_path))
        setattr(moteur.etat, "_cfg", cfg)

    a_cfg = cfg.actions.get(data.type)
    if not a_cfg:
        return ValidationResult(ok=False, reason="action_inconnue")

    # 1) préconditions YAML (phase, exigences, etc.)
    from moteur_jeu.moteur import Action as A

    pre = _check_preconditions(
        moteur.etat,
        A(type=data.type, auteur_id=data.auteur_id, payload=data.payload),
        a_cfg,
    )
    if pre:
        # uniformiser en codes simples
        r = (
            pre.donnees.get("reason")
            if isinstance(pre.donnees, dict)
            else "refus_precondition"
        )
        return ValidationResult(ok=False, reason=str(r))

    # 2) budget d’attention (sans payer)
    j = moteur.etat.joueurs.get(data.auteur_id)
    if not j:
        return ValidationResult(ok=False, reason="joueur_introuvable")
    cost = int(a_cfg.get("attention_cost", 1))
    if j.attention < cost:
        return ValidationResult(ok=False, reason="attention_insuffisante")

    return ValidationResult(ok=True)


@app.get("/tables")
def lister_tables(active_only: int = 0):
    # ménage léger: supprimer les tables démarrées dont la partie est finie/absente
    to_delete = []
    for tid, t in list(tables.items()):
        if t.demarree and t.partie_id:
            m = parties.get(t.partie_id)
            if (m is None) or (m.etat.partie_status == "terminee"):
                to_delete.append(tid)
    for tid in to_delete:
        tables.pop(tid, None)

    items = []
    for t in tables.values():
        if active_only == 1 and t.demarree:
            # si on veut voir seulement les salles d’attente (non démarrées)
            continue
        items.append(
            {
                "id": t.id,
                "nom_table": t.nom_table,
                "attendus_min": t.attendus_min,
                "joueurs": t.joueurs,
                "host": t.host,
                "demarree": t.demarree,
                "partie_id": t.partie_id,
            }
        )
    return items


@app.post("/tables/cleanup")
def cleanup_tables():
    removed = []
    for tid, t in list(tables.items()):
        if t.demarree and t.partie_id:
            m = parties.get(t.partie_id)
            if (m is None) or (m.etat.partie_status == "terminee"):
                removed.append(tid)
                tables.pop(tid, None)
    return {"ok": True, "removed": removed}


@app.post("/tables")
def creer_table(req: TableCreateRequest):
    tid = str(uuid.uuid4())
    t = TableEtat(
        id=tid,
        cree_a=time.time(),
        nom_table=req.nom_table,
        attendus_min=max(2, req.attendus_min),
        joueurs={},
        host=None,
        regles_file=req.regles_file,
        demarree=False,
        partie_id=None,
    )
    tables[tid] = t
    return {"ok": True, "table": t.dict()}


@app.get("/tables/{tid}")
def etat_table(tid: str):
    t = tables.get(tid)
    if not t:
        return JSONResponse(
            {"error": "not_found", "reason": "table introuvable"}, status_code=404
        )
    return t.dict()


@app.post("/tables/{tid}/join")
def table_join(tid: str, req: TableJoinRequest):
    t = tables.get(tid)
    if not t:
        return JSONResponse(
            {"error": "not_found", "reason": "table introuvable"}, status_code=404
        )
    if t.demarree:
        return JSONResponse(
            {"error": "already_started", "reason": "la partie est déjà démarrée"},
            status_code=400,
        )
    # inscrit le joueur s'il n'existe pas
    if req.nom not in t.joueurs:
        t.joueurs[req.nom] = False
        if not t.host:
            t.host = req.nom
    return {"ok": True, "table": t.dict(), "you_are_host": (t.host == req.nom)}


@app.post("/tables/{tid}/ready")
def table_ready(tid: str, req: TableReadyRequest):
    t = tables.get(tid)
    if not t:
        return JSONResponse(
            {"error": "not_found", "reason": "table introuvable"}, status_code=404
        )
    if req.nom not in t.joueurs:
        return JSONResponse(
            {"error": "forbidden", "reason": "non inscrit à cette table"},
            status_code=403,
        )
    t.joueurs[req.nom] = bool(req.ready)
    return {"ok": True, "table": t.dict()}


@app.post("/tables/{tid}/start")
def table_start(tid: str, body: dict = Body(...)):
    t = tables.get(tid)
    if not t:
        return JSONResponse({"error": "not_found"}, status_code=404)

    host = (body or {}).get("host")
    noms = (body or {}).get("joueurs", []) or list(t.joueurs.keys())
    if host and host not in noms:
        noms.append(host)

    m = Moteur.creer_partie(noms)
    try:
        m.charger_regles_yaml(str(YAML_DEFAULT))
    except Exception as e:
        return JSONResponse({"error": "regles", "reason": str(e)}, status_code=500)

    parties[m.etat.id] = m

    t.demarree = True
    t.partie_id = m.etat.id
    return {"ok": True, "pid": m.etat.id}


# ===============================
# WEBSOCKET (notifications temps réel)
# ===============================


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Un simple canal WebSocket pour recevoir les journaux en direct.
    Le client envoie: {"type": "subscribe", "partie_id": "..."}
    """
    await ws.accept()
    moteur: Moteur = None
    try:
        msg = await ws.receive_json()
        if msg.get("type") == "subscribe":
            partie_id = msg.get("partie_id")
            moteur = parties.get(partie_id)
            if not moteur:
                await ws.send_json({"error": "partie introuvable"})
                return
            await ws.send_json({"ok": True, "msg": f"Abonné à la partie {partie_id}"})
        else:
            await ws.send_json({"error": "commande invalide"})
            return

        # Boucle d’envoi du journal
        last_len = 0
        while True:
            e = moteur.etat
            if len(e.journal) > last_len:
                new_entries = e.journal[last_len:]
                await ws.send_text(json.dumps(new_entries, ensure_ascii=False))
                last_len = len(e.journal)
            await ws.receive_text()  # ping ou noop pour garder la connexion
    except WebSocketDisconnect:
        print("🔌 WebSocket déconnecté")
    except Exception as ex:
        await ws.send_json({"error": str(ex)})


# ===============================
# Utilitaires
# ===============================
def _trouver_joueur_id_par_nom(etat, nom: str) -> Optional[str]:
    for j in etat.joueurs.values():
        if j.nom == nom:
            return j.id
    return None


# ===============================
# Lancement local
# ===============================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8080, reload=True)
