import json
import typer
from .adaptateur import SessionLocale

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("init-partie")
def init_partie(
    joueur: list[str] = typer.Option(
        ..., "--joueur", "-j", help="Nom de joueur (option répétable)"
    ),
):
    s = SessionLocale()
    s.nouvelle_partie(joueur)
    typer.echo(f"✅ Partie initialisée avec: {', '.join(joueur)}")


@app.command("charger-regles")
def charger_regles(path: str = typer.Argument(..., help="Chemin YAML des règles")):
    s = SessionLocale()
    s.charger_regles(path)
    typer.echo(f"📜 Règles chargées depuis {path}")


@app.command("ajouter-joueur")
def ajouter_joueur(nom: str, role: str = typer.Option("citoyen", "--role", "-R")):
    s = SessionLocale()
    s.ajouter_joueur(nom, role)
    typer.echo(f"👤 Joueur « {nom} » ajouté (role={role}).")


@app.command("actions")
def actions(
    joueur: str = typer.Option(
        "", "--joueur", "-j", help="Filtrer pour un joueur (nom ou id)"
    ),
    phase_only: bool = typer.Option(
        False, "--phase-only", help="Limiter aux actions de la phase courante"
    ),
    json_only: bool = typer.Option(False, "--json", help="Sortie JSON brute"),
):
    s = SessionLocale()
    filtre = {}
    if joueur:
        filtre["joueur"] = joueur
    if phase_only:
        filtre["phase_only"] = True

    specs = s.actions_possibles(filtre)  # list[ActionSpec]

    if json_only:
        typer.echo(json.dumps(specs, ensure_ascii=False, indent=2))
        return

    if not specs:
        typer.echo("Aucune action jouable selon les filtres.")
        return

    typer.echo("Actions possibles:")
    for a in specs:
        nom = a.get("nom") or a.get("id")
        cout = a.get("cout_attention", 1)
        phase = a.get("phase", "")
        roles = ", ".join(a.get("roles", [])) if a.get("roles") else "tous"
        desc = a.get("description", "")
        typer.echo(
            f" - {nom}  (attention={cout}, phase={phase or 'toutes'}, roles={roles})"
        )
        if desc:
            typer.echo(f"     {desc}")
        params = a.get("params") or {}
        if params:
            typer.echo(f"     params: {', '.join(params.keys())}")


@app.command("jouer")
def jouer(
    auteur: str, action: str, param: list[str] = typer.Option([], "--param", "-p")
):
    s = SessionLocale()
    kv = {}
    for p in param:
        if "=" not in p:
            raise typer.BadParameter(f"Paramètre invalide: {p} (attendu clé=valeur)")
        k, v = p.split("=", 1)
        kv[k] = v
    res = s.jouer_action(auteur, action, **kv)
    typer.echo(json.dumps(res, ensure_ascii=False, indent=2))


@app.command("tour")
def tour():
    s = SessionLocale()
    s.tour_suivant()
    e = s.etat_public()
    typer.echo(f"🔁 Nouveau tour = {e['tour']} (tension={e['tension']})")


@app.command("etat")
def etat(json_only: bool = typer.Option(False, "--json")):
    s = SessionLocale()
    e = s.etat_public()
    if json_only:
        typer.echo(json.dumps(e, ensure_ascii=False, indent=2))
        return
    noms = ", ".join(f"{j['nom']}({j['attention']})" for j in e["joueurs_liste"])
    typer.echo(
        f"📌 tour={e['tour']} | tension={e['tension']} | phase={e['phase']} | status={e['partie_status']}"
    )
    typer.echo(f"👥 joueurs: {noms}")


@app.command("journal")
def journal(n: int = typer.Option(25, "--n")):
    from pathlib import Path

    p = Path(".avpol/journal.jsonl")
    if not p.exists():
        typer.echo("Aucun journal.")
        raise typer.Exit(0)
    for line in p.read_text(encoding="utf-8").splitlines()[-n:]:
        typer.echo(line)
