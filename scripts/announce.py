"""Annonce un tool déployé à SMO, qui met à jour les agents H qui l'attendent après un precheck réel.

    python3 scripts/announce.py <nom> <sha> [<adresse du tool>]      SMO_SERVER_URL, SMO_SERVER_TOKEN

Tool web (avec son adresse Railway) : SMO appelle le tool ; on recommence tant qu'il ne voit pas le nouveau commit
(Railway bascule le trafic quand /health répond). SMO fait alors un precheck avec le vault de chaque agent qui
attend ce tool : s'il échoue, le déploiement est en échec et l'agent reste à l'écran avec la version d'avant.
Tool de bureau (sans adresse) : on envoie ses fichiers (le tool, le runtime, run.sh), que SMO pose dans la Skill
de l'agent bureau par l'API H. Bibliothèque standard seulement : tourne avec le python3 du runner.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ("__init__.py", "config.py", "loader.py", "desk.py", "cli.py")   # pas de Playwright ni de serveur


def bundle(name: str, sha: str) -> dict[str, str]:
    """Les fichiers d'un tool de bureau tels que l'agent les lance : ./run.sh run '{...}'."""
    files = {"run.sh": (ROOT / "scripts" / "run.sh").read_text(encoding="utf-8")}
    for module in RUNTIME:
        files[f"h_tools/{module}"] = (ROOT / "h_tools" / module).read_text(encoding="utf-8")
    folder = ROOT / "tools" / name
    for path in sorted(folder.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and not path.name.startswith("test_"):
            files[f"tool/{path.relative_to(folder).as_posix()}"] = path.read_text(encoding="utf-8")
    files["tool/VERSION"] = f"{sha}\n"
    return files


def describe(name: str) -> dict:
    """Nom, description, schéma des paramètres et Skill du tool : SMO les met dans la Skill de l'agent bureau.
    Lu avec le runtime (pydantic) par uv, que le workflow de déploiement a installé."""
    done = subprocess.run(["uv", "run", "--no-sync", "python", "-m", "h_tools.cli", f"tools/{name}", "describe"],
                          cwd=ROOT, capture_output=True, text=True)
    try:
        return json.loads(done.stdout)
    except ValueError:
        print(f"describe de {name} illisible : {done.stderr.strip()[-300:]}", file=sys.stderr)
        return {}


def post(url: str, token: str, body: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"content-type": "application/json", "X-SMO-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read() or b"{}")
    except (urllib.error.URLError, ValueError) as err:
        print(f"SMO : {err}", file=sys.stderr)
        return {}


def main(name: str, sha: str, tool_url: str | None = None) -> int:
    server, token = os.environ.get("SMO_SERVER_URL", "").rstrip("/"), os.environ.get("SMO_SERVER_TOKEN", "")
    if not server:
        print("SMO_SERVER_URL absent : le tool est déployé mais aucun agent n'est mis à jour", file=sys.stderr)
        return 0 if tool_url else 1   # un tool de bureau n'existe que par SMO
    if tool_url:
        body = {"tool": name, "sha": sha, "url": tool_url}
    else:
        body = {"tool": name, "sha": sha, "kind": "desktop", "files": bundle(name, sha), "describe": describe(name)}
    answer: dict = {}
    for _ in range(60):
        answer = post(f"{server}/hooks/tool-deployed", token, body)
        if answer.get("live_sha") == sha:
            break
        time.sleep(10)
    else:
        print(f"SMO ne voit pas {name} au commit {sha} après 10 min", file=sys.stderr)
        return 1
    failed = {agent: r for agent, r in (answer.get("prechecks") or {}).items() if not r.get("ok")}
    for agent, result in failed.items():
        print(f"precheck en échec pour {agent} : {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
    upgraded = answer.get("upgraded") or []
    print(f"{name} ({sha}) : {len(upgraded)} agent(s) mis à jour {upgraded}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
