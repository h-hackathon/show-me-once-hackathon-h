#!/usr/bin/env bash
# Déploie tools/<nom> sur Railway (service tool-<nom>), attend qu'il tourne, puis prévient SMO.
# Lancé par .github/workflows/deploy.yml, une fois par tool modifié.
#
#   RAILWAY_API_TOKEN, RAILWAY_PROJECT_ID   obligatoires (token de compte : un token de projet ne crée pas de service)
#   RAILWAY_ENV_NAME                        environnement Railway (défaut : production)
#   SMO_WATCHER_URL, SMO_SERVER_TOKEN       optionnels : attendre que le watcher voie le nouveau commit
#   SMO_SERVER_URL                          optionnel : prévenir SMO, qui met l'agent H à jour
#
#   bash scripts/deploy_tool.sh <nom>
set -euo pipefail

name=$1
service="tool-${name//_/-}"            # nom DNS du réseau privé (tool-<nom>.railway.internal) : pas de _
sha=${GITHUB_SHA:-$(git rev-parse HEAD)}
[ -f "tools/$name/tool.py" ] || { echo "tools/$name/tool.py introuvable" >&2; exit 1; }
if grep -qE '^KIND *= *"desktop"' "tools/$name/tool.py"; then
  echo "$name : tool de bureau (accessibilité macOS), il tourne sur le Mac, pas sur Railway"
  exit 0
fi

# 1. Le contexte de build : le runtime commun et ce tool seul, copié en tool/
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
cp -r Dockerfile railway.json pyproject.toml uv.lock h_tools "$build/"
cp -r "tools/$name" "$build/tool"
echo "$sha" > "$build/tool/VERSION"
find "$build" -name __pycache__ -type d -prune -exec rm -rf {} +
cd "$build"

# 2. Nouveau tool : on crée son service. Ses variables pointent vers les variables partagées du projet.
railway link --project "$RAILWAY_PROJECT_ID" --environment "${RAILWAY_ENV_NAME:-production}"
if ! railway variables --service "$service" --kv >/dev/null 2>&1; then
  vars=(--variables "PORT=8080")
  for key in $(grep -vE '^[[:space:]]*(#|$)' tool/env.txt 2>/dev/null || true); do
    vars+=(--variables "$key=\${{shared.$key}}")
  done
  echo "nouveau service : $service"
  railway add --service "$service" "${vars[@]}"
fi

# 3. Build et déploiement : sort en erreur si le build échoue
railway up --service "$service" --ci

# 4. Attendre que le nouveau commit réponde (Railway bascule le trafic quand /health répond)
if [ -n "${SMO_WATCHER_URL:-}" ]; then
  live=""
  for _ in $(seq 60); do
    live=$(curl -fsS -H "X-SMO-Token: ${SMO_SERVER_TOKEN:-}" "$SMO_WATCHER_URL/tools/$name" | jq -r .sha) || live=""
    [ "$live" = "$sha" ] && break
    sleep 10
  done
  [ "$live" = "$sha" ] || { echo "$service ne répond pas avec le commit $sha après 10 min" >&2; exit 1; }
  echo "$service en ligne ($sha)"
fi

# 5. SMO met l'agent H à jour : precheck_<nom>, run_<nom> et la Skill du repo
if [ -n "${SMO_SERVER_URL:-}" ]; then
  curl -fsS -X POST "$SMO_SERVER_URL/hooks/tool-deployed" -H "X-SMO-Token: ${SMO_SERVER_TOKEN:-}" \
       -H "content-type: application/json" -d "{\"tool\": \"$name\", \"sha\": \"$sha\"}"
  echo
fi
