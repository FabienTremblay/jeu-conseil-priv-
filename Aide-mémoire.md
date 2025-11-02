# Jeu d’aventure politique — Monorepo

- **moteur-jeu** : noyau Python (domaine + règles)
- **api** : FastAPI (REST + WebSocket), migrations Alembic
- **worker** : tâches asynchrones (RQ)
- **monitor-web** : moniteur/observabilité (Next.js)
- **mobile** : squelette (Expo RN/PWA — optionnel)

## Démarrer

```bash
docker compose -f infra/compose/docker-compose.dev.yml up -d --build

## Tester le noyau et d'autres gogosses :
source env/dev/bin/activate

PYTHONPATH=packages pytest -v packages/cabinet/tests

python -m jsonschema -i packages/cabinet/skins/demo_minimal.yaml packages/cabinet/schemas/regles.schema.json
check-jsonschema --schemafile packages/cabinet/schemas/regles.schema.json packages/cabinet/skins/demo_minimal.yaml 

## Suivi des métrics 
Collecter pendant un run manuel (tests/dev) :

from cabinet.moteur.metrics import MetricsSink
sink = MetricsSink(partie_id="p-1")
etat = run_tour(etat, cfg, rng, actions_conseil=actions, votes=votes, metrics=sink)
### … après N tours :
sink.flush_csv("out/telemetry.csv")


Batch :

PYTHONPATH=packages python3 packages/cabinet/tools/sim_runner.py \
  --skin packages/cabinet/skins/demo_minimal.yaml \
  --games 200 --tours 10 --out out/telemetry.csv


Le CSV te donne, par tour et par partie, de quoi:

tracer la dynamique des axes,

voir la pression budgétaire (solde/dette),

mesurer l’utilisation de capacité et la taille du programme,

quantifier l’impact net sur le capital politique collectif.

## Jouer
### CLI
avpol --help

### TUI
PYTHONPATH=packages/moteur-jeu/src:packages/api:packages/tui-jeu/src   python -m tui_jeu.main
```
