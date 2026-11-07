#!/usr/bin/env bash
# Déploie tools/<nom> sur Railway (service tool-<nom>), lui donne une adresse publique, puis l'annonce à SMO.
# Lancé par .github/workflows/deploy.yml, une fois par tool modifié.
#
#   RAILWAY_API_TOKEN, RAILWAY_PROJECT_ID   obligatoires (token de compte : un token de projet ne crée pas de service)
#   RAILWAY_ENV_NAME                        environnement Railway (défaut : production)
#   SMO_SERVER_URL, SMO_SERVER_TOKEN        annoncer le tool à SMO (adresse + commit), qui met l'agent H à jour
#
#   bash scripts/deploy_tool.sh <nom>
set -euo pipefail

name=$1
service="tool-${name//_/-}"            # nom de service Railway : pas de _
sha=${GITHUB_SHA:-$(git rev-parse HEAD)}
[ -f "tools/$name/tool.py" ] || { echo "tools/$name/tool.py introuvable" >&2; exit 1; }
if grep -qE '^KIND *= *"desktop"' "tools/$name/tool.py"; then
  echo "$name : tool de bureau (accessibilité macOS), il tourne là où tourne l'appli, pas sur Railway"
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

# 2. Nouveau tool : on crée son service. Ses variables pointent vers les variables partagées du projet,
#    dont SMO_SERVER_TOKEN : le tool n'accepte que les appels de SMO.
railway link --project "$RAILWAY_PROJECT_ID" --environment "${RAILWAY_ENV_NAME:-production}"
if ! railway variables --service "$service" --kv >/dev/null 2>&1; then
  vars=(--variables "PORT=8080" --variables "SMO_SERVER_TOKEN=\${{shared.SMO_SERVER_TOKEN}}")
  for key in $(grep -vE '^[[:space:]]*(#|$)' tool/env.txt 2>/dev/null || true); do
    vars+=(--variables "$key=\${{shared.$key}}")
  done
  echo "nouveau service : $service"
  railway add --service "$service" "${vars[@]}"
fi

# 3. Build et déploiement : sort en erreur si le build échoue
railway up --service "$service" --ci

# 4. Adresse publique : SMO tourne dans un autre projet Railway, le réseau privé ne le joint pas
out=$(railway domain --service "$service" --port 8080 2>&1 || true)
url=$(printf '%s\n' "$out" | grep -oE 'https://[a-z0-9.-]+\.up\.railway\.app' | head -1 || true)
if [ -z "$url" ]; then
  domain=$(railway variables --service "$service" --kv | sed -n 's/^RAILWAY_PUBLIC_DOMAIN=//p' | head -1)
  [ -n "$domain" ] && url="https://$domain"
fi
[ -n "$url" ] || { echo "$service : pas d'adresse publique ($out)" >&2; exit 1; }
echo "$service : $url"

# 5. Annonce à SMO (adresse + commit) ; SMO répond live_sha = le commit qu'il voit en appelant le tool.
#    On recommence tant que Railway n'a pas basculé sur le nouveau commit.
if [ -n "${SMO_SERVER_URL:-}" ]; then
  live=""
  for _ in $(seq 60); do
    live=$(curl -fsS -X POST "$SMO_SERVER_URL/hooks/tool-deployed" -H "X-SMO-Token: ${SMO_SERVER_TOKEN:-}" \
             -H "content-type: application/json" -d "{\"tool\": \"$name\", \"sha\": \"$sha\", \"url\": \"$url\"}" \
           | jq -r .live_sha) || live=""
    [ "$live" = "$sha" ] && break
    sleep 10
  done
  [ "$live" = "$sha" ] || { echo "SMO ne voit pas $service au commit $sha après 10 min" >&2; exit 1; }
  echo "$service annoncé à SMO ($sha) : l'agent H est mis à jour"
fi
