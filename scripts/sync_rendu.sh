#!/usr/bin/env bash
# Met ce repo de rendu à jour avec les repos de travail de l'équipe (à relancer juste avant le dépôt).
#   bash scripts/sync_rendu.sh && git push
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --no-edit https://github.com/Jean-Christophe972/show-me-once main          # smo/, comptarex/, prep/
git subtree pull --prefix=chargebacks https://github.com/noahsgds/show-me-once main -m "Rendu : synchro chargebacks"
git subtree pull --prefix=h-tools https://github.com/Tomoroshimaru/h-tools main -m "Rendu : synchro h-tools"
