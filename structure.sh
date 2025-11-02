#!/usr/bin/env bash
set -euo pipefail

PROJ="."
echo "==> Création du projet: $PROJ"

mkdir -p "$PROJ"/{docs/{decisions,schemas,regles},env/dev,infra/compose/traefik,outils/scripts,packages/{moteur-jeu,api,worker,monitor-web},mobile,tests/{unitaires,integra}}

# -------------------------------------------------------------------
# FICHIERS RACINE
# -------------------------------------------------------------------
cat > "$PROJ/.gitignore" <<'GIT'
# Python
__pycache__/
*.pyc
.venv/
.env
env/dev/.env

# Node
node_modules/
.next/
dist/

# Docker
*.log
pgdata/
redisdata/

# IDE
.vscode/
.idea/
GIT

cat > "$PROJ/.editorconfig" <<'EC'
root = true
[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
indent_style = space
indent_size = 2
EC

cat > "$PROJ/README.md" <<'MD'
# Jeu d’aventure politique — Monorepo

- **moteur-jeu** : noyau Python (domaine + règles)
- **api** : FastAPI (REST + WebSocket), migrations Alembic
- **worker** : tâches asynchrones (RQ)
- **monitor-web** : moniteur/observabilité (Next.js)
- **mobile** : squelette (Expo RN/PWA — optionnel)
MD


