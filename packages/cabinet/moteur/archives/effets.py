# packages/cabinet/moteur/effets.py
from typing import Callable, Dict, Any
from .etat import Etat

Impact = Dict[str, Any]
EffectFn = Callable[[Etat, Dict[str, Any], "RngFacade"], Impact]
EFFECTS: Dict[str, EffectFn] = {}

def register(name: str):
    def deco(fn: EffectFn):
        EFFECTS[name] = fn
        return fn
    return deco

def appliquer_effets(etat, effets, rng):
    """
    Applique la liste d’effets (dicts {'type':..., 'params':...}) via le registre EFFECTS.
    Renvoie la liste des impacts pour l’historique.
    """
    impacts = []
    for eff in effets or []:
        fn = EFFECTS[eff["type"]]
        impacts.append(fn(etat, eff.get("params", {}), rng))
    return impacts

@register("tension_axis_delta")
def eff_tension_axis_delta(etat: Etat, params, rng) -> Impact:
    axe = params["axis"]
    delta = int(params["delta"])
    a = etat.axes[axe]
    old = a.valeur
    a.valeur = max(0, min(10, a.valeur + delta))
    return {"event":"tension_axis_changee","axis":axe,"old":old,"new":a.valeur,"delta":delta}

@register("depenses_poste_delta")
def eff_depenses_poste_delta(etat: Etat, params, rng) -> Impact:
    poste = params["poste"]; d = int(params["delta"])
    old = etat.eco.depenses_postes.get(poste, 0)
    etat.eco.depenses_postes[poste] = old + d
    return {"event":"depenses_poste_changees","poste":poste,"old":old,"new":old+d}

@register("emit_event")
def eff_emit_event(etat: Etat, params, rng) -> Impact:
    # effet “no-op” pour tests, utile pour tracer
    kind = params.get("kind", "noop")
    return {"event":"emit_event","kind":kind}

@register("capital_politique_delta")
def eff_capital_politique_delta(etat: Etat, params, rng) -> Impact:
    # prend en charge cible="auteur" et auto-injection auteur_id si absent (conforme aux tests)
    cible = params.get("cible", "auteur")
    delta = int(params.get("delta", 0))
    auteur_id = params.get("auteur_id")
    if cible == "auteur" and not auteur_id:
        auteur_id = getattr(etat, "_effet_auteur_id", None)  # posé par l’exécution de mesure
    if not auteur_id or auteur_id not in etat.joueurs:
        return {"event":"capital_politique_delta_ignored"}
    j = etat.joueurs[auteur_id]
    old = j.capital_politique
    j.capital_politique = old + delta
    return {"event":"capital_politique_change","joueur":auteur_id,"old":old,"new":j.capital_politique,"delta":delta}

