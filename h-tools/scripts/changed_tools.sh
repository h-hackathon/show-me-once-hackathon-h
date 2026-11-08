#!/usr/bin/env bash
# Les tools à tester ou déployer depuis un commit : ceux dont le dossier a changé, tous si le runtime commun a changé.
#
#   bash scripts/changed_tools.sh <commit de base> [<commit>]     base vide ou inconnue → tous les tools
set -euo pipefail
base=${1:-}
head=${2:-HEAD}

all_tools() {
  for dir in tools/*/; do
    name=$(basename "$dir")
    case $name in _*|.*) continue ;; esac
    if [ -f "tools/$name/tool.py" ]; then echo "$name"; fi
  done
}

if [ -z "$base" ] || ! git cat-file -e "$base^{commit}" 2>/dev/null; then
  all_tools
  exit 0
fi
changed=$(git diff --name-only "$base" "$head")
if grep -qE '^(h_tools/|Dockerfile$|railway\.json$|pyproject\.toml$|uv\.lock$)' <<<"$changed"; then
  all_tools
  exit 0
fi
for name in $( { grep -E '^tools/[^/]+/' <<<"$changed" || true; } | cut -d/ -f2 | sort -u); do
  case $name in _*|.*) continue ;; esac
  if [ -f "tools/$name/tool.py" ]; then echo "$name"; fi   # un dossier supprimé ne se déploie pas
done
