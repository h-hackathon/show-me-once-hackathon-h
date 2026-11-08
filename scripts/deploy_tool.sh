#!/usr/bin/env bash
# Déploie tools/<nom> sur Railway (service tool-<nom>), lui donne une adresse publique, puis l'annonce à SMO.
# Un tool de bureau ne va pas sur Railway : ses fichiers partent à SMO, qui les pose dans la Skill de l'agent bureau.
# Lancé par .github/workflows/deploy.yml, une fois par tool modifié. Aucune variable de site : les identifiants
# viennent du vault H, lus par SMO à chaque appel.
#
#   RAILWAY_API_TOKEN, RAILWAY_PROJECT_ID   obligatoires (token de compte : un token de projet ne crée pas de service)
#   RAILWAY_ENV_NAME                        environnement Railway (défaut : production)
#   SMO_SERVER_URL, SMO_SERVER_TOKEN        annoncer le tool à SMO, qui le vérifie (precheck) et met l'agent H à jour
#
#   bash scripts/deploy_tool.sh <nom>
set -euo pipefail

name=$1
service="tool-${name//_/-}"            # nom de service Railway : pas de _
sha=${GITHUB_SHA:-$(git rev-parse HEAD)}
here=$(cd "$(dirname "$0")" && pwd)
[ -f "tools/$name/tool.py" ] || { echo "tools/$name/tool.py introuvable" >&2; exit 1; }
if grep -qE '^KIND *= *"desktop"' "tools/$name/tool.py"; then
  echo "$name : tool de bureau, livré avec la Skill de l'agent (pas de Railway)"
  exec python3 "$here/announce.py" "$name" "$sha"
fi

# 1. Le contexte de build : le runtime commun et ce tool seul, copié en tool/
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
cp -r Dockerfile railway.json pyproject.toml uv.lock h_tools "$build/"
cp -r "tools/$name" "$build/tool"
echo "$sha" > "$build/tool/VERSION"
find "$build" -name __pycache__ -type d -prune -exec rm -rf {} +
cd "$build"

# 2. Nouveau tool : on crée son service. Deux variables seulement : PORT, et SMO_SERVER_TOKEN pour que le tool
#    n'accepte que les appels de SMO.
#    Un jeton d'équipe (workspace) ne lit pas `me` : sans --workspace, railway link répond « Unauthorized ».
workspace=$(curl -sS --max-time 20 https://backboard.railway.com/graphql/v2 -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -d "$(printf '{"query":"query($id: String!) { project(id: $id) { workspaceId } }","variables":{"id":"%s"}}' "$RAILWAY_PROJECT_ID")" \
  | sed -n 's/.*"workspaceId":"\([^"]*\)".*/\1/p')
railway link --project "$RAILWAY_PROJECT_ID" --environment "${RAILWAY_ENV_NAME:-production}" ${workspace:+--workspace "$workspace"}
if ! railway variables --service "$service" --kv >/dev/null 2>&1; then
  echo "nouveau service : $service"
  railway add --service "$service"
fi
#    Posées à chaque déploiement (un service créé à la main n'en a aucune) : sans PORT, Railway en choisit un autre que
#    celui de l'adresse publique (502) ; le jeton vient du secret GitHub, sans variable partagée Railway à créer.
railway variables --service "$service" --skip-deploys --set "PORT=8080" \
  ${SMO_SERVER_TOKEN:+--set "SMO_SERVER_TOKEN=$SMO_SERVER_TOKEN"} > /dev/null

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

# 5. Annonce à SMO (adresse + commit) : il attend le nouveau commit, fait un precheck avec le vault de chaque agent
#    qui attend ce tool, puis le leur donne. Precheck en échec → déploiement en échec (Devin le voit : gh run watch).
python3 "$here/announce.py" "$name" "$sha" "$url"
