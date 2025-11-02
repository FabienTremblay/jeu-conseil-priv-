#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8080}"
TMP_SAVE="${TMP_SAVE:-/tmp/partie-reforme.json}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "❌ Il faut '$1' dans le PATH"; exit 1; }
}

need curl
need jq

echo "▶️  Test API base = $API_BASE"

# 1) Créer une partie
echo "➕ Création de partie…"
CREATE_JSON=$(curl -s -X POST "$API_BASE/parties" -H "Content-Type: application/json" -d '["Alice","Bob"]')
PID=$(echo "$CREATE_JSON" | jq -r '.id')
[ -n "$PID" ] || { echo "❌ PID vide"; echo "$CREATE_JSON"; exit 1; }
echo "   PID=$PID"

# 2) Récupérer l'état + JID d'Alice
STATE_JSON=$(curl -s "$API_BASE/parties/$PID")
JID_ALICE=$(echo "$STATE_JSON" | jq -r '.joueurs | to_entries[] | select(.value.nom=="Alice") .value.id')
[ -n "$JID_ALICE" ] || { echo "❌ JID_ALICE introuvable"; exit 1; }
echo "   JID_ALICE=$JID_ALICE"

# 3) Lister actions possibles (si dispo)
echo "📜 Actions possibles (si endpoint présent)…"
if curl -s -f "$API_BASE/parties/$PID/actions/possibles?joueur_id=$JID_ALICE" >/dev/null 2>&1; then
  POSSIBLES=$(curl -s "$API_BASE/parties/$PID/actions/possibles?joueur_id=$JID_ALICE" | jq -r '.possibles | join(", ")')
  echo "   possibles: $POSSIBLES"
else
  echo "   (endpoint /actions/possibles non disponible — OK)"
fi

# Dry-run: devrait répondre { "ok": true }
curl -s -X POST "$API_BASE/parties/$PID/actions/valider" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"proposer_reforme\",\"auteur_id\":\"$JID_ALICE\",\"payload\":{}}" | jq

# Si tu brûles l’attention d’Alice puis relances un dry-run:
# --> { "ok": false, "reason": "attention_insuffisante" }

# 4) Proposer la réforme
echo "🗳️  proposer_reforme…"
curl -s -X POST "$API_BASE/parties/$PID/actions" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"proposer_reforme\",\"auteur_id\":\"$JID_ALICE\",\"payload\":{}}" | jq -e '.[0].type=="attention_depensee"' >/dev/null

# 5) Ouvrir la négociation
echo "🤝 ouvrir_negociation…"
curl -s -X POST "$API_BASE/parties/$PID/actions" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"ouvrir_negociation\",\"auteur_id\":\"$JID_ALICE\",\"payload\":{}}" | jq -e 'map(select(.type=="phase_changee")) | length >= 1' >/dev/null

# 6) Faire campagne
echo "📣 faire_campagne…"
curl -s -X POST "$API_BASE/parties/$PID/actions" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"faire_campagne\",\"auteur_id\":\"$JID_ALICE\",\"payload\":{}}" | jq -e 'map(select(.type=="campagne_menee")) | length >= 1' >/dev/null

# 7) Nouveau tour
echo "🔁 début nouveau tour…"
curl -s -X POST "$API_BASE/parties/$PID/tour/debut" | jq -e '.[0].type=="nouveau_tour"' >/dev/null

# 8) Refaire campagne — devrait mener vers victoire si règles par défaut
echo "📣 faire_campagne (tour 2)…"
curl -s -X POST "$API_BASE/parties/$PID/actions" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"faire_campagne\",\"auteur_id\":\"$JID_ALICE\",\"payload\":{}}" >/dev/null

# 9) Vérifier l'état final (victoire OU soutien >=5)
STATE_FINAL=$(curl -s "$API_BASE/parties/$PID")
STATUS=$(echo "$STATE_FINAL" | jq -r '.partie_status')
SOUTIEN=$(echo "$STATE_FINAL" | jq -r '.contentieux.reforme_x.soutien // 0')

if [[ "$STATUS" == "terminee" ]] || [[ "$SOUTIEN" -ge 5 ]]; then
  echo "🏁 État final OK (status=$STATUS, soutien=$SOUTIEN)"
else
  echo "❌ État final inattendu (status=$STATUS, soutien=$SOUTIEN)"
  echo "$STATE_FINAL" | jq
  exit 1
fi

# 10) Sauvegarder, recharger et vérifier cohérence de phase
echo "💾 Sauvegarde…"
curl -s -X POST "$API_BASE/parties/$PID/save" -H "Content-Type: application/json" -d "{\"path\":\"$TMP_SAVE\"}" | jq -e '.ok==true' >/dev/null
PHASE_BEFORE=$(echo "$STATE_FINAL" | jq -r '.phase')

echo "📂 Rechargement…"
LOAD_JSON=$(curl -s -X POST "$API_BASE/parties/load" -H "Content-Type: application/json" -d "{\"path\":\"$TMP_SAVE\"}")
PID2=$(echo "$LOAD_JSON" | jq -r '.id')
PHASE_AFTER=$(echo "$LOAD_JSON" | jq -r '.phase')

if [[ -n "$PID2" ]]; then
  echo "   PID2=$PID2 (phase=$PHASE_AFTER)"
else
  echo "❌ Rechargement a échoué"; echo "$LOAD_JSON"; exit 1
fi

if [[ "$PHASE_AFTER" != "" && "$PHASE_BEFORE" == "$PHASE_AFTER" ]]; then
  echo "🔒 Phase cohérente après reload ($PHASE_AFTER) — OK"
else
  echo "⚠️  Phase différente après reload (avant=$PHASE_BEFORE, après=$PHASE_AFTER) — vérifie le /parties/load"
fi

echo "✅ Smoke test API — PASS"
