"""Lancer un tool en ligne de commande : par l'agent bureau H (tool de bureau) ou en local, par Devin.

    python -m h_tools.cli tools/<nom> describe
    python -m h_tools.cli tools/<nom> precheck
    python -m h_tools.cli tools/<nom> run '{"reference": "F-1", ...}'

Le contexte (SITE_URL, SITE_USERNAME…) vient de l'environnement. Le résultat est un JSON sur la sortie standard,
sans aucun secret ; code de sortie 1 si c'est une erreur ou un precheck en échec.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Context
from .loader import load_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m h_tools.cli")
    parser.add_argument("tool", help="le dossier du tool (tools/<nom>)")
    parser.add_argument("action", choices=["describe", "precheck", "run"])
    parser.add_argument("params", nargs="?", default="{}", help="paramètres en JSON (run)")
    args = parser.parse_args(argv)

    tool, cfg = load_tool(Path(args.tool)), Context.from_env()
    if args.action == "describe":
        out = tool.describe()
    elif args.action == "precheck":
        out = tool.precheck(cfg)
    else:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as err:
            params, out = None, {"ok": False, "status": "error", "error": f"paramètres : JSON invalide ({err})"}
        if isinstance(params, dict):
            out = tool.run(cfg, **params)
        elif params is not None:
            out = {"ok": False, "status": "error", "error": "paramètres : un objet JSON est attendu"}
    print(json.dumps(out, ensure_ascii=False))
    return 1 if out.get("status") == "error" or out.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
