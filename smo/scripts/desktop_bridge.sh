#!/usr/bin/env bash
# Relais bureau du PC du live : l'agent H bureau de SMO pilote l'écran de cette machine.
#
# SMO (Railway) donne à l'agent l'environnement {"kind": "desktop", "host": "user_device", "session_id": H_DESKTOP_BRIDGE} ;
# H envoie ses clics au relais qui sert cet identifiant, c'est-à-dire ce script. Le relais s'arrête à la fin de
# chaque session H : on le relance en boucle. Ctrl-C arrête tout.
#
# Lit HAI_API_KEY et H_DESKTOP_BRIDGE dans l'environnement, sinon dans smo/.env (rien n'est affiché).
set -u

ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"

from_env_file() {   # valeur de $1 dans .env, guillemets retirés
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}

HAI_API_KEY="${HAI_API_KEY:-$(from_env_file HAI_API_KEY)}"
H_DESKTOP_BRIDGE="${H_DESKTOP_BRIDGE:-$(from_env_file H_DESKTOP_BRIDGE)}"
export HAI_API_KEY

if ! command -v holo >/dev/null 2>&1; then
  echo "holo introuvable. Installe-le : uv tool install \"hai-agents[cli,desktop]==1.4.3\"" >&2
  exit 1
fi
if [ -z "$HAI_API_KEY" ]; then
  echo "HAI_API_KEY absente (ni dans l'environnement ni dans $ENV_FILE), ou lance : holo login" >&2
fi
if [ -z "$H_DESKTOP_BRIDGE" ]; then
  H_DESKTOP_BRIDGE="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  echo "Identifiant du relais : $H_DESKTOP_BRIDGE"
  echo "→ mets H_DESKTOP_BRIDGE=$H_DESKTOP_BRIDGE dans les variables Railway de SMO (et dans .env pour le garder)."
fi

trap 'echo; echo "Relais arrêté."; exit 0' INT TERM
echo "Relais bureau $H_DESKTOP_BRIDGE : un seul agent à la fois pilote cette machine. Ctrl-C pour arrêter."
while true; do
  started=$SECONDS
  holo local desktop --session-id "$H_DESKTOP_BRIDGE"
  code=$?
  if [ "$code" -ne 0 ] && [ $((SECONDS - started)) -lt 5 ]; then
    # échec immédiat (autorisations macOS, clé) : relancer n'y changerait rien
    echo "Le relais n'a pas démarré (code $code) : corrige le message ci-dessus, puis relance ce script." >&2
    exit "$code"
  fi
  sleep 2   # fin de session H : on rouvre le relais pour la session suivante
done
