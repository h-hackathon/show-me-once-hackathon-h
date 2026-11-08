#!/bin/sh
# Lance le tool de bureau livré avec cette Skill, depuis le shell de l'agent H :
#   ./run.sh precheck
#   ./run.sh run '{"reference": "F-1", ...}'
# Le résultat est un JSON sur la sortie standard (status = draft_saved | duplicate | flagged | error).
# Python : python3 s'il a pydantic, sinon celui de `cua` (le CLI de H, déjà dans l'environnement de l'agent).
here=$(cd "$(dirname "$0")" && pwd)
cua_python=$(sed -n '1s/^#!//p' "$(command -v cua 2>/dev/null)" 2>/dev/null)
for py in python3 "$cua_python"; do
  if [ -n "$py" ] && "$py" -c "import pydantic" 2>/dev/null; then
    PYTHONPATH="$here" exec "$py" -m h_tools.cli "$here/tool" "$@"
  fi
done
echo '{"ok": false, "status": "error", "error": "aucun Python avec pydantic dans cet environnement"}'
exit 1
