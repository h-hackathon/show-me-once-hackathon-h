"""Commandes d'administration du banc de test.

    uv run comptarex-admin init          # crée .env (identifiants + jeton admin) s'il n'existe pas
    uv run comptarex-admin reset         # vide les saisies de l'agent (garde la boîte de réception)
    uv run comptarex-admin rebuild       # recrée la base à l'identique
    uv run comptarex-admin ui v2 [--confirm]
    uv run comptarex-admin verite        # écrit data/verite_terrain_situation.json
"""
from __future__ import annotations

import argparse
import json
import secrets

from . import compta, config, db


def main() -> None:
    parser = argparse.ArgumentParser(prog="comptarex-admin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("reset")
    sub.add_parser("rebuild")
    sub.add_parser("verite")
    ui = sub.add_parser("ui")
    ui.add_argument("version", choices=["v1", "v2"])
    ui.add_argument("--confirm", action="store_true", help="fenêtre de confirmation avant « Sauvegarder » (v2)")
    args = parser.parse_args()

    if args.cmd == "init":
        env = config.ROOT / ".env"
        if env.exists():
            print(f"{env} existe déjà : rien n'est modifié.")
            return
        env.write_text(
            f"SITE_LOGIN={config.LOGIN}\n"
            f"SITE_PASSWORD=Cptx-{secrets.token_hex(4)}\n"
            f"SITE_ADMIN_TOKEN={secrets.token_urlsafe(24)}\n"
            f"SECRET_KEY={secrets.token_hex(24)}\n"
            "PORT=8042\nHOST=127.0.0.1\n", encoding="utf-8")
        print(f"{env} créé.")
    elif args.cmd == "rebuild":
        db.rebuild()
        print(f"Base recréée : {config.DB_PATH}")
    else:
        conn = db.connect()
        if args.cmd == "reset":
            print(compta.reset_saisies(conn))
        elif args.cmd == "ui":
            print(compta.set_ui(conn, args.version, args.confirm))
        elif args.cmd == "verite":
            path = config.DATA / "verite_terrain_situation.json"
            path.write_text(json.dumps(compta.verite_situation(conn), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{path} écrit.")


if __name__ == "__main__":
    main()
