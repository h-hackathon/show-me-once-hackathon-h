#!/usr/bin/env bash
# Avant tout déploiement : RAILWAY_API_TOKEN voit-il le projet RAILWAY_PROJECT_ID ? Sinon, dit pourquoi en clair (le
# CLI ne répond que « Unauthorized »). N'affiche jamais le jeton.
#
#   RAILWAY_API_TOKEN=… RAILWAY_PROJECT_ID=… bash scripts/check_railway_token.sh
set -uo pipefail

api=https://backboard.railway.com/graphql/v2
token=${RAILWAY_API_TOKEN:-}
project=${RAILWAY_PROJECT_ID:-}

ask() {   # ask <en-tête d'auth> <requête GraphQL> [id du projet]
  curl -sS --max-time 20 "$api" -H "Content-Type: application/json" -H "$1" \
    -d "$(printf '{"query":"%s","variables":{"id":"%s"}}' "$2" "${3:-}")"
}

[ -n "$token" ] || { echo "RAILWAY_API_TOKEN est vide : secret GitHub absent" >&2; exit 1; }
[ -n "$project" ] || { echo "RAILWAY_PROJECT_ID est vide : secret GitHub absent" >&2; exit 1; }
[ "$token" = "$(printf '%s' "$token" | tr -d '[:space:]')" ] \
  || echo "attention : RAILWAY_API_TOKEN contient un espace ou un retour à la ligne (copier-coller ?)" >&2
[ "$project" = "$(printf '%s' "$project" | tr -d '[:space:]')" ] \
  || echo "attention : RAILWAY_PROJECT_ID contient un espace ou un retour à la ligne (copier-coller ?)" >&2

seen=$(ask "Authorization: Bearer $token" 'query($id: String!) { project(id: $id) { name } }' "$project")
if printf '%s' "$seen" | grep -q '"name"'; then
  echo "jeton Railway OK : il voit le projet $(printf '%s' "$seen" | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')"
  exit 0
fi

if ask "Authorization: Bearer $token" '{ me { id } }' | grep -q '"id"'; then
  echo "RAILWAY_API_TOKEN est un jeton de compte valide, mais ce compte ne voit pas le projet RAILWAY_PROJECT_ID :" \
       "le jeton vient d'un autre compte, ou l'identifiant de projet est faux (c'est l'UUID dans Project Settings)." >&2
  exit 1
fi

if ask "Project-Access-Token: $token" '{ projectToken { projectId } }' | grep -q '"projectId"'; then
  echo "RAILWAY_API_TOKEN est un jeton de PROJET : il ne crée pas de service. Il faut un jeton de compte," \
       "créé dans Account Settings → Tokens (sans équipe) par le propriétaire du projet." >&2
  exit 1
fi

echo "RAILWAY_API_TOKEN refusé par Railway : jeton révoqué ou mal copié, ou jeton d'une équipe qui n'a pas ce projet." \
     "Réponse : $(printf '%s' "$seen" | sed -n 's/.*"message":"\([^"]*\)".*/\1/p')" >&2
exit 1
